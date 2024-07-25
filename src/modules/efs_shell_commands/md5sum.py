#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from argparse import ArgumentParser, _SubParsersAction, Namespace
from os.path import basename, dirname, expanduser, exists, isdir
from struct import pack, unpack, calcsize
from typing import List, Dict, Optional
from os import strerror, getcwd
from random import randint

from ._base_efs_shell_command import BaseEfsShellCommand
from ...inputs._base_input import message_id_to_name
from ...protocol.subsystems import *
from ...protocol.messages import *
from ...protocol.efs2 import *

class Md5sumCommand(BaseEfsShellCommand):
    #Add new parameter efs_type to the initialization method
    def __init__(self, efs_type=None):
        # Save efs_type for use by other methods of the class
        self.efs_type = efs_type
        # Call the parent class's initialization method, if necessary
        super().__init__(fs_type=efs_type)
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('md5sum',
            description = "Obtain a MD5 checksum of the desired file, for a given path.")
        
        argument_parser.add_argument('path')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        if self.fs_type == 'efs':
            subsys_code = DIAG_SUBSYS_FS  # Assuming DIAG_SUBSYS_FS is the code for primary
        elif self.fs_type == 'efs2':
            subsys_code = DIAG_SUBSYS_FS_ALTERNATE
        else:
            raise ValueError("Invalid filesystem type specified.")
        # Obtain the file checksum
        
        sequence_number = randint(0, 0xffff)
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHH',
            subsys_code, # Command subsystem number
            EFS2_DIAG_MKDIR,
            sequence_number
        ) + args.path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing MD5SUM: %s received with payload "%s"' % (
                message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        md5sum_spec = '<BHHi'
        
        (cmd_subsystem_id, subcommand_code, sequence_number, errno) = unpack(md5sum_spec, payload[:calcsize(md5sum_spec)])
        
        text_hash : str = payload[calcsize(md5sum_spec):].hex()
        
        if errno:
            print('Error executing MD5SUM: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        print(text_hash)
        
        
        
