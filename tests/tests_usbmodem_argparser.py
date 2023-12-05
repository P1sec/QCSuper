#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from os.path import dirname, realpath
from unittest import TestCase

TESTS_DIR = dirname(realpath(__file__))
ROOT_DIR = dirname(TESTS_DIR)

import sys
sys.path.insert(0, ROOT_DIR)

from src.inputs.usb_modem_argparser import UsbModemArgParser, \
    UsbModemArgType

"""
    This file is an include file.

    It should be run from the "tests.py" entry point
    located into the current directory

    It contains the tests for the
    "src/inputs/usb_modem_argparser.py" file.
"""

class UsbmodemArgparserTests(TestCase):

    def test_arg_parsing_invalid(self):
        test_case = UsbModemArgParser('xxxxx:x')
        self.assertEqual(test_case.pyserial_device, None)

        test_case = UsbModemArgParser('00:00:0:0')
        self.assertEqual(test_case.pyserial_device, None)

    def test_arg_parsing_valid(self):

        test_case = UsbModemArgParser('COM9')
        self.assertEqual(test_case.arg_type, UsbModemArgType.pyserial_dev)
        self.assertEqual(test_case.pyserial_device, 'COM9')

        test_case = UsbModemArgParser('/dev/ttyHS2')
        self.assertEqual(test_case.arg_type, UsbModemArgType.pyserial_dev)
        self.assertEqual(test_case.pyserial_device, '/dev/ttyHS2')

        test_case = UsbModemArgParser('/dev/tty.usbserial')
        self.assertEqual(test_case.arg_type, UsbModemArgType.pyserial_dev)
        self.assertEqual(test_case.pyserial_device, '/dev/tty.usbserial')

        test_case = UsbModemArgParser('1d6b:0003')
        self.assertEqual(test_case.arg_type, UsbModemArgType.pyusb_vid_pid)
        self.assertEqual(test_case.pyusb_vid, 0x1d6b)
        self.assertEqual(test_case.pyusb_pid, 0x0003)

        test_case = UsbModemArgParser('1d6b:0003:0:9')
        self.assertEqual(test_case.arg_type, UsbModemArgType.pyusb_vid_pid_cfg_intf)
        self.assertEqual(test_case.pyusb_vid, 0x1d6b)
        self.assertEqual(test_case.pyusb_pid, 0x0003)
        self.assertEqual(test_case.pyusb_cfg, 0)
        self.assertEqual(test_case.pyusb_intf, 9)

        test_case = UsbModemArgParser('001:009')
        self.assertEqual(test_case.arg_type, UsbModemArgType.pyusb_bus_device)
        self.assertEqual(test_case.pyusb_bus, 1)
        self.assertEqual(test_case.pyusb_device, 9)

        test_case = UsbModemArgParser('001:009:0:9')
        self.assertEqual(test_case.arg_type, UsbModemArgType.pyusb_bus_device_cfg_intf)
        self.assertEqual(test_case.pyusb_bus, 1)
        self.assertEqual(test_case.pyusb_device, 9)
        self.assertEqual(test_case.pyusb_cfg, 0)
        self.assertEqual(test_case.pyusb_intf, 9)

        test_case = UsbModemArgParser('auto')
        self.assertTrue(test_case.pyusb_auto)
