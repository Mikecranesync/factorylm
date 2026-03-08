"""
Set Micro820 PLC to static IP 192.168.1.100 via EtherNet/IP CIP protocol.

Usage:
    python scripts/set_plc_static_ip.py discover     # Find PLC on network
    python scripts/set_plc_static_ip.py identify IP   # Verify PLC identity
    python scripts/set_plc_static_ip.py setip IP      # Set static IP config
    python scripts/set_plc_static_ip.py verify        # Verify 192.168.1.100 Modbus
"""

import argparse
import socket
import struct
import subprocess
import sys
import concurrent.futures
from pathlib import Path

# Target configuration
TARGET_IP = "192.168.1.100"
TARGET_SUBNET = "255.255.255.0"
TARGET_GATEWAY = "192.168.1.1"
ETHERNET_IP_PORT = 44818
MODBUS_PORT = 502
ROCKWELL_OUI_PREFIXES = ("00-1d-9c", "00:1d:9c", "00-5a-06", "00:5a:06")


def scan_host(ip: str) -> str | None:
    """Ping host, then check if EtherNet/IP port 44818 is open."""
    try:
        r = subprocess.run(
            ["ping", "-n", "1", "-w", "500", ip],
            capture_output=True,
            timeout=3,
        )
        if r.returncode != 0:
            return None
        s = socket.socket()
        s.settimeout(1)
        s.connect((ip, ETHERNET_IP_PORT))
        s.close()
        return ip
    except Exception:
        return None


def discover():
    """Sweep 192.168.1.0/24 for devices with EtherNet/IP port open."""
    print("Scanning 192.168.1.0/24 for EtherNet/IP devices (port 44818)...")
    found = []
    with concurrent.futures.ThreadPoolExecutor(50) as pool:
        futures = {
            pool.submit(scan_host, f"192.168.1.{i}"): i for i in range(1, 255)
        }
        for f in concurrent.futures.as_completed(futures):
            result = f.result()
            if result:
                print(f"  Found EtherNet/IP device: {result}")
                found.append(result)

    # Also check ARP table for Rockwell MACs
    print("\nChecking ARP table for Rockwell MAC prefixes...")
    arp = subprocess.run(["arp", "-a"], capture_output=True, text=True)
    for line in arp.stdout.splitlines():
        lower = line.lower()
        for prefix in ROCKWELL_OUI_PREFIXES:
            if prefix in lower:
                print(f"  Rockwell MAC found: {line.strip()}")

    if found:
        print(f"\nEtherNet/IP devices found: {found}")
    else:
        print("\nNo EtherNet/IP devices found. Check cable and link lights.")
    return found


def identify(ip: str):
    """Get module info from the PLC to confirm it's a Micro820."""
    from pycomm3 import CIPDriver

    print(f"Connecting to {ip} via CIP...")
    with CIPDriver(ip) as driver:
        info = driver.get_module_info(slot=0)
        print(f"Module info: {info}")
        return info


def set_static_ip(current_ip: str):
    """Set the PLC to static IP 192.168.1.100 via CIP TCP/IP Interface Object."""
    from pycomm3 import CIPDriver

    ip_bytes = socket.inet_aton(TARGET_IP)
    subnet_bytes = socket.inet_aton(TARGET_SUBNET)
    gateway_bytes = socket.inet_aton(TARGET_GATEWAY)

    # TCP/IP Interface Object attribute 5 structure:
    # IP(4) + Subnet(4) + Gateway(4) + NameServer1(4) + NameServer2(4) + DomainNameLen(2)
    config_data = (
        ip_bytes
        + subnet_bytes
        + gateway_bytes
        + b"\x00\x00\x00\x00"  # name server 1
        + b"\x00\x00\x00\x00"  # name server 2
        + struct.pack("<H", 0)  # domain name length = 0
    )

    print(f"Connecting to {current_ip}...")
    with CIPDriver(current_ip) as driver:
        # Step 1: Set Interface Configuration (Attribute 5)
        print(f"Setting IP config: {TARGET_IP} / {TARGET_SUBNET} / {TARGET_GATEWAY}")
        resp = driver.generic_message(
            service=0x10,  # Set_Attribute_Single
            class_code=0xF5,  # TCP/IP Interface Object
            instance=1,
            attribute=5,  # Interface Configuration
            request_data=config_data,
            connected=False,
            unconnected_send=False,
        )
        print(f"  Set IP response: {resp}")
        if resp.error:
            print(f"  ERROR: {resp.error}")
            print("  Micro820 may not support CIP IP set. See fallback options.")
            return False

        # Step 2: Set Configuration Control to Static (Attribute 3, value 0)
        print("Setting configuration mode to static (attribute 3 = 0)...")
        resp2 = driver.generic_message(
            service=0x10,
            class_code=0xF5,
            instance=1,
            attribute=3,
            request_data=struct.pack("<I", 0),  # 0 = static
            connected=False,
            unconnected_send=False,
        )
        print(f"  Set static response: {resp2}")
        if resp2.error:
            print(f"  ERROR: {resp2.error}")
            return False

    print(f"\nIP set to {TARGET_IP}. Connection to {current_ip} will drop.")
    print("Wait 5 seconds, then run: python scripts/set_plc_static_ip.py verify")
    return True


def verify():
    """Verify PLC is reachable at target IP via ping and Modbus TCP."""
    print(f"Pinging {TARGET_IP}...")
    r = subprocess.run(
        ["ping", "-n", "4", TARGET_IP], capture_output=True, text=True
    )
    print(r.stdout)
    if r.returncode != 0:
        print("Ping failed. PLC may still be rebooting or IP change didn't take.")
        return False

    print(f"Testing Modbus TCP on {TARGET_IP}:{MODBUS_PORT}...")
    try:
        from pymodbus.client import ModbusTcpClient

        client = ModbusTcpClient(TARGET_IP, port=MODBUS_PORT, timeout=3)
        if not client.connect():
            print("Modbus TCP connection failed.")
            return False
        result = client.read_coils(address=0, count=18)
        if result.isError():
            print(f"Modbus read error: {result}")
            client.close()
            return False
        bits = [int(b) for b in result.bits[:18]]
        print(f"Coils 0-17: {bits}")
        client.close()
        print("Modbus TCP verified!")
        return True
    except ImportError:
        print("pymodbus not installed. Testing raw TCP socket instead...")
        s = socket.socket()
        s.settimeout(3)
        try:
            s.connect((TARGET_IP, MODBUS_PORT))
            print(f"TCP connection to {TARGET_IP}:{MODBUS_PORT} succeeded!")
            s.close()
            return True
        except Exception as e:
            print(f"TCP connection failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Micro820 Static IP Configuration")
    parser.add_argument(
        "action",
        choices=["discover", "identify", "setip", "verify"],
        help="Action to perform",
    )
    parser.add_argument("ip", nargs="?", help="PLC IP address (for identify/setip)")
    args = parser.parse_args()

    if args.action == "discover":
        discover()
    elif args.action == "identify":
        if not args.ip:
            print("Usage: set_plc_static_ip.py identify <IP>")
            sys.exit(1)
        identify(args.ip)
    elif args.action == "setip":
        if not args.ip:
            print("Usage: set_plc_static_ip.py setip <CURRENT_IP>")
            sys.exit(1)
        print(f"WARNING: This will change the PLC IP from {args.ip} to {TARGET_IP}")
        print(f"  Target: {TARGET_IP} / {TARGET_SUBNET} / gw {TARGET_GATEWAY}")
        confirm = input("Proceed? [y/N] ")
        if confirm.lower() != "y":
            print("Aborted.")
            sys.exit(0)
        set_static_ip(args.ip)
    elif args.action == "verify":
        ok = verify()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
