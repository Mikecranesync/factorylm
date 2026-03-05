"""Quick probe of the discovered PLC at 169.254.47.96."""
import socket

PLC_IP = '169.254.47.96'
PORTS = [502, 44818, 80, 443, 2222]

print(f"Probing {PLC_IP}...")
for port in PORTS:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((PLC_IP, port))
        s.close()
        label = {502: 'Modbus', 44818: 'EtherNet/IP', 80: 'HTTP/Web', 443: 'HTTPS', 2222: 'CCW'}
        print(f"  Port {port:5d} ({label.get(port, '?'):12s}) — OPEN")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"  Port {port:5d} — closed/filtered ({type(e).__name__})")
