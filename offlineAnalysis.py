#!/usr/bin/env python3
#-*- encoding: Utf-8 -*-

from argparse import RawTextHelpFormatter, ArgumentParser
from src.modules.enb_tracker import OfflineAnalyzer

def main():
    parser = ArgumentParser(
        description="Offline analysis of LTE cell traces given a PCAP file and a cellID <-> packet number mapping file.",
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument('--pcap_file', metavar='PCAP_FILE', help='Path to the input PCAP file containing LTE traffic.', required=True)
    parser.add_argument('--cell_map_file', metavar='CELL_MAP_FILE', help='Path to the cell map file containing packet number to cell ID mappings.', required=True)

    args = parser.parse_args()

    analyzer = OfflineAnalyzer(args.pcap_file, args.cell_map_file)
    analyzer.process_packets()

main()