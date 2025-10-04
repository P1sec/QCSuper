from src.trackers.tracker import Tracker

# Network-forced handovers, e.g. due to measurement reports
class RRCReconfigurationTracker(Tracker):
    def isStart(self, packet):
        if packet.has_field('lte_rrc_rrcconnectionreconfiguration_element') and packet.has_field('lte_rrc_targetphyscellid'):
            return True

        return False

    def isGoodHandover(self, packet):
        if packet.has_field('lte_rrc_rrcconnectionreconfigurationcomplete_element'):
            return True
        return False
    
    def getBadHandoverMessage(self):
        return "Bad Handover: RRC Reconfiguration did not complete successfully"