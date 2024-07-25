
from argparse import ArgumentParser, _SubParsersAction, Namespace

class BaseEfsShellCommand:

    # Initialization method, add an attribute used to store the file system type
    def __init__(self, fs_type='efs'):
        self.fs_type = fs_type
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        pass
    
    def execute_command(self, diag_input, args : Namespace):
        pass
