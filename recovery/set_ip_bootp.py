"""
Assign IP to Micro 820 via BOOTP reply.

The Micro 820 on APIPA (169.254.x.x) may still be sending BOOTP requests.
This script sends an unsolicited BOOTP reply directly to the PLC's MAC address
to assign the desired IP.

Alternative approach: Use the PLC's current IP (169.254.47.96) and reconfigure
via CCW over EtherNet/IP.

Usage:
    python recovery/set_ip_bootp.py

Must run as Administrator (port 67/68 require elevation).
"""

import socket
import struct
import sys
import time

PLC_MAC = bytes([0x5C, 0x88, 0x16, 0xD8, 0xE4, 0xD7])
PLC_MAC_STR = '5C:88:16:D8:E4:D7'
ASSIGN_IP = '192.168.1.100'
SUBNET = '255.255.255.0'
GATEWAY = '192.168.1.1'
SERVER_IP = '192.168.1.10'


def build_bootp_reply(assign_ip, server_ip, subnet, gateway, client_mac, xid=b'\x00\x00\x00\x01'):
    """Build a BOOTP reply packet."""
    reply = bytearray(300)

    reply[0] = 2              # op: BOOT_REPLY
    reply[1] = 1              # htype: Ethernet
    reply[2] = 6              # hlen: MAC length
    reply[3] = 0              # hops
    reply[4:8] = xid          # transaction ID
    reply[16:20] = socket.inet_aton(assign_ip)   # yiaddr (your IP)
    reply[20:24] = socket.inet_aton(server_ip)   # siaddr (server IP)
    reply[28:34] = client_mac                     # chaddr (client MAC)

    # DHCP magic cookie
    reply[236:240] = b'\x63\x82\x53\x63'

    idx = 240

    # Option 53: DHCP Message Type = 2 (OFFER)
    reply[idx:idx+3] = bytes([53, 1, 2])
    idx += 3

    # Option 1: Subnet Mask
    reply[idx] = 1
    reply[idx+1] = 4
    reply[idx+2:idx+6] = socket.inet_aton(subnet)
    idx += 6

    # Option 3: Router
    reply[idx] = 3
    reply[idx+1] = 4
    reply[idx+2:idx+6] = socket.inet_aton(gateway)
    idx += 6

    # Option 54: Server Identifier
    reply[idx] = 54
    reply[idx+1] = 4
    reply[idx+2:idx+6] = socket.inet_aton(server_ip)
    idx += 6

    # Option 51: Lease Time (infinite)
    reply[idx] = 51
    reply[idx+1] = 4
    reply[idx+2:idx+6] = struct.pack('!I', 0xFFFFFFFF)
    idx += 6

    # End
    reply[idx] = 255
    idx += 1

    return bytes(reply[:idx])


def main():
    print("=" * 60)
    print("BOOTP IP Assignment for Micro 820")
    print("=" * 60)
    print(f"PLC MAC:     {PLC_MAC_STR}")
    print(f"Assign IP:   {ASSIGN_IP}")
    print(f"Subnet:      {SUBNET}")
    print(f"Gateway:     {GATEWAY}")
    print(f"Server IP:   {SERVER_IP}")
    print()

    # Send BOOTP reply as broadcast on port 68
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        sock.bind((SERVER_IP, 67))
    except PermissionError:
        print("ERROR: Must run as Administrator!")
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: {e}")
        print("Port 67 may be in use. Stop any DHCP servers first.")
        sys.exit(1)

    reply = build_bootp_reply(ASSIGN_IP, SERVER_IP, SUBNET, GATEWAY, PLC_MAC)

    print("Sending BOOTP replies (5 attempts, 2s apart)...")
    for i in range(5):
        # Send as broadcast — the PLC should pick it up
        sock.sendto(reply, ('255.255.255.255', 68))
        # Also try unicast to the PLC's current IP
        try:
            sock.sendto(reply, ('169.254.47.96', 68))
        except OSError:
            pass
        print(f"  Reply {i+1}/5 sent")
        if i < 4:
            time.sleep(2)

    sock.close()

    print(f"\nWaiting 5 seconds for PLC to process...")
    time.sleep(5)

    print(f"Pinging {ASSIGN_IP}...")
    import subprocess
    result = subprocess.run(['ping', '-n', '3', ASSIGN_IP], capture_output=True, text=True)
    print(result.stdout)

    if 'Reply from' in result.stdout:
        print(f"SUCCESS! PLC is now at {ASSIGN_IP}")
    else:
        print(f"PLC not responding at {ASSIGN_IP}.")
        print(f"PLC is still reachable at 169.254.47.96")
        print()
        print("Options:")
        print("  1. Use CCW to connect via EtherNet/IP to 169.254.47.96 and set IP")
        print("  2. Use ConfigMeFirst.txt on a 32GB SD card (power cycle required)")
        print("  3. Connect via USB and use CCW")


if __name__ == '__main__':
    main()
