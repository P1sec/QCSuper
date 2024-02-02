#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from pycrate_core.utils import pack_val, TYPE_UINT
from collections import defaultdict, namedtuple
from pycrate_asn1dir import RRC3G
from ..protocol.log_types import *
from traceback import format_exc
from struct import pack, unpack
from logging import warning
from time import time

RRC3G.ASN1Obj._SILENT = True

from ..modules._enable_log_mixin import EnableLogMixin, TYPES_FOR_RAW_PACKET_LOGGING

"""
    This module decodes SIBs from 3G RRC frames, independantly of the input
    format.
    
    It implements reassembly logic from "TS 25.331: Radio Resource Control
    (RRC); Protocol specification § 8.1.1 Broadcast of system information":
    ftp://ftp.3gpp.org/Specs/archive/25_series/25.331/25331-bi0.zip
"""

SIB_NAME_TO_CLASS = {
    'masterInformationBlock': RRC3G.InformationElements.MasterInformationBlock,
    'systemInformationBlockType1': RRC3G.InformationElements.SysInfoType1,
    'systemInformationBlockType2': RRC3G.InformationElements.SysInfoType2,
    'systemInformationBlockType3': RRC3G.InformationElements.SysInfoType3,
    'systemInformationBlockType4': RRC3G.InformationElements.SysInfoType4,
    'systemInformationBlockType5': RRC3G.InformationElements.SysInfoType5,
    'systemInformationBlockType6': RRC3G.InformationElements.SysInfoType6,
    'systemInformationBlockType7': RRC3G.InformationElements.SysInfoType7,
    'systemInformationBlockType11': RRC3G.InformationElements.SysInfoType11,
    'systemInformationBlockType12': RRC3G.InformationElements.SysInfoType12,
    'systemInformationBlockType13': RRC3G.InformationElements.SysInfoType13,
    'systemInformationBlockType13-1': RRC3G.InformationElements.SysInfoType13_1,
    'systemInformationBlockType13-2': RRC3G.InformationElements.SysInfoType13_2,
    'systemInformationBlockType13-3': RRC3G.InformationElements.SysInfoType13_3,
    'systemInformationBlockType13-4': RRC3G.InformationElements.SysInfoType13_4,
    'systemInformationBlockType14': RRC3G.InformationElements.SysInfoType14,
    'systemInformationBlockType15': RRC3G.InformationElements.SysInfoType15,
    'systemInformationBlockType15-1': RRC3G.InformationElements.SysInfoType15_1,
    'systemInformationBlockType15-2': RRC3G.InformationElements.SysInfoType15_2,
    'systemInformationBlockType15-3': RRC3G.InformationElements.SysInfoType15_3,
    'systemInformationBlockType16': RRC3G.InformationElements.SysInfoType16,
    'systemInformationBlockType17': RRC3G.InformationElements.SysInfoType17,
    'systemInformationBlockType15-4': RRC3G.InformationElements.SysInfoType15_4,
    'systemInformationBlockType18': RRC3G.InformationElements.SysInfoType18,
    'schedulingBlock1': RRC3G.InformationElements.SysInfoTypeSB1,
    'schedulingBlock2': RRC3G.InformationElements.SysInfoTypeSB2,
    'systemInformationBlockType15-5': RRC3G.InformationElements.SysInfoType15_5,
    'systemInformationBlockType5bis': RRC3G.InformationElements.SysInfoType5bis,
    
    # Extensions
    'systemInfoType11bis': RRC3G.InformationElements.SysInfoType11bis,
    'systemInfoType15bis': RRC3G.InformationElements.SysInfoType15bis,
    'systemInfoType15-1bis': RRC3G.InformationElements.SysInfoType15_1bis,
    'systemInfoType15-2bis': RRC3G.InformationElements.SysInfoType15_2bis,
    'systemInfoType15-3bis': RRC3G.InformationElements.SysInfoType15_3bis,
    'systemInfoType15-6': RRC3G.InformationElements.SysInfoType15_6,
    'systemInfoType15-7': RRC3G.InformationElements.SysInfoType15_7,
    'systemInfoType15-8': RRC3G.InformationElements.SysInfoType15_8,
    'systemInfoType19': RRC3G.InformationElements.SysInfoType19,
    'systemInfoType15-2ter': RRC3G.InformationElements.SysInfoType15_2ter,
    'systemInfoType20': RRC3G.InformationElements.SysInfoType20,
    'systemInfoType21': RRC3G.InformationElements.SysInfoType21,
    'systemInfoType22': RRC3G.InformationElements.SysInfoType22,
}

"""
    Named tuple holding scheduling information from a MIB or SB, regarding
    extension SIBs only because their type can't be known from their own frame
    otherwise (they're specified with the "extensionType" type)
"""

SIBSchedule = namedtuple('SIBSchedule', [
    'sib_period',
    'sib_position',
    'num_segments'
])

bearer_to_sib_schedule_to_sib_type = defaultdict(dict)

"""
    Class holding state about a specified SIB pending reassembly
"""

class SIB:
    
    def __init__(self):
        
        self.segment_bitstrings = [] # A list of bit sequences tuples consumable by Pycrate's pack_val module
        
        self.first_sfn = None # First SFN for the RRC frame containing this SIB
        
        self.last_sfn = None # Lastest received SFN
    
    """
        Add a SIB segment and maybe return the whole SIB if complete.
    """
        
    def add_segment_and_decode(self, radio_bearer, sfn_prime, sib_type, segment_index, is_final, segment_data_int, segment_data_bitlen, on_sib_decoding_error):
        
        if (self.last_sfn and not (1 <= sfn_prime - self.last_sfn <= 16)) or \
           (len(self.segment_bitstrings) != segment_index):
            
            on_sib_decoding_error('DEBUG: Uncomplete %s reassembly: SFN jump from %s to %s (%d), index expected to be %d but is %d' % (getattr(self, 'sib_type', sib_type), self.last_sfn, sfn_prime, sfn_prime - (self.last_sfn or 0), len(self.segment_bitstrings), segment_index))
            self.__init__() # Reset state
        
        if len(self.segment_bitstrings) != segment_index:
            return
        
        if not segment_index:
            self.first_sfn = sfn_prime
        self.last_sfn = sfn_prime
        
        self.segment_bitstrings.append([TYPE_UINT, segment_data_int, segment_data_bitlen])
        
        if is_final:
            
            # Convert segments bitstrings to bytes
            
            sib_byte_string = pack_val(*self.segment_bitstrings)[0]
                        
            """
                From spec: "If the value "Extension Type" is signalled,
                    the UE shall use the scheduling information in
                    the MIB and, if present, in the SB1 and SB2 to
                    identify the specific type of system information
                    block."
            """
            
            if sib_type == 'extensionType':
                
                for sib_schedule, sib_ext_type in bearer_to_sib_schedule_to_sib_type[radio_bearer].items():
                    
                    if self.first_sfn % sib_schedule.sib_period == sib_schedule.sib_position and \
                       len(self.segment_bitstrings) == sib_schedule.num_segments:
                        
                        self.sib_type = sib_type = sib_ext_type
            
            if sib_type == 'extensionType':
                
                on_sib_decoding_error('DEBUG: Received an extensionType SIB with SFN %d for which no scheduling information is known from MIB/SBs' % sfn_prime)
                return
            
            sib_object = SIB_NAME_TO_CLASS[sib_type]
            
            try:
                sib_object.from_uper(sib_byte_string)
            except Exception:
                on_sib_decoding_error('ERROR: SIB decoding failed for %s (%s): %s' % (sib_type, repr(sib_byte_string), format_exc()))
                return
            
            sib_dict = sib_object()
            
            # Reset state
            
            self.__init__()
            
            return sib_type, sib_dict, sib_byte_string

bearer_to_sib_type_to_sib = defaultdict(lambda: defaultdict(SIB))

"""
    Default callbacks when a SIB is decoded
"""

def print_decoded_sib(sib_type, sib_dict, sib_bytes, rrc_sfn, timestamp):
    
    print()
    print(sib_type, '=>', sib_dict)

def print_sib_decoding_error(decoding_error):
    
    print()
    print(decoding_error)

class DecodedSibsDumper(EnableLogMixin):
    
    def __init__(self, diag_input,
        on_decoded_sib = print_decoded_sib,
        on_sib_decoding_error = print_sib_decoding_error
    ):
        
        self.diag_input = diag_input
        self.on_decoded_sib = on_decoded_sib
        self.on_sib_decoding_error = on_sib_decoding_error
        
        self.limit_registered_logs = TYPES_FOR_RAW_PACKET_LOGGING
    
    def on_log(self, log_type, log_payload, log_header, timestamp = 0):
        
        if log_type == WCDMA_SIGNALLING_MESSAGE: # 0x412f
            
            (channel_type, radio_bearer, length), signalling_message = unpack('<BBH', log_payload[:4]), log_payload[4:]
            
            packet = signalling_message[:length]
            
            if channel_type == 254:
                return # Master Information Block, duplicated from the RRCLOG_SIG_DL_BCCH_BCH that was just logged
            
            if channel_type == 255:
                return
            
            if channel_type == RRCLOG_EXTENSION_SIB:
                return # Same for a limited number of extensions SIBs
            
            if channel_type == RRCLOG_SIB_CONTAINER:
                return # Generally unimplemented, ignore
            
            pycrate_class = {
                RRCLOG_SIG_UL_CCCH: RRC3G.Class_definitions.UL_CCCH_Message,
                RRCLOG_SIG_UL_DCCH: RRC3G.Class_definitions.UL_DCCH_Message,
                RRCLOG_SIG_DL_CCCH: RRC3G.Class_definitions.DL_CCCH_Message,
                RRCLOG_SIG_DL_DCCH: RRC3G.Class_definitions.DL_DCCH_Message,
                RRCLOG_SIG_DL_BCCH_BCH: RRC3G.Class_definitions.BCCH_BCH_Message,
                RRCLOG_SIG_DL_BCCH_FACH: RRC3G.Class_definitions.BCCH_FACH_Message,
                RRCLOG_SIG_DL_PCCH: RRC3G.Class_definitions.PCCH_Message
            }.get(channel_type)
            
            if pycrate_class is None:
                
                warning('Unknown log type received for WCDMA_SIGNALLING_MESSAGE: %d' % channel_type)
                return
            
            """
                Decode the PER-encoded RRC object
            """
            
            rrc_object = pycrate_class
            try:
                rrc_object.from_uper(packet)
            except Exception:
                self.on_sib_decoding_error('ERROR: RRC decoding failed (%s): %s' % (repr(packet), format_exc()))
                return
                        
            message = rrc_object()['message']
            
            if type(message) == dict:
                
                """
                    Deal with firstSegment, subsequentSegment, lastSegmentShort, etc.
                """
                
                rrc_payload_type, rrc_payload = message['payload']
                
                # rrc_payload should be made like {'kind_of_segment': dict_representing_the_segment}
                
                if 'And' not in rrc_payload_type:
                    rrc_payload = {rrc_payload_type: rrc_payload}
                
                for rrc_item_type, rrc_item in sorted(dict(rrc_payload).items()):
                    if '-List' in rrc_item_type:
                        
                        for list_item_nb, list_item in enumerate(rrc_item):
                            rrc_payload[rrc_item_type.replace('-List', '') + str(list_item_nb)] = list_item
                        
                        del rrc_payload[rrc_item_type]
                
                # Iterate over each segment
                
                for rrc_item_type, rrc_item in sorted(rrc_payload.items()):
                    
                    if not rrc_item:
                        continue
                    
                    is_final = False # Is this the last segment?
                    segment_index = 0
                    segment_data_int, segment_data_bitlen = rrc_item.get('sib-Data-fixed') or rrc_item['sib-Data-variable']
                    
                    if rrc_item_type == 'firstSegment':
                        segment_index = 0
                    
                    elif rrc_item_type == 'subsequentSegment':
                        segment_index = rrc_item['segmentIndex']
                    
                    elif rrc_item_type in ('lastSegment', 'lastSegmentShort'):
                        segment_index = rrc_item['segmentIndex']
                        is_final = True
                    
                    elif 'completeSIB' in rrc_item_type:
                        segment_index = 0
                        is_final = True
                    
                    else:
                        raise NotImplementedError
                    
                    sib_type = rrc_item['sib-Type']
                    sib_py_class = bearer_to_sib_type_to_sib[radio_bearer][sib_type]
                    decoded_sib = sib_py_class.add_segment_and_decode(radio_bearer, message['sfn-Prime'], sib_type, segment_index, is_final, segment_data_int, segment_data_bitlen, self.on_sib_decoding_error)
                
                    if decoded_sib:
                        
                        sib_type, sib_dict, sib_bytes = decoded_sib
                        
                        self.on_decoded_sib(sib_type, sib_dict, sib_bytes, message['sfn-Prime'], timestamp)
                        
                        """
                            Deal with extensions schedule information contained in MIBs and SBs
                        """
                        
                        message_exts = dict(sib_dict)
                        
                        for extension_level in [
                            'v690NonCriticalExtensions', 'v6b0NonCriticalExtensions', 'masterInformationBlock-v6b0ext',
                            'sysInfoTypeSB1-v6b0ext', 'sysInfoTypeSB2-v6b0ext', 'v860NonCriticalExtensions',
                            'masterInformationBlock-v860ext', 'sysInfoTypeSB1-v860ext', 'sysInfoTypeSB2-v860ext'
                        ]:
                            if extension_level in message_exts:
                                message_exts.update(message_exts[extension_level])
                                
                                extension_sibs = message_exts[extension_level].get('extSIBTypeInfoSchedulingInfo-List')
                                if extension_sibs:
                                    for extension_sib in extension_sibs:
                                        
                                        sib_type = extension_sib.get('extensionSIB-Type') or extension_sib['extensionSIB-Type2']
                                        sib_type = sib_type[0]
                                        
                                        sib_period, sib_position = extension_sib['schedulingInfo']['scheduling']['sib-Pos']
                                        sib_period = int(sib_period.replace('rep', '')) // 2
                                        
                                        num_segments = extension_sib['schedulingInfo']['scheduling']['segCount']
                                        
                                        sib_schedule = SIBSchedule(sib_period, sib_position, num_segments)
                                        
                                        bearer_to_sib_schedule_to_sib_type[radio_bearer][sib_schedule] = sib_type
            
            
