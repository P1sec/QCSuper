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

class ChmodCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('chmod',
            description = "This will change the permissions of a file, link or directory present on the remote EFS, according to arguments.")
        
        argument_parser.add_argument('--set-file-type', help = 'Possible values: S_IFIFO (FIFO), S_IFCHR (character device), S_IFDIR (directory), S_IFBLK (block device), S_IFREG (regular file), S_IFLNK (symbolic link), S_IFSOCK (socket), S_IFITM (item file)')
        argument_parser.add_argument('--set-suid', action = 'store_true')
        argument_parser.add_argument('--unset-suid', action = 'store_true')
        argument_parser.add_argument('--set-sgid', action = 'store_true')
        argument_parser.add_argument('--unset-sgid', action = 'store_true')
        argument_parser.add_argument('--set-sticky', action = 'store_true')
        argument_parser.add_argument('--unset-sticky', action = 'store_true')
        argument_parser.add_argument('octal_perms', help = 'UNIX permissions, for example: 666')
        argument_parser.add_argument('file_path', help = 'For example: /policyman/post.xml')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
    
        try:
            assert int(args.octal_perms, 8) & ~0o777 == 0
        except Exception:
            print('Error: "octal_perms" should be a three-digit octal number')
            return
    
        # First, emit a stat() (EFS2_DIAG_STAT) call in order to understand whether
        # the remote path input by the user is a directory or not
        
        is_directory : bool = False
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_STAT,
        ) + args.file_path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
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
    
        file_mode = (file_mode & ~0o777) | (int(args.octal_perms, 8) & 0o777)
        file_mode &= ~0o170000 # S_IFMT (don't try to change the file type bits by default)
        
        if args.set_file_type:
            S_IFMT = 0o170000 # Mask of all values
            
            file_type_value = {
                'S_IFIFO': 0o010000,
                'S_IFCHR': 0o020000,
                'S_IFDIR': 0o040000,
                'S_IFBLK': 0o060000,
                'S_IFREG': 0o100000,
                'S_IFLNK': 0o120000,
                'S_IFSOCK': 0o140000,
                'S_IFITM': 0o160000
            }.get(args.set_file_type.upper())
            
            if not file_type_value:
                print(('Error: "%s" is not a valid file type, please see ' +
                    'the command help for details') % args.set_file_type)
                return
            
            file_mode = (file_mode & ~S_IFMT) | file_type_value
        
        if args.set_suid:
            file_mode |= 0o4000 # S_ISUID
        if args.unset_suid:
            file_mode &= ~0o4000 # S_ISUID
        if args.set_sgid:
            file_mode |= 0o2000 # S_ISGID
        if args.unset_sgid:
            file_mode &= ~0o2000 # S_ISGID
        if args.set_sticky:
            file_mode |= 0o1000 # S_ISVTX
        if args.unset_sticky:
            file_mode &= ~0o1000 # S_ISVTX
            
    
        # Then, actually open the file for write and/or creation
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHH',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_CHMOD,
            file_mode
        ) + args.file_path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing CHMOD: %s received with payload "%s"' % (
                message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        (cmd_subsystem_id, subcommand_code, errno) = unpack('<BHi', payload)
        
        if errno:
            print('Error executing CHMOD: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        
        
