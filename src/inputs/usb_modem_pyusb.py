#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from src.inputs.usb_modem_argparser import UsbModemArgParser, \
    UsbModemArgType

from src.inputs.usb_modem_pyusb_devfinder import PyusbDevInterface, \
    PyusbDevNotFoundReason

from src.inputs._hdlc_mixin import HdlcMixin
from src.inputs._base_input import BaseInput

from usb.util import dispose_resources
from usb.core import USBError
from typing import Optional

class UsbModemPyusbConnector(HdlcMixin, BaseInput):

    dev_intf : Optional[PyusbDevInterface] = None

    def __init__(self, usb_arg : UsbModemArgParser):

        if usb_arg.arg_type == UsbModemArgType.pyusb_vid_pid:
            self.dev_intf = PyusbDevInterface.find_by_vid_pid(usb_arg.pyusb_vid, usb_arg.pyusb_pid)
        elif usb_arg.arg_type == UsbModemArgType.pyusb_vid_pid_cfg_intf:
            self.dev_intf = PyusbDevInterface.find_by_vid_pid(usb_arg.pyusb_vid, usb_arg.pyusb_pid,
                usb_arg.pyusb_cfg, usb_arg.pyusb_intf)
        elif usb_arg.arg_type == UsbModemArgType.pyusb_bus_device:
            self.dev_intf = PyusbDevInterface.find_by_bus_device(usb_arg.pyusb_bus, usb_arg.pyusb_device)
        elif usb_arg.arg_type == UsbModemArgType.pyusb_bus_device_cfg_intf:
            self.dev_intf = PyusbDevInterface.find_by_bus_device(usb_arg.pyusb_bus, usb_arg.pyusb_device,
                usb_arg.pyusb_cfg, usb_arg.pyusb_intf)
        elif usb_arg.arg_type == UsbModemArgType.pyusb_auto:
            self.dev_intf = PyusbDevInterface.find_auto()
        else:
            assert False # unreachable

        if self.dev_intf.not_found_reason:
            exit('[!] No Qualcomm Diag interface was found with the specified ' +
                 'criteria. Please be more specific.')
            # TODO: Print a more user-friendly message here?

        # TODO : Test with n devices...

        # print(self.dev_intf.interface) # DEBUG
        # print(self.dev_intf.interface.__dict__)
        try:
            status = self.dev_intf.device.is_kernel_driver_active(self.dev_intf.interface.index)
        except Exception:
            pass
        else:
            if status:
                exit('[!] The USB modem device seems to be taken by a kernel driver, such as "usbserial" ' +
                     'or "hso". Please pass directly a device name using an option like "--usb-modem /dev/ttyUSB2" ' +
                     'or "/dev/ttyHS0" (on Linux) or "COM0" (on Windows) if it applies, or unmount the corresponding ' +
                     'driver.')
        # self.dev_intf.device.set_configuration(self.dev_intf.configuration) # DEBUG Commented
        # TODO : Handle non-root users?

        self.received_first_packet = False

        super().__init__()

    def __del__(self):
        
        if self.dev_intf and self.dev_intf.device:
            dispose_resources(self.dev_intf.device)
        # XX# TO BE TESTED

    def send_request(self, packet_type, packet_payload):
        
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)
        
        try:
            self.dev_intf.write_endpoint.write(raw_payload)
        except USBError:
            print("[!] Can't write to the USB device. Maybe that you need " +
                "root/administrator privileges, or that the device was unplugged?")
        # XX TO BE TESTED

    def read_loop(self):
        
        while True:
                
            # Read more bytes until a trailer character is found

            raw_payload = b''
            
            while not raw_payload.endswith(self.TRAILER_CHAR):
                
                try:
                    data_read = bytes(self.dev_intf.read_endpoint.read(1024 * 1024 * 10))
                    assert data_read
                
                except Exception:
                    print("[!] Can't read to the USB device. Maybe that you need " +
                       "root/administrator privileges, or that the device was " +
                       "unplugged?")

                    exit()
                
                raw_payload += data_read
            
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
