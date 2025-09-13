#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from collections import namedtuple
import io
from logging import warning, debug
import re
from struct import Struct, pack # TODO: Clean up?
import sys
import uuid
import zlib

from ..inputs._base_input import message_id_to_name, MSG_EXT_SUBCMD_SET_RT_MASK, MSG_EXT_SUBCMD_SET_ALL_RT_MASKS

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

class TerseMeta(ParseableStruct, namedtuple('TerseMeta', ['line', 'ssid', 'ss_mask', 'hash'])):
    STRUCT = Struct('<HHII')

class Qsr4TerseMeta(ParseableStruct, namedtuple('Qsr4TerseMeta', ['hash', 'magic'])):
    STRUCT = Struct('<IH')


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

    def __init__(self, diag_input, qshrink_fds, msg_filters, enable_style):

        self.diag_input = diag_input

        self.msg_filters = msg_filters
        self.enable_style = enable_style and sys.stdout.isatty()

        self.qdb = QdbFile()
        for fd in qshrink_fds:
            self.qdb.parse(fd)


    def on_init(self):

        if self.msg_filters is None:
            self.diag_input.send_recv(DIAG_EXT_MSG_CONFIG_F, pack('<BxxI', MSG_EXT_SUBCMD_SET_ALL_RT_MASKS, 0xffffffff), accept_error = False)
        else:
            for f in self.msg_filters:
                self.diag_input.send_recv(DIAG_EXT_MSG_CONFIG_F, pack('<BHHxxI', MSG_EXT_SUBCMD_SET_RT_MASK, f[0], f[0], f[1]), accept_error = False)


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
        elif opcode == DIAG_QSR_EXT_MSG_TERSE_F:
            meta, rest = TerseMeta._parse_start(data)
            args, rest = args_at_start(rest, 4, hdr.num_args)

            h = self.qdb.messages.get(meta.hash)
            if h is not None:
                self.log_message(meta.ssid, meta.ss_mask, meta.line, h.file, h.string, args)
            else:
                warning(f'Unmapped terse message (try --qdb): {meta.hash}{self.debug_args(args)}')
        elif opcode == DIAG_QSR4_EXT_MSG_TERSE_F:
            meta, rest = Qsr4TerseMeta._parse_start(data)

            arg_size = (hdr.num_args >> 4) & 0xf
            num_args = (hdr.num_args >> 0) & 0xf
            args, _ = args_at_start(rest, arg_size, num_args)

            h = self.qdb.qsr4_messages.get(meta.hash)
            if h is not None:
                self.log_message(h.ssid, h.ss_mask, h.line, h.file, h.string, args)
            else:
                warning(f'Unmapped terse message (try --qdb): {meta.hash}{self.debug_args(args)}')
        else:
            warning(f'Unhandled message opcode {message_id_to_name.get(opcode, opcode)}')


    def log_message(self, ssid, ss_mask, line, file, string, args):

        try:
            formatted = cprintf(string, args, self.bold).decode('ascii', 'replace')
        except IndexError:
            fallback_string = string.decode('ascii', 'replace')
            formatted = f'{fallback_string} ← {self.bold(self.debug_args(args))}'

        # Replace newlines with a glyph so that each message appears on a single line
        formatted = formatted.replace('\n', '⏎')

        file = file.decode('utf-8', 'replace')
        line_spec = f'{file}:{line}'

        print(f'[{ssid:5}] {line_spec:44} {formatted}')


    def bold(self, text):

        if self.enable_style:
            return f'\x1b[1m{text}\x1b[0m'
        else:
            return text


    @staticmethod
    def debug_args(args):
        values = ', '.join(f'{int.from_bytes(arg, 'little', signed=False):#010x}' for arg in args)
        return f'[{values}]'


class QdbFile:

    HashedMessage = namedtuple('HashedMessage', ['hash', 'file', 'string'])
    Qsr4HashedMessage = namedtuple('Qsr4HashedMessage', ['hash', 'ss_mask', 'ssid', 'line', 'file', 'string'])

    QDB_HEADER_SIZE = 0x40
    TAG_REGEX = re.compile(rb'<(\w+)>(?:\s*(.*?)\s*<[\\/]\1>)?\s*')


    def __init__(self):

        self.messages = {}
        self.qsr4_messages = {}


    def parse(self, file):

        qdb_header = file.read(self.QDB_HEADER_SIZE)
        if len(qdb_header) == self.QDB_HEADER_SIZE and qdb_header.startswith(b'\x7fQDB'):
            # Compressed `.qdb` file
            guid = uuid.UUID(bytes=qdb_header[4:20])
            debug(f'Detected compressed .qdb file with GUID {guid}')

            inner = io.BufferedReader(ZlibReader(file))
            parsed = self.parse_uncompressed(inner)

            # TODO: check GUID match
        else:
            # Not compressed, try to parse directly
            file.seek(0)
            parsed = self.parse_uncompressed(file)

        debug(f'Parsed QDB {parsed}')
        return parsed


    def parse_uncompressed(self, file):

        meta = {}

        cur_tag = None
        expected_close = None
        for line in file:
            line = line.rstrip(b'\n')
            if not line or line.startswith(b'#'):
                continue
            elif cur_tag is not None and line.rstrip() in expected_close:
                cur_tag = None
                expected_close = None
            elif cur_tag is None and (match := self.TAG_REGEX.fullmatch(line)):
                tag, singleline_content = match.groups()
                if singleline_content is not None:
                    # Single-line tags contain file metadata
                    meta[tag] = singleline_content
                else:
                    cur_tag = tag
                    expected_close = [rb'<\%s>' % cur_tag, rb'</%s>' % cur_tag]
            else:
                self.process_line(cur_tag, line)

        if cur_tag is not None:
            raise ValueError('unclosed tag', cur_tag)

        return meta


    def process_line(self, tag, line):

        if tag is None:
            m = self.intify(self.HashedMessage, line.split(b':', 2), ('hash',))
            self.messages[m.hash] = m
        elif tag == b'Content':
            m = self.intify(self.Qsr4HashedMessage, line.split(b':', 5), ('hash', 'ss_mask', 'ssid', 'line'))
            self.qsr4_messages[m.hash] = m


    @staticmethod
    def intify(tuple_type, tuple_values, to_convert):

        mapped = (int(v) if tuple_type._fields[i] in to_convert else v for i, v in enumerate(tuple_values))
        return tuple_type._make(mapped)


PRINTF_FLAG = [b'#', b'0', b'-', b' ', b'+']
PRINTF_LENGTH = [b'hh', b'h', b'll', b'l', b'q', b'L', b'j', b'z', b'Z', b't']
PRINTF_CONV = [b'd', b'i', b'o', b'u', b'x', b'X', b'e', b'E', b'f', b'F', b'g', b'G', b'a', b'A', b'c', b's', b'p', b'%']
def cprintf(fmt, args, arg_styler=lambda x: x):

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
            formatted = arg_styler(f'%{py_flags}{py_width}{py_precision}{py_conv}' % val)

            result.extend(formatted.encode('ascii'))
        elif conv == b'%':
            result.extend(b'%')
        else:
            # The Qualcomm arg list doesn't really support non-integral types,
            # so just print the raw conversion specifier and argument value.
            py_conv = conv.decode('ascii')

            val = int.from_bytes(args.pop(), 'little', signed=False)
            formatted = arg_styler(f'%{py_conv}[{val:#010x}]')

            result.extend(formatted.encode('ascii'))

    if len(args):
        raise IndexError('more arguments than format conversions')

    return result


class ZlibReader(io.RawIOBase):

    def __init__(self, raw):

        self.raw = raw
        self.decompressor = zlib.decompressobj()


    def readable(self):

        return True


    def readinto(self, buf):

        if not len(buf):
            return 0

        compressed = self.decompressor.unconsumed_tail or self.raw.read(io.DEFAULT_BUFFER_SIZE)
        decompressed = self.decompressor.decompress(compressed, len(buf))

        buf[:len(decompressed)] = decompressed
        return len(decompressed)


    def close(self):

        self.decompressor = None
        self.raw.close()
        return super().close()
