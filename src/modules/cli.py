#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from os.path import isdir, expanduser
from traceback import print_exc
from sys import argv, stdout
from subprocess import run
from shutil import which
from shlex import split
from glob import glob
from re import sub

"""
    This module allows the user to use a command prompt, to which it will be
    able to send arguments that directly map to the standard arguments of the
    program. For example, "./qcsuper.py --pcap-dump test.pcap" will map to the
    command "pcap-dump test.pcap".
    
    Due to the blocking behavior of this task, it is run in a separate thread.
"""

class CommandLineInterface:
    
    """
        :param diag_input: The object for the input mode chosen by the user.
        :param parser: The original ArgumentParser for the program.
        :param parse_modules_args: A callback receiving parsed again arguments,
            where the original argv has been concatenated with the module the
            user has just queried through the CLI.
    """
    
    def __init__(self, diag_input, parser, parse_modules_args):
        
        self.diag_input = diag_input
        self.parser = parser
        self.parse_modules_args = parse_modules_args
        
        self.parser.print_help = self.print_help
    
    """
        Process commands coming from stdout.
    """
        
    def on_init(self):
        
        print()
        print('Welcome to the QCSuper CLI. Type "help" for a list of available commands.')
        print()
        
        command_to_module = {} # {"raw user-issued command": Module()}
        
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
            
            if line.strip().startswith('stop '):
                
                # Stop a running command
                
                command = line.replace('stop', '', 1).strip()
                
                if command_to_module.get(command, None) in self.diag_input.modules:
                    
                    self.diag_input.remove_module(command_to_module[command])
                    
                    print('Command stopped')
                
                else:
                    
                    print('Command "%s" does not appear to be running' % command)
            
            elif line:
                
                # Launch a new command
                
                try:
                    parsed_again_args = self.parser.parse_args(argv[1:] + split('--' + line.strip('- \t')))
                    
                    old_number_of_modules = len(self.diag_input.modules)
                    
                    self.parse_modules_args(parsed_again_args)
                    
                    if len(self.diag_input.modules) == old_number_of_modules + 1:
                        
                        command_to_module[line.strip()] = self.diag_input.modules[-1]
                        
                        print('Command started in the background, you can stop it using "stop %s"' % line.strip())
                
                except SystemExit:
                    pass
                
                except Exception:
                    print_exc()

    """
        Enable using the direction keys and autocompletion for the command line.
    """
    
    def setup_readline(self):

        try:
            
            from readline import parse_and_bind, set_completer, set_completer_delims
        
        except ImportError:
            
            pass
        
        else: 
            
            def complete_command_or_path(text, nb_tries):
                
                try:
                    
                    # Match commands
                    
                    matches = []
                    
                    for command_prefix in ['-', '']:
                        
                        matches += [
                            arg.strip(command_prefix) + ' ' for arg in self.parser._option_string_actions
                            
                            if arg.strip(command_prefix).startswith(text.strip(command_prefix))
                        ]
                        
                    # Match directories and files
                    
                    matches += [
                        path + '/' if isdir(path) else path + ' '
                        for path in glob(expanduser(text + '*'))
                    ]
                    
                    return matches[nb_tries] if nb_tries < len(matches) else None
                
                except Exception:
                    
                    print_exc()
            
            set_completer(complete_command_or_path)
            
            set_completer_delims(' \t\n')
            
            parse_and_bind('tab: complete')
    
    
    """
        Print the help for the command-line prompt, adapting the original
        output from ArgumentParser.
    """
    
    def print_help(self):
        
        help_text = self.parser.format_help()
        
        _, help_modules_prefix, help_modules = help_text.partition('Modules:')
        
        help_modules, help_options_prefix, help_options = help_modules.partition('options:')
        
        print(
            '\nCommand format: module_name [ARGUMENT] [--option [ARGUMENT]]\n\n' +
            help_modules_prefix + sub(r'--', '', help_modules) +
            help_options_prefix + sub(r'--([\w-]+-dump)', r'"\1"', help_options)
        )
    
    def on_deinit(self):
        
        print('')

