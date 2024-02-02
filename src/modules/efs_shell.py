#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from argparse import ArgumentParser, _SubParsersAction, Namespace
from typing import Dict, List, Set, Sequence, Optional
from logging import error, warning, debug, info
from traceback import print_exc
from struct import pack, unpack
from subprocess import run
from shutil import which
from shlex import split

from ..inputs._base_input import BaseInput
from ..protocol.subsystems import *
from ..protocol.messages import *
from ..protocol.efs2 import *

from .efs_shell_commands._base_efs_shell_command import BaseEfsShellCommand
from .efs_shell_commands.device_info import DeviceInfoCommand
from .efs_shell_commands.md5sum import Md5sumCommand
from .efs_shell_commands.chmod import ChmodCommand
from .efs_shell_commands.mkdir import MkdirCommand
from .efs_shell_commands.stat import StatCommand
from .efs_shell_commands.get import GetCommand
from .efs_shell_commands.put import PutCommand
from .efs_shell_commands.cat import CatCommand
from .efs_shell_commands.mv import MvCommand
from .efs_shell_commands.ln import LnCommand
from .efs_shell_commands.rm import RmCommand
from .efs_shell_commands.ls import LsCommand

ALL_COMMAND_CLASSES = [CatCommand, LsCommand, GetCommand, PutCommand, RmCommand, ChmodCommand, MkdirCommand, MvCommand, LnCommand,
    DeviceInfoCommand, StatCommand]
# "Md5sumCommand" is currently not used, it returns an invalid packet on my device

class EfsShell:
    
    def __init__(self, diag_input : BaseInput):
        
        self.diag_input : BaseInput = diag_input
        
        self.parser = ArgumentParser(description = 'Spawn an interactive shell to navigate within the embedded filesystem (EFS) of the baseband device.', prog = '')
        
        self.sub_parsers : _SubParsersAction = self.parser.add_subparsers()
        
        self.sub_parser_command_name_to_command_object : Dict[str, BaseEfsShellCommand] = {}
        
        for command_class in ALL_COMMAND_CLASSES:
            
            command_object = command_class()
            
            sub_parser = command_object.get_argument_parser(self.sub_parsers) # Will populate the "self.sub_parsers._name_parser_map" map, see the source of "argparse.py" in Python's standard library for reference
            
            self.sub_parser_command_name_to_command_object[sub_parser.prog.split(' ')[1]] = command_object
        
    def on_init(self):
        
        print()
        
        self.setup_readline()
        
        while True:
            
            try:
            
                line = input('>>> ')
            
                if line.strip().lower() in ('q', 'quit', 'exit'):
                    
                    raise EOFError
            
            except (EOFError, IOError):
                
                # Interrupt the main and the current thread
                
                with self.diag_input.shutdown_event:
                    
                    self.diag_input.shutdown_event.notify()
                
                return
            
            if line:
                
                try:
                    
                    user_args : List[str] = split(line)
                
                except Exception:
                    
                    print_exc()
                
                else:
                    
                    if user_args and user_args[0] in self.sub_parsers._name_parser_map:
                        
                        sub_command_name : str = user_args[0]
                        
                        sub_parser_args : List[str] = user_args[1:]
                        
                        sub_parser : ArgumentParser = self.sub_parsers._name_parser_map[sub_command_name]
                        
                        command_object : BaseEfsShellCommand = self.sub_parser_command_name_to_command_object[sub_command_name]
                        
                        try:
                            
                            parsed_args : Namespace = sub_parser.parse_args(sub_parser_args)
                        
                        except SystemExit:
                            
                            pass
                        
                        except Exception:
                            
                            print_exc()
                        
                        else:
                            
                            self.send_efs_handshake()
                            
                            try:
                            
                                command_object.execute_command(self.diag_input, parsed_args)
                            
                            except SystemExit:
                                
                                pass
                    
                    else:
                        
                        self.print_help()
    
    def send_efs_handshake(self):
        
        opcode, payload = self.diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BH6I3II',
            DIAG_SUBSYS_FS, # Command subsystem number
            EFS2_DIAG_HELLO, # Command code
            0x100000, # Put all the windows size to high values, let the device negociate these down
            0x100000,
            0x100000,
            0x100000,
            0x100000,
            0x100000,
            1, # We are version 1, we support min version 1 up to max version 1
            1,
            1,
            0xffffffff # Set all the feature bits
        ), accept_error = False)
        
        (cmd_subsystem_id, subcommand_code,
            targ_pkt_window, targ_byte_window,
            host_pkt_window, host_byte_window,
            iter_pkt_window, iter_byte_window,
            version, min_version, max_version,
            feature_bits) = unpack('<BH6I3II', payload)
        
        if version != 1:
            
            error('EFS version unsupported')
            exit()

    """
        Enable using the direction for the command line.
    """
    
    def setup_readline(self):

        try:
            
            from readline import parse_and_bind, set_completer, set_completer_delims
        
        except ImportError:
            
            pass
    
    
    """
        Print the help for the command-line prompt, adapting the original
        output from ArgumentParser.
    """ 
    
    def print_help(self):
        
        help_text = self.parser.format_help()
        print(help_text)
    
    def on_deinit(self):
        
        print('')
            

