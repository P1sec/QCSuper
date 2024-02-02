#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from .usb_modem_pyusb_devfinder import PyusbDevInterface
from logging import error, warning, info, debug
from ._hdlc_mixin import HdlcMixin
from ._base_input import BaseInput

from usb.util import dispose_resources
from traceback import format_exc
from usb.core import USBError
from typing import Optional

class UsbModemPyusbConnector(HdlcMixin, BaseInput):

    dev_intf : Optional[PyusbDevInterface] = None

    def __init__(self, dev_intf : PyusbDevInterface):

        self.dev_intf = dev_intf

        try:
            status = self.dev_intf.device.is_kernel_driver_active(self.dev_intf.interface.index)
        except Exception:
            pass
        else:
            if status:
                error('The USB modem device seems to be taken by a kernel driver, such as "usbserial" ' +
                     'or "hso". Please pass directly a device name using an option like "--usb-modem /dev/ttyUSB2" ' +
                     'or "/dev/ttyHS0" (on Linux) or "COM0" (on Windows) if it applies, or unmount the corresponding ' +
                     'driver.')

                exit()

        try:
            # Needed on Windows, won't always work on Linux:
            self.dev_intf.device.set_configuration(self.dev_intf.configuration.bConfigurationValue)
        except USBError:
            pass

        self.received_first_packet = False

        super().__init__()

    def __del__(self):
        
        if self.dev_intf and self.dev_intf.device:
            dispose_resources(self.dev_intf.device)

    def send_request(self, packet_type, packet_payload):
        
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)
        
        try:
            self.dev_intf.write_endpoint.write(raw_payload)
        except USBError:
            error("[!] Can't write to the USB device. Maybe that you need " +
                "root/administrator privileges, or that the device was unplugged? " + format_exc())

    def read_loop(self):
        
        while True:
                
            # Read more bytes until a trailer character is found

            raw_payload = b''
            
            while not raw_payload.endswith(self.TRAILER_CHAR):
                
                try:
                    data_read = bytes(self.dev_intf.read_endpoint.read(0x1000, timeout = 0x7fffffff))
                    assert data_read
                
                except Exception:

                    info('Connection from the USB link closed')
                    debug('Reason for closing the link: ' + format_exc())
                    exit()
                
                raw_payload += data_read
            
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
