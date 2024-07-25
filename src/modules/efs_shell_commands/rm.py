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

class RmCommand(BaseEfsShellCommand):
    #Add new parameter efs_type to the initialization method
    def __init__(self, efs_type=None):
        # Save efs_type for use by other methods of the class
        self.efs_type = efs_type
        # Call the parent class's initialization method, if necessary
        super().__init__(fs_type=efs_type)
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('rm',
            description = "This will delete/unlink a file, link or empty directory present on the remote EFS. It will not remove a non-empty directory.")
        
        argument_parser.add_argument('path')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        if self.fs_type == 'efs':
            subsys_code = DIAG_SUBSYS_FS  # Assuming DIAG_SUBSYS_FS is the code for primary
        elif self.fs_type == 'efs2':
            subsys_code = DIAG_SUBSYS_FS_ALTERNATE
        else:
            raise ValueError("Invalid filesystem type specified.")
        # First, emit a stat() (EFS2_DIAG_STAT) call in order to understand whether
        # the remote path input by the user is a directory or not
        
        is_directory : bool = False
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            subsys_code, # Command subsystem number
            EFS2_DIAG_STAT,
        ) + args.path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
    
            print('Error executing STAT: %s received with payload "%s"' % (message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
    
        (cmd_subsystem_id, subcommand_code,
            errno, file_mode, file_size, num_links,
            atime, mtime, ctime) = unpack('<BH7i', payload)
        
        if errno:
            print('Error executing STAT: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        if file_mode & 0o170000 == 0o040000: # S_IFDIR
            
            is_directory = True
    
        # Then, actually open the file for write and/or creation
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            subsys_code, # Command subsystem number
            EFS2_DIAG_RMDIR if is_directory else EFS2_DIAG_UNLINK,
        ) + args.path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing %s: %s received with payload "%s"' % ('RMDIR' if is_directory else 'UNLINK',
                message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        (cmd_subsystem_id, subcommand_code, errno) = unpack('<BHi', payload)
        
        if errno:
            print('Error executing %s: %s' % ('RMDIR' if is_directory else 'UNLINK',
                EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        
        
