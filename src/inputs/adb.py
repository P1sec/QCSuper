#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from subprocess import Popen, run, PIPE, DEVNULL, STDOUT, TimeoutExpired, list2cmdline
from socket import socket, AF_INET, SOCK_STREAM
from logging import debug, error, info, warning
from os.path import realpath, dirname, exists
from sys import stderr, platform
from traceback import print_exc
from functools import partial
from typing import Optional
from shutil import which
from time import sleep
from re import search

try:
    from os import setpgrp, getenv, setresgid, setresuid, setgroups, getgrouplist
    from pwd import getpwuid
    IS_UNIX = True

except Exception:
    IS_UNIX = False

from .usb_modem_pyusb_devfinder import PyusbDevInterface
from ._hdlc_mixin import HdlcMixin
from ._base_input import BaseInput

INPUTS_DIR = dirname(realpath(__file__))
ADB_BRIDGE_DIR = realpath(INPUTS_DIR + '/adb_bridge')
ADB_BIN_DIR = realpath(INPUTS_DIR + '/external/adb')

ANDROID_TMP_DIR = '/data/local/tmp'

def drop_privileges(detach_process = False):

    try:
        # Don't be hit by CTRL+C

        if detach_process:
            setpgrp()
        
        # Drop privileges if needed

        uid, gid = getenv('SUDO_UID'), getenv('SUDO_GID')
        
        if uid and gid:
            uid, gid = int(uid), int(gid)

            setgroups(getgrouplist(getpwuid(uid).pw_name, gid))
            setresgid(gid, gid, -1)
            setresuid(uid, uid, -1)
    
    except Exception:
        print_exc()

if not IS_UNIX:
    drop_privileges = None

# Print adb output to stdout when "-v" is passed to QCSuper

def run_safe(args, **kwargs):
    debug('[>] Running adb command: ' + list2cmdline(args))
    result = run(args, preexec_fn = drop_privileges, **kwargs)
    result_string = ((result.stdout or b'') + (result.stderr or b''))
    if result and result_string:
        debug('[<] Obtained result for running "%s": %s' % (list2cmdline(args), result_string))
    return result

"""
    This class implements reading Qualcomm DIAG data from a the /dev/diag
    character device, on a remote Android device connected through ADB.
    
    For this, it uploads the C program located in "./adb_bridge/" which
    creates a TCP socket acting as a proxy to /dev/diag.
"""

QCSUPER_TCP_PORT = 43555

class AdbConnector(HdlcMixin, BaseInput):
    
    def __init__(self, adb_exe = None, adb_host = 'localhost'):
        self._disposed = False

        if not adb_exe:
            if platform in ('cygwin', 'win32'):
                self.adb_exe = ADB_BIN_DIR + '/adb_windows.exe'
            elif platform == 'darwin':
                self.adb_exe = which('adb') or ADB_BIN_DIR + '/adb_macos'
            else:
                self.adb_exe = which('adb') or ADB_BIN_DIR + '/adb_linux'
        else:
            self.adb_exe = adb_exe

        self.adb_host = adb_host

        self.su_command = '%s'
        
        # Whether we can use "adb exec-out" instead
        # of "adb shell" (we should do it if the
        # remote phone supports it)
        self.can_use_exec_out = None # (boolean, None = unknown)
        
        self.ADB_TIMEOUT = 10

        # Use Diag-over-ADB if available for the device.

        self.usb_modem : Optional[PyusbDevInterface] = self._check_for_usb_diag_interface()
        if self.usb_modem:
            return

        if platform in ('cygwin', 'win32'):
            self.usb_modem = PyusbDevInterface.auto_find()
            if not self.usb_modem.not_found_reason:
                return
        
        # Send batch commands to check for the writability of /dev/diag through
        # adb, and for the availability of the "su" command
        
        bash_output = self.adb_shell(
            'test -w /dev/diag; echo DIAG_NOT_WRITEABLE=$?; ' +
            'test -e /dev/diag; echo DIAG_NOT_EXISTS=$?; ' +
            'test -r /dev; echo DEV_NOT_READABLE=$?; ' +
            'test -e /dev/ffs-diag; echo FFS_DIAG_NOT_HERE=$?; '
            'su -c id'
        )
        
        # Check for the presence of /dev/diag
        
        if not search('DIAG_NOT_WRITEABLE=[01]', bash_output):
            
            error('Could not run a bash command your phone, is adb functional?')
            
            error('ADB output: ' + bash_output)
            exit()
        
        # If writable, continue
        
        elif 'DIAG_NOT_WRITEABLE=0' in bash_output:
            
            pass

        # If not present and "/dev/ffs-diag" is not here, raise an error
        
        elif ('DEV_NOT_READABLE=0' in bash_output and 'DIAG_NOT_EXISTS=1' in bash_output
              and 'FFS_DIAG_NOT_HERE=1' in bash_output):

            error('Could not find /dev/diag, does your phone have a Qualcomm chip?')
            exit()

        # If maybe present but not writable, check for root
        
        elif 'uid=0' in bash_output:
            
            self.su_command = "su -c '%s'"
        
        elif 'uid=0' in self.adb_shell("su 0,0 sh -c 'id'"):
            
            self.su_command = "su 0,0 sh -c '%s'"
    
        else:
            
            # "adb shell su" didn't work, try "adb root"
            
            adb = run_safe([self.adb_exe, 'root'], stdout = PIPE, stderr = STDOUT, stdin = DEVNULL)
            
            if b'cannot run as root' in adb.stdout:
                
                error('Could not get root to adb, is your phone rooted?')
                exit()
        
            run_safe([self.adb_exe, 'wait-for-device'], stdin = DEVNULL, check = True)
        
        # Once root has been obtained, send batch commands to check
        # for the presence of /dev/diag through adb
        
        bash_output = self.adb_shell(
            'test -e /dev/diag; echo DIAG_NOT_EXISTS=$?; ' +
            'test -e /dev/ffs-diag; echo FFS_DIAG_NOT_HERE=$?'
        )

        # If not present, raise an error
        
        if 'DIAG_NOT_EXISTS=1' in bash_output and 'FFS_DIAG_NOT_HERE=1' in bash_output:
            
            error('Could not find /dev/diag, does your phone have a Qualcomm chip?')
            exit()
        
        if 'DIAG_NOT_EXISTS=1' in bash_output and 'FFS_DIAG_NOT_HERE=0' in bash_output:
            
            # Mode-switch the device

            for command in ['setprop sys.usb.config diag,adb']: # , 'setprop sys.usb.config diag,diag_mdm,adb'

                adb = run_safe([self.adb_exe, 'exec-out' if self.can_use_exec_out else 'shell', self.su_command % command],
                    
                    stdin = DEVNULL, stdout = PIPE, stderr = STDOUT, timeout = self.ADB_TIMEOUT
                )

                sleep(2)

                self.usb_modem : Optional[PyusbDevInterface] = self._check_for_usb_diag_interface()
                if self.usb_modem:
                    return

                if platform in ('cygwin', 'win32'):
                    self.usb_modem = PyusbDevInterface.auto_find()
                    if not self.usb_modem.not_found_reason:
                        return

                for i in range(3):

                    sleep(4)

                    self.usb_modem : Optional[PyusbDevInterface] = self._check_for_usb_diag_interface()
                    if self.usb_modem:
                        return

                    self.usb_modem = PyusbDevInterface.auto_find()
                    if not self.usb_modem.not_found_reason:
                        return
            
            error('Could not automatically mode-switch your device to enable ' +
                'Diag-over-USB. Please read the QCSuper README for more background over this.')
            if platform in ('cygwin', 'win32'):
                error('As you are on Windows, you may need to add a libusb-win32 filter ' +
                      'using the utility accessible through the Start Menu now.')
            exit()
            
        else:

            # Upload the adb_bridge
            
            adb = run_safe([self.adb_exe, 'push', ADB_BRIDGE_DIR + '/adb_bridge', ANDROID_TMP_DIR],
                
                stdin = DEVNULL, stdout = PIPE, stderr = STDOUT
            )
        
            if b'error' in adb.stdout or adb.returncode != 0:
                
                error('Could not transfer "adb_bridge" onto the device: ' + adb.stdout.decode('utf8'))
                exit()
            
            # Launch the adb_bridge
            
            self._relaunch_adb_bridge()

            self.packet_buffer = b''
            
            super().__init__()
    
    def _check_for_usb_diag_interface(self) -> Optional[PyusbDevInterface]:

        devices_list = run_safe([self.adb_exe, 'devices', '-l'],
            stdin = DEVNULL, stdout = PIPE, stderr = STDOUT).stdout.decode('utf8')

        device_num = search(r'usb:(\d+)-(\d+)', devices_list)
        if device_num and exists('/sys/bus/usb/devices'):
            bus_idx = int(device_num.group(1), 10)
            port_idx = int(device_num.group(2), 10)

            dev_intf = PyusbDevInterface.from_bus_port(bus_idx, port_idx)
            if not dev_intf.not_found_reason:
                return dev_intf
    
        return None

    def _relaunch_adb_bridge(self):
        
        if hasattr(self, 'adb_proc'):
            self.adb_proc.terminate()
        
        self.adb_shell(
            'killall -q adb_bridge; ' +
            'chmod 755 ' + ANDROID_TMP_DIR + '/adb_bridge'
        )
        
        run_safe([self.adb_exe, 'forward', 'tcp:' + str(QCSUPER_TCP_PORT), 'tcp:' + str(QCSUPER_TCP_PORT)], check = True,
                stdout = DEVNULL, stdin = DEVNULL)
        
        self.adb_proc = Popen([self.adb_exe, 'exec-out' if self.can_use_exec_out else 'shell', self.su_command % (ANDROID_TMP_DIR + '/adb_bridge')],
            
            stdin = DEVNULL, stdout = PIPE, stderr = STDOUT,
            preexec_fn = (lambda: partial(drop_privileges, True)) if drop_privileges else None,
            bufsize = 0, universal_newlines = True
        )
    
        for line in self.adb_proc.stdout:
            
            if 'Connection to Diag established' in line:
                
                break
            
            else:
                
                warning('Unexpected adb_bridge output: ' + line)

        self.socket = socket(AF_INET, SOCK_STREAM)

        try:
            
            self.socket.connect((self.adb_host, QCSUPER_TCP_PORT))
        
        except Exception:
            
            self.adb_proc.terminate()
            
            error('Could not communicate with the adb_bridge through TCP')
            exit()
        
        self.received_first_packet = False
    
    """
        This utility function tries to run a command to adb,
        raising an exception when it is unreachable.
        
        :param command: A shell command (string)
        
        :returns The combined stderr and stdout from "adb shell" (string)
    """
    
    def adb_shell(self, command):
        
        try:
            
            # Can we use "adb exec-out"?
            
            if self.can_use_exec_out is None:
                        
                adb = run_safe([self.adb_exe, 'exec-out', 'id'],
                    
                    stdin = DEVNULL, stdout = PIPE, stderr = STDOUT, timeout = self.ADB_TIMEOUT
                )
            
                self.can_use_exec_out = (adb.returncode == 0)
            
            # Can we execute commands?

            adb = run_safe([self.adb_exe, 'exec-out' if self.can_use_exec_out else 'shell', self.su_command % command],
                
                stdin = DEVNULL, stdout = PIPE, stderr = STDOUT, timeout = self.ADB_TIMEOUT
            )
        
        except TimeoutExpired:
            
            error('Communication with adb timed out, is your phone displaying ' +
                'a confirmation dialog?')
            exit()

        if b'error' in adb.stdout or adb.returncode != 0:
    
            if b'device not found' in adb.stdout or b'no devices' in adb.stdout:
            
                error('Could not connect to the adb, is your phone plugged with USB '
                    + 'debugging enabled?')
                exit()
            
            elif b'confirmation dialog on your device' in adb.stdout:
            
                error('Could not connect to the adb, is your phone displaying ' +
                    'a confirmation dialog?')
                exit()
            
            else:
                
                error('Could not connect to your device through adb')

                error('adb output: ' + adb.stdout.decode('utf8'))
                exit()
        
        return adb.stdout.decode('utf8').strip()
    
    def send_request(self, packet_type, packet_payload):
        
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)
        
        self.socket.send(raw_payload)
    
    def get_gps_location(self):
        
        lat = None
        lng = None
        
        gps_info = run_safe([self.adb_exe, 'exec-out' if self.can_use_exec_out else 'shell', 'dumpsys', 'location'], stdout = PIPE)
        gps_info = gps_info.stdout.decode('utf8')
        
        gps_info = search(r'(\d+\.\d+),(\d+\.\d+)', gps_info)
        if gps_info:
            lat, lng = map(float, gps_info.groups())
        
        return lat, lng
    
    def read_loop(self):
        
        while True:
            
            while self.TRAILER_CHAR not in self.packet_buffer:
                
                # Read message from the TCP socket
                
                socket_read = self.socket.recv(1024 * 1024 * 10)
                
                if not socket_read and platform in ('cygwin', 'win32'):
                    
                    # Windows user hit Ctrl+C from the terminal, which
                    # subsequently propagated to adb_bridge and killed it.
                    # Try to restart the subprocess in order to perform
                    # the deinitialization sequence well.
                    
                    self._relaunch_adb_bridge()
                    
                    # If restarting adb succeeded, this confirms the idea
                    # than the user did Ctrl+C, so we propagate the actual
                    # Ctrl+C to the main thread.
                    
                    if not self.program_is_terminating:
                        
                        with self.shutdown_event:
                        
                            self.shutdown_event.notify()
                    
                    socket_read = self.socket.recv(1024 * 1024 * 10)
                
                if not socket_read:
                    
                    error('\nThe connection to the adb bridge was closed, or ' +
                        'preempted by another QCSuper instance')
                    
                    return
                
                self.packet_buffer += socket_read
            
            while self.TRAILER_CHAR in self.packet_buffer:
                
                # Parse frame
                
                raw_payload, self.packet_buffer = self.packet_buffer.split(self.TRAILER_CHAR, 1)
                
                # Decapsulate and dispatch
                
                try:
                
                    unframed_message = self.hdlc_decapsulate(
                        payload = raw_payload + self.TRAILER_CHAR,
                        
                        raise_on_invalid_frame = not self.received_first_packet
                    )
                
                except self.InvalidFrameError:
                    
                    # The first packet that we receive over the Diag input may
                    # be partial
                    
                    continue
                
                finally:
                    
                    self.received_first_packet = True
                
                self.dispatch_received_diag_packet(unframed_message)

    def dispose(self, disposing=True):

        if not self._disposed:
            if hasattr(self, 'adb_proc'):
                self.adb_proc.terminate()

            self._disposed = True
