from src.atutil.celltracker import CellTracker
from src.trackers.tracker import Tracker

# UE-initiated handovers, e.g. due to radio link failure
class RRCReestablishmentTracker(Tracker):

    def __init__(self, enb_sets, current_set,  window_size, tracker : CellTracker = None):
        super().__init__(enb_sets, current_set, window_size, tracker)
        if tracker is None:
            raise ValueError("RRCReestablishmentTracker requires a CellTracker instance")

    def isStart(self, packet):
        if packet.has_field('lte_rrc_rrcconnectionreestablishmentrequest_element') and packet.has_field('lte_rrc_physcellid'):
            #We know that physcellid contains the physical cell ID of the previous cell
            return True

        return False

    def isGoodHandover(self, packet):
        #We can match either on connection reestablishment complete or on 
        if packet.has_field('lte_rrc_rrcconnectionreestablishmentcomplete_element'):
            return True
        return False