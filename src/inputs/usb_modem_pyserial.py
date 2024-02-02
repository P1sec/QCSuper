#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from subprocess import run, DEVNULL, PIPE, STDOUT, CalledProcessError
from os import access, R_OK, W_OK, listdir, kill, makedirs, remove
from logging import error, warning, info, debug
from os.path import exists, realpath, basename
from subprocess import Popen
from signal import SIGTERM
from serial import Serial
from shutil import which
from sys import platform
from time import sleep
try:
    from os import setpgrp
except ImportError:
    setpgrp = None


try:
    from os import geteuid
except ImportError:
    pass

from ._hdlc_mixin import HdlcMixin
from ._base_input import BaseInput
from ..protocol.messages import *

"""
    This class implements reading Qualcomm DIAG data from an USB modem
    exposing a pseudo-serial port.
"""

class UsbModemPyserialConnector(HdlcMixin, BaseInput):
    
    """
        The constructor of the UsbModemPyserialConnector class checks
        that no process interferes with the serial port we're trying to
        connect to, then creates the serial port.
        
        It may create a temporary udev rule and restart ModemManager
        to prevent this interference.
    
        :param device (str): Name of the serial device (like "/dev/ttyHS2" on
            UNIX, or "COM1" on Windows)
    """
    
    def __init__(self, device):

        # WIP
        # <Implement Parser of USB-device syntax BEGIN>

        # <Implement Parser of USB-device syntax END>
        
        if platform not in ('win32', 'cygwin'):
            
            # Try to access the device
            
            if not exists(device):
                
                error('The device "%s" does not exist' % device)
                exit()
            
            elif not access(device, W_OK):
                
                error('Could not open "%s" for write, have you sufficient privileges?' % device)
                exit()
            
            self.device = device = realpath(device)
            
            self.detect_diag_interference()
        
        # Initialize the serial device
        
        self.serial = Serial(
            port = device,
            
            baudrate = 115200,
            
            rtscts = True,
            dsrdtr = True
        )
        
        self.device = device
        
        self.received_first_packet = False
        
        super().__init__()
    
    def detect_diag_interference(self, try_handle_modemmanager = True):
        
        # Try to detect another process which may interfere with the Diag port,
        # propose to terminate it when it is present
    
        if exists('/proc'):
            
            for pid in filter(str.isdigit, listdir('/proc')):
                
                cmdline_path = '/proc/%s/cmdline' % pid
                fds_dir = '/proc/%s/fd' % pid
                
                try:
                                
                    with open(cmdline_path) as cmdline_fd:
                    
                        proc_name = cmdline_fd.read().replace('\x00', ' ').strip()
                    
                    if 'modemmanager' not in proc_name.lower() and 'qc' not in proc_name.lower():
                        
                        continue
                    
                    if not access(fds_dir, R_OK):
                        
                        error(('The process "%s" may possibly be interfering with ' +
                               "QCSuper, however it can't be confirmed because " +
                               "you're not root. Please re-run with sudo to " +
                               'take appropriate action.') % proc_name)
                        
                        exit()
                        
                    for fd in listdir(fds_dir):
                    
                        if realpath(fds_dir + '/' + fd) == self.device:
                            
                            if 'modemmanager' in proc_name.lower() and try_handle_modemmanager:
                                
                                self.handle_modemmanager_interference()
                                
                                self.detect_diag_interference(try_handle_modemmanager = False)
                                
                                return
                            
                            if 'y' in input(('The process "%s" is already connected to "%s", do ' +
                                'you want to kill it? [y/n] ') % (proc_name, self.device)).lower():
                                
                                kill(int(pid), SIGTERM)
                                
                                sleep(0.2)
                            
                            else:
                                
                                error('Cannot connect on the Diag port at the same time')
                                exit()
                    
                except (FileNotFoundError, PermissionError):
                    
                    pass
    
    def handle_modemmanager_interference(self):
        
        # Try to handle ModemManager interference by adding an udev rule

        if which('udevadm') and which('systemctl') and which('ModemManager'):
            
            try:
                
                makedirs('/run/udev/rules.d', exist_ok = True)
                
                self.udev_rule_file_path = '/run/udev/rules.d/99-qcsuper-blacklist-%s.rules' % basename(self.device)
                
                with open(self.udev_rule_file_path, 'w') as udev_rule:
                    
                    udev_rule.write('KERNEL=="%s", ENV{ID_MM_PORT_IGNORE}="1"\n' % basename(self.device))
                
                run(['udevadm', 'control', '--reload-rules'], check = True)
                run(['udevadm', 'trigger', '--name-match=' + self.device], check = True)
                
                try:
                    
                    if run(['systemctl', '--quiet', 'is-active', 'ModemManager']).returncode == 0:
                        
                        run(['systemctl', 'restart', 'ModemManager'], check = True)
                
                except CalledProcessError:
                    
                    warning('Note: cannot restart the ModemManager daemon ' +
                          'through systemd')
                
                warning('Note: cooperation with ModemManager was enabled ' +
                      'through adding a temporary udev rule. This udev ' +
                      'rule will be automatically removed when quitting ' +
                      'QCSuper.')
            
            except (OSError, CalledProcessError) as error:
                
                if geteuid() != 0:
                    
                    error("ModemManager is running on this system, and " +
                          "QCSuper needs to add a temporary udev rule to " +
                          "enable cooperation with it on the Diag port.\n\n" +
                          "Please either: \n" +
                          "- Run this command as root so that QCSuper can " +
                          "add the temporary udev rule.\n" +
                          "- Alternatively, stop ModemManager.")
                
                    exit()
                
                else:
                    
                    warning("Cannot dynamically create an udev rule for preventing " +
                          "ModemManager to access the Diag port:", error)
    
    def __del__(self):
        
        try:
            
            if hasattr(self, 'udev_rule_file_path') and exists(self.udev_rule_file_path):
                
                remove(self.udev_rule_file_path)
                
                run(['udevadm', 'control', '--reload-rules'], check = True)
                run(['udevadm', 'trigger', '--name-match=' + self.device], check = True)
                
                if run(['systemctl', '--quiet', 'is-active', 'ModemManager']).returncode == 0:
                    
                    Popen(['systemctl', 'restart', 'ModemManager'], preexec_fn = setpgrp)
        
        except Exception:
            
            pass
    
    def send_request(self, packet_type, packet_payload):
        
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)
        
        self.serial.write(raw_payload)
    
    def read_loop(self):
        
        while True:
                
            # Read more bytes until a trailer character is found

            raw_payload = b''
            
            while not raw_payload.endswith(self.TRAILER_CHAR):
                
                try:
                    char_read = self.serial.read()
                    assert char_read
                
                except Exception:
                    error('\nThe serial port was closed or preempted by another process.')
                    
                    exit()
                
                raw_payload += char_read
            
            # Decapsulate and dispatch
            
            if raw_payload == self.TRAILER_CHAR:
                error('The modem seems to be unavailable.')
                
                exit()
            
            try:
            
                unframed_message = self.hdlc_decapsulate(
                    payload = raw_payload,
                    
                    raise_on_invalid_frame = not self.received_first_packet
                )
            
            except self.InvalidFrameError:
                
                # The first packet that we receive over the Diag input may
                # be partial
                
                continue
            
            finally:
                
                self.received_first_packet = True
            
            self.dispatch_received_diag_packet(unframed_message)


