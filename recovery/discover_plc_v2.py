"""
Enhanced EtherNet/IP discovery — binds to specific interface and tries
multiple broadcast addresses. Also does a raw UDP probe on port 44818
to the subnet broadcast and 169.254 range.

Run as Administrator for best results.

Usage:
    python recovery/discover_plc_v2.py
"""

import socket
import struct
import sys
import time


def build_list_identity():
    """EtherNet/IP List Identity request (24-byte encapsulation header)."""
    command = 0x0063
    length = 0
    session_handle = 0
    status = 0
    sender_context = b'\x00' * 8
    options = 0
    return struct.pack('<HHI I 8s I',
                       command, length, session_handle,
                       status, sender_context, options)


def parse_response(data, addr):
    """Parse List Identity response, return summary dict or None."""
    if len(data) < 24:
        return None
    command = struct.unpack_from('<H', data, 0)[0]
    if command != 0x0063:
        return None

    info = {'ip': addr[0], 'port': addr[1], 'raw_len': len(data)}

    try:
        if len(data) > 48:
            offset = 34  # past header + item count + item type/len + protocol version
            sin_addr = socket.inet_ntoa(data[offset:offset+4])
            offset += 12  # past full socket address
            vendor_id, device_type, product_code = struct.unpack_from('<HHH', data, offset)
            offset += 6
            major, minor = struct.unpack_from('BB', data, offset)
            offset += 2
            cip_status, serial = struct.unpack_from('<HI', data, offset)
            offset += 6
            name_len = data[offset]
            offset += 1
            name = data[offset:offset+name_len].decode('ascii', errors='replace') if offset+name_len <= len(data) else '?'

            info.update({
                'reported_ip': sin_addr,
                'vendor_id': vendor_id,
                'product': name,
                'revision': f'{major}.{minor}',
                'serial': f'{serial:08X}',
            })
    except (struct.error, IndexError):
        pass

    return info


def discover_on(bind_ip, broadcast_addrs, timeout=3):
    """Send List Identity from bind_ip to each broadcast_addr, collect responses."""
    packet = build_list_identity()
    found = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)

    try:
        sock.bind((bind_ip, 0))
    except OSError as e:
        print(f"  Cannot bind to {bind_ip}: {e}")
        sock.close()
        return found

    for bcast in broadcast_addrs:
        try:
            sock.sendto(packet, (bcast, 44818))
            print(f"  Sent List Identity to {bcast}:44818 (from {bind_ip})")
        except OSError as e:
            print(f"  Failed to send to {bcast}: {e}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        sock.settimeout(remaining)
        try:
            data, addr = sock.recvfrom(4096)
            info = parse_response(data, addr)
            if info:
                found.append(info)
                print(f"  >>> FOUND: {info['ip']} — {info.get('product', '?')} (serial: {info.get('serial', '?')})")
        except socket.timeout:
            break
        except OSError:
            break

    sock.close()
    return found


def tcp_probe(ip, port, timeout=0.3):
    """Quick TCP connect probe. Returns True if port is open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def scan_range_modbus(prefix, start, end, port=502):
    """Scan an IP range for open Modbus port 502."""
    print(f"\nScanning {prefix}.{start}-{end} for Modbus (port {port})...")
    found = []
    for i in range(start, end + 1):
        ip = f"{prefix}.{i}"
        if tcp_probe(ip, port, timeout=0.15):
            found.append(ip)
            print(f"  >>> MODBUS OPEN: {ip}:{port}")
    return found


def main():
    print("=" * 60)
    print("Micro 820 PLC Discovery Tool v2")
    print("=" * 60)
    print(f"Target MAC: 5C:88:16:D8:E4:D7")
    print(f"Expected IP: 192.168.1.100")
    print()

    all_found = []

    # --- Phase 1: EtherNet/IP broadcast from 192.168.1.10 ---
    print("[Phase 1] EtherNet/IP broadcast from 192.168.1.10")
    results = discover_on('192.168.1.10', [
        '192.168.1.255',     # subnet broadcast
        '255.255.255.255',   # global broadcast
    ], timeout=3)
    all_found.extend(results)

    # --- Phase 2: Try 0.0.0.0 binding (all interfaces) ---
    print("\n[Phase 2] EtherNet/IP broadcast from 0.0.0.0 (all interfaces)")
    results = discover_on('0.0.0.0', [
        '192.168.1.255',
        '255.255.255.255',
    ], timeout=3)
    all_found.extend(results)

    # --- Phase 3: Quick Modbus scan on 192.168.1.x ---
    print("\n[Phase 3] Modbus scan on 192.168.1.x subnet")
    modbus = scan_range_modbus('192.168.1', 1, 254, port=502)

    # --- Phase 4: Check 44818 on common IPs ---
    print("\n[Phase 4] EtherNet/IP direct probe on common IPs...")
    for ip in ['192.168.1.100', '192.168.1.1', '192.168.1.2']:
        if tcp_probe(ip, 44818, timeout=0.5):
            print(f"  >>> EtherNet/IP port open: {ip}:44818")
        else:
            print(f"  {ip}:44818 — no response")

    # --- Phase 5: Check 169.254 range (APIPA) ---
    # Only useful if we have a 169.254.x.x address on our NIC
    print("\n[Phase 5] Checking if 169.254.x.x alias is configured...")
    try:
        # Try to bind to 169.254.100.1 to see if it's configured
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.bind(('169.254.100.1', 0))
        test_sock.close()
        print("  169.254.100.1 alias is active! Broadcasting on APIPA range...")
        results = discover_on('169.254.100.1', [
            '169.254.255.255',
            '255.255.255.255',
        ], timeout=3)
        all_found.extend(results)

        # Quick Modbus scan on common APIPA addresses
        # Micro 820 APIPA is typically 169.254.x.x where x derives from MAC
        # MAC: 5C:88:16:D8:E4:D7 → last 2 bytes = 0xE4, 0xD7 = 228, 215
        # APIPA often uses last 2 MAC bytes: 169.254.228.215
        print("\n  Probing likely APIPA address based on MAC (169.254.228.215)...")
        for ip in ['169.254.228.215', '169.254.216.228', '169.254.1.1']:
            if tcp_probe(ip, 502, timeout=0.5):
                print(f"  >>> MODBUS OPEN: {ip}:502")
                modbus.append(ip)
            elif tcp_probe(ip, 44818, timeout=0.5):
                print(f"  >>> EtherNet/IP: {ip}:44818")
            else:
                print(f"  {ip} — no response")

    except OSError:
        print("  169.254.x.x alias NOT configured.")
        print("  Run as Admin: netsh interface ip add address \"Ethernet\" 169.254.100.1 255.255.0.0")
        print("  Then re-run this script.")

    # --- Summary ---
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if all_found:
        print(f"EtherNet/IP devices found: {len(all_found)}")
        for d in all_found:
            print(f"  IP: {d['ip']}  Product: {d.get('product', '?')}  Serial: {d.get('serial', '?')}")
    else:
        print("No EtherNet/IP devices found via broadcast.")

    if modbus:
        print(f"\nModbus devices found: {len(modbus)}")
        for ip in modbus:
            print(f"  {ip}:502")
    else:
        print("No Modbus devices found on 192.168.1.x.")

    if not all_found and not modbus:
        print()
        print("NEXT STEPS:")
        print("  1. Add 169.254 alias (Admin PowerShell):")
        print("     netsh interface ip add address \"Ethernet\" 169.254.100.1 255.255.0.0")
        print("  2. Re-run this script")
        print("  3. If still nothing — use 32GB SD card with ConfigMeFirst.txt")
        print("  4. Or connect via USB and use CCW")


if __name__ == '__main__':
    main()
