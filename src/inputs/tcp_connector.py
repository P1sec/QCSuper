#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from socket import socket, AF_INET, SOCK_STREAM
from logging import debug, error, info, warning
from ._hdlc_mixin import HdlcMixin
from ._base_input import BaseInput

"""
    This class implements reading Qualcomm DIAG data from a remote TCP service.
"""

class TcpConnector(HdlcMixin, BaseInput):
    
    def __init__(self, args):
        
        address, port = args.split(':')
        self.socket = socket(AF_INET, SOCK_STREAM)

        try:
            self.socket.connect((address, int(port)))

        except Exception:
            error('Could not communicate with the DIAG device through TCP')
            exit()

        self.received_first_packet = False

        self.packet_buffer = b''
        
        super().__init__()
    
    def send_request(self, packet_type, packet_payload):
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)

        self.socket.send(raw_payload)
    
    def read_loop(self):
        while True:

            while self.TRAILER_CHAR not in self.packet_buffer:

                # Read message from the TCP socket

                socket_read = self.socket.recv(1024 * 1024 * 10)

                self.packet_buffer += socket_read

            while self.TRAILER_CHAR in self.packet_buffer:
                # Parse frame

                raw_payload, self.packet_buffer = self.packet_buffer.split(self.TRAILER_CHAR, 1)

                # Decapsulate and dispatch

                try:

                    unframed_message = self.hdlc_decapsulate(
                        payload = raw_payload + self.TRAILER_CHAR
                    )

                except self.InvalidFrameError:

                    # The first packet that we receive over the Diag input may
                    # be partial

                    continue

                finally:

                    self.received_first_packet = True

                self.dispatch_received_diag_packet(unframed_message)
 
    def __del__(self):
        self.socket.close()
    
