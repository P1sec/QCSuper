from pyshark.capture.pipe_capture import PipeCapture
from pyshark.capture.file_capture import FileCapture
from src.atutil.celltracker import CellTracker, OfflineCellTracker
from src.atutil.atsock import ATSock
from src.trackers.implicit_handover_tracker import ImplicitHandoverServiceRequestTracker, ImplicitHandoverTrackingAreaUpdateTracker
from src.trackers.reestablishment_tracker import RRCReestablishmentTracker
from src.trackers.reconfiguration_tracker import RRCReconfigurationTracker

import threading

class ENBTracker:
    
    def __init__(self, pipe_input, packet_cell_map_file):
        self.capture = PipeCapture(pipe=pipe_input)
        self.capture_thread = None
        self.trackers = []
        self.enb_sets = []
        self.packet_cell_map_file = packet_cell_map_file
        if self.packet_cell_map_file is None:
            raise ValueError("ENBTracker requires a valid filename")


    def process_packets(self):
        try:
            with open(self.packet_cell_map_file, 'a') as cellMap, ATSock() as sock:
                cell_tracker = CellTracker(sock)
                self.init_trackers(cell_tracker)
                current_cell = cell_tracker.update_current_cell()
                if current_cell is None:
                    raise RuntimeError("ENBTracker: Could not get initial cell from CellTracker")

                initial_set = {current_cell}
                self.enb_sets.append(initial_set)

                for packet in self.capture:
                    if 'lte_rrc' not in packet:
                        continue

                    rrc_packet = packet.lte_rrc
                    for tracker in self.trackers:
                        tracker.consumePacket(rrc_packet)

                    #TODO: Save to file with same name as pcap file
                    self.append_packet_cell_mapping(packet, cell_tracker.get_current_cell(), cellMap)

                    #Debug
                    for enbset in self.enb_sets:
                        print([cell for cell in enbset])

        except Exception as e:
            print(f"Capture loop stopped or an error occurred: {e.with_traceback(tb=None)}")

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

    def init_trackers(self, cell_tracker):
        self.trackers.append(ImplicitHandoverServiceRequestTracker(self.enb_sets, 0, 20, cell_tracker))
        self.trackers.append(ImplicitHandoverTrackingAreaUpdateTracker(self.enb_sets, 0, 20, cell_tracker))
        self.trackers.append(RRCReestablishmentTracker(self.enb_sets, 0, 10, cell_tracker))
        self.trackers.append(RRCReconfigurationTracker(self.enb_sets, 0, 10, cell_tracker))

    def append_packet_cell_mapping(self, packet, current_cell, cellMap):
        if current_cell is not None:
            cellMap.write(f"{packet.number};{current_cell}\n")

class OfflineAnalyzer(ENBTracker):
    def __init__(self, pcap_file, packet_cell_map_file_name):
        self.capture = FileCapture(pcap_file)
        self.capture_thread = None
        self.trackers = []
        self.enb_sets = []
        self.packet_cell_map_file_name = packet_cell_map_file_name
        if self.packet_cell_map_file_name is None:
            raise ValueError("OfflineAnalyzer requires a valid cell map filename")
        
    def process_packets(self):
        try:
            with open(self.packet_cell_map_file_name, 'r') as cellMap:
                cell_tracker = OfflineCellTracker(cellMap)
                self.init_trackers(cell_tracker)
                cell_tracker.increment_cell()
                current_cell = cell_tracker.get_current_cell()

                initial_set = {current_cell}
                self.enb_sets.append(initial_set)

                for packet in self.capture:
                    if 'lte_rrc' not in packet:
                        continue

                    rrc_packet = packet.lte_rrc
                    for tracker in self.trackers:
                        tracker.consumePacket(rrc_packet)
                    #Debug
                    for enbset in self.enb_sets:
                        print([cell for cell in enbset])
                    print()

                    cell_tracker.increment_cell()

        except Exception as e:
            print(f"Capture loop stopped or an error occurred: {e.with_traceback(tb=None)}")
        


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