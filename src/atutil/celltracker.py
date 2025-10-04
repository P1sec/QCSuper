import sys
from src.atutil.atsock import ATSock

class CellTracker:
    def __init__(self, atsock : ATSock, verbose: bool = False):
        self.atsock = atsock
        self.verbose = verbose

        # Cell is a tuple (cell_id, phys_cell_id, earfcn)
        self.current_cell = None
        self.full_cell_info = None

    def update_current_cell(self):
        if not self.atsock or not self.atsock.ser or not self.atsock.ser.is_open:
            print("Error: ATSock is not connected.")
            return None

        response = self.atsock.send_command('AT+QENG="servingcell"')
        if "ERROR" in response or "+QENG:" not in response:
            print("Error: Failed to get cell information.")
            return None

        # Example response: +QENG: "servingcell", "NOCONN","LTE","FDD",001,01,1A2D002,2,300,1,3,3,1,-59,-9,-32,18,0,-,81
        # In this case 1A2D002 is the cell ID and 2 is the physical cell ID.
        lines = response.splitlines()
        for line in lines:
            if line.startswith("+QENG:"):
                parts = line.split(',')
                if len(parts) >= 9:
                    self.current_cell = (parts[6].strip(), parts[7].strip(), parts[8].strip())
                    self.full_cell_info = line.strip()
                    return self.current_cell

        if self.verbose:
            print("Error: Cell information not found in response.", file=sys.stderr)
        return None
    
    def get_current_cell(self):
        return self.current_cell
    
    def get_full_cell_info(self):
        return self.full_cell_info
    
class OfflineCellTracker(CellTracker):
    def __init__(self, cell_map_file):
        super().__init__(None)
        self.file = cell_map_file

    def update_current_cell(self):
        return self.current_cell

    def increment_cell(self):
        current_line = self.file.readline()
        if current_line:
            self.current_cell = current_line.strip().split(';')[1]

