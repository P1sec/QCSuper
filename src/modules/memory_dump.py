#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from struct import pack, unpack_from, calcsize
from ..protocol.messages import *
from datetime import datetime
from struct import unpack
from enum import IntEnum
from os import makedirs

"""
    This module is meant to dump the memory from a QCDM device. It will better
    work on older devices (e.g the Qualcomm Icon 225 from 2008, as presented in
    research from Guillaume Delugré), on other it will work on certain memory ranges,
    on some it will not work at all.
    
    This module creates an output directory where raw memory chunks will be
    written using filenames like "chunk_<start address>".
"""

"""
    The Diag commands purporting to read the memory allow only reading a word
    of memory at once.

    In order to find the readable memory ranges faster when only certain are,
    it will seek through memory by increments of 0x1000 bytes (state
    LOOKING_FORWARD_1000_BY_1000) until one is found.
    
    When an offset pertaining to a readable chunk is found, it will seek
    backwards one word at once (LOOKING_BACKWARDS_10_BY_10) until the beginning
    of this chunk is found.
    
    Once done, it reads it sequentially (READING_FORWARD_10_BY_10).
"""

class MemoryReaderState(IntEnum):
    LOOKING_FORWARD_1000_BY_1000 = 0
    LOOKING_BACKWARDS_10_BY_10 = 1
    READING_FORWARD_10_BY_10 = 2

CLEAR_LINE = '\x1b[2K' # From https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_sequences

class MemoryDumper:
    
    def __init__(self, diag_input, output_dir, start_address, end_address):
        
        self.diag_input = diag_input
        
        self.output_dir = output_dir
        
        makedirs(self.output_dir, exist_ok = True)
        
        self.start_address, self.end_address = start_address, end_address
    
    def on_init(self):
        
        """
            Initialize the state machine and local variables
        """
        
        state = MemoryReaderState.READING_FORWARD_10_BY_10
        
        output_file = None
        
        print()
        
        current_address = self.start_address
        
        """
            Start seeking through the memory in a loop
        """
        
        while current_address < self.end_address:
            
            """
                Print the state of the program
            """
            
            if state != MemoryReaderState.READING_FORWARD_10_BY_10:
            
                print(CLEAR_LINE + 'Trying to read at %08x/%08x (%.1f%%)...' % (
                    current_address,
                    self.end_address,
                    current_address / self.end_address * 100
                ), end = '\r')
            
            else:
                
                print(CLEAR_LINE + 'Reading at %08x/%08x (%.1f%%)...' % (
                    current_address,
                    self.end_address,
                    current_address / self.end_address * 100
                ), end = '\r')
            
            """
                Try to read a given address
            """
            
            opcode, payload = self.diag_input.send_recv(DIAG_PEEKB_F, pack('<IH', current_address, 16), accept_error = True)
            
            if opcode == DIAG_PEEKB_F: # Read succeeded
                
                address_read, bytes_read, contents = unpack('<IH16s', payload)
                assert address_read == current_address and bytes_read == 16
                
                # We hit redable data in the middle of a chunk will trying to
                # read an address incrementing 0x1000 by 0x1000: start reading
                # backwards word by word until we find the start of the chunk.
                
                if state == MemoryReaderState.LOOKING_FORWARD_1000_BY_1000:
                    
                    state = MemoryReaderState.LOOKING_BACKWARDS_10_BY_10
                
                # We're reading forward the contents of a chunk word by word:
                # write the contents to a file.
                
                elif state == MemoryReaderState.READING_FORWARD_10_BY_10:
                
                    if not output_file: # Open the output file if we're writing to an new chunk.
                        
                        current_chunk_base_address = current_address
                        
                        output_file_name = '%s/chunk_%08x' % (self.output_dir, current_chunk_base_address)
                        
                        output_file = open(output_file_name, 'wb')
                    
                    output_file.write(contents)
            
            elif opcode == DIAG_BAD_PARM_F: # Read failed
                
                # We hit the word right before the beginning of a memory chunk
                # when searching for the beginning this memory chunk: start
                # reading the chunk forward.
                
                if state == MemoryReaderState.LOOKING_BACKWARDS_10_BY_10:
                    
                    state = MemoryReaderState.READING_FORWARD_10_BY_10
                    
                    print(CLEAR_LINE + 'Found memory at %08x' % (current_address + 0x10))
                
                # We hit the word right after the end of a memory chunk when
                # reading the chunk forward: get back to searching for more chunks.
                
                elif state == MemoryReaderState.READING_FORWARD_10_BY_10:
                    
                    state = MemoryReaderState.LOOKING_FORWARD_1000_BY_1000
                    
                    if output_file: # Close the current output file and print status.
                        
                        print(CLEAR_LINE + 'Memory at %08x had length %08x\n' % (
                            current_chunk_base_address,
                            output_file.tell()
                        ))
                        
                        output_file.close()
                        output_file = None
            
            else: # Command refused
                
                print(CLEAR_LINE + 'Dumping memory seems not to be supported on this device')
                
                break
            
            """
                Mutate the read address for the next iteration, depending on the
                current state of the state machine
            """
            
            if state == MemoryReaderState.READING_FORWARD_10_BY_10:
                
                current_address += 0x10
            
            elif state == MemoryReaderState.LOOKING_BACKWARDS_10_BY_10:
                
                current_address -= 0x10
            
            elif state == MemoryReaderState.LOOKING_FORWARD_1000_BY_1000:
                
                if current_address % 0x1000 == 0:
                    current_address += 0x1000
                else:
                    current_address += -current_address % 0x1000
                
                if current_address == 0xc0000000: # Reading at 0xc0000000 may crash certain devices
                    current_address += 0x10000000
        
        print()
        
        """
            Deinitialize remaining descriptors
        """
        
        if output_file:
            
            output_file.close()


