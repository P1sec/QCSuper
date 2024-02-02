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

class LnCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('ln',
            description = "Create an UNIX symbolic link across the remote EFS.")
        
        argument_parser.add_argument('remote_newlink')
        argument_parser.add_argument('remote_target')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        
        # Rename the target path
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_SYMLINK,
        ) + args.remote_newlink.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00'
          + args.remote_target.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing SYMLINK: %s received with payload "%s"' % (
                message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        (cmd_subsystem_id, subcommand_code, errno) = unpack('<BHi', payload)
        
        if errno:
            print('Error executing SYMLINK: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        
        
