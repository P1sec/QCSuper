from src.trackers.tracker import Tracker
from src.atutil.celltracker import CellTracker

# Implicit handovers, i.e. when requesting connection from RRC idle mode to a new cell with a valid TMSI
class ImplicitHandoverServiceRequestTracker(Tracker):

    def __init__(self, enb_sets, current_set,  window_size, tracker : CellTracker = None, verbose: bool = False):
        super().__init__(enb_sets, current_set, window_size, tracker, verbose)
        self.service_request_started = False
        if tracker is None:
            raise ValueError("ImplicitHandoverServiceRequestTracker requires a CellTracker instance")

    def isStart(self, packet):
        if packet.has_field('lte_rrc_rrcconnectionrequest_element'):
            return True

        return False

    def isGoodHandover(self, packet):
        if packet.has_field('lte_rrc_rrcconnectionsetupcomplete_element') and packet.has_field('lte_rrc_dedicatedinfonas') and packet.lte_rrc_dedicatedinfonas.startswith('c'): #Service Request NAS Security header
            self.updateCellData() # Update cell as soon as we connect to the new cell
            self.service_request_started = True
        elif self.service_request_started and packet.has_field('lte_rrc_securitymodecomplete_element'):
            return True
        return False

    def resetState(self):
        super().resetState()
        self.service_request_started = False

    def getBadHandoverMessage(self):
        return "Bad Haandover: Service Request did not complete successfully"


class ImplicitHandoverTrackingAreaUpdateTracker(Tracker):

    def __init__(self, enb_sets, current_set,  window_size, tracker : CellTracker = None, verbose: bool = False, nas_decrypted=False):
        super().__init__(enb_sets, current_set, window_size, tracker, verbose)
        self.nas_decrypted = nas_decrypted
        if tracker is None:
            raise ValueError("ImplicitHandoverAreaUpdateTracker requires a CellTracker instance")

    def isStart(self, packet):
        if (packet.has_field('lte_rrc_rrcconnectionsetupcomplete_element') or packet.has_field('lte_rrc_ulinformationtransfer_element')) and packet.has_field('nas_eps_nas_msg_emm_type') and packet.nas_eps_nas_msg_emm_type.startswith('0x48'): #Tracking Area Update Request
            return True

        return False

    def isGoodHandover(self, packet):
        if self.nas_decrypted:
            if packet.has_field('nas_msg_emm_type') and packet.nas_msg_emm_type.startswith('0x49'): #Tracking Area Update Accept
                return True
        elif packet.has_field('lte_rrc_dlinformationtransfer_element') and (not packet.has_field('nas_eps_nas_msg_emm_type') or not packet.nas_eps_nas_msg_emm_type.startswith('0x4b')): 
            return True
        return False

    def getBadHandoverMessage(self):
        return "Bad Handover: Tracking Area Update did not complete successfully"