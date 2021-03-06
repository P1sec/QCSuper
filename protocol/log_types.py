#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

"""
    This file enumerates DIAG log types, used in DIAG_LOG_F packets.
"""

"""
    These are 2G-related log types.
"""

LOG_GSM_RR_SIGNALING_MESSAGE_C = 0x512f

DCCH = 0x00
BCCH = 0x01
L2_RACH = 0x02
CCCH = 0x03
SACCH = 0x04
SDCCH = 0x05
FACCH_F = 0x06
FACCH_H = 0x07
L2_RACH_WITH_NO_DELAY = 0x08

"""
    These are GPRS-related log types.
"""

LOG_GPRS_MAC_SIGNALLING_MESSAGE_C = 0x5226

PACCH_RRBP_CHANNEL = 0x03
UL_PACCH_CHANNEL = 0x04
DL_PACCH_CHANNEL = 0x83

PACKET_CHANNEL_REQUEST = 0x20

"""
    These are 4G-related log types.
"""

LOG_LTE_RRC_OTA_MSG_LOG_C = 0xb0c0
LOG_LTE_NAS_ESM_OTA_IN_MSG_LOG_C = 0xb0e2
LOG_LTE_NAS_ESM_OTA_OUT_MSG_LOG_C = 0xb0e3
LOG_LTE_NAS_EMM_OTA_IN_MSG_LOG_C = 0xb0ec
LOG_LTE_NAS_EMM_OTA_OUT_MSG_LOG_C = 0xb0ed

LTE_BCCH_DL_SCH = 2
LTE_PCCH = 4
LTE_DL_CCCH = 5
LTE_DL_DCCH = 6
LTE_UL_CCCH = 7
LTE_UL_DCCH = 8

LTE_BCCH_DL_SCH_NB = 46
LTE_PCCH_NB = 47
LTE_DL_CCCH_NB = 48
LTE_DL_DCCH_NB = 49
LTE_UL_CCCH_NB = 50
LTE_UL_DCCH_NB = 52

"""
    These are 3G-related log types.
"""

RRCLOG_SIG_UL_CCCH = 0
RRCLOG_SIG_UL_DCCH = 1
RRCLOG_SIG_DL_CCCH = 2
RRCLOG_SIG_DL_DCCH = 3
RRCLOG_SIG_DL_BCCH_BCH = 4
RRCLOG_SIG_DL_BCCH_FACH = 5
RRCLOG_SIG_DL_PCCH = 6
RRCLOG_EXTENSION_SIB = 9
RRCLOG_SIB_CONTAINER = 10


"""
    3G layer 3 packets:
"""

WCDMA_SIGNALLING_MESSAGE = 0x412f


"""
    Upper layers
"""

LOG_DATA_PROTOCOL_LOGGING_C = 0x11eb

LOG_UMTS_NAS_OTA_MESSAGE_LOG_PACKET_C = 0x713a



