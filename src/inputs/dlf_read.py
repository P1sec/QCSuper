#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from datetime import datetime
from struct import unpack
import gzip

from ._base_input import BaseInput

"""
    This class implements reading Qualcomm DIAG data from a DLF file.
    
    DLF files are simply files containing inner payloads for DIAG_LOG_F
    records (excluding the number of pending messages and first length).
    
    The default export format for recent versions of QXDM is ISF, but an
    ISF file can be converted to DLF using an internal QXDM tool. This
    format is implemented here for interoperability purposes.
"""

class DlfReader(BaseInput):
    
    def __init__(self, dlf_file):
        
        self.dlf_file = dlf_file
        
        # We keep track of the timestamp of the latest read packet, in the case
        # where the next packet we'll read happens to use an uncommon format
        
        self.timestamp = 0
        
        super().__init__()
    
    def read_loop(self):
        
        while True:
            
            TIMESTAMP_OFFSET = datetime(1980, 1, 6).timestamp()
            TIMESTAMP_MIN = datetime(2010, 1, 1).timestamp()
            TIMESTAMP_MAX = datetime(2050, 1, 1).timestamp()
            
            """
                Parse the inner header and payload.
            """
            
            log_header = self.dlf_file.read(12)
            if not log_header:
                exit(0)
            
            log_length, log_type, log_time = unpack('<HHQ', log_header)
            
            log_data = self.dlf_file.read(log_length - 12)
            
            """
                You can encounter multiple formats for the timestamps used
                in Diag LOG frames, but the most common uses a QWORD where
                the upper bits are units of 20 ms, and the 20 lower bits
                are the mantissa.
            """
            
            log_time = (log_time >> 20) / 50 + TIMESTAMP_OFFSET + ((log_time & 0xfffff) / 0x100000)
            
            if TIMESTAMP_MIN <= log_time <= TIMESTAMP_MAX:
                self.timestamp = log_time        
            """
                Dispatch the log frame to modules.
            """
            
            self.dispatch_diag_log(log_type, log_data, log_header, self.timestamp)


