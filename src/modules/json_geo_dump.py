#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from ..protocol.gsmtap import build_gsmtap_ip
from ..protocol.log_types import *
from struct import pack, unpack
from base64 import b64encode
from subprocess import run
from json import dumps
from time import time

from ._enable_log_mixin import EnableLogMixin, TYPES_FOR_RAW_PACKET_LOGGING

"""
    This module registers various diag LOG events, and generates a JSON file
    with both GPS location from the Android ADB, and raw LOG diag frames.
    
    It produces raw output deemed for off-line reuse by another module.
    
    Format:
    {"lat": 49.52531, "lng": 2.17493, "timestamp": 1521834122.2525692}
    {"log_type": 0xb0e2, "log_frame": "[base64 encoded]", "timestamp": 1521834122.2525692}
    
    This module is meant to be used with the "ADB" input.
"""

DELAY_CHECK_GEOLOCATION = 10 # Check GPS location every 10 seconds

class JsonGeoDumper(EnableLogMixin):
    
    def __init__(self, diag_input, json_geo_file):
        
        self.json_geo_file = json_geo_file
        
        self.diag_input = diag_input
        
        self.limit_registered_logs = TYPES_FOR_RAW_PACKET_LOGGING
        
        self.last_time_geolocation_was_checked = 0
        self.lat, self.lng = None, None
    
    def on_log(self, log_type, log_payload, log_header, timestamp = 0):
        
        if hasattr(self.diag_input, 'get_gps_location'):
            
            if self.last_time_geolocation_was_checked < time() - DELAY_CHECK_GEOLOCATION:
                
                lat, lng = self.diag_input.get_gps_location()
                
                if lat and lng and (lat, lng) != (self.lat, self.lng):
            
                    json_record = dumps({
                        'lat': lat,
                        'lng': lng,
                        'timestamp': time()
                    }, sort_keys = True)
                    
                    self.json_geo_file.write(json_record + '\n')
                
                self.last_time_geolocation_was_checked = time()
        
        if log_type in TYPES_FOR_RAW_PACKET_LOGGING:
    
            json_record = dumps({
                'log_type': log_type,
                'log_frame': b64encode(log_header + log_payload).decode('ascii'),
                'timestamp': time()
            }, sort_keys = True)
            
            self.json_geo_file.write(json_record + '\n')
    
    def __del__(self):
        
        self.json_geo_file.close()
