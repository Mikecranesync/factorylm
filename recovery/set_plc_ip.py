"""
Set Micro 820 PLC IP address via EtherNet/IP CIP Set_Attribute_Single.

Target: TCP/IP Interface Object (class 0xF5, instance 1, attribute 5 = IP config)

This uses the CIP protocol over EtherNet/IP to change the PLC's network settings
without needing CCW or a ConfigMeFirst SD card.

Usage:
    python recovery/set_plc_ip.py [--current 169.254.47.96] [--new-ip 192.168.1.100]
"""

import socket
import struct
import argparse
import sys
import time


def build_register_session():
    """EtherNet/IP Register Session request."""
    command = 0x0065  # Register Session
    length = 4
    session_handle = 0
    status = 0
    sender_context = b'\x00' * 8
    options = 0

    header = struct.pack('<HHI I 8s I',
                         command, length, session_handle,
                         status, sender_context, options)
    # Protocol version 1, options flags 0
    data = struct.pack('<HH', 1, 0)
    return header + data


def build_get_attribute_single(session_handle, class_id, instance, attribute):
    """Build a CIP Get_Attribute_Single wrapped in SendRRData."""
    # CIP service: Get_Attribute_Single = 0x0E
    # Path: class (class_id), instance (instance), attribute (attribute)
    cip_path = b''
    # 8-bit class segment
    cip_path += struct.pack('BB', 0x20, class_id & 0xFF)
    # 8-bit instance segment
    cip_path += struct.pack('BB', 0x24, instance & 0xFF)
    # 8-bit attribute segment
    # For Get_Attribute_Single, attribute is in the service path

    cip_service = struct.pack('BB', 0x0E, len(cip_path) // 2) + cip_path

    # Unconnected Send item
    # Item 0: Null address (type 0x0000, length 0)
    # Item 1: Unconnected data (type 0x00B2, length = len(cip_service))
    items = struct.pack('<HH', 0x0000, 0)  # Null address item
    items += struct.pack('<HH', 0x00B2, len(cip_service))  # Data item
    items += cip_service

    # SendRRData header
    cpf_data = struct.pack('<IHH', 0, 2, 0)  # Interface handle, timeout, item count... wait
    # Actually: Interface handle (4 bytes) + timeout (2 bytes) + item count (2 bytes)
    send_rr_data = struct.pack('<IH', 0, 0)  # interface handle=0, timeout=0
    send_rr_data += struct.pack('<H', 2)  # 2 items
    send_rr_data += items

    # Encapsulation header
    command = 0x006F  # SendRRData
    length = len(send_rr_data)
    status = 0
    sender_context = b'GETATTR\x00'
    options = 0

    header = struct.pack('<HHI I 8s I',
                         command, length, session_handle,
                         status, sender_context, options)
    return header + send_rr_data


def build_set_attribute_single_ip(session_handle, ip, subnet, gateway):
    """
    Build CIP Set_Attribute_Single to set the TCP/IP Interface Object configuration.

    Class 0xF5 (TCP/IP Interface), Instance 1
    Attribute 5: Interface Configuration

    The interface configuration structure:
      - IP Address (4 bytes)
      - Subnet Mask (4 bytes)
      - Gateway (4 bytes)
      - DNS1 (4 bytes)
      - DNS2 (4 bytes)
    """
    # CIP path: Class 0xF5, Instance 1
    cip_path = b''
    cip_path += struct.pack('BB', 0x20, 0xF5)  # 8-bit class: TCP/IP Interface Object
    cip_path += struct.pack('BB', 0x24, 0x01)  # 8-bit instance: 1

    # Attribute data for Set_Attribute_Single on attribute 5
    # First, we need to set attribute 3 (Configuration Capability) or attribute 5 (Interface Config)
    # Actually, for Micro800 series, we should set attribute 5 via a different approach

    # IP config data
    ip_data = socket.inet_aton(ip)
    subnet_data = socket.inet_aton(subnet)
    gateway_data = socket.inet_aton(gateway)
    dns1 = socket.inet_aton('0.0.0.0')
    dns2 = socket.inet_aton('0.0.0.0')

    # Full interface config structure for attribute 5
    config_data = ip_data + subnet_data + gateway_data + dns1 + dns2

    # CIP Set_Attribute_Single service (0x10)
    # Path includes the attribute
    full_path = cip_path + struct.pack('BB', 0x30, 0x05)  # attribute 5

    cip_service = struct.pack('BB', 0x10, len(full_path) // 2)  # service, path size in words
    cip_service += full_path
    cip_service += config_data

    # Wrap in SendRRData
    items = struct.pack('<HH', 0x0000, 0)  # Null address item
    items += struct.pack('<HH', 0x00B2, len(cip_service))  # Data item
    items += cip_service

    send_rr_data = struct.pack('<IH', 0, 0)  # interface handle=0, timeout=0
    send_rr_data += struct.pack('<H', 2)  # 2 items
    send_rr_data += items

    command = 0x006F  # SendRRData
    length = len(send_rr_data)
    sender_context = b'SETIP\x00\x00\x00'

    header = struct.pack('<HHI I 8s I',
                         command, length, session_handle,
                         0, sender_context, 0)
    return header + send_rr_data


def parse_encap_header(data):
    """Parse EtherNet/IP encapsulation header."""
    if len(data) < 24:
        return None
    command, length, session, status = struct.unpack_from('<HHII', data, 0)
    return {
        'command': command,
        'length': length,
        'session': session,
        'status': status,
        'data': data[24:24+length] if len(data) >= 24 + length else data[24:],
    }


def main():
    parser = argparse.ArgumentParser(description="Set Micro 820 PLC IP via CIP")
    parser.add_argument('--current', default='169.254.47.96', help='Current PLC IP')
    parser.add_argument('--new-ip', default='192.168.1.100', help='New IP to assign')
    parser.add_argument('--subnet', default='255.255.255.0', help='Subnet mask')
    parser.add_argument('--gateway', default='192.168.1.1', help='Gateway')
    parser.add_argument('--read-only', action='store_true', help='Only read current config, do not set')
    args = parser.parse_args()

    print(f"Connecting to PLC at {args.current}:44818...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        sock.connect((args.current, 44818))
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"ERROR: Cannot connect to {args.current}:44818 — {e}")
        sys.exit(1)

    print("Connected! Registering session...")

    # Step 1: Register Session
    sock.sendall(build_register_session())
    resp = sock.recv(4096)
    hdr = parse_encap_header(resp)

    if hdr is None or hdr['status'] != 0:
        print(f"ERROR: Register Session failed (status={hdr['status'] if hdr else 'no response'})")
        sys.exit(1)

    session_handle = hdr['session']
    print(f"Session registered: handle=0x{session_handle:08X}")

    # Step 2: Read current TCP/IP config (Get_Attribute_Single, class 0xF5, inst 1)
    print("\nReading current TCP/IP configuration...")
    req = build_get_attribute_single(session_handle, 0xF5, 1, 5)
    sock.sendall(req)
    resp = sock.recv(4096)
    hdr = parse_encap_header(resp)

    if hdr:
        print(f"  Response status: {hdr['status']}")
        if hdr['data']:
            print(f"  Data ({len(hdr['data'])} bytes): {hdr['data'].hex()}")
            # Try to extract CIP response from the data
            if len(hdr['data']) > 6:
                # Skip SendRRData wrapper: interface_handle(4) + timeout(2) + item_count(2) + items...
                inner = hdr['data']
                if len(inner) >= 8:
                    iface_handle, timeout, item_count = struct.unpack_from('<IHH', inner, 0)
                    offset = 8
                    for i in range(item_count):
                        if offset + 4 > len(inner):
                            break
                        item_type, item_len = struct.unpack_from('<HH', inner, offset)
                        offset += 4
                        item_data = inner[offset:offset+item_len]
                        if item_type == 0x00B2 and len(item_data) >= 4:
                            # CIP response
                            cip_service = item_data[0]
                            cip_status = item_data[2]
                            cip_ext_status_size = item_data[3]
                            print(f"  CIP Service: 0x{cip_service:02X}")
                            print(f"  CIP Status: 0x{cip_status:02X} ({'OK' if cip_status == 0 else 'ERROR'})")
                            if cip_status == 0 and len(item_data) > 4:
                                payload = item_data[4:]
                                print(f"  Payload ({len(payload)} bytes): {payload.hex()}")
                                # Try to parse as IP config
                                if len(payload) >= 12:
                                    ip = socket.inet_ntoa(payload[0:4])
                                    sn = socket.inet_ntoa(payload[4:8])
                                    gw = socket.inet_ntoa(payload[8:12])
                                    print(f"  Current IP:      {ip}")
                                    print(f"  Current Subnet:  {sn}")
                                    print(f"  Current Gateway: {gw}")
                        offset += item_len

    if args.read_only:
        print("\n(Read-only mode, not changing IP)")
        sock.close()
        return

    # Step 3: Set new IP
    print(f"\nSetting new IP configuration:")
    print(f"  IP:      {args.new_ip}")
    print(f"  Subnet:  {args.subnet}")
    print(f"  Gateway: {args.gateway}")

    req = build_set_attribute_single_ip(session_handle, args.new_ip, args.subnet, args.gateway)
    sock.sendall(req)
    resp = sock.recv(4096)
    hdr = parse_encap_header(resp)

    if hdr:
        print(f"\n  Response status: {hdr['status']}")
        if hdr['data']:
            inner = hdr['data']
            if len(inner) >= 8:
                iface_handle, timeout, item_count = struct.unpack_from('<IHH', inner, 0)
                offset = 8
                for i in range(item_count):
                    if offset + 4 > len(inner):
                        break
                    item_type, item_len = struct.unpack_from('<HH', inner, offset)
                    offset += 4
                    item_data = inner[offset:offset+item_len]
                    if item_type == 0x00B2 and len(item_data) >= 4:
                        cip_service = item_data[0]
                        cip_status = item_data[2]
                        print(f"  CIP Service: 0x{cip_service:02X}")
                        print(f"  CIP Status: 0x{cip_status:02X} ({'OK — IP SET!' if cip_status == 0 else 'ERROR'})")
                        if cip_status != 0:
                            ext_size = item_data[3]
                            if ext_size > 0 and len(item_data) >= 4 + ext_size * 2:
                                ext = struct.unpack_from(f'<{ext_size}H', item_data, 4)
                                print(f"  Extended status: {ext}")
                    offset += item_len

    sock.close()

    # Step 4: Verify
    print(f"\nWaiting 3 seconds for PLC to apply new IP...")
    time.sleep(3)

    print(f"Pinging {args.new_ip}...")
    import subprocess
    result = subprocess.run(['ping', '-n', '3', args.new_ip], capture_output=True, text=True)
    print(result.stdout)

    if 'Reply from' in result.stdout:
        print(f"SUCCESS! PLC is now at {args.new_ip}")
        print(f"Next: python scripts/test_connection.py --host {args.new_ip}")
    else:
        print(f"PLC not responding at {args.new_ip} yet.")
        print("The PLC may need a power cycle to apply the new IP.")
        print("Or try ConfigMeFirst.txt on a 32GB SD card.")


if __name__ == '__main__':
    main()
