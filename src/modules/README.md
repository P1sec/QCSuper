# Willing to get introduced to the source code? :)

Just read the [QCSuper architecture.md](../../docs/QCSuper%20architecture.md) document to get a quick glimpse about it.

This directory contains "modules", Python classes dedicaded to performing specific tasks using the Diag protocol.

Modules are included from the entry point, [`qcsuper.py`](../qcsuper.py) and called depending on the command line flags passed by the end user.

A simple template for a module could be:

```python
#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from src.protocol.messages import *

class MyExampleModule:
    
    def __init__(self, diag_input, command_line_arg):
        
        self.diag_input = diag_input
        
        self.command_line_arg = command_line_arg
    
    """
        This function is called when the Diag input source is
        ready for write.
        
        Not called when replaying from a file.
    """
    
    def on_init(self):
    
        opcode, payload = self.diag_input.send_recv(DIAG_VERNO_F, b'some raw payload')
        
        print('Response received:', payload)
    
    """
        This function is optionally called when the Diag input source
        sends binary structures called "logs" containing, e.g, raw mobile
        traffic.
        
        In order to use it, you have to inherit from the "EnableLogMixin"
        class.
    """
    
    def on_log(self, log_type, log_payload, log_header, timestamp):
    
        pass # Not useful here :)
    
    """
        Use these functions for any necessary, systematical cleanup.
        
        on_deinit is not called when replaying from a file while __del__ is.
    """
    
    def on_deinit(self):
    
        pass
    
    def __del__(self):
    
        pass
```
