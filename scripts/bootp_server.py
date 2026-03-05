"""
Minimal BOOTP server to assign a static IP to a Micro 820 PLC.

The PLC broadcasts BOOTP requests (UDP port 67) when it has no IP.
This server listens for those requests and replies with the configured IP.

Must be run as Administrator (binding to port 67 requires elevation).

Usage:
    python scripts/bootp_server.py
    python scripts/bootp_server.py --ip 192.168.1.100 --mac AA:BB:CC:DD:EE:FF
"""

import socket
import struct
import argparse
import subprocess
import sys


# BOOTP/DHCP constants
BOOTP_REQUEST = 1
BOOTP_REPLY = 2
BOOTP_SERVER_PORT = 67
BOOTP_CLIENT_PORT = 68


def check_admin():
    """Check if running as Administrator on Windows."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def check_firewall_rule():
    """Check/add Windows Firewall rule for UDP 67 (BOOTP)."""
    if sys.platform != "win32":
        return

    print("[DIAG] Checking Windows Firewall for UDP 67...")

    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=BOOTP"],
            capture_output=True, text=True, timeout=10,
        )
        if "BOOTP" in result.stdout and "67" in result.stdout:
            print("[DIAG]   Firewall rule 'BOOTP' exists — OK")
            return
    except Exception:
        pass

    print("[DIAG]   No firewall rule for UDP 67. Adding one...")
    try:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                "name=BOOTP", "dir=in", "action=allow",
                "protocol=UDP", "localport=67",
            ],
            capture_output=True, text=True, timeout=10,
        )
        print("[DIAG]   Firewall rule 'BOOTP' added (UDP 67 inbound allow)")
    except Exception as e:
        print(f"[WARN]   Could not add firewall rule: {e}")
        print("[WARN]   Manually run: netsh advfirewall firewall add rule name=\"BOOTP\" dir=in action=allow protocol=UDP localport=67")


def check_dhcp_client_service():
    """Warn if Windows DHCP Client service is running (it grabs port 67)."""
    if sys.platform != "win32":
        return

    print("[DIAG] Checking DHCP Client service...")

    try:
        result = subprocess.run(
            ["sc", "query", "dhcp"],
            capture_output=True, text=True, timeout=10,
        )
        if "RUNNING" in result.stdout:
            print("[WARN]   DHCP Client service is RUNNING — it may grab port 67!")
            print("[WARN]   If port 67 is already in use, stop it temporarily:")
            print("[WARN]     net stop dhcp")
            print("[WARN]   Re-enable after:  net start dhcp")
            return True
        else:
            print("[DIAG]   DHCP Client service is not running — OK")
            return False
    except Exception:
        print("[DIAG]   Could not check DHCP Client service status")
        return False


def show_network_diagnostics():
    """Print adapter IPs and link-local addresses for troubleshooting."""
    print("[DIAG] Network adapter information:")

    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True, text=True, timeout=10,
        )
        current_adapter = None
        for line in result.stdout.splitlines():
            stripped = line.strip()
            # Adapter header lines aren't indented
            if line and not line.startswith(" ") and "adapter" in line.lower():
                current_adapter = stripped.rstrip(":")
            elif "IPv4 Address" in line or "IPv4" in line:
                ip = stripped.split(":")[-1].strip()
                print(f"[DIAG]   {current_adapter}: {ip}")
            elif "Subnet Mask" in line:
                mask = stripped.split(":")[-1].strip()
                print(f"[DIAG]     Mask: {mask}")
    except Exception:
        print("[DIAG]   Could not enumerate adapters")

    # Also try to check if port 67 is in use
    print("[DIAG] Checking if port 67 is in use...")
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "UDP"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if ":67 " in line or ":67\t" in line:
                print(f"[DIAG]   {line.strip()}")
        else:
            # Check if we actually found anything
            found = any(":67 " in l or ":67\t" in l for l in result.stdout.splitlines())
            if not found:
                print("[DIAG]   Port 67 appears free — OK")
    except Exception:
        print("[DIAG]   Could not check port usage")

    print()


def parse_bootp_request(data):
    """Parse a BOOTP request packet, return dict with key fields."""
    if len(data) < 236:
        return None

    op = data[0]
    if op != BOOTP_REQUEST:
        return None

    htype = data[1]   # hardware type (1 = Ethernet)
    hlen = data[2]    # hardware address length (6 for MAC)
    xid = data[4:8]   # transaction ID
    ciaddr = socket.inet_ntoa(data[12:16])  # client IP (0.0.0.0 if none)
    chaddr = data[28:28+hlen]  # client hardware address (MAC)

    mac_str = ":".join(f"{b:02X}" for b in chaddr)

    return {
        "op": op,
        "htype": htype,
        "hlen": hlen,
        "xid": xid,
        "ciaddr": ciaddr,
        "chaddr": chaddr,
        "mac": mac_str,
        "raw": data,
    }


def build_bootp_reply(request, assigned_ip, server_ip, subnet_mask, gateway):
    """Build a BOOTP reply packet."""
    reply = bytearray(300)

    reply[0] = BOOTP_REPLY        # op: reply
    reply[1] = request["htype"]   # htype
    reply[2] = request["hlen"]    # hlen
    reply[3] = 0                  # hops
    reply[4:8] = request["xid"]   # transaction ID (echo back)
    reply[8:10] = b'\x00\x00'     # secs
    reply[10:12] = b'\x00\x00'    # flags

    # ciaddr — leave 0
    reply[12:16] = b'\x00\x00\x00\x00'

    # yiaddr — "your" IP address (the one we're assigning)
    reply[16:20] = socket.inet_aton(assigned_ip)

    # siaddr — server IP
    reply[20:24] = socket.inet_aton(server_ip)

    # giaddr — gateway
    reply[24:28] = b'\x00\x00\x00\x00'

    # chaddr — client hardware address (echo back)
    reply[28:28+request["hlen"]] = request["chaddr"]

    # sname (64 bytes) and file (128 bytes) — leave zeros
    # They start at offset 44 and 108 respectively

    # DHCP magic cookie at offset 236
    reply[236:240] = b'\x63\x82\x53\x63'

    # DHCP options
    idx = 240

    # Option 53: DHCP Message Type = 2 (OFFER) — some PLCs expect this
    reply[idx:idx+3] = bytes([53, 1, 2])
    idx += 3

    # Option 1: Subnet Mask
    reply[idx] = 1
    reply[idx+1] = 4
    reply[idx+2:idx+6] = socket.inet_aton(subnet_mask)
    idx += 6

    # Option 3: Router/Gateway
    reply[idx] = 3
    reply[idx+1] = 4
    reply[idx+2:idx+6] = socket.inet_aton(gateway)
    idx += 6

    # Option 51: Lease time (infinite — 0xFFFFFFFF)
    reply[idx] = 51
    reply[idx+1] = 4
    reply[idx+2:idx+6] = struct.pack("!I", 0xFFFFFFFF)
    idx += 6

    # Option 54: Server identifier
    reply[idx] = 54
    reply[idx+1] = 4
    reply[idx+2:idx+6] = socket.inet_aton(server_ip)
    idx += 6

    # End option
    reply[idx] = 255
    idx += 1

    return bytes(reply[:idx])


def main():
    parser = argparse.ArgumentParser(description="BOOTP server for Micro 820 PLC IP assignment")
    parser.add_argument("--ip", default="192.168.1.100", help="IP to assign to PLC (default: 192.168.1.100)")
    parser.add_argument("--server-ip", default="192.168.1.10", help="This machine's IP (default: 192.168.1.10)")
    parser.add_argument("--subnet", default="255.255.255.0", help="Subnet mask (default: 255.255.255.0)")
    parser.add_argument("--gateway", default="192.168.1.1", help="Gateway (default: 192.168.1.1)")
    parser.add_argument("--mac", default=None, help="Only respond to this MAC (e.g. AA:BB:CC:DD:EE:FF). If not set, responds to ALL requests.")
    parser.add_argument("--bind", default="0.0.0.0", help="Interface to bind to (default: 0.0.0.0)")
    parser.add_argument("--skip-checks", action="store_true", help="Skip firewall/DHCP/network diagnostics")
    args = parser.parse_args()

    # Pre-flight checks
    if not check_admin():
        print("ERROR: Must run as Administrator to bind to port 67!")
        print("Right-click your terminal and 'Run as administrator', then retry.")
        sys.exit(1)

    if not args.skip_checks:
        print("=" * 50)
        print("PRE-FLIGHT DIAGNOSTICS")
        print("=" * 50)
        check_firewall_rule()
        check_dhcp_client_service()
        show_network_diagnostics()

    target_mac = None
    if args.mac:
        target_mac = args.mac.upper().replace("-", ":")

    print(f"=== BOOTP Server for Micro 820 PLC ===")
    print(f"Assigning IP:  {args.ip}")
    print(f"Server IP:     {args.server_ip}")
    print(f"Subnet:        {args.subnet}")
    print(f"Gateway:       {args.gateway}")
    print(f"MAC filter:    {target_mac or 'ANY (responding to all requests)'}")
    print(f"Listening on:  {args.bind}:{BOOTP_SERVER_PORT}")
    print(f"=" * 40)
    print(f"Waiting for BOOTP requests... (Ctrl+C to stop)")
    print(f">>> Power cycle the PLC now! <<<")
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        sock.bind((args.bind, BOOTP_SERVER_PORT))
    except PermissionError:
        print("ERROR: Must run as Administrator to bind to port 67!")
        print("Right-click your terminal and 'Run as administrator', then retry.")
        sys.exit(1)
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            print(f"ERROR: Port {BOOTP_SERVER_PORT} already in use!")
            print("The Windows DHCP Client service likely has port 67 open.")
            print("Fix: run 'net stop dhcp' in an admin terminal, then retry.")
            print("Re-enable after: 'net start dhcp'")
        else:
            print(f"ERROR: {e}")
        sys.exit(1)

    reply_count = 0
    ignored_count = 0

    try:
        while True:
            data, addr = sock.recvfrom(1024)
            req = parse_bootp_request(data)

            if req is None:
                ignored_count += 1
                if ignored_count <= 3:
                    print(f"[DEBUG] Non-BOOTP packet from {addr} ({len(data)} bytes)")
                elif ignored_count == 4:
                    print(f"[DEBUG] (suppressing further non-BOOTP packet logs)")
                continue

            print(f"[BOOTP REQUEST] from MAC={req['mac']}, ciaddr={req['ciaddr']}, src={addr}")
            print(f"  Packet: op={req['op']} htype={req['htype']} hlen={req['hlen']} xid={req['xid'].hex()}")

            # Filter by MAC if specified
            if target_mac and req["mac"] != target_mac:
                print(f"  -> Ignoring (MAC doesn't match filter {target_mac})")
                continue

            # Build and send reply
            reply = build_bootp_reply(req, args.ip, args.server_ip, args.subnet, args.gateway)

            # Send reply as broadcast (PLC has no IP yet)
            sock.sendto(reply, ("255.255.255.255", BOOTP_CLIENT_PORT))
            reply_count += 1

            print(f"  -> REPLIED #{reply_count}: assigned {args.ip} to {req['mac']}")
            print(f"     (PLC may need a few seconds to accept. Keep this running.)")
            print()

    except KeyboardInterrupt:
        print(f"\nStopped. Sent {reply_count} replies total.")
        if reply_count == 0:
            print("\nNo BOOTP requests were received. Troubleshooting:")
            print("  1. Was the PLC power-cycled AFTER starting this script?")
            print("  2. Is the Ethernet cable directly connected (no switch)?")
            print("  3. Check firewall: netsh advfirewall firewall show rule name=BOOTP")
            print("  4. Try stopping DHCP Client: net stop dhcp")
            print("  5. The PLC BOOTP window is ~10s after power-on — cycle again quickly")
            print(f"  6. Consider using CCW directly at the APIPA address instead.")
            print(f"     See recovery/CCW_SETUP_GUIDE.txt Part A.")
        else:
            print(f"Verify with: ping {args.ip}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
