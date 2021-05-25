#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from socket import socket, AF_INET, SOCK_STREAM
from logging import debug

try:
    from os import setpgrp
except ImportError:
    setpgrp = None

from inputs._hdlc_mixin import HdlcMixin
from inputs._base_input import BaseInput

QCSUPER_TCP_PORT = 43555


class TcpConnector(HdlcMixin, BaseInput):

    def __init__(self, addr):

        self.addr = addr
        self._relaunch_adb_bridge()

        self.packet_buffer = b''

        super().__init__()

    def _relaunch_adb_bridge(self):

        self.socket = socket(AF_INET, SOCK_STREAM)

        try:

            self.socket.connect((self.addr, QCSUPER_TCP_PORT))

        except Exception:

            exit('Could not communicate with the adb_bridge through TCP',self.addr)

        self.received_first_packet = False


    def __del__(self):

        pass

    def send_request(self, packet_type, packet_payload):

        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)

        self.socket.send(raw_payload)


    def read_loop(self):

        while True:

            while self.TRAILER_CHAR not in self.packet_buffer:

                # Read message from the TCP socket

                socket_read = self.socket.recv(1024 * 1024 * 10)

                if not socket_read:

                    print('\nThe connection to the adb bridge was closed, or ' +
                        'preempted by another QCSuper instance')

                    exit()

                self.packet_buffer += socket_read

            while self.TRAILER_CHAR in self.packet_buffer:

                # Parse frame

                raw_payload, self.packet_buffer = self.packet_buffer.split(self.TRAILER_CHAR, 1)

                # Decapsulate and dispatch

                try:

                    unframed_message = self.hdlc_decapsulate(
                        payload = raw_payload + self.TRAILER_CHAR,

                        raise_on_invalid_frame = not self.received_first_packet
                    )

                except self.InvalidFrameError:

                    # The first packet that we receive over the Diag input may
                    # be partial

                    continue

                finally:

                    self.received_first_packet = True

                self.dispatch_received_diag_packet(unframed_message)
