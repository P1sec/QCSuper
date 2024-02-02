#!/usr/bin/python3
#-*- encoding: Utf-8 -*-

from argparse import ArgumentParser, _SubParsersAction, Namespace
from struct import pack, unpack, calcsize
from typing import List, Dict, Optional
from datetime import datetime

from ._base_efs_shell_command import BaseEfsShellCommand
from ...inputs._base_input import message_id_to_name
from ...protocol.subsystems import *
from ...protocol.messages import *
from ...protocol.efs2 import *
from os import strerror

class StatCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('stat',
            description = 'View meta-information about a given file or directory in the remote EFS filesystem.')
        
        argument_parser.add_argument('path',
            nargs = '?', default = '/')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):

        encoded_path : bytes = args.path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00'

        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            DIAG_SUBSYS_FS, # Command subsystem number,
            EFS2_DIAG_STAT) + encoded_path, accept_error = True)
            
        readdir_struct = '<BHI8i'
        
        (cmd_subsystem_id, subcommand_code,
            errno, mode, size, num_links,
            atime, mtime, ctime) = unpack('<BH7i', payload)
        
        if errno:
            print('Error executing STAT: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        if opcode != DIAG_SUBSYS_CMD_F:
    
            print('Error executing STAT: %s received with payload "%s"' % (message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        special_flags : List[str] = []
        if mode & 0o4000:
            special_flags.append('(setuid)') # S_ISUID - Set UID on execution.
        if mode & 0o2000:
            special_flags.append('(setgid)') # S_ISGID - Set GID on execution.
        if mode & 0o1000:
            special_flags.append('(sticky)') # S_ISVTX - Sticky (HIDDEN attribute in HFAT)
        
        file_rights = ''
        for shift in range(8, -1, -1): # (1<<8) == 0o400, ...
            file_rights += 'rwx'[(8 - shift) % 3] if (mode & (1 << shift)) else '-'
        
        # Resolve the symbolic file of the concerned file if needed
        
        real_path : Optional[str] = None
        
        if mode & 0o170000 == 0o120000: # S_IFLNK

            opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
                DIAG_SUBSYS_FS, # Command subsystem number,
                EFS2_DIAG_READLINK) + encoded_path, accept_error = False)
                
            readlink_struct = '<BHI'
            
            (cmd_subsystem_id, subcommand_code, errno) = unpack(readlink_struct, payload[:calcsize(readlink_struct)])
            
            real_path = payload[calcsize(readlink_struct):].rstrip(b'\x00').decode('latin1')
            
            if errno:
                print('Error executing READLINK: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                return                    
        
        print()
        
        for row, value in {
            'File type': EFS2_FILE_TYPES[mode & 0o170000],
            'Special flags': ' '.join(special_flags),
            'File rights': file_rights,
            'File name': repr(args.path) + (
                (' -> ' + repr(real_path)) if real_path else ''),
            'Number of entries' if mode & 0o170000 == 0o040000 else 'File size': str(size), # Directory (S_IFDIR)
            'Number of links on the filesystem': str(num_links),
            'Modification time': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'Access time': datetime.fromtimestamp(atime).strftime('%Y-%m-%d %H:%M:%S'), # Was taking too much horizontal space
            'Creation time': datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S'),
        }.items():
            if value:
                print(' - %s: %s' % (row, value))
        
        print()

