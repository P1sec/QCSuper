#!/usr/bin/python3
#-*- encoding: utf-8 -*-
from struct import pack, unpack, unpack_from, calcsize
from logging import debug, info, warning, error
from logging import warning
from crcmod import mkCrcFun
from time import time

from ..protocol.messages import *

"""
    This class implements the pseudo-HDLC framing using for the Qualcomm Diag
    protocol.
"""

class HdlcMixin:

    ESCAPE_CHAR = b'\x7d'
    TRAILER_CHAR = b'\x7e'

    ccitt_crc16 = staticmethod(
        mkCrcFun(0x11021, initCrc=0, xorOut=0xffff)
    )

    """
        Utility function to add CRC + escape the message + add the trailer
        
        :param payload: A raw payload to be encapsulated
    """

    def hdlc_encapsulate(self, payload) -> bytes:
        
        debug('[>] Sending request %s of length %d: %s' % (message_id_to_name.get(payload[0], payload[0]), len(payload[1:]), payload[1:]))
        
        # Add the CRC16
        
        payload += pack('<H', self.ccitt_crc16(payload))
        
        # Escape the message
        
        payload = payload.replace(self.ESCAPE_CHAR, bytes([self.ESCAPE_CHAR[0], self.ESCAPE_CHAR[0] ^ 0x20]))
        payload = payload.replace(self.TRAILER_CHAR, bytes([self.ESCAPE_CHAR[0], self.TRAILER_CHAR[0] ^ 0x20]))
        
        # Add the trailer
        
        payload += self.TRAILER_CHAR
        
        return payload

    """
        Utility function to decode the reverse way
        
        :param payload: An encapsulated payload to be made raw
        :param raise_on_invalid_frame: Whether to signal to the caller through
            an Exception that a packet that is too short or with an invalid
            CRC-16 was received, rather than just printing a warning
    """

    def hdlc_decapsulate(self, payload, raise_on_invalid_frame = False) -> bytes:
        
        # Check the message length
        
        if len(payload) < 3:
            
            if raise_on_invalid_frame:
                raise self.InvalidFrameError
            
            error('Too short Diag frame received')
            
            exit()
        
        # Remove the trailer
        
        assert payload[-1:] == self.TRAILER_CHAR
        payload = payload[:-1]
        
        # Unescape the message
        
        payload = payload.replace(bytes([self.ESCAPE_CHAR[0], self.TRAILER_CHAR[0] ^ 0x20]), self.TRAILER_CHAR)
        payload = payload.replace(bytes([self.ESCAPE_CHAR[0], self.ESCAPE_CHAR[0] ^ 0x20]), self.ESCAPE_CHAR)
        
        # Check the CRC16
        
        if payload[-2:] != pack('<H', self.ccitt_crc16(payload[:-2])):
            
            if raise_on_invalid_frame:
                raise self.InvalidFrameError
            
            debug('Ignoring (partial?) frame: Wrong CRC: %s (is: %02x, should be: %02x)' % (
                    repr(payload[:-2]),
                    unpack('<H', payload[-2:])[0],
                    self.ccitt_crc16(payload[:-2])))
        
        payload = payload[:-2]
        
        return payload
    
    class InvalidFrameError(Exception):
        
        pass
    
from ..protocol import messages

message_id_to_name = {
    value: key
    for key, value in messages.__dict__.items()
    if key.startswith('DIAG_')
}

