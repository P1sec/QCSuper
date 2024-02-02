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

class LsCommand(BaseEfsShellCommand):
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        argument_parser = subparsers_object.add_parser('ls',
            description = 'List files within a given directory of the EFS.')
        
        argument_parser.add_argument('path',
            nargs = '?', default = '/')
        
        return argument_parser
        
    def execute_command(self, diag_input, args : Namespace):
        
        opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_OPENDIR
        ) + args.path.encode('latin1').decode('unicode_escape').encode('latin1') + b'\x00', accept_error = True)
        
        if opcode != DIAG_SUBSYS_CMD_F:
            print('Error executing OPENDIR: %s received with payload "%s"' % (message_id_to_name.get(opcode, opcode),
                repr(payload)))
            return
        
        (cmd_subsystem_id, subcommand_code,
            dir_fd, errno) = unpack('<BHIi', payload)
        
        if errno:
            print('Error executing OPENDIR: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
            return
        
        try: # Close the directory identifier in all cases using the "finally" block below
            
            sequence_number = 1 # For the protocol
            
            table_rows_to_print : List[Dict[str, str]] = [] # For the standard output
            
            while True: # Iterate over directory files
            
                opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHIi',
                    DIAG_SUBSYS_FS, # Command subsystem number,
                    EFS2_DIAG_READDIR,
                    dir_fd, sequence_number), accept_error = False)
                    
                readdir_struct = '<BHI8i'
                
                (cmd_subsystem_id, subcommand_code,
                    dir_fd, sequence_number, errno,
                    entry_type, mode, size,
                    atime, mtime, ctime) = unpack(readdir_struct, payload[:calcsize(readdir_struct)])
                
                entry_path = payload[calcsize(readdir_struct):]
                
                if errno:
                    print('Error executing READDIR: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                    return
                
                if not entry_path.strip(b'\x00'): # End of directory reached
                    break
                
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
                        EFS2_DIAG_READLINK) + entry_path.rstrip(b'\x00') + b'\x00', accept_error = False)
                        
                    readlink_struct = '<BHI'
                    
                    (cmd_subsystem_id, subcommand_code, errno) = unpack(readlink_struct, payload[:calcsize(readlink_struct)])
                    
                    real_path = payload[calcsize(readlink_struct):].rstrip(b'\x00').decode('latin1')
                    
                    if errno:
                        print('Error executing READLINK: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                        return                    
                
                table_rows_to_print.append({
                    'File type': EFS2_FILE_TYPES[mode & 0o170000],
                    'Special flags': ' '.join(special_flags),
                    'File rights': file_rights,
                    'File name': repr(entry_path.rstrip(b'\x00').decode('latin1')) + (
                        (' -> ' + repr(real_path)) if real_path else ''),
                    'File size': str(size) if entry_type != 0x01 else '', # 0x01: "FS_DIAG_FTYPE_DIR - Directory file"
                    'Modification': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    # 'Access': datetime.fromtimestamp(atime).strftime('%Y-%m-%d %H:%M:%S'), # Was taking too much horizontal space
                    'Creation': datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S'),
                })
                
                sequence_number += 1
            
            if table_rows_to_print:
                column_names : List[str] = list(table_rows_to_print[0].keys())
                
                column_index_to_max_value_char_width : List[int] = [
                    max(len(column_name), max(len(row[column_name]) for row in table_rows_to_print))
                    for column_name in column_names
                ]
                
                separator_row_text : str = ('+' + '-' * (sum(char_width + 3 for
                    char_width in column_index_to_max_value_char_width) - 1) + '+')
                
                print(separator_row_text)
                
                print('+ ' + ' | '.join(column_name.ljust(column_index_to_max_value_char_width[column_index], ' ') for
                    column_index, column_name in enumerate(column_names)) + ' +')
                
                print(separator_row_text)
                
                for row in table_rows_to_print:
                    print('+ ' + ' | '.join(row[column_name].ljust(column_index_to_max_value_char_width[column_index], ' ') for
                        column_index, column_name in enumerate(column_names)) + ' +')
                
                print(separator_row_text)
        
        finally:
            
            opcode, payload = diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHi',
                DIAG_SUBSYS_FS, # Command subsystem number
                EFS2_DIAG_CLOSEDIR,
                dir_fd
            ))
            
            (cmd_subsystem_id, subcommand_code, errno) = unpack('<BHi', payload)
            
            if errno:
                print('Error executing CLOSEDIR: %s' % (EFS2_ERROR_CODES.get(errno) or strerror(errno)))
                return
        
        
