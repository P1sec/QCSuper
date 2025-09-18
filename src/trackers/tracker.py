# Base tracker class
from src.atutil.celltracker import CellTracker


class Tracker:
    def __init__(self, enb_sets : list[set], current_set: int,  window_size: int, tracker : CellTracker = None):
        self.is_open = False
        self.enb_sets = enb_sets
        self.current_set = current_set
        self.MAX_WINDOW_SIZE = window_size
        self.current_window_size = 0
        self.tracker = tracker
        if tracker is None:
            raise ValueError("Tracker requires a CellTracker instance")
        self.enb = None

    def consumePacket(self, packet):
        self.current_window_size += 1
        if self.current_window_size > self.MAX_WINDOW_SIZE:
            self.resetState()
            return
        
        if not self.is_open:
            self.is_open = self.isStart(packet)
            self.current_window_size = 1 if self.is_open else 0
            return
        elif self.isGoodHandover(packet):
            self.updateCellData()
            self.enb_sets[self.current_set].add(self.enb)
            self.resetState()
            self.checkMergeSets(self.enb, self.current_set)
            return
        elif self.isBadHandover(packet):
            self.updateCellData()
            self.checkBadCell(self.enb)

        #TODO: Conceptualize bad handover

    
    def updateCellData(self):
        self.tracker.update_current_cell()
        self.enb = self.tracker.get_current_cell()

    def checkBadCell(self, new_enb_id):
        #Checks if the new cell should be added to a new set of cells or if it already exists within another set
        #Should we even do this? If a cell imitates another cell's identity, we wouldn't add a new cell. GPS data could help here.
        for enb_set in self.enb_sets:
            if (new_enb_id in enb_set):
                return
        self.enb_sets.append({new_enb_id})
        self.current_set = len(self.enb_sets) - 1

    def checkMergeSets(self, new_enb_id, added_set):
        for i, enb_set in enumerate(self.enb_sets):
            if i != added_set and new_enb_id in enb_set:
                #Merge sets
                self.enb_sets[added_set] = self.enb_sets[added_set].union(enb_set)
                del self.enb_sets[i]
                if i < added_set:
                    self.current_set -= 1
                return


    def isStart(self, packet):
        pass

    def isGoodHandover(self, packet):
        # new_enb MUST be set before returning True
        pass

    def isBadHandover(self, packet):
        # Case: Attach Request with IMSI
        if packet.has_field('nas_eps_nas_msg_emm_type') and packet.nas_eps_nas_msg_emm_type.strip() == '0x41' and (packet.has_field('e212_imsi') or packet.has_field('e212_assoc_imsi')):
            return True

        # Case: Identity Request for IMSI
        if packet.has_field('nas_eps_nas_msg_emm_type') and packet.nas_eps_nas_msg_emm_type.strip() == '0x55' and packet.has_field('nas_eps_emm_id_type2') and packet.nas_eps_emm_id_type2.strip() == '1':
            return True
        # new_enb MUST be set before returning True
        return False

    def resetState(self):
        self.is_open = False
        self.current_window_size = 0