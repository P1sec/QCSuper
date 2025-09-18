import pyshark
from pyshark.capture.pipe_capture import PipeCapture

capture = pyshark.FileCapture('test.pcap')
capture_pipe = PipeCapture(pipe="/dev/null")

print(capture[0])