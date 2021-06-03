
from argparse import ArgumentParser, _SubParsersAction, Namespace

class BaseEfsShellCommand:
    
    def get_argument_parser(self, subparsers_object : _SubParsersAction) -> ArgumentParser:
        
        pass
    
    def execute_command(self, diag_input, args : Namespace):
        
        pass
