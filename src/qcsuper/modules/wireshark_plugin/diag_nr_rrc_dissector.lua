-- Qualcomm Diag NR RRC OTA log dissector (QCSuper companion script)
-- Supports packet version >= 17 (0x11) with corrected 31-byte header, verified
-- against a 340-packet S22-class capture (msg_length matched payload on 340/340).
--
-- v17 header (31 bytes):
--   0     u8   packet version
--   1-3   u24  unknown
--   4     u8   RRC release number
--   5     u8   RRC version number
--   6     u8   radio bearer ID
--   7-8   u16  physical cell ID
--   9-16  8B   unknown (likely modem timestamp)
--   17-20 u32  NR-ARFCN
--   21    u8   unknown
--   22-23 u16  sysframe*10 + subframe
--   24    u8   PDU type
--   25-28 u32  SIB mask in SI
--   29-30 u16  message length
--   31..  RRC PER-encoded payload (for OTA channels)
--
-- PDU types 0x0f-0x12 are Qualcomm-internal cached containers (per-cell config /
-- NSA blobs), NOT over-the-air RRC. They are labelled but deliberately routed to
-- the "data" dissector, because Wireshark has no nr-rrc.* dissector for them and
-- forcing one would produce fabricated decodes. See the note above the dissector
-- table if you later identify them and want to attach a real dissector.

local CONSTANT_UDP_PORT = 47928

local diag_nr_rrc_protocol = Proto('qcdiag.log.nr_rrc', 'Qualcomm Diag NR RRC log')

local f = {
    packet_version = ProtoField.uint8('qcdiag.log.nr_rrc.packet_version', 'Packet version', base.DEC),
    unknown1 = ProtoField.uint24('qcdiag.log.nr_rrc.unknown1', 'Unknown 1', base.DEC),
    rrc_release_number = ProtoField.uint8('qcdiag.log.nr_rrc.rrc_release_number', 'RRC Release number', base.DEC),
    rrc_version_number = ProtoField.uint8('qcdiag.log.nr_rrc.rrc_version_number', 'RRC Version number', base.DEC),
    radio_bearer_id = ProtoField.uint8('qcdiag.log.nr_rrc.radio_bearer_id', 'Radio bearer ID', base.DEC),
    physical_cell_id = ProtoField.uint16('qcdiag.log.nr_rrc.physical_cell_id', 'Physical cell ID', base.DEC),
    timestamp = ProtoField.bytes('qcdiag.log.nr_rrc.timestamp', 'Unknown (timestamp?)'),
    nrarfcn = ProtoField.uint32('qcdiag.log.nr_rrc.nrarfcn', 'NR-ARFCN', base.DEC),
    unknown3 = ProtoField.uint8('qcdiag.log.nr_rrc.unknown3', 'Unknown 3', base.DEC),
    sfn_subfn = ProtoField.uint16('qcdiag.log.nr_rrc.sfn_subfn', 'SysFrameNum*10+SubFrameNum', base.DEC),
    frequency = ProtoField.uint32('qcdiag.log.nr_rrc.frequency', 'Frequency', base.DEC),
    sysframenum_subframenum = ProtoField.uint32('qcdiag.log.nr_rrc.sysframenum_subframenum', 'SysFrameNum/SubFrameNum', base.HEX),
    pdu_number = ProtoField.uint8('qcdiag.log.nr_rrc.pdu_number', 'PDU Number', base.DEC),
    sib_mask_in_si = ProtoField.uint32('qcdiag.log.nr_rrc.sib_mask_in_si', 'SIB Mask in SI', base.DEC),
    sib_mask_in_si8 = ProtoField.uint8('qcdiag.log.nr_rrc.sib_mask_in_si8', 'SIB Mask in SI', base.DEC),
    unknown2 = ProtoField.uint24('qcdiag.log.nr_rrc.unknown2', 'Unknown 2', base.DEC),
    msg_length = ProtoField.uint16('qcdiag.log.nr_rrc.msg_length', 'Message length', base.DEC),
    unknown_v26 = ProtoField.bytes('qcdiag.log.nr_rrc.unknown_v26', 'Unknown (extra header bytes)'),
}
local proto_fields = {}
for _, v in pairs(f) do proto_fields[#proto_fields + 1] = v end
diag_nr_rrc_protocol.fields = proto_fields

-- Over-the-air logical channels / messages: name + nr-rrc dissector.
local NR_RRC_LOG_TYPES = {
    [0x01] = 'BCCH/BCH',
    [0x02] = 'BCCH/DL-SCH',
    [0x03] = 'DL-CCCH',
    [0x04] = 'DL-DCCH',
    [0x05] = 'PCCH',
    [0x06] = 'UL-CCCH',
    [0x07] = 'UL-CCCH1',
    [0x08] = 'UL-DCCH',
    [0x09] = 'RRC Reconfiguration',
    [0x0a] = 'UL-DCCH',
    [0x18] = 'Radio Bearer Configuration',
    [0x19] = 'Radio Bearer Configuration',
    [0x1a] = 'Radio Bearer Configuration',
    [0x1e] = 'UE Capability (NR)',
    [0x1f] = 'UE Capability (MRDC)',
    -- Internal/cached containers seen on v17 (NOT over-the-air; routed to "data").
    -- Identified empirically: fixed content, logged as a group of four, per-cell
    -- variants tracking the serving carriers. If you ever map one to a real
    -- nr-rrc dissector, add it to NR_RRC_LOG_DISSECTORS below.
    [0x0f] = 'Internal container A (cached, non-OTA)',
    [0x10] = 'Internal container B (cached, non-OTA)',
    [0x11] = 'Internal container C (cached, non-OTA)',
    [0x12] = 'Internal container D (cached, non-OTA)',
}

local NR_RRC_LOG_DISSECTORS = {
    [0x01] = 'nr-rrc.bcch.bch',
    [0x02] = 'nr-rrc.bcch.dl.sch',
    [0x03] = 'nr-rrc.dl.ccch',
    [0x04] = 'nr-rrc.dl.dcch',
    [0x05] = 'nr-rrc.pcch',
    [0x06] = 'nr-rrc.ul.ccch',
    [0x07] = 'nr-rrc.ul.ccch1',
    [0x08] = 'nr-rrc.ul.dcch',
    [0x09] = 'nr-rrc.rrc_reconf_msg',
    [0x0a] = 'nr-rrc.ul.dcch',
    [0x18] = 'nr-rrc.radiobearerconfig',
    [0x19] = 'nr-rrc.radiobearerconfig',
    [0x1a] = 'nr-rrc.radiobearerconfig',
    [0x1e] = 'nr-rrc.ue_nr_cap',
    [0x1f] = 'nr-rrc.ue_mrdc_cap',
    -- 0x0f-0x12 intentionally absent -> handled by the "data" dissector.
}

-- Packet version >= 26 (0x1a) renumbers some PDU types. Only the codes
-- verified against captured RRCSetupRequest / RRCSetupComplete are overridden.
local NR_RRC_LOG_TYPES_V26 = {
    [0x07] = 'UL-CCCH',
    [0x09] = 'UL-DCCH',
}

local NR_RRC_LOG_DISSECTORS_V26 = {
    [0x07] = 'nr-rrc.ul.ccch',
    [0x09] = 'nr-rrc.ul.dcch',
}

-- 3GPP TS 38.104 NR-ARFCN -> frequency (MHz)
local function nrarfcn_to_mhz(a)
    if a < 600000 then
        return a * 0.005
    elseif a < 2016667 then
        return 3000.0 + (a - 600000) * 0.015
    else
        return 24250.08 + (a - 2016667) * 0.06
    end
end

local function safe_get_dissector(name)
    if name == nil then return nil end
    local ok, d = pcall(Dissector.get, name)
    if ok then return d end
    return nil
end

local function pdu_type_name(raw_pdu_type, raw_packet_version)
    if raw_packet_version and raw_packet_version >= 26 and NR_RRC_LOG_TYPES_V26[raw_pdu_type] then
        return NR_RRC_LOG_TYPES_V26[raw_pdu_type]
    end
    return NR_RRC_LOG_TYPES[raw_pdu_type]
end

local function pdu_dissector_name(raw_pdu_type, raw_packet_version)
    if raw_packet_version and raw_packet_version >= 26 and NR_RRC_LOG_DISSECTORS_V26[raw_pdu_type] then
        return NR_RRC_LOG_DISSECTORS_V26[raw_pdu_type]
    end
    return NR_RRC_LOG_DISSECTORS[raw_pdu_type]
end

local function dissect_payload(buffer, packet, tree, payload_offset, raw_pdu_type, raw_msg_length, raw_packet_version)
    if buffer:len() <= payload_offset then return end
    local payload = buffer(payload_offset):tvb()
    local subdissector = nil
    local dissector_name = pdu_dissector_name(raw_pdu_type, raw_packet_version)
    if dissector_name and raw_msg_length > 1 then
        subdissector = safe_get_dissector(dissector_name)
    end
    if subdissector == nil then
        subdissector = safe_get_dissector('data')
    end
    if subdissector then
        subdissector:call(payload, packet, tree)
    end
end

local function set_info(packet, raw_pdu_type, raw_packet_version)
    local type_name = pdu_type_name(raw_pdu_type, raw_packet_version)
    if type_name then
        packet.cols.info = ('NR RRC OTA: %s'):format(type_name)
    else
        packet.cols.info = ('NR RRC OTA: unknown PDU type 0x%02x (version %d)')
            :format(raw_pdu_type, raw_packet_version)
    end
end

-- Layout for packet version >= 17 (31-byte header)
local function dissect_v17(buffer, packet, tree)
    if buffer:len() < 31 then
        packet.cols.info = 'NR RRC OTA: truncated v17 header'
        dissect_payload(buffer, packet, tree, 0, nil, 0)
        return
    end
    local subtree = tree:add(diag_nr_rrc_protocol, buffer(0, 31))
    subtree:add_le(f.packet_version, buffer(0, 1))
    subtree:add_le(f.unknown1, buffer(1, 3))
    subtree:add_le(f.rrc_release_number, buffer(4, 1))
    subtree:add_le(f.rrc_version_number, buffer(5, 1))
    subtree:add_le(f.radio_bearer_id, buffer(6, 1))
    subtree:add_le(f.physical_cell_id, buffer(7, 2))
    subtree:add(f.timestamp, buffer(9, 8))
    local arfcn = buffer(17, 4):le_uint()
    subtree:add_le(f.nrarfcn, buffer(17, 4))
        :append_text((' (%.2f MHz)'):format(nrarfcn_to_mhz(arfcn)))
    subtree:add_le(f.unknown3, buffer(21, 1))
    local sfn = buffer(22, 2):le_uint()
    subtree:add_le(f.sfn_subfn, buffer(22, 2))
        :append_text((' (frame %d, subframe %d)'):format(math.floor(sfn / 10), sfn % 10))
    local raw_packet_version = buffer(0, 1):le_uint()
    local raw_pdu_type = buffer(24, 1):le_uint()
    local pdu_item = subtree:add_le(f.pdu_number, buffer(24, 1))
    local type_name = pdu_type_name(raw_pdu_type, raw_packet_version)
    if type_name then
        pdu_item:append_text((' (%s)'):format(type_name))
    else
        pdu_item:append_text(' (Unknown PDU type)')
    end
    subtree:add_le(f.sib_mask_in_si, buffer(25, 4))
    local raw_msg_length = buffer(29, 2):le_uint()
    subtree:add_le(f.msg_length, buffer(29, 2))
    set_info(packet, raw_pdu_type, raw_packet_version)
    -- Newer versions (e.g. 26 / 0x1a) insert extra bytes between the message
    -- length and the payload (35-byte header), so locate the payload from the
    -- end of the buffer using the message length when it is consistent.
    local payload_offset = 31
    if raw_msg_length > 0 and buffer:len() - raw_msg_length > 31 then
        payload_offset = buffer:len() - raw_msg_length
        subtree:add(f.unknown_v26, buffer(31, payload_offset - 31))
    end
    dissect_payload(buffer, packet, tree, payload_offset, raw_pdu_type, raw_msg_length, raw_packet_version)
end

-- Original layout for packet versions < 17
local function dissect_legacy(buffer, packet, tree)
    if buffer:len() < 24 then
        packet.cols.info = 'NR RRC OTA: truncated header'
        dissect_payload(buffer, packet, tree, 0, nil, 0)
        return
    end
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
    subtree:add_le(f.packet_version, buffer(0, 1))
    subtree:add_le(f.unknown1, buffer(1, 3))
    subtree:add_le(f.rrc_release_number, buffer(4, 1))
    subtree:add_le(f.rrc_version_number, buffer(5, 1))
    subtree:add_le(f.radio_bearer_id, buffer(6, 1))
    subtree:add_le(f.physical_cell_id, buffer(7, 2))
    subtree:add_le(f.frequency, buffer(9, 3 + extra_off))
    subtree:add_le(f.sysframenum_subframenum, buffer(12 + extra_off, 4))
    local raw_pdu_type = buffer(16 + extra_off, 1):le_uint()
    local pdu_item = subtree:add_le(f.pdu_number, buffer(16 + extra_off, 1))
    if NR_RRC_LOG_TYPES[raw_pdu_type] then
        pdu_item:append_text((' (%s)'):format(NR_RRC_LOG_TYPES[raw_pdu_type]))
    else
        pdu_item:append_text(' (Unknown PDU type)')
    end
    subtree:add_le(f.sib_mask_in_si8, buffer(17 + extra_off, 1))
    subtree:add_le(f.unknown2, buffer(18 + extra_off, 3))
    local raw_msg_length = buffer(21 + extra_off, 2):le_uint()
    subtree:add_le(f.msg_length, buffer(21 + extra_off, 2))
    set_info(packet, raw_pdu_type, raw_packet_version)
    dissect_payload(buffer, packet, tree, 23 + extra_off, raw_pdu_type, raw_msg_length)
end

function diag_nr_rrc_protocol.dissector(buffer, packet, tree)
    packet.cols.protocol = 'QC NR-RRC'
    if buffer:len() < 1 then return end
    local raw_packet_version = buffer(0, 1):le_uint()
    if raw_packet_version >= 17 then
        dissect_v17(buffer, packet, tree)
    else
        dissect_legacy(buffer, packet, tree)
    end
end

local udp_port = DissectorTable.get("udp.port")
udp_port:add(CONSTANT_UDP_PORT, diag_nr_rrc_protocol)
