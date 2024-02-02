#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from ..modules._enable_log_mixin import EnableLogMixin
from ..protocol.gsmtap import build_gsmtap_ip
from ..protocol.log_types import *
from struct import pack, unpack

"""
    This module registers various diag LOG events, and generated a raw DLF
    dump openable with QCSuper or QXDM (for interoperability purposes).
"""

class DlfDumper(EnableLogMixin):
    
    def __init__(self, diag_input, dlf_file):
        
        super().__init__()
        
        self.dlf_file = dlf_file
        
        self.diag_input = diag_input
    
    def on_log(self, log_type, log_payload, log_header, timestamp = 0):
        
        assert unpack('<H', log_header[:2])[0] == len(log_header + log_payload)
        
        self.dlf_file.write(log_header + log_payload)
    
    def __del__(self):
        
        self.dlf_file.close()
