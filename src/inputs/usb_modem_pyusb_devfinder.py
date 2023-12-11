#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from usb.util import find_descriptor, endpoint_direction, ENDPOINT_OUT, ENDPOINT_IN
from usb.core import find, Device, Configuration, Interface, Endpoint, USBError
from typing import Optional, Union, Dict, List, Sequence, Set, Any

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

class PyusbDevInterface:

    device : Optional[Device] = None
    configuration : Optional[Configuration] = None
    interface : Optional[Interface] = None

    read_endpoint : Optional[Endpoint] = None
    write_endpoint : Optional[Endpoint] = None

    not_found_reason : Optional[PyusbDevNotFoundReason] = None

    @classmethod
    def find_by_vid_pid(cls, vid : int, pid : int, cfg_idx : int = None,
        intf_idx : int = None):

        self = cls()

        self.device : Optional[Device] = find(idVendor = vid, idProduct = pid)
        if not self.device:
            self.not_found_reason = PyusbDevNotFoundReason.vid_pid_not_found

        else:
            self._find_cfg_intf(cfg_idx, intf_idx)

        self._find_endpoints()
        return self

    def _find_cfg_intf(self, cfg_idx : int = None, intf_idx = None):

        if cfg_idx is None or intf_idx is None:

            for ruleset in DEV_FINDER_RULES_SET:
                self.interface : Optional[Interface] = next(
                    (find_descriptor(configuration, **ruleset)
                        for configuration in self.device.configurations()),
                    None
                )
                if self.interface:
                    self.configuation = self.device[self.interface.configuration]
                    break
            else:
                self.not_found_reason = PyusbDevNotFoundReason.intf_criteria_not_guessed
        else:
            try:
                self.configuration = self.device[cfg_idx]
                try:
                    self.interface = self.configuration[intf_idx]
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

    @classmethod
    def find_by_bus_device(cls, bus_id : int, device_id : int, cfg_idx : int = None,
        intf_idx : int = None):

        self = cls()

        self.device : Optional[Device] = find(bus = bus_id, address = device_id)
        if not self.device:
            self.not_found_reason = PyusbDevNotFoundReason.bus_device_not_found

        else:
            self._find_cfg_intf(cfg_idx, intf_idx)

        self._find_endpoints()
        return self

    @classmethod
    def find_auto(cls):

        self = cls()

        for ruleset in DEV_FINDER_RULES_SET:
            for device in find(find_all = True):
                self.interface : Optional[Interface] = next(
                    (find_descriptor(configuration, **ruleset)
                        for configuration in device.configurations()),
                    None
                )
                if self.interface:
                    self.device = device
                    self.configuation = self.device[self.interface.configuration]
                    break
            if self.interface:
                break
        else:
            self.not_found_reason = PyusbDevNotFoundReason.auto_criteria_did_not_match

        self._find_endpoints()
        return self


