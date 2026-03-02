# Pi Factory Deploy — Ubuntu Server 24.04 LTS

## Flash the SD Card

### Requirements
- microSD card: 32GB+ Class 10 / A1
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (any OS)

### Steps

1. Open **Raspberry Pi Imager**
2. **Choose Device** — select your Pi model (Pi 4, Pi 5, etc.)
3. **Choose OS** — navigate to:
   `Other general-purpose OS > Ubuntu > Ubuntu Server 24.04 LTS (64-bit)`
   > **Do NOT select Raspberry Pi OS.** Pi Factory targets Ubuntu Server for
   > Netplan + systemd-networkd networking.
4. **Choose Storage** — select your microSD card
5. Click the **gear icon** (or "Edit Settings") to configure:
   - **Hostname:** `pi-factory`
   - **Enable SSH:** Yes (use password authentication or add your key)
   - **Username:** `pi`
   - **Password:** set a strong password
   - **Locale:** your timezone
6. Click **Write** and wait for flashing + verification to complete

### After Flashing

1. Insert the SD card into the Pi
2. Connect Ethernet cable to the factory switch
3. Connect power — the Pi will boot and get a DHCP address
4. SSH in:
   ```bash
   ssh pi@pi-factory.local
   ```
   If mDNS hasn't propagated yet, find the IP from your router or use:
   ```bash
   ping pi-factory.local
   ```

## Install Pi Factory

```bash
git clone https://github.com/factorylm/plc-client.git ~/factorylm/services/plc-modbus
cd ~/factorylm/services/plc-modbus
bash deploy/setup-pi-factory.sh
```

The script performs a 6-step unattended install:
1. System packages (avahi, python3, net-tools)
2. Hostname set to `pi-factory`
3. Netplan config: DHCP primary + link-local fallback on eth0
4. Avahi mDNS service registration
5. Python venv + dependencies
6. Systemd service (`pi-factory.service`)

## Verify

```bash
bash deploy/verify-pi-factory.sh
```

All checks should pass. Then open a browser on any device on the same LAN:

```
http://pi-factory.local:8000
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `pi-factory.local` doesn't resolve | Wait 30s for Avahi, or use the IP directly |
| No IP on eth0 | Check cable; link-local 169.254.x.x should appear within 60s |
| Service not running | `sudo systemctl status pi-factory` / `journalctl -u pi-factory -f` |
| Dashboard loads but no PLCs found | Verify PLCs are on the same subnet and have Modbus TCP enabled |
