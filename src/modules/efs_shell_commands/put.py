#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from argparse import ArgumentParser, _SubParsersAction, Namespace
from os.path import basename, dirname, expanduser, exists, isdir
from struct import pack, unpack, calcsize
from typing import List, Dict, Optional
from os import strerror, getcwd
from datetime import datetime

from ._base_efs_shell_command import BaseEfsShellCommand
from ...inputs._base_input import message_id_to_name
from ...protocol.subsystems import *
from ...protocol.messages import *
from ...protocol.efs2 import *

class PutCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('put',
            description = "Read a file from the local disk, and upload it to the EFS (create it if does not exist).")
        
        argument_parser.add_argument('local_src')
        argument_parser.add_argument('remote_dst')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        
        local_src : str = expanduser(args.local_src)
        remote_dst : str = args.remote_dst
        
        if not exists(local_src):
            
            print('Error: "%s" does not exist on your local disk' % local_src)
            return
        
        with open(local_src, 'rb') as input_file:
            
            # First, emit a stat() (EFS2_DIAG_STAT) call in order to understand whether
            # the remote target path input by the user is a directory or not, and to
            # know the UNIX mode of the original file in the case where it already
            # exists, so that we don't have to overwrite it when uploading our
            # new file with open() (EFS2_DIAG_OPEN)
            
            file_mode_int : int = 0o100777 # By default, our remotely created file will have all rights, and be a regular file (S_IFREG)
            is_directory : bool = False
            
            opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
                DIAG_SUBSYS_FS, # Command subsystem number
                EFS2_DIAG_STAT,
            ) + remote_dst.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
            
            if opcode == DIAG_SUBSYS_CMD_F: # No error, file or directory exists?
                
                (cmd_subsystem_id, subcommand_code,
                    errno, file_mode, file_size, num_links,
                    atime, mtime, ctime) = unpack('<BH7i', payload)
                
                if not errno:
                    
                    if file_mode & 0o170000 == 0o040000: # S_IFDIR
                        is_directory = True
                    
                    else:
                        file_mode_int = file_mode
            
            if is_directory:
                
                remote_dst += '/' + basename(local_src)
            
            # Then, actually open the file for write and/or creation
            
            opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHii',
                DIAG_SUBSYS_FS, # Command subsystem number
                EFS2_DIAG_OPEN,
                0o1101, # oflag - "O_WRONLY | O_TRUNC | O_CREAT "
                file_mode_int, # mode
            ) + remote_dst.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
            
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
                
                BYTES_TO_WRITE = 1024
                
                while True:
                    
                    read_position : int = input_file.tell()
                    read_data : bytes = input_file.read(BYTES_TO_WRITE)
                    
                    if not read_data: # EOF was reached
                        break
                    
                    opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHiI',
                        DIAG_SUBSYS_FS, # Command subsystem number
                        EFS2_DIAG_WRITE,
                        file_fd, # File descriptor to write to
                        read_position # File position to write at
                    ) + read_data)
                    
                    (cmd_subsystem_id, subcommand_code,
                            file_fd, offset, num_bytes_written,
                            errno) = unpack('<BHiIii', payload)
                    
                    if errno:
                        print('Error executing WRITE: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                        return
                
            
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
            
            
            
