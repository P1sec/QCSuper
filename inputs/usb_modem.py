#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from subprocess import run, DEVNULL, PIPE, STDOUT
from os import access, W_OK, listdir, kill
from os.path import exists, realpath
from signal import SIGTERM
from serial import Serial
from shutil import which
from sys import platform
from time import sleep

from inputs._hdlc_mixin import HdlcMixin
from inputs._base_input import BaseInput
from protocol.messages import *

"""
    This class implements reading Qualcomm DIAG data from an USB modem
    exposing a pseudo-serial port.
"""

class UsbModemConnector(HdlcMixin, BaseInput):
    
    def __init__(self, device):
        
        if platform not in ('win32', 'cygwin'):
            
            # Try to access the device
            
            if not exists(device):
                
                exit('The device "%s" does not exist' % device)
            
            elif not access(device, W_OK):
                
                exit('Could not open "%s" for write, are you root?' % device)
            
            # Try to detect ModemManager which may interfere with the Diag port,
            # propose to terminate it when it is present
            
            device = realpath(device)
        
            if exists('/proc'):
                
                for pid in filter(str.isdigit, listdir('/proc')):
                    
                    cmdline_path = '/proc/%s/cmdline' % pid
                    fds_dir = '/proc/%s/fd' % pid
                    
                    try:
                                    
                        with open(cmdline_path) as cmdline_fd:
                            
                            proc_name = cmdline_fd.read().replace('\x00', ' ').strip()
                        
                        if 'modem' not in proc_name.lower() and 'qc' not in proc_name.lower():
                            
                            continue
                            
                        for fd in listdir(fds_dir):
                        
                            if realpath(fds_dir + '/' + fd) == device:
                                
                                if 'y' in input(('The process "%s" is already connected to "%s", do ' +
                                    'you want to kill it? [y/n] ') % (proc_name, device)).lower():
                                    
                                    kill(int(pid), SIGTERM)
                                    
                                    sleep(0.2)
                                
                                else:
                                    
                                    exit('Cannot connect on the Diag port at the same time')
                        
                    except (FileNotFoundError, PermissionError):
                        
                        pass
        
        # Initialize the serial device
        
        self.serial = Serial(
            port = device,
            
            baudrate = 115200,
            
            rtscts = True,
            dsrdtr = True
        )
        
        self.received_first_packet = False
        
        super().__init__()
    
    def send_request(self, packet_type, packet_payload):
        
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)
        
        self.serial.write(raw_payload)
    
    def read_loop(self):
        
        while True:
                
            # Read more bytes until a trailed character is found

            raw_payload = b''
            
            while not raw_payload.endswith(self.TRAILER_CHAR):
                
                try:
                    char_read = self.serial.read()
                    assert char_read
                
                except Exception:
                    print('\nThe serial port was closed or preempted by another process.')
                    
                    exit()
                
                raw_payload += char_read
            
            # Decapsulate and dispatch
            
            if raw_payload == self.TRAILER_CHAR:
                print('The modem seems to be unavailable.')
                
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


