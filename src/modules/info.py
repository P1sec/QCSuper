#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from struct import pack, unpack, unpack_from, calcsize
from collections import OrderedDict
from logging import warning, info
from time import sleep
from ctypes import *

from ..protocol.messages import *

"""
    This module exposes a class from which a module may inherit in order to
    enable logging packets.
"""

LOG_CONFIG_RETRIEVE_ID_RANGES_OP = 1
LOG_CONFIG_SET_MASK_OP = 3

LOG_CONFIG_SUCCESS_S = 0

class DiagVernoResponse(LittleEndianStructure):
    
    _pack_ = 1
    
    _fields_ = [
        ('comp_date', c_char * 11),
        ('comp_time', c_char * 8),
        
        ('rel_date', c_char * 11),
        ('rel_time', c_char * 8),
        
        ('ver_dir', c_char * 8),
        
        ('scm', c_ubyte),
        ('mob_cai_rev', c_ubyte),
        ('mob_model', c_ubyte),
        
        ('mob_firm_rev', c_uint16),
        
        ('slot_cycle_index', c_ubyte),
        ('hw_maj_ver', c_ubyte),
        ('hw_min_ver', c_ubyte)
    ]

def print_row(key, value):
    
    print('[+] %s %s' % ((key + ':').ljust(20), value))

class InfoRetriever:
    
    def __init__(self, diag_input):
        
        self.diag_input = diag_input
        
    def on_init(self):
        
        print()
        
        opcode, payload = self.diag_input.send_recv(DIAG_VERNO_F, b'', accept_error = False)
        
        if opcode == DIAG_VERNO_F: # No error occured
            
            info = DiagVernoResponse.from_buffer(bytearray(payload))
            
            print_row('Compilation date', '%s %s' % (info.comp_date.decode('ascii'), info.comp_time.decode('ascii')))
            print_row('Release date', '%s %s' % (info.rel_date.decode('ascii'), info.rel_time.decode('ascii')))
            print_row('Version directory', info.ver_dir.decode('ascii'))
            print()
            
            print_row('Common air interface information', '')
            print_row('  Station classmark', info.scm)
            print_row('  Common air interface revision', info.mob_cai_rev)
            print_row('  Mobile model', info.mob_model)
            print_row('  Mobile firmware revision', info.mob_firm_rev)
            print_row('  Slot cycle index', info.slot_cycle_index)
            print_row('  Hardware revision', '0x%x%02x (%d.%d)' % (
                info.hw_maj_ver, info.hw_min_ver,
                info.hw_maj_ver, info.hw_min_ver
            ))
            print()
        
        opcode, payload = self.diag_input.send_recv(DIAG_EXT_BUILD_ID_F, b'', accept_error = True)
        
        if opcode == DIAG_EXT_BUILD_ID_F:
            
            (msm_hw_version_format, msm_hw_version, mobile_model_id), ver_strings = unpack('<B2xII', payload[:11]), payload[11:]
            
            build_id, model_string, _ = ver_strings.split(b'\x00', 2)
            
            if msm_hw_version_format == 2:
                version, partnum = msm_hw_version >> 28, (msm_hw_version >> 12) & 0xffff
            else:
                version, partnum = msm_hw_version & 0b1111, (msm_hw_version >> 12) >> 4
            
            # Duplicate with information from DIAG_VERNO_F:
            
            # print_row('Hardware revision', '0x%x (%d.%d)' % (partnum, partnum >> 8, partnum & 0xff))
            
            # Sometimes duplicate with information from DIAG_VERNO_F:
            
            if mobile_model_id > 255:
                print_row('Mobile model ID', '0x%x' % mobile_model_id)
            
            print_row('Chip version', version)
            print_row('Firmware build ID', build_id.decode('ascii'))
            if model_string:
                print_row('Model string', model_string.decode('ascii'))
            
            print()
        
        opcode, payload = self.diag_input.send_recv(DIAG_DIAG_VER_F, b'', accept_error = True)
        
        if opcode == DIAG_DIAG_VER_F:
            
            print_row('Diag version', unpack('<H', payload)[0])
            
            print()
        
        opcode, payload = self.diag_input.send_recv(DIAG_ESN_F, b'', accept_error = True)
        
        if opcode == DIAG_ESN_F:
            
            esn = unpack('<I', payload)[0]
            
            if esn != 0xdeadd00d:
                
                print_row('Serial number', esn)
                
                print()
        
