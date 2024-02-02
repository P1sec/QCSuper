#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from os.path import basename, realpath, dirname, expanduser, exists, isdir
from argparse import ArgumentParser, _SubParsersAction, Namespace
from struct import pack, unpack, calcsize
from typing import List, Dict, Optional
from os import strerror, getcwd
from datetime import datetime

from ._base_efs_shell_command import BaseEfsShellCommand
from ...inputs._base_input import message_id_to_name
from ...protocol.subsystems import *
from ...protocol.messages import *
from ...protocol.efs2 import *

class GetCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('get',
            description = "Read a file in the EFS, and download it to the disk to the specified location (to the shell's current directory if not specified.")
        
        argument_parser.add_argument('remote_src')
        argument_parser.add_argument('local_dst', nargs = '?')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        
        remote_src : str = args.remote_src
        local_dst : str = expanduser(args.local_dst or (getcwd() + '/' + basename(remote_src)))
        
        if exists(local_dst) and isdir(local_dst):
            local_dst += '/' + basename(remote_src)
        
        if not exists(realpath(dirname(local_dst))):
            print('Error: "%s": No such file or directory' % local_dst)
            return
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHii',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_OPEN,
            0x0, # oflag - "O_RDONLY"
            0, # mode (ignored)
        ) + remote_src.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
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
            
            BYTES_TO_READ = 1024
            
            with open(local_dst, 'wb') as output_file:
                
                while True:
                    
                    opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHiII',
                        DIAG_SUBSYS_FS, # Command subsystem number
                        EFS2_DIAG_READ,
                        file_fd, # File descriptor to read from
                        BYTES_TO_READ, # Bytes to read at once
                        output_file.tell() # Offset where to read
                    ))
                    
                    read_struct = '<BHiIii'
                    
                    (cmd_subsystem_id, subcommand_code,
                            file_fd, offset, num_bytes_read,
                            errno) = unpack(read_struct, payload[:calcsize(read_struct)])
                    
                    read_data : bytes = payload[calcsize(read_struct):]
                    
                    output_file.write(read_data)
                    
                    if errno:
                        print('Error executing READ: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                        return
                    
                    if len(read_data) < BYTES_TO_READ:
                        break # EOF was reached
            
        
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
        
        
        
