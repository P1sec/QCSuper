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

class MvCommand(BaseEfsShellCommand):
    #Add new parameter efs_type to the initialization method
    def __init__(self, efs_type=None):
        # Save efs_type for use by other methods of the class
        self.efs_type = efs_type
        # Call the parent class's initialization method, if necessary
        super().__init__(fs_type=efs_type)
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('mv',
            description = "Rename or move a given file or directory in the remote EFS.")
        
        argument_parser.add_argument('remote_src')
        argument_parser.add_argument('remote_dst')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        if self.fs_type == 'efs':
            subsys_code = DIAG_SUBSYS_FS  # Assuming DIAG_SUBSYS_FS is the code for primary
        elif self.fs_type == 'efs2':
            subsys_code = DIAG_SUBSYS_FS_ALTERNATE
        else:
            raise ValueError("Invalid filesystem type specified.")
        # Rename the target path
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            subsys_code, # Command subsystem number
            EFS2_DIAG_RENAME,
        ) + args.remote_src.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00'
          + args.remote_dst.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing RENAME: %s received with payload "%s"' % (
                message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        (cmd_subsystem_id, subcommand_code, errno) = unpack('<BHi', payload)
        
        if errno:
            print('Error executing RENAME: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        
        
        
        
