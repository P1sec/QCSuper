#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from typing import Optional, Union, Dict, List, Sequence, Set, Any
from re import match, Match, IGNORECASE
from enum import IntEnum

class UsbModemArgType(IntEnum):
    pyserial_dev = 1
    pyusb_vid_pid = 2
    pyusb_vid_pid_cfg_intf = 3
    pyusb_bus_device = 4
    pyusb_bus_device_cfg_intf = 5
    pyusb_auto = 6

USB_ARG_REGEX_TO_MODE = {
    r'COM\d+|/dev.+': UsbModemArgType.pyserial_dev,
    r'([0-9a-f]{4}):([0-9a-f]{4})': UsbModemArgType.pyusb_vid_pid,
    r'([0-9a-f]{4}):([0-9a-f]{4}):(\d+):(\d+)': UsbModemArgType.pyusb_vid_pid_cfg_intf,
    r'([0-9]{3}):([0-9]{3})': UsbModemArgType.pyusb_bus_device,
    r'([0-9]{3}):([0-9]{3}):(\d+):(\d+)': UsbModemArgType.pyusb_bus_device_cfg_intf,
    'auto': UsbModemArgType.pyusb_auto
}

class UsbModemArgParser:

    arg_type : UsbModemArgType

    pyserial_device : Optional[str] = None

    pyusb_vid : Optional[int] = None
    pyusb_pid : Optional[int] = None
    pyusb_bus : Optional[int] = None
    pyusb_device : Optional[int] = None
    pyusb_cfg : Optional[int] = None
    pyusb_intf : Optional[int] = None
    pyusb_auto : bool = False

    def __init__(self, arg : str):

        """
        if arg.startswith('COM') or arg.startswith('/dev'):
            self.arg_type = UsbModemArgType.pyserial_dev
            self.pyserial_device = arg
        """

        regex_result : Optional[Match] = None
        syntax_type : Optional[UsbModemArgType] = None

        for possible_syntax, arg_type in USB_ARG_REGEX_TO_MODE.items():
            regex_result = match('^' + possible_syntax + '$', arg, flags = IGNORECASE)
            if regex_result:
                syntax_type = arg_type
                break
        
        if syntax_type:
            self.arg_type = syntax_type

            if syntax_type == UsbModemArgType.pyserial_dev:
                self.pyserial_device = regex_result.group(0)
            elif syntax_type == UsbModemArgType.pyusb_vid_pid:
                self.pyusb_vid = int(regex_result.group(1), 16)
                self.pyusb_pid = int(regex_result.group(2), 16)
            elif syntax_type == UsbModemArgType.pyusb_vid_pid_cfg_intf:
                self.pyusb_vid = int(regex_result.group(1), 16)
                self.pyusb_pid = int(regex_result.group(2), 16)
                self.pyusb_cfg = int(regex_result.group(3), 10)
                self.pyusb_intf = int(regex_result.group(4), 10)
            elif syntax_type == UsbModemArgType.pyusb_bus_device:
                self.pyusb_bus = int(regex_result.group(1), 10)
                self.pyusb_device = int(regex_result.group(2), 10)
            elif syntax_type == UsbModemArgType.pyusb_bus_device_cfg_intf:
                self.pyusb_bus = int(regex_result.group(1), 10)
                self.pyusb_device = int(regex_result.group(2), 10)
                self.pyusb_cfg = int(regex_result.group(3), 10)
                self.pyusb_intf = int(regex_result.group(4), 10)
            elif syntax_type == UsbModemArgType.pyusb_auto:
                self.pyusb_auto = True