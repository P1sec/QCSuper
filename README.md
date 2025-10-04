# QCSuper Handover Tracker Extension

This tool is an extension of the cellular packet-capturing tool QCSuper. Like QCSuper it allows to capture raw radio frames from Qualcomm-based phones and modems. For 4G, this extension now allows you to track the coherent sets of cells that the device camped or attempted to connect to during the analysis. This is based on successful and unsuccessful handovers, where a new cell is added to an existing set of cells if there was a successful handover from a cell inside the set to the current one.

## Installation
This extension was tested on Ubuntu 22.04 LTS. 
To set up the tool, both QCSuper and Pyshark are required as prerequisites. 
For the former, follow the [QCSuper installation guide](https://github.com/P1sec/QCSuper?tab=readme-ov-file#ubuntu-and-debian-installation). 
For the latter, install the pyshark package:

```bash
pip install pyshark
```
## Setup
The tool needs locked read/write access to both the Modem's DIAG and AT interface which are likely located at `/dev/ttyUSB0` or `/dev/ttyUSB2`. For this, run:
```bash
sudo chmod 666 /dev/ttyUSB2
sudo chmod 666 /dev/ttyUSB0
```
AT commands can still be written to the interface via echo output redirection (>>) to the interface.

## Usage
The extension is ran with QCSuper. You can use all the same options and a typical run will be started like this:
```bash
./qcsuper.py --usb-modem /dev/ttyUSB0 --pcap-dump <pcap_filename> --handover-tracker --decrypt-nas
```
QCSuper then runs, writing all packets to `<pcap_filename>` and keeping track of the sets of ENBs, printing them on every received packet. Additionally, the extension will also store a file `<pcap_filename>_cell_map.txt` which contains a mapping from packet number to current cell. This can later be used to run **offline Analysis** with `offlineAnalysis.py`.
If possible, include the --decrypt-nas flag so that Tracking Area Updates are detected with full certainty. If this is not done, TA updates are considered finished once a DLInformationTransfer without a "TA Reject" flag is seen.

**Offline Analysis** takes two arguments `--pcap-file` and `--cell-map-file` and prints the sets of ENBs on all received packets.

Both the **Live Analysis** and the **Offline Analysis** can be adapted in `offlineAnalysis.py` and `enb_tracker.py` respectively.