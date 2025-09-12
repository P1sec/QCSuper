#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from collections import namedtuple
from logging import warning
from struct import Struct, pack # TODO: Clean up?

from ..inputs._base_input import message_id_to_name, MSG_EXT_SUBCMD_SET_ALL_RT_MASKS

from ..protocol.messages import *

class ParseableStruct:

    @classmethod
    def _parse(cls, data):
        return cls._make(cls.STRUCT.unpack(data))

    @classmethod
    def _parse_start(cls, data):
        parsed = cls._parse(data[:cls.STRUCT.size])
        remainder = data[cls.STRUCT.size:]
        return parsed, remainder


# From https://github.com/osmocom/osmo-qcdiag/blob/5b01f0bedd70f0c0df589eba347a8580d510d737/src/protocol/protocol.h#L26-L33
class MsgHeader(ParseableStruct, namedtuple('MsgHeader', ['ts_type', 'num_args', 'drop_cnt', 'timestamp'])):
    STRUCT = Struct('<BBBQ')

class NormalMeta(ParseableStruct, namedtuple('NormalMeta', ['line', 'ssid', 'ss_mask'])):
    STRUCT = Struct('<HHI')


def args_at_start(data, arg_size, num_args):

    args_size = arg_size * num_args

    if args_size == 0:
        return [], data

    # TODO: Catch too few bytes
    args = [data[i:i+arg_size] for i in range(0, args_size, arg_size)]
    rest = data[args_size:]

    return args, rest


"""
    This module collects, formats, and prints modem debugging logs sourced from
    diag MSG events.
"""

class MessagePrinter:

    def __init__(self, diag_input, qshrink_fds):

        self.diag_input = diag_input


    def on_init(self):

        self.diag_input.send_recv(DIAG_EXT_MSG_CONFIG_F, pack('<BxxI', MSG_EXT_SUBCMD_SET_ALL_RT_MASKS, 0xffffffff), accept_error = False)


    def on_deinit(self):

        self.diag_input.send_recv(DIAG_EXT_MSG_CONFIG_F, pack('<BxxI', MSG_EXT_SUBCMD_SET_ALL_RT_MASKS, 0), accept_error = False)


    """
        Process a single message event, either terse or non-terse.
    """

    def on_message(self, opcode, payload):

        hdr, data = MsgHeader._parse_start(payload)

        if hdr.drop_cnt > 0:
            warning(f"Dropped {hdr.drop_cnt} log message(s); consider adding filters")

        if opcode == DIAG_EXT_MSG_F:
            meta, rest = NormalMeta._parse_start(data)
            args, rest = args_at_start(rest, 4, hdr.num_args)
            string, file, _ = rest.split(b'\x00')

            self.log_message(meta.ssid, meta.ss_mask, meta.line, file, string, args)
        else:
            warning(f'Unhandled message opcode {message_id_to_name.get(opcode, opcode)}')


    def log_message(self, ssid, ss_mask, line, file, string, args):

        try:
            formatted = cprintf(string, args).decode('ascii', 'replace')
        except IndexError:
            fallback_string = string.decode('ascii', 'replace')
            formatted = f'{fallback_string} ← {self.debug_args(args)}'

        # Replace newlines with a glyph so that each message appears on a single line
        formatted = formatted.replace('\n', '⏎')

        file = file.decode('utf-8', 'replace')
        line_spec = f'{file}:{line}'

        print(f'[{ssid:5}] {line_spec:44} {formatted}')


    @staticmethod
    def debug_args(args):
        values = ', '.join(f'{int.from_bytes(arg, 'little', signed=False):#010x}' for arg in args)
        return f'[{values}]'


PRINTF_FLAG = [b'#', b'0', b'-', b' ', b'+']
PRINTF_LENGTH = [b'hh', b'h', b'll', b'l', b'q', b'L', b'j', b'z', b'Z', b't']
PRINTF_CONV = [b'd', b'i', b'o', b'u', b'x', b'X', b'e', b'E', b'f', b'F', b'g', b'G', b'a', b'A', b'c', b's', b'p', b'%']
def cprintf(fmt, args):

    result = bytearray()
    pos = 0

    def take_int():
        nonlocal pos

        val = None
        while pos < len(fmt) and (c := chr(fmt[pos])).isdigit():
            val = ((val or 0) * 10) + int(c)
            pos += 1
        return val

    def take_token(tokens):
        nonlocal pos

        for t in tokens:
            if fmt[pos:pos+len(t)] == t:
                pos += len(t)
                return t
        return None

    def take_repeated_tokens(tokens):
        res = set()
        while (t := take_token(tokens)) is not None:
            res.add(t)
        return res

    # For efficient pop()ing
    args.reverse()

    while pos < len(fmt):
        try:
            conv_start = fmt.index(b'%', pos)
        except ValueError:
            result.extend(fmt[pos:])
            break

        result.extend(fmt[pos:conv_start])
        pos = conv_start + 1

        flags = take_repeated_tokens(PRINTF_FLAG)
        width = take_int()
        if take_token((b'.',)):
            precision = take_token((b'*',)) or take_int()
        else:
            precision = None
        length = take_token(PRINTF_LENGTH)
        conv = take_token(PRINTF_CONV)

        if conv is None:
            # Malformed. Unroll and treat as literal.
            pos = conv_start + 1
            result.extend(b'%')
            continue

        if precision == b'#':
            precision = int.from_bytes(args.pop(), 'little', signed=True)
            if precision < 0:
                precision = None

        # TODO: Trim args based on length?

        signed = False
        if conv == b'p':
            flags.add(b'#')
            conv = b'x'
        elif conv in (b'd', b'i'):
            signed = True
            conv = b'u'

        if conv in (b'u', b'o', b'x', b'X', b'c'):
            py_flags = b''.join(flags).decode('ascii')
            py_width = str(width) if width is not None else ''
            py_precision = f'.{precision}' if precision is not None else ''
            py_conv = conv.decode('ascii')

            val = int.from_bytes(args.pop(), 'little', signed=signed)
            formatted = f'%{py_flags}{py_width}{py_precision}{py_conv}' % val

            result.extend(formatted.encode('ascii'))
        elif conv == b'%':
            result.extend(b'%')
        else:
            # The Qualcomm arg list doesn't really support non-integral types,
            # so just print the raw conversion specifier and argument value.
            py_conv = conv.decode('ascii')

            val = int.from_bytes(args.pop(), 'little', signed=False)
            formatted = f'%{py_conv}[{val:#010x}]'

            result.extend(formatted.encode('ascii'))

    if len(args):
        raise IndexError('more arguments than format conversions')

    return result
