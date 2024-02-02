#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from argparse import ArgumentParser, _SubParsersAction, Namespace
from struct import pack, unpack, calcsize
from typing import List, Dict, Optional
from datetime import datetime
from os import strerror

from ._base_efs_shell_command import BaseEfsShellCommand
from ...inputs._base_input import message_id_to_name
from ...protocol.subsystems import *
from ...protocol.messages import *
from ...protocol.efs2 import *

class CatCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('cat',
            description = 'Read a file in the EFS, and display it to the standard input, as free text if it is printable or as a ascii-hexadecimal dump if it is not.')
        
        argument_parser.add_argument('path',
            nargs = '?', default = '/')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHii',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_OPEN,
            0x0, # oflag - "O_RDONLY"
            0, # mode (ignored)
        ) + args.path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing OPEN: %s received with payload "%s"' % (message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        (cmd_subsystem_id, subcommand_code,
            file_fd, errno) = unpack('<BHIi', payload)
        
        if errno:
            print('Error executing OPEN: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        try: # try/finally block for remotely closing the file opened with the "EFS2_DIAG_OPEN" command in all cases:
            
            bytes_read : bytes = b''
            
            BYTES_TO_READ = 1024
            
            while True:
                
                opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHiII',
                    DIAG_SUBSYS_FS, # Command subsystem number
                    EFS2_DIAG_READ,
                    file_fd, # File descriptor to read from
                    BYTES_TO_READ, # Bytes to read at once
                    len(bytes_read) # Offset where to read
                ))
                
                read_struct = '<BHiIii'
                
                (cmd_subsystem_id, subcommand_code,
                        file_fd, offset, num_bytes_read,
                        errno) = unpack(read_struct, payload[:calcsize(read_struct)])
                
                read_data : bytes = payload[calcsize(read_struct):]
                
                if errno:
                    print('Error executing READ: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                    return
                
                bytes_read += read_data
                if len(read_data) < BYTES_TO_READ:
                    break # EOF was reached
            
            is_printable : bool = False
            
            try:
                if bytes_read.decode('utf8').replace('\n', '').replace('\t', '').isprintable():
                    is_printable = True
            except Exception:
                pass
            
            if is_printable: # Print raw text if printable
                print(bytes_read.decode('utf8'))
                
            else: # Print an hexadecimal/ascii dump if non-ascii printable
                BYTES_PER_LINE = 32
                
                print()
                
                for position in range(0, len(bytes_read), BYTES_PER_LINE):
                    hexdump_line : str = '  '
                    
                    for byte_index in range(BYTES_PER_LINE): # Display hex bytes
                        
                        if position + byte_index < len(bytes_read):
                            hexdump_line += '%02x ' % bytes_read[position + byte_index]
                        else: # Apply padding if needed
                            hexdump_line += '   '
                        
                        if byte_index & 3 == 3:
                            hexdump_line += ' '
                
                    hexdump_line += '  '
                
                    for byte in bytes_read[position:position + BYTES_PER_LINE]: # Display ascii bytes at the end of the printed line
                        
                        hexdump_line += chr(byte) if 0x20 <= byte <= 0x7f else '.'
                    
                    hexdump_line += ' '
                    
                    print(hexdump_line)
                
                print()
            
        
        finally:
            
            opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHi',
                DIAG_SUBSYS_FS, # Command subsystem number
                EFS2_DIAG_CLOSE,
                file_fd
            ))
            
            (cmd_subsystem_id, subcommand_code, errno) = unpack('<BHi', payload)
            
            if errno:
                print('Error executing CLOSE: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                return
        
        
        
