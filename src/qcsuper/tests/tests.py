#!/usr/bin/env python3
# -*- encoding: Utf-8 -*-
from unittest import main, TestLoader, TextTestRunner

"""
    Doc.: https://docs.python.org/3/library/unittest.html
"""

loader = TestLoader()
runner = TextTestRunner(verbosity=2)

try:
    import tests_usbmodem_argparser
except ImportError:
    from qcsuper.tests import tests_usbmodem_argparser

suite = loader.loadTestsFromModule(tests_usbmodem_argparser)
runner.run(suite)
