#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from threading import current_thread, main_thread, Thread
from struct import pack, unpack, unpack_from, calcsize
from logging import debug, info, warning, error
from threading import Condition, Lock
from traceback import format_exc
from time import sleep, time
from subprocess import run
from shutil import which
from struct import pack

from ..modules.cli import CommandLineInterface
from ..protocol.messages import *

LOG_CONFIG_DISABLE_OP = 0

MSG_EXT_SUBCMD_SET_ALL_RT_MASKS = 5
MSG_LVL_NONE = 0

"""
    With QCSuper, one or more modules can read/write to a Diag device or
    read from dump files. They do so through exactly one input (USB modem,
    phone...).
    
    An input is materialized through a class. All inputs will inherit from
    this base class.
"""

class BaseInput:
    
    def __init__(self):
        
        self.modules = [] # Instances for running modules
        
        self.modules_already_initialized = False # Whether these instances have been initialized yet
        
        """
            Inter-thread context used for dispatching responses, when the
            self.send_recv() response is called
        """
        
        self.event_diag_response_received = Condition()
        
        self.raw_diag_response = None
        
        self.DIAG_TIMEOUT = 5
        self.DIAG_MAX_RETRANSMITS = 3
        
        """
            Shutdown event sent from background threads to the main thread.
            
            Sent at most twice, when the shutdown is initially request and when
            the deinitialization is done.
        """
        
        self.shutdown_event = Condition()
        
        self.program_is_terminating = False
        
        self.read_thread_did_shutdown = False
        
        """
            Locks to ensure that an input is written to once at a time, and
            that a given module is deinitialized once at a time
        """
        
        self.input_send_lock = Lock()
        
        self.deinitialization_lock = Lock()
    
    """
        add_module: Add a module to self.modules.
    """
    
    def add_module(self, module):
        
        self.modules.append(module)
        
        # Call the "on_init" callback if the initial step where we initialize
        # all modules was already taken (because we're adding a module through
        # the interactive prompt)
        
        if self.modules_already_initialized:
                
            self._init_single_module(module)
        
    """
        Processing loop.
        
        QCSuper uses a concurrency model where only the main threads performs
        reads on the input source, triggering callbacks in the modules.
        
        * The "on_init" callback from modules is called from a background thread
          once and may block (waiting to obtain responses to requests from the
          main thread, using the "send_recv" method which uses a thread
          synchronization primitive to enable notification).
        
        * The "on_message" and "on_log" callbacks from modules are called from
          the main thread when receiving Diag frames and may not block.
        
        * The "on_deinit" callback from modules is called from the main or
          background thread once and may not block.
    """
    
    def run(self):

        with self.shutdown_event:

            try:
                
                if self.modules:
                    
                        # Initalize modules sequentially in the initialization
                        # thread, triggering the "on_init" callback from modules
                        
                        Thread(target = self._init_modules, daemon = True).start()
                        
                        # Perform all reads in the read thread, propagating to the "on_log"
                        # and "on_message" callbacks from modules
                        
                        Thread(target = self._read_thread, daemon = True).start()
                        
                        self.shutdown_event.wait()

            except KeyboardInterrupt:

                # The main thread stops when the use hits Ctrl+C, or there is no more
                # active module and the last call to diag_input.remove_module()
                # triggers a SIGABRT to the main thread
                
                pass
            
            except Exception:
                
                error(format_exc())

            finally:
                
                self.program_is_terminating = True
                
                with self.deinitialization_lock:
                    
                    modules_remain = len(self.modules) > 0
                
                if not self.read_thread_did_shutdown and modules_remain:
                    
                    Thread(target = self._deinit_modules, daemon = True).start()

                    self.shutdown_event.wait()

                # When the daemon thread holding a terminal CLI is present, an abrupt
                # shutdown may break the state of the terminal (suppress echo). Avoid
                # this by restoring the TTY's state.
                
                if which('stty'):
                    run(['stty', 'sane'])
                
                # Apply any further actions to clean up the Input class's
            
                self.__del__()
    
    def _read_thread(self):
        
        try:
            
            self.read_loop()
        
        except Exception:
            
            error(format_exc())
        
        finally:
            
            with self.shutdown_event:
                
                self.read_thread_did_shutdown = True
                
                self.shutdown_event.notify()
            
    """
        _init_modules: if the current input is a Diag device to which we can
        send messages, send Diag commands to disable preexisting logging,
        then call the "on_init" method for each module.
        
        Must be called in another thread than the main thread (which is reserved
        for reading on the Diag device).
    """
    
    def _init_modules(self):
        
        self.modules_already_initialized = True
        
        try:
            
            if hasattr(self, 'send_request'):
                
                self.send_recv(DIAG_LOG_CONFIG_F, pack('<3xI', LOG_CONFIG_DISABLE_OP), accept_error = True)
                
                self.send_recv(DIAG_EXT_MSG_CONFIG_F, pack('<BxxI', MSG_EXT_SUBCMD_SET_ALL_RT_MASKS, MSG_LVL_NONE), accept_error = True)
            
                for module in self.modules:
                    
                    self._init_single_module(module)
        
        except Exception:
            
            error(format_exc())
            
            with self.shutdown_event:
            
                self.shutdown_event.notify()
    
    def _init_single_module(self, module):

        # Don't call "on_init" if the current input isn't a Diag device we
        # can send messages to
        
        if not hasattr(self, 'send_request'):
            
            return
        
        if hasattr(module, 'on_init'):
            
            try:
                
                # Initialize the module by calling the "on_init" callback.
                
                module.on_init()
                    
            except Exception:
                
                error(format_exc())
                self.remove_module(module)
            
            finally:
                
                # Once "on_init" has been done running, deregister the module if it
                # does not have asynchronous callbacks.
                
                if not hasattr(module, 'on_log') and not hasattr(module, 'on_message'):
                    
                    self.remove_module(module)
    
    """
        This function will send a message on the diag socket, and wait for
        the main thread to wake it up when the corresponding response is
        received, for returning it.
        
        :param req_opcode: first byte of the unframed Diag message to send (int).
        :param req_payload: subsequent bytes (bytes).
        :param accept_error: Whether an error response is acceptable
        
        :returns An (resp_opcode, resp_payload) tuple of the response.
    """
    
    def send_recv(self, req_opcode, req_payload, accept_error = False):
        
        with self.input_send_lock:
            
            with self.event_diag_response_received:
                
                for nb_tries in range(self.DIAG_MAX_RETRANSMITS + 1):
                    
                    self.send_request(req_opcode, req_payload) # Dispatched to the underlying input
                    
                    OPCODE_ERRORS = [
                        DIAG_BAD_CMD_F, DIAG_BAD_PARM_F, DIAG_BAD_LEN_F,
                        DIAG_BAD_MODE_F, DIAG_BAD_SPC_MODE_F, DIAG_BAD_SEC_MODE_F,
                        DIAG_BAD_TRANS_F
                    ]
                    
                    response_received = self.event_diag_response_received.wait(self.DIAG_TIMEOUT)
                    
                    if response_received:
                        
                        break
                
                if not response_received:
                    
                    error('Error: Diag request %s with payload %s timed out' % (
                        message_id_to_name.get(req_opcode, req_opcode),
                        repr(req_payload)
                    ))
                    
                    with self.shutdown_event:
                    
                        self.shutdown_event.notify()
                    
                    exit()
                
                resp_opcode, resp_payload = self.raw_diag_response[0], self.raw_diag_response[1:]
                
                if resp_opcode not in [req_opcode, *OPCODE_ERRORS]:
                    
                    error(('Error: unmatched response received: %s with payload %s, while ' +
                        'the request was %s with payload %s. This is possibly due to ' +
                        'another client talking to the Diag device (which is forbidden).') % (
                        message_id_to_name.get(resp_opcode, resp_opcode),
                        repr(resp_payload),
                        message_id_to_name.get(req_opcode, req_opcode),
                        repr(req_payload)
                    ))
                    
                    with self.shutdown_event:
                    
                        self.shutdown_event.notify()
                    
                    exit()
                
                if resp_opcode in OPCODE_ERRORS and not accept_error:
                    
                    error(('Error: error response received: %s with payload %s, while ' +
                        'the request was %s with payload %s. Maybe this operation is ' +
                        'not supported by your device.') % (
                        message_id_to_name.get(resp_opcode, resp_opcode),
                        repr(resp_payload),
                        message_id_to_name.get(req_opcode, req_opcode),
                        repr(req_payload)
                    ))
                    
                    with self.shutdown_event:
                    
                        self.shutdown_event.notify()
                    
                    exit()
                
                return resp_opcode, resp_payload
    
    """
        This function will call the "on_message" and "on_log" function for
        each of the current modules, when a response, message or log is
        received
    """
    
    def dispatch_received_diag_packet(self, unframed_diag_packet):
        
        opcode, payload = unframed_diag_packet[0], unframed_diag_packet[1:]
        
        if opcode == DIAG_LOG_F: # This is a raw "log" structure
            
            # It is made of an outer header and an inner header. When logs are
            # saved using the DLF format, generated by QXDM, only the inner
            # header is saved.
            
            (pending_msgs, log_outer_length), inner_log_packet = unpack_from('<BH', payload), payload[calcsize('<BH'):]

            (log_inner_length, log_type, log_time), log_payload = unpack_from('<HHQ', inner_log_packet), inner_log_packet[calcsize('<HHQ'):]
            
            # Call the function that will dispatch the log packet, along with
            # metadata (log type, original inner header, timestamp)
            
            # For the timestamp, we're passing the current timestamp of the
            # host machine, as we're here because we received the packet live,
            # and we can't always reliably decode the timestamp contained in
            # the log header which may use a handful of different formats.
            
            self.dispatch_diag_log(
                log_type, # 16-bit log code
                log_payload, # Inner log payload
                inner_log_packet[:calcsize('<HHQ')], # Inner log header
                time() # Timestamp
            )
        
        elif opcode == DIAG_MULTI_RADIO_CMD_F:
            
            # See https://github.com/fgsect/scat/blob/f1538b3/parsers/qualcomm/qualcommparser.py#L331
            
            self.dispatch_received_diag_packet(payload[7:])
        
        elif opcode in (DIAG_MSG_F, DIAG_EXT_MSG_F, DIAG_EXT_MSG_TERSE_F, DIAG_QSR_EXT_MSG_TERSE_F, DIAG_QSR4_EXT_MSG_TERSE_F): # This is a "message" string
            
            self.dispatch_diag_message(opcode, payload)
        
        else: # This is a "response"
            
            self.dispatch_diag_response(unframed_diag_packet)
            
    
    def dispatch_diag_response(self, unframed_diag_packet):
        
        opcode, payload = unframed_diag_packet[0], unframed_diag_packet[1:]
        
        debug('[<] Received response %s of length %d: %s' % (message_id_to_name.get(opcode, opcode), len(payload), repr(payload)))

        with self.event_diag_response_received:
            
            self.raw_diag_response = unframed_diag_packet

            self.event_diag_response_received.notifyAll()
            
    
    def dispatch_diag_log(self, log_type, log_payload, log_header, timestamp):
        
        debug('[<] Received log 0x%04x of length %d: %s' % (log_type, len(log_payload), repr(log_payload)))
        
        for module in self.modules:
            if hasattr(module, 'on_log'):
                
                module.on_log(log_type, log_payload, log_header, timestamp)
            
    
    def dispatch_diag_message(self, opcode, payload):
        
        debug('[<] Received message with opcode %s of length %d: %s' % (message_id_to_name.get(opcode, opcode), len(payload), repr(payload)))
        
        for module in self.modules:
            if hasattr(module, 'on_message'):
                
                module.on_message(opcode, payload)

    
    """
        remove_module: Remove a module from self.modules. If the current input
        allows to send diag messages to a device, call "on_deinit" for this
        module. In all cases, call "__del__" for this module.
    """
    
    def remove_module(self, module):
        
        try:
            
            with self.deinitialization_lock:
            
                if module in self.modules:
                
                    self.modules.remove(module)
                    
                    try:

                        if hasattr(module, 'on_deinit') and hasattr(self, 'send_request'):
                            
                            module.on_deinit()
                    
                    except Exception:

                        error(format_exc())
                    
                    finally:
                        
                        if hasattr(module, '__del__'):
                            
                            module.__del__()
        
        finally:
            
            # When all modules have been removed and deinitialized successfully,
            # interrupt the main thread.
            
            if not self.modules:
                
                with self.shutdown_event:
                    
                    self.shutdown_event.notify()

    """
        _deinit_modules: call remove_module() for all modules.
    """
    
    def _deinit_modules(self):
        
        for module in list(self.modules):
            
            self.remove_module(module)
    

    def dispose(self, disposing=True):
        """
            Release unmanaged ressources
        """
        pass 

    def __del__(self):
        self.dispose(disposing=False)

from ..protocol import messages

message_id_to_name = {
    value: key
    for key, value in messages.__dict__.items()
    if key.startswith('DIAG_')
}
