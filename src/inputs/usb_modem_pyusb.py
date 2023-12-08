#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from src.inputs.usb_modem_argparser import UsbModemArgParser, \
    UsbModemArgType

from src.inputs.usb_modem_pyusb_devfinder import PyusbDevfinderMatch, \
    PyusbDevfinder, PyusbDevNotFound

from src.inputs._hdlc_mixin import HdlcMixin
from src.inputs._base_input import BaseInput

class UsbModemPyusbConnector(HdlcMixin, BaseInput):

    def __init__(self, usb_arg : UsbModemArgParser):

        if usb_arg.arg_type == UsbModemArgType.pyusb_vid_pid:
            WIP
        elif usb_arg.arg_type == UsbModemArgType.pyusb_vid_pid_cfg_intf:
            WIP
        elif usb_arg.arg_type == UsbModemArgType.pyusb_bus_device:
            XX
        elif usb_arg.arg_type == UsbModemArgType.pyusb_bus_device_cfg_intf:
            XX
        elif usb_arg.arg_type == UsbModemArgType.auto:
            XX#: Call "UsbModemPyusbDevfinder.XX" here
        else:
            assert False # unreachable

        XX# TO BE IMPLEMENTED

        self.received_first_packet = False

        super().__init__()

    def __del__(self):
        
        XX# TO BE IMPLEMENTED

    def send_request(self, packet_type, packet_payload):
        
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)
        
        XX# TO BE IMPLEMENTED.write(raw_payload)

    def read_loop(self):
        
        while True:
                
            XX# TO BE IMPLEMENTED

            self.dispatch_received_diag_packet(unframed_message)