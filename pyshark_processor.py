import pyshark
from pyshark.capture.pipe_capture import PipeCapture
import threading

# This is just a testing class for pyshark usage

class PysharkProcessor:
    def __init__(self, pipe_input):
        self.capture = PipeCapture(pipe=pipe_input)
        self.capture_thread = None

    def process_packets(self):
        try:
            for packet in self.capture:
                result = packet.number + " " + packet.highest_layer + ": "
                if 'lte_rrc' in packet:
                    lte_rrc = packet.lte_rrc
                    if lte_rrc.has_field('lte_rrc_rrcconnectionreconfiguration_element') and lte_rrc.has_field('lte_rrc_targetphyscellid'):
                        result += packet.number + ", Handover Reconfiguration"
                    else: 
                        result += packet.number + ", Other RRC Record"
                print(result)
        except Exception as e:
            # This might catch errors when the pipe closes, which can be normal.
            print(f"Pyshark: Capture loop stopped or an error occurred: {e.with_traceback(tb=None)}")

    def start(self):
        if (self.capture_thread is not None and self.capture_thread.is_alive()):
            print("Pyshark: Capture thread is already running.")
            return
        
        self.capture_thread = threading.Thread(target=self.process_packets)
        self.capture_thread.start()
        print("Pyshark: Capture thread started.")

    def stop(self):
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture.close()
            self.capture_thread.join()

class WritePipeAdapter:
    def __init__(self, pipe):
        self.pipe = pipe
        self.appending_to_file = False

    def write(self, data):
        self.pipe.write(data)
        self.pipe.flush()

    def flush(self):
        pass

    def close(self):
        self.pipe.close()