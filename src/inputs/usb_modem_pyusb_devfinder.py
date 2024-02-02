#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from usb.util import find_descriptor, endpoint_direction, ENDPOINT_OUT, ENDPOINT_IN
from usb.core import find, Device, Configuration, Interface, Endpoint, USBError
from typing import Optional, Union, Dict, List, Sequence, Set, Any
from os.path import exists, realpath, dirname, basename, islink
from os import listdir, scandir, readlink
from enum import IntEnum
from glob import glob

from .usb_modem_argparser import UsbModemArgParser, UsbModemArgType

"""
    This class contains a collection of methods that will
    return a "PyusbDevfinderMatch" object embedding a pair
    of "Device, Configuration, Interface" objects if an
    USB device interface matching the given criteria (please
    see the documentation of the "--usb-modem" option of
    QCSuper for more detail about this) is found, or
    a "PyusbDevfinderMatch" object embedding a
    "PyusbDevNotFoundReason" code otherwise.
"""

class PyusbDevNotFoundReason:
    vid_pid_not_found = 1
    bus_device_not_found = 2
    cfg_code_not_found = 3
    intf_code_not_found = 4
    intf_criteria_not_guessed = 5
    auto_criteria_did_not_match = 6

# Preferred rules for detecting an USB device interface
# potentially corresponding to a QC Diag interface:
DEV_FINDER_RULES_SET = [
    dict(bInterfaceClass = 255, bInterfaceSubClass = 255,
         bInterfaceProtocol = 48, bNumEndpoints = 2),
    dict(bInterfaceClass = 255, bInterfaceSubClass = 255,
         bInterfaceProtocol = 255, bNumEndpoints = 2)
]

class SysbusMountType(IntEnum):
    hsoserial_device = 1
    usbserial_device = 2

class SysbusMountEntry:

    mount_type : SysbusMountType

    vendor_id : int
    product_id : int

    bus_number : int
    dev_number : int

    configuration_id : int

    interface_number : int
    interface_class : int
    interface_subclass : int
    interface_protocol : int
    num_endpoints : int

    hsotype : Optional[str] = None

    sysbus_intf_path : str # XX
    chardev_path : str

class SysbusMountFinder:

    mount_entries : List[SysbusMountEntry] = None

    def __init__(self):

        self.mount_entries = []

        for tty_dir in glob('/sys/bus/usb/devices/*/tty*'):

            intf_path = realpath(dirname(tty_dir))

            if ':' in basename(intf_path) and exists(intf_path + '/bInterfaceClass'):

                dev_path = dirname(intf_path)
                configuration_id = int(basename(intf_path).split(':')[1].split('.')[0], 10)

                with open(dev_path + '/idVendor') as fd:
                    vendor_id = int(fd.read().strip(), 16)
                with open(dev_path + '/idProduct') as fd:
                    product_id = int(fd.read().strip(), 16)
                
                with open(dev_path + '/busnum') as fd:
                    bus_number = int(fd.read().strip(), 10)
                with open(dev_path + '/devnum') as fd:
                    dev_number = int(fd.read().strip(), 10)
                
                with open(intf_path + '/bInterfaceNumber') as fd:
                    interface_number = int(fd.read().strip(), 16)
                with open(intf_path + '/bInterfaceClass') as fd:
                    interface_class = int(fd.read().strip(), 16)
                with open(intf_path + '/bInterfaceSubClass') as fd:
                    interface_subclass = int(fd.read().strip(), 16)
                with open(intf_path + '/bInterfaceProtocol') as fd:
                    interface_protocol = int(fd.read().strip(), 16)
                with open(intf_path + '/bNumEndpoints') as fd:
                    num_endpoints = int(fd.read().strip(), 16)
                
                if basename(tty_dir) != 'tty':
                    tty_subdirs = [tty_dir]
                else:
                    tty_subdirs = [
                        dir.path for dir in scandir(tty_dir)
                    ]
                
                for tty_subdir in tty_subdirs:
                    char_dev_name = basename(tty_subdir)
                    char_dev_path = '/dev/' + char_dev_name

                    hsotype = None
                    if exists(tty_subdir + '/hsotype'):
                        with open(tty_subdir + '/hsotype') as fd:
                            hsotype = fd.read().strip()
                    
                    entry = SysbusMountEntry()
                    if char_dev_name.startswith('ttyHS'):
                        entry.mount_type = SysbusMountType.hsoserial_device
                    else:
                        entry.mount_type = SysbusMountType.usbserial_device
                    entry.vendor_id = vendor_id
                    entry.product_id = product_id
                    entry.bus_number = bus_number
                    entry.dev_number = dev_number
                    entry.configuration_id = configuration_id
                    entry.interface_number = interface_number
                    entry.interface_class = interface_class
                    entry.interface_subclass = interface_subclass
                    entry.interface_protocol = interface_protocol
                    entry.num_endpoints = num_endpoints
                    entry.hsotype = hsotype
                    entry.sysbus_intf_path = intf_path
                    entry.chardev_path = char_dev_path

                    self.mount_entries.append(entry)

    
    def find_entry(self, dev_intf : 'PyusbDevInterface') -> Optional[SysbusMountEntry]:

        for entry in self.mount_entries:
            if (dev_intf.device.bus == entry.bus_number and
                dev_intf.device.address == entry.dev_number and
                # dev_intf.device.idVendor == entry.vendor_id and
                # dev_intf.device.idProduct == entry.product_id and
                dev_intf.configuration.bConfigurationValue == entry.configuration_id and
                dev_intf.interface.bInterfaceNumber == entry.interface_number):

                return entry
                
        return None

class PyusbDevInterface:

    chardev_if_mounted : Optional[str] = None # <-- WIP FILL THIS WHEN ACCURATE

    device : Optional[Device] = None
    configuration : Optional[Configuration] = None
    interface : Optional[Interface] = None

    read_endpoint : Optional[Endpoint] = None
    write_endpoint : Optional[Endpoint] = None

    not_found_reason : Optional[PyusbDevNotFoundReason] = None

    @classmethod
    def from_arg(cls, usb_arg : UsbModemArgParser):
        self = cls()

        if usb_arg.arg_type == UsbModemArgType.pyusb_vid_pid:
            self._find_by_vid_pid(usb_arg.pyusb_vid, usb_arg.pyusb_pid)
        
        elif usb_arg.arg_type == UsbModemArgType.pyusb_vid_pid_cfg_intf:
            self._find_by_vid_pid(usb_arg.pyusb_vid, usb_arg.pyusb_pid,
                usb_arg.pyusb_cfg, usb_arg.pyusb_intf)
        
        elif usb_arg.arg_type == UsbModemArgType.pyusb_bus_device:
            self._find_by_bus_device(usb_arg.pyusb_bus, usb_arg.pyusb_device)
        
        elif usb_arg.arg_type == UsbModemArgType.pyusb_bus_device_cfg_intf:
            self._find_by_bus_device(usb_arg.pyusb_bus, usb_arg.pyusb_device,
                usb_arg.pyusb_cfg, usb_arg.pyusb_intf)
        
        elif usb_arg.arg_type == UsbModemArgType.pyusb_auto:
            self._find_auto()
        
        else:
            raise ValueError('Not a valid UsbModemArgType value') # unreachable

        if not self.not_found_reason:
            self._find_endpoints()
            self._find_char_dev()
        
        return self
    
    @classmethod
    def from_bus_port(cls, bus_idx : int, port_idx : int):
        self = cls()

        base_path = '/sys/bus/usb/devices/%d-%d/' % (bus_idx, port_idx)

        with open(base_path + 'busnum') as fd:
            bus_num = int(fd.read().strip(), 10)
        with open(base_path + 'devnum') as fd:
            dev_num = int(fd.read().strip(), 10)

        self._find_by_bus_device(bus_num, dev_num)

        if not self.not_found_reason:
            self._find_endpoints()
            self._find_char_dev()

        return self
    
    @classmethod
    def auto_find(cls):
        self = cls()

        self._find_auto()

        if not self.not_found_reason:
            self._find_endpoints()
            self._find_char_dev()

        return self

    def _find_by_vid_pid(self, vid : int, pid : int, cfg_id : int = None,
        intf_id : int = None):

        self.device : Optional[Device] = find(idVendor = vid, idProduct = pid)
        if not self.device:
            self.not_found_reason = PyusbDevNotFoundReason.vid_pid_not_found

        else:
            self._find_cfg_intf(cfg_id, intf_id)

    def _find_cfg_intf(self, cfg_id : int = None, intf_id = None):

        if cfg_id is None or intf_id is None:

            for ruleset in DEV_FINDER_RULES_SET:
                self.interface : Optional[Interface] = next(
                    (find_descriptor(configuration, **ruleset)
                        for configuration in self.device.configurations()),
                    None
                )
                if self.interface:
                    self.configuration = self.device[self.interface.configuration]
                    break
            else:
                self.not_found_reason = PyusbDevNotFoundReason.intf_criteria_not_guessed
        else:
            try:
                self.configuration = find_descriptor(self.device, bConfigurationValue = cfg_id) or self.device[cfg_id]
                try:
                    self.interface = find_descriptor(self.configuration, bInterfaceNumber = intf_id) or self.configuration[intf_id]
                except USBError:
                    self.not_found_reason = PyusbDevNotFoundReason.intf_code_not_found
            except USBError:
                self.not_found_reason = PyusbDevNotFoundReason.cfg_code_not_found

    def _find_endpoints(self):
        if self.interface:
            self.read_endpoint = find_descriptor(self.interface, custom_match =
                lambda endpoint: endpoint_direction(endpoint.bEndpointAddress) ==
                ENDPOINT_IN)
            self.write_endpoint = find_descriptor(self.interface, custom_match =
                lambda endpoint: endpoint_direction(endpoint.bEndpointAddress) ==
                ENDPOINT_OUT)

    def _find_char_dev(self):
        sysbus_entry = SysbusMountFinder().find_entry(self)
        if sysbus_entry:
            self.chardev_if_mounted = sysbus_entry.chardev_path

    def _find_by_bus_device(self, bus_id : int, device_id : int, cfg_id : int = None,
        intf_id : int = None):

        self.device : Optional[Device] = find(bus = bus_id, address = device_id)
        if not self.device:
            self.not_found_reason = PyusbDevNotFoundReason.bus_device_not_found

        else:
            self._find_cfg_intf(cfg_id, intf_id)

    def _find_auto(self):

        for ruleset in DEV_FINDER_RULES_SET:
            for device in find(find_all = True):
                self.interface : Optional[Interface] = next(
                    (find_descriptor(configuration, **ruleset)
                        for configuration in device.configurations()),
                    None
                )
                if self.interface:
                    self.device = device
                    self.configuration = self.device[self.interface.configuration]
                    break
            if self.interface:
                break
        else:
            self.not_found_reason = PyusbDevNotFoundReason.auto_criteria_did_not_match


