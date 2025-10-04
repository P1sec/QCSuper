import pyshark
from pyshark.capture.pipe_capture import PipeCapture

capture = pyshark.FileCapture('../relevant_logs/bus_ride.pcapng')

for packet in capture:
    result = packet.number + ", "
    if 'lte_rrc' in packet:
        lte_rrc = packet.lte_rrc
        if lte_rrc.has_field('lte_rrc_rrcconnectionreconfiguration_element') and lte_rrc.has_field('lte_rrc_targetphyscellid'):
            print(packet.number + ", Handover Reconfiguration")