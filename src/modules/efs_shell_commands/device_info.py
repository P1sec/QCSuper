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

class DeviceInfoCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('device_info',
            description = "Obtain information about the NOR/NAND device information underlying the EFS filesystem of the baseband.")
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        
        # Obtain the EFS underlying flash device information
        
        sequence_number = randint(0, 0xffff)
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_DEV_INFO), accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing DEV_INFO: %s received with payload "%s"' % (
                message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        device_info_spec = '<BH7iB'
        
        (cmd_subsystem_id, subcommand_code, errno,
            num_blocks, pages_per_block, page_size,
            total_page_size, maker_id, device_id,
            device_type) = unpack(device_info_spec, payload[:calcsize(device_info_spec)])
        
        device_name : str = payload[calcsize(device_info_spec):].rstrip(b'\x00').decode('utf8')
        
        if errno:
            print('Error executing DEV_INFO: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        print()
        print('Device information:')
        print('- Number of blocks: %d' % num_blocks)
        print('- Number of pages per block: %d' % pages_per_block)
        print('- Page size in bytes: %d' % page_size)
        print('- Total page size: %d' % total_page_size)
        print('- Device marker ID: %d' % maker_id)
        print('- Device ID: %d' % device_id)
        print('- Device type: ' + ('NAND' if device_type else 'NOR'))
        print('- Device name: %s' % device_name)
        print()
        
        
        
