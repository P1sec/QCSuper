#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from os.path import exists, getsize, isdir, expanduser
from os import kill, getpid, dup, dup2, fdopen
from sys import argv, stdin, stdout, stderr
from traceback import print_exc
from re import sub, match
from shlex import split
from io import BytesIO
from glob import glob
import gzip

try:
    from signal import CTRL_C_EVENT as SIGINT
except Exception:
    from signal import SIGINT

"""
    This class wraps opening a file for reading or appending, possibly in a
    Gzipped format if the name says so.
    
    It is a substitute for argparse.FileType, which doesn't provide automatic
    Gzipping. It is to be instancied and then passed to the "type =" argument
    of "ArgumentParser.add_argument".
"""

class FileType:
    
    """
        :param mode: "r", "rb", "a", "ab"
    """
    
    def __init__(self, mode):
        
        self.mode = mode
    
    """
        :param path: A path to the disk, the file will be considered GZipped
            if if contains ".gz"
    """
    
    def __call__(self, path):
        
        path = expanduser(path)
        
        if path == '/dev/stdout' and 'a' in self.mode:
            
            self.mode = self.mode.replace('a', 'w')
        
        if path == '-':
            
            if 'r' in self.mode:
                file_obj = stdin.buffer if 'b' in self.mode else stdin
            else:
                file_obj = fdopen(dup(stdout.fileno()), 'wb' if 'b' in self.mode else 'w')
                dup2(stderr.fileno(), stdout.fileno())
            
            file_obj.appending_to_file = False
            
            return file_obj
        
        elif path[-3:] != '.gz':
            
            file_obj = open(path, self.mode)
        
        else:
            
            file_obj = gzip.open(path, {'r': 'rt', 'a': 'at'}.get(self.mode, self.mode))
        
        file_obj.appending_to_file = bool(exists(path) and getsize(path))
        
        return file_obj

"""
    Same as above, but only for reading, and may accept an hex string instead
    of a path
"""

class FileOrHexStringType(FileType):
    
    def __init__(self):
        
        self.mode = 'rb'
    
    def __call__(self, path):
        
        hex_string = sub(r'\s', '', path)
        
        is_valid_hex = len(hex_string) % 2 == 0 and match('[a-fA-F0-9]', hex_string)
        
        if not exists(expanduser(path)) and is_valid_hex:
            
            return BytesIO(bytes.fromhex(hex_string))
        
        else:
            
            return super().__call__(path)

