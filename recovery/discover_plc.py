"""
EtherNet/IP List Identity broadcast discovery.

Sends CIP List Identity (0x0063) to UDP broadcast on port 44818.
ALL EtherNet/IP devices on the local network respond, regardless of subnet.
This finds the Micro 820 even if it's on a 169.254.x.x APIPA address.

Usage:
    python recovery/discover_plc.py
"""

import socket
import struct
import sys


def build_list_identity():
    """Build an EtherNet/IP List Identity request (24-byte encapsulation header)."""
    command = 0x0063       # List Identity
    length = 0             # No data payload
    session_handle = 0
    status = 0
    sender_context = b'\x00' * 8
    options = 0

    header = struct.pack('<HHI I 8s I',
                         command, length, session_handle,
                         status, sender_context, options)
    return header


def parse_list_identity_response(data, addr):
    """Parse a List Identity response and extract device info."""
    if len(data) < 24:
        return None

    command, length, session, status = struct.unpack_from('<HHII', data, 0)

    if command != 0x0063:
        return None

    info = {
        'ip': addr[0],
        'port': addr[1],
        'raw_length': len(data),
    }

    # Try to parse the identity object (after 24-byte header + 2-byte item count + item header)
    try:
        if len(data) > 48:
            # Skip encapsulation header (24) + item count (2) + item type/length (4)
            offset = 30
            # CIP Identity object
            protocol_version = struct.unpack_from('<H', data, offset)[0]
            offset += 2

            # Socket address (sin_family, sin_port, sin_addr, sin_zero)
            sin_family, sin_port = struct.unpack_from('>HH', data, offset)
            offset += 4
            sin_addr = socket.inet_ntoa(data[offset:offset+4])
            offset += 4 + 8  # skip sin_zero

            info['reported_ip'] = sin_addr
            info['reported_port'] = sin_port

            # Vendor ID, Device Type, Product Code
            vendor_id, device_type, product_code = struct.unpack_from('<HHH', data, offset)
            offset += 6

            # Revision
            major, minor = struct.unpack_from('BB', data, offset)
            offset += 2
            info['revision'] = f'{major}.{minor}'

            # Status, Serial Number
            cip_status, serial = struct.unpack_from('<HI', data, offset)
            offset += 6

            # Product Name (length-prefixed string)
            name_len = data[offset]
            offset += 1
            if offset + name_len <= len(data):
                info['product_name'] = data[offset:offset+name_len].decode('ascii', errors='replace')

            info['vendor_id'] = vendor_id
            info['serial'] = f'{serial:08X}'

    except (struct.error, IndexError):
        pass  # Return what we have

    return info


def main():
    print("=" * 60)
    print("EtherNet/IP Device Discovery (List Identity Broadcast)")
    print("=" * 60)
    print("Sending broadcast to 255.255.255.255:44818...")
    print("Waiting for responses (3 second timeout)...")
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(3)

    packet = build_list_identity()

    try:
        sock.sendto(packet, ('255.255.255.255', 44818))
    except OSError as e:
        print(f"ERROR sending broadcast: {e}")
        print("Make sure you're connected to the Ethernet network.")
        sys.exit(1)

    devices = []

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            info = parse_list_identity_response(data, addr)
            if info:
                devices.append(info)
                print(f"  FOUND: {info['ip']}:{info['port']}")
                if 'product_name' in info:
                    print(f"         Product: {info['product_name']}")
                if 'reported_ip' in info:
                    print(f"         Reported IP: {info['reported_ip']}")
                if 'revision' in info:
                    print(f"         Firmware: {info['revision']}")
                if 'serial' in info:
                    print(f"         Serial: {info['serial']}")
                if 'vendor_id' in info:
                    print(f"         Vendor ID: {info['vendor_id']} {'(Rockwell/AB)' if info['vendor_id'] == 1 else ''}")
                print()
        except socket.timeout:
            break
        except OSError as e:
            print(f"  Error receiving: {e}")
            break

    sock.close()

    print("-" * 60)
    if devices:
        print(f"Found {len(devices)} device(s)!")
        print()
        for d in devices:
            name = d.get('product_name', 'Unknown')
            print(f"  {d['ip']:20s}  {name}")
        print()
        print("Next steps:")
        print("  1. If PLC IP is 169.254.x.x, add a route:")
        print("     netsh interface ip add address \"Ethernet\" 169.254.100.1 255.255.0.0")
        print("  2. Then ping the PLC IP shown above")
        print("  3. Then connect with Modbus: python scripts/test_connection.py --host <IP>")
    else:
        print("No EtherNet/IP devices found!")
        print()
        print("Possible reasons:")
        print("  - PLC is powered off")
        print("  - Ethernet cable not connected")
        print("  - Windows Firewall blocking UDP 44818")
        print()
        print("Try:")
        print("  1. Check cable and PLC power")
        print("  2. Temporarily disable Windows Firewall:")
        print("     netsh advfirewall set allprofiles state off")
        print("  3. Run again")


if __name__ == '__main__':
    main()
