#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from usb.core import find, Device, Configuration, Interface, USBError
from typing import Optional, Union, Dict, List, Sequence, Set, Any
from usb.util import find_descriptor

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

class PyusbDevfinderMatch:

    device : Optional[Device] = None
    configuration : Optional[Configuration] = None
    interface : Optional[Interface] = None
    not_found_reason : Optional[PyusbDevNotFoundReason] = None

class PyusbDevNotFound(Exception):
    pass

# Preferred rules for detecting an USB device interface
# potentially corresponding to a QC Diag interface:
DEV_FINDER_RULES_SET = [
    dict(bInterfaceClass = 255, bInterfaceSubClass = 255,
         bInterfaceProtocol = 48, bNumEndpoints = 2),
    dict(bInterfaceClass = 255, bInterfaceSubClass = 255,
         bInterfaceProtocol = 48),
    dict(bInterfaceClass = 255, bInterfaceSubClass = 255,
         bInterfaceProtocol = 255, bNumEndpoints = 2),
    dict(bInterfaceClass = 255, bInterfaceSubClass = 255,
         bInterfaceProtocol = 255)
]

class PyusbDevfinder:

    @staticmethod
    def find_by_vid_pid(vid : int, pid : int, cfg_idx : int = None,
        intf_idx : int = None) -> Optional[PyusbDevfinderMatch]:

        retval = PyusbDevfinderMatch()

        retval.device : Optional[Device] = find(idVendor = vid, idProduct = pid)
        if not retval.device:
            retval.not_found_reason = PyusbDevNotFoundReason.vid_pid_not_found

        else:
            if cfg_idx is None or intf_idx is None:

                for ruleset in DEV_FINDER_RULES_SET:
                    retval.interface : Optional[Interface] = next(
                        (find_descriptor(configuration, **ruleset)
                            for configuration in retval.device.configurations()),
                        None
                    )
                    if retval.interface:
                        retval.configuation = retval.device[retval.interface.configuration]
                        break
                else:
                    retval.not_found_reason = PyusbDevNotFoundReason.intf_criteria_not_guessed
            else:
                try:
                    retval.configuration = retval.device[cfg_idx]
                    try:
                        retval.interface = retval.configuration[intf_idx]
                    except USBError:
                        retval.not_found_reason = PyusbDevNotFoundReason.intf_code_not_found
                except USBError:
                    retval.not_found_reason = PyusbDevNotFoundReason.cfg_code_not_found

        return retval

    @staticmethod
    def find_by_bus_device(bus_id : int, device_id : int, cfg_idx : int = None,
        intf_idx : int = None) -> Optional[PyusbDevfinderMatch]:

        XX# WIP

    @staticmethod
    def find_auto() -> Optional[PyusbDevfinderMatch]:

        XX# WIP


