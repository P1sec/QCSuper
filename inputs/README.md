# Willing to get introduced to the source code? :)

Just read the [QCSuper architecture.md](../docs/QCSuper%20architecture.md) document to get a quick glimpse about it.

This directory contains "inputs", Python classes providing a source from which we can communicate using the Diag protocol - either a live device (e.g a smartphone or an USB modem), or a dump file.

Inputs are intended to be used by "modules", which are located in the [`modules/`](../modules/) directory.

A simple template for implementing a new input could be:

```python
#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from inputs._base_input import BaseInput

class MyExampleInput(BaseInput):
    
    def __init__(self, command_line_arg):
        
        self.my_device = command_line_arg
        
        pass # Connect to the example device here...
        
        super().__init__()
    
    """
        Function called when a module wants to send a
        diag packet
    """
    
    def send_request(self, packet_type, packet_payload):
    
        pass # Send a diag packet here...
    
    """
        Function called when the modules have started loading
        and we're meant to read data from the diag device
    """
    
    def read_loop(self):
    
        from unframed_packet in self.my_device.read():
        
            # "unframed_message" is a Diag packet without HDLC framing
        
            self.dispatch_received_diag_packet(unframed_packet)
    
    """
        Use this function for any necessary, systematical cleanup.
    """
    
    def __del__(self):
    
        pass
```
