

-- UDP port used for decoding from a QCSuper-issued PCAP
-- capture
local CONSTANT_UDP_PORT = 47928

local diag_nr_rrc_protocol = Proto('qcdiag.log.nr_rrc', 'Qualcomm Diag NR RRC log')

local diag_nr_rrc_fields = {
    ['packet_version'] = ProtoField.uint8('qcdiag.log.nr_rrc.packet_version', 'Packet version', base.DEC),
    ['unknown1'] = ProtoField.uint24('qcdiag.log.nr_rrc.unknown1', 'Unknown 1', base.DEC),
    ['rrc_release_number'] = ProtoField.uint8('qcdiag.log.nr_rrc.rrc_release_number', 'RRC Release number', base.DEC),
    ['rrc_version_number'] = ProtoField.uint8('qcdiag.log.nr_rrc.rrc_version_number', 'RRC Version number', base.DEC),
    ['radio_bearer_id'] = ProtoField.uint8('qcdiag.log.nr_rrc.radio_bearer_id', 'Radio bearer ID', base.DEC),
    ['physical_cell_id'] = ProtoField.uint16('qcdiag.log.nr_rrc.physical_cell_id', 'Physical cell ID', base.DEC),
    ['frequency'] = ProtoField.uint32('qcdiag.log.nr_rrc.frequency', 'Frequency', base.HEX),
    ['sysframenum_subframenum'] = ProtoField.uint32('qcdiag.log.nr_rrc.sysframenum_subframenum', 'SysFrameNum/SubFrameNum', base.HEX),
    ['pdu_number'] = ProtoField.uint8('qcdiag.log.nr_rrc.pdu_number', 'PDU Number', base.DEC),
    ['sib_mask_in_si'] = ProtoField.uint8('qcdiag.log.nr_rrc.sib_mask_in_si', 'SIB Mask in SI', base.DEC),
    ['unknown2'] = ProtoField.uint24('qcdiag.log.nr_rrc.unknown2', 'Unknown 2', base.DEC),
    ['msg_length'] = ProtoField.uint8('qcdiag.log.nr_rrc.msg_length', 'Message length', base.DEC)
}
diag_nr_rrc_protocol.fields = diag_nr_rrc_fields


function diag_nr_rrc_protocol.dissector(buffer, packet, tree)
    
    local subtree = tree:add(diag_nr_rrc_protocol, buffer(0, 24))

    local raw_packet_version = buffer(0, 1):le_uint()
    local tentative_packet_len = buffer(22, 2):le_uint()
    local extra_off
    if raw_packet_version >= 14 or (
            raw_packet_version > 7 and
            buffer:len() ~= 24 + tentative_packet_len) then
        extra_off = 0
    else
        extra_off = 1
    end

    subtree:add_le(diag_nr_rrc_fields.packet_version, buffer(0, 1))
    subtree:add_le(diag_nr_rrc_fields.unknown1, buffer(1, 3))
    subtree:add_le(diag_nr_rrc_fields.rrc_release_number, buffer(4, 1))
    subtree:add_le(diag_nr_rrc_fields.rrc_version_number, buffer(5, 1))
    subtree:add_le(diag_nr_rrc_fields.radio_bearer_id, buffer(6, 1))
    subtree:add_le(diag_nr_rrc_fields.physical_cell_id, buffer(7, 2))
    subtree:add_le(diag_nr_rrc_fields.frequency, buffer(9, 3 + extra_off))
    subtree:add_le(diag_nr_rrc_fields.sysframenum_subframenum, buffer(12 + extra_off, 4))
    local pdu_number_subtree = subtree:add_le(diag_nr_rrc_fields.pdu_number, buffer(16 + extra_off, 1))
    subtree:add_le(diag_nr_rrc_fields.sib_mask_in_si, buffer(17 + extra_off, 1))
    subtree:add_le(diag_nr_rrc_fields.unknown2, buffer(18 + extra_off, 3))
    subtree:add_le(diag_nr_rrc_fields.msg_length, buffer(21 + extra_off, 2))
    
    local raw_pdu_type = buffer(16 + extra_off, 1):le_uint()
    local raw_msg_length = buffer(21 + extra_off, 2):le_uint()
    
    local NR_RRC_LOG_TYPES = {
        [0x01] = 'BCCH/BCH',
        [0x02] = 'BCCH/DL-SCH',
        [0x03] = 'DL-CCCH',
        [0x04] = 'DL-DCCH',
        [0x05] = 'PCCH',
        [0x06] = 'UL-CCCH',
        [0x08] = 'UL-DCCH - a',
        [0x09] = 'RRC Reconfiguration',
        [0x0a] = 'UL-DCCH - b',
        [0x18] = 'Radio Bearer Configuration - a',
        [0x19] = 'Radio Bearer Configuration - b',
        [0x1a] = 'Radio Bearer Configuration - c',
    }
    
    local NR_RRC_LOG_DISSECTORS = {
        [0x01] = 'nr-rrc.bcch.bch',
        [0x02] = 'nr-rrc.bcch.dl.sch',
        [0x03] = 'nr-rrc.dl.ccch',
        [0x04] = 'nr-rrc.dl.dcch',
        [0x05] = 'nr-rrc.pcch',
        [0x06] = 'nr-rrc.ul.ccch',
        [0x08] = 'nr-rrc.ul.dcch',
        [0x09] = 'nr-rrc.rrc_reconf_msg',
        [0x0a] = 'nr-rrc.ul.dcch',
        [0x18] = 'nr-rrc.radiobearerconfig',
        [0x19] = 'nr-rrc.radiobearerconfig',
        [0x1a] = 'nr-rrc.radiobearerconfig',
    }
    
    if NR_RRC_LOG_TYPES[raw_pdu_type] then
        pdu_number_subtree:append_text((' (%s)'):format(NR_RRC_LOG_TYPES[raw_pdu_type]))
    end
    
    if NR_RRC_LOG_TYPES[raw_pdu_type] and raw_msg_length > 1 then
        Dissector.get(NR_RRC_LOG_DISSECTORS[raw_pdu_type]):call(buffer(23 + extra_off):tvb(), packet, tree)
    else
        Dissector.get('data'):call(buffer(23 + extra_off):tvb(), packet, tree)
    end
end


local udp_port = DissectorTable.get("udp.port")
udp_port:add(CONSTANT_UDP_PORT, diag_nr_rrc_protocol)

