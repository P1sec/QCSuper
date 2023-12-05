#!/usr/bin/python3
from struct import pack, unpack

# GSMTAP definition:
# - https://github.com/wireshark/wireshark/blob/wireshark-2.5.0/epan/dissectors/packet-gsmtap.h
# - https://github.com/wireshark/wireshark/blob/wireshark-2.5.0/epan/dissectors/packet-gsmtap.c#L82
# - http://osmocom.org/projects/baseband/wiki/GSMTAP

GSMTAP_PORT = 4729
NR_RRC_UDP_PORT = 47928

def build_gsmtap_ip(gsmtap_protocol, gsmtap_channel_type, payload, is_uplink):
    
    packet = pack('>BBBxHxx4xBxxx',
        2, # GSMTAP version
        4, # Header words
        gsmtap_protocol,
        int(is_uplink) << 14,
        gsmtap_channel_type
    ) + payload
    
    # UDP:
    
    packet = pack('>HHHH',
        GSMTAP_PORT, # From GSMTAP UDP port
        GSMTAP_PORT, # To GSMTAP UDP port
        len(packet) + 8, # Total length
        0 # Ignore checksum
    ) + packet
    
    # IP:
    
    return pack('>BBHHHBBH8B',
        (4 << 4) | 5, # IPv4 version and header words
        0, # DSCP
        len(packet) + 20, # Total length
        0, # Identification
        0, # Fragment offset
        64, # Time to live
        17, # Protocol: UDP
        0, # Ignore checksum
        0,0,0,0, # From 0.0.0.0
        0,0,0,0, # To 0.0.0.0
    ) + packet

def build_nr_rrc_log_ip(log_payload : bytes):

    # UDP:

    packet = pack('>HHHH',
        NR_RRC_UDP_PORT, # From custom QCSuper plug-in UDP port
        NR_RRC_UDP_PORT, # To custom QCSuper plug-in UDP port
        len(log_payload) + 8, # Total length
        0 # Ignore checksum
    ) + log_payload
    
    # IP:
    
    return pack('>BBHHHBBH8B',
        (4 << 4) | 5, # IPv4 version and header words
        0, # DSCP
        len(packet) + 20, # Total length
        0, # Identification
        0, # Fragment offset
        64, # Time to live
        17, # Protocol: UDP
        0, # Ignore checksum
        0,0,0,0, # From 0.0.0.0
        0,0,0,0, # To 0.0.0.0
    ) + packet



GSMTAP_TYPE_UM = 0x01
GSMTAP_TYPE_ABIS = 0x02
GSMTAP_TYPE_UMTS_RRC = 0x0c
GSMTAP_TYPE_LTE_RRC = 0x0d
GSMTAP_TYPE_LTE_NAS = 0x12

GSMTAP_CHANNEL_UNKNOWN = 0x00
GSMTAP_CHANNEL_BCCH = 0x01
GSMTAP_CHANNEL_CCCH = 0x02
GSMTAP_CHANNEL_RACH = 0x03
GSMTAP_CHANNEL_AGCH = 0x04
GSMTAP_CHANNEL_PCH = 0x05
GSMTAP_CHANNEL_SDCCH = 0x06
GSMTAP_CHANNEL_SDCCH4 = 0x07
GSMTAP_CHANNEL_SDCCH8 = 0x08
GSMTAP_CHANNEL_TCH_F = 0x09
GSMTAP_CHANNEL_TCH_H = 0x0a
GSMTAP_CHANNEL_PACCH = 0x0b
GSMTAP_CHANNEL_CBCH52 = 0x0c
GSMTAP_CHANNEL_PDTCH = 0x0d
GSMTAP_CHANNEL_PTCCH = 0x0e
GSMTAP_CHANNEL_CBCH51 = 0x0f

GSMTAP_CHANNEL_ACCH = 0x80 # To be combined, ACCH + SDCCH = SACCH

GSMTAP_RRC_SUB_DL_DCCH_Message = 0
GSMTAP_RRC_SUB_UL_DCCH_Message = 1
GSMTAP_RRC_SUB_DL_CCCH_Message = 2
GSMTAP_RRC_SUB_UL_CCCH_Message = 3
GSMTAP_RRC_SUB_PCCH_Message = 4
GSMTAP_RRC_SUB_DL_SHCCH_Message = 5
GSMTAP_RRC_SUB_UL_SHCCH_Message = 6
GSMTAP_RRC_SUB_BCCH_FACH_Message = 7
GSMTAP_RRC_SUB_BCCH_BCH_Message = 8
GSMTAP_RRC_SUB_MCCH_Message = 9
GSMTAP_RRC_SUB_MSCH_Message = 10
GSMTAP_RRC_SUB_HandoverToUTRANCommand = 11
GSMTAP_RRC_SUB_InterRATHandoverInfo = 12
GSMTAP_RRC_SUB_SystemInformation_BCH = 13
GSMTAP_RRC_SUB_System_Information_Container = 14
GSMTAP_RRC_SUB_UE_RadioAccessCapabilityInfo = 15
GSMTAP_RRC_SUB_MasterInformationBlock = 16
GSMTAP_RRC_SUB_SysInfoType1 = 17
GSMTAP_RRC_SUB_SysInfoType2 = 18
GSMTAP_RRC_SUB_SysInfoType3 = 19
GSMTAP_RRC_SUB_SysInfoType4 = 20
GSMTAP_RRC_SUB_SysInfoType5 = 21
GSMTAP_RRC_SUB_SysInfoType5bis = 22
GSMTAP_RRC_SUB_SysInfoType6 = 23
GSMTAP_RRC_SUB_SysInfoType7 = 24
GSMTAP_RRC_SUB_SysInfoType8 = 25
GSMTAP_RRC_SUB_SysInfoType9 = 26
GSMTAP_RRC_SUB_SysInfoType10 = 27
GSMTAP_RRC_SUB_SysInfoType11 = 28
GSMTAP_RRC_SUB_SysInfoType11bis = 29
GSMTAP_RRC_SUB_SysInfoType12 = 30
GSMTAP_RRC_SUB_SysInfoType13 = 31
GSMTAP_RRC_SUB_SysInfoType13_1 = 32
GSMTAP_RRC_SUB_SysInfoType13_2 = 33
GSMTAP_RRC_SUB_SysInfoType13_3 = 34
GSMTAP_RRC_SUB_SysInfoType13_4 = 35
GSMTAP_RRC_SUB_SysInfoType14 = 36
GSMTAP_RRC_SUB_SysInfoType15 = 37
GSMTAP_RRC_SUB_SysInfoType15bis = 38
GSMTAP_RRC_SUB_SysInfoType15_1 = 39
GSMTAP_RRC_SUB_SysInfoType15_1bis = 40
GSMTAP_RRC_SUB_SysInfoType15_2 = 41
GSMTAP_RRC_SUB_SysInfoType15_2bis = 42
GSMTAP_RRC_SUB_SysInfoType15_2ter = 43
GSMTAP_RRC_SUB_SysInfoType15_3 = 44
GSMTAP_RRC_SUB_SysInfoType15_3bis = 45
GSMTAP_RRC_SUB_SysInfoType15_4 = 46
GSMTAP_RRC_SUB_SysInfoType15_5 = 47
GSMTAP_RRC_SUB_SysInfoType15_6 = 48
GSMTAP_RRC_SUB_SysInfoType15_7 = 49
GSMTAP_RRC_SUB_SysInfoType15_8 = 50
GSMTAP_RRC_SUB_SysInfoType16 = 51
GSMTAP_RRC_SUB_SysInfoType17 = 52
GSMTAP_RRC_SUB_SysInfoType18 = 53
GSMTAP_RRC_SUB_SysInfoType19 = 54
GSMTAP_RRC_SUB_SysInfoType20 = 55
GSMTAP_RRC_SUB_SysInfoType21 = 56
GSMTAP_RRC_SUB_SysInfoType22 = 57
GSMTAP_RRC_SUB_SysInfoTypeSB1 = 58
GSMTAP_RRC_SUB_SysInfoTypeSB2 = 59
GSMTAP_RRC_SUB_ToTargetRNC_Container = 60
GSMTAP_RRC_SUB_TargetRNC_ToSourceRNC_Container = 61

GSMTAP_LTE_RRC_SUB_DL_CCCH_Message = 0
GSMTAP_LTE_RRC_SUB_DL_DCCH_Message = 1
GSMTAP_LTE_RRC_SUB_UL_CCCH_Message = 2
GSMTAP_LTE_RRC_SUB_UL_DCCH_Message = 3
GSMTAP_LTE_RRC_SUB_BCCH_BCH_Message = 4
GSMTAP_LTE_RRC_SUB_BCCH_DL_SCH_Message = 5
GSMTAP_LTE_RRC_SUB_PCCH_Message = 6
GSMTAP_LTE_RRC_SUB_MCCH_Message = 7

GSMTAP_LTE_RRC_SUB_BCCH_BCH_Message_MBMS = 8
GSMTAP_LTE_RRC_SUB_BCCH_DL_SCH_Message_BR = 9
GSMTAP_LTE_RRC_SUB_BCCH_DL_SCH_Message_MBMS = 10
GSMTAP_LTE_RRC_SUB_SC_MCCH_Message = 11
GSMTAP_LTE_RRC_SUB_SBCCH_SL_BCH_Message = 12
GSMTAP_LTE_RRC_SUB_SBCCH_SL_BCH_Message_V2X = 13
GSMTAP_LTE_RRC_SUB_DL_CCCH_Message_NB = 14
GSMTAP_LTE_RRC_SUB_DL_DCCH_Message_NB = 15
GSMTAP_LTE_RRC_SUB_UL_CCCH_Message_NB = 16
GSMTAP_LTE_RRC_SUB_UL_DCCH_Message_NB = 17
GSMTAP_LTE_RRC_SUB_BCCH_BCH_Message_NB = 18
GSMTAP_LTE_RRC_SUB_BCCH_BCH_Message_TDD_NB = 19
GSMTAP_LTE_RRC_SUB_BCCH_DL_SCH_Message_NB = 20
GSMTAP_LTE_RRC_SUB_PCCH_Message_NB = 21
GSMTAP_LTE_RRC_SUB_SC_MCCH_Message_NB = 22

GSMTAP_LTE_NAS_PLAIN = 0
