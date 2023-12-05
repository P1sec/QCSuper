#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from unittest import main, TestLoader, TextTestRunner

"""
    Doc.: https://docs.python.org/3/library/unittest.html
"""

loader = TestLoader()
runner = TextTestRunner(verbosity = 2)

import tests_usbmodem_argparser
suite = loader.loadTestsFromModule(tests_usbmodem_argparser)
runner.run(suite)