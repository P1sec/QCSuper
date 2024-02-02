#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from base64 import b64decode
from struct import unpack
from json import loads
from time import time
import gzip

from ._base_input import BaseInput

"""
    This class implements reading JSON files produced with the json_geo_dump.py
    module.
"""

class JsonGeoReader(BaseInput):
    
    def __init__(self, json_file):
        
        self.json_file = json_file
        
        super().__init__()
    
    def read_loop(self):
        
        while True:
            
            row = next(self.json_file, None)
            
            if not row:
                exit(0)
            
            row = loads(row)
            
            if 'log_frame' in row:
                
                log_type, log_frame, timestamp = row['log_type'], b64decode(row['log_frame']), row['timestamp']
                
                self.dispatch_diag_log(log_type, log_frame[12:], log_frame[:12], timestamp)
            
            elif 'lat' in row:
                
                self.latitude = row['lat']
                self.longitude = row['lng']

    
