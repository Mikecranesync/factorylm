# RIVET Pi Gateway - Claude Code CLI Prompt

## Project Overview

Build a complete eWON-style industrial IoT gateway on Raspberry Pi 4 that provides:
- Secure VPN remote access to PLC networks
- PLC data collection (OPC UA, Modbus TCP/RTU, S7, EtherNet/IP)
- Web-based management dashboard
- MQTT/REST API for cloud integration
- Alerting and notifications
- Zero-touch provisioning for field deployment

**Target Hardware:** Raspberry Pi 4 Model B (2GB+ RAM recommended)
**Target OS:** Raspberry Pi OS Lite (64-bit) or Ubuntu Server 24.04

---

## Phase 1: Core Infrastructure

### 1.1 System Setup Script
Create a bash script `setup.sh` that:
- Updates the system packages
- Configures hostname as `rivet-gateway-{SERIAL}` using Pi's serial number
- Sets timezone to America/New_York
- Enables SSH with key-based auth only (disable password auth)
- Configures static IP or DHCP reservation support
- Installs required system packages: python3, pip, git, wireguard, mosquitto, nginx, sqlite3, supervisor
- Creates a dedicated `rivet` user with appropriate permissions
- Sets up log rotation for all services
- Configures watchdog timer for auto-recovery

### 1.2 WireGuard VPN Server
Create Python module `vpn/wireguard_manager.py` that:
- Generates server keys and configuration
- Manages client peer configurations (add/remove/list)
- Generates QR codes for mobile clients
- Tracks connected peers and connection status
- Provides API endpoints for VPN management
- Supports both site-to-site and road-warrior configurations
- Auto-configures iptables for NAT and forwarding
- Persists configuration to `/etc/wireguard/wg0.conf`

### 1.3 Network Bridge Configuration
Create `network/bridge_manager.py` that:
- Configures the Pi as a transparent bridge between WiFi and Ethernet
- Supports VLAN tagging for network segmentation
- Implements MAC address filtering
- Provides network diagnostics (ping, traceroute, port scan)
- Monitors bandwidth usage per interface
- Detects and reports network topology

---

## Phase 2: PLC Communication Layer

### 2.1 OPC UA Client
Create `plc/opcua_client.py` using `asyncua` library:
- Connect to multiple OPC UA servers simultaneously
- Browse server address space and discover available nodes
- Subscribe to node value changes with configurable sampling
- Read/write node values with proper error handling
- Support for security policies (None, Basic256Sha256)
- Certificate management for secure connections
- Connection health monitoring with auto-reconnect
- Tag database with human-readable names mapped to NodeIDs

### 2.2 Modbus Client
Create `plc/modbus_client.py` using `pymodbus`:
- Support both Modbus TCP and Modbus RTU (via USB-RS485 adapter)
- Poll multiple devices on configurable intervals
- Read coils, discrete inputs, holding registers, input registers
- Write single/multiple coils and registers
- Configurable data types (INT16, UINT16, INT32, FLOAT32, etc.)
- Byte order configuration (Big/Little Endian, Word Swap)
- Connection pooling for multiple slaves
- Automatic reconnection on communication failure

### 2.3 Siemens S7 Client
Create `plc/s7_client.py` using `python-snap7`:
- Connect to S7-300, S7-400, S7-1200, S7-1500
- Read/write DB blocks, inputs, outputs, markers, timers, counters
- Support for optimized block access (S7-1200/1500)
- Handle S7 data types including strings and arrays
- Connection monitoring with keep-alive
- Bulk read optimization for efficiency

### 2.4 EtherNet/IP Client
Create `plc/ethernet_ip_client.py` using `pycomm3`:
- Connect to Allen-Bradley PLCs (ControlLogix, CompactLogix, Micro800)
- Read/write tags by name
- Support for UDT (User Defined Types)
- Program scope and controller scope tags
- Array and structure access
- Connection management with auto-recovery

### 2.5 Universal Tag Engine
Create `plc/tag_engine.py` that:
- Provides unified interface across all PLC protocols
- Manages tag configuration in SQLite database
- Supports tag groups with independent polling rates
- Implements data buffering for unreliable connections
- Calculates derived values (scaling, math expressions)
- Tracks tag quality (Good, Bad, Uncertain)
- Provides change-of-value (COV) notifications
- Logs historical data to time-series database (SQLite or InfluxDB)

---

## Phase 3: Data Services

### 3.1 MQTT Broker & Publisher
Create `data/mqtt_service.py`:
- Configure local Mosquitto broker with authentication
- Publish tag values to configurable topics
- Support Sparkplug B specification for industrial IoT
- Bridge to external MQTT brokers (AWS IoT, Azure IoT Hub, HiveMQ)
- QoS levels and retain flag support
- Last Will and Testament for connection monitoring
- Topic structure: `rivet/{gateway_id}/data/{tag_group}/{tag_name}`

### 3.2 REST API
Create `api/main.py` using FastAPI:
```
GET  /api/v1/tags                    - List all tags
GET  /api/v1/tags/{tag_id}           - Get tag details and current value
POST /api/v1/tags/{tag_id}/write     - Write value to tag
GET  /api/v1/tags/{tag_id}/history   - Get historical values

GET  /api/v1/devices                 - List configured PLC devices
POST /api/v1/devices                 - Add new device
PUT  /api/v1/devices/{device_id}     - Update device config
DELETE /api/v1/devices/{device_id}   - Remove device

GET  /api/v1/vpn/status              - VPN server status
GET  /api/v1/vpn/peers               - List VPN peers
POST /api/v1/vpn/peers               - Add new peer
DELETE /api/v1/vpn/peers/{peer_id}   - Remove peer
GET  /api/v1/vpn/peers/{peer_id}/qr  - Get QR code for peer

GET  /api/v1/system/status           - System health and metrics
GET  /api/v1/system/network          - Network configuration
POST /api/v1/system/reboot           - Reboot gateway
POST /api/v1/system/update           - Trigger software update

GET  /api/v1/alerts                  - List active alerts
POST /api/v1/alerts/acknowledge      - Acknowledge alert
```

### 3.3 WebSocket Real-time Updates
Implement WebSocket endpoint `/ws/live`:
- Stream real-time tag value updates
- Push alert notifications
- VPN connection status changes
- System health metrics

### 3.4 Data Export
Create `data/export.py`:
- Export historical data to CSV
- Generate PDF reports with charts
- Email reports on schedule
- FTP/SFTP upload capability

---

## Phase 4: Web Dashboard

### 4.1 Frontend Application
Create React-based SPA in `web/` directory:
- Modern responsive design (works on mobile)
- Dark/light theme support
- Real-time data display with live updates
- Interactive tag browser
- Device configuration wizard
- VPN peer management with QR code display
- Historical data charts (Chart.js or Recharts)
- Alert management console
- System settings and diagnostics
- User authentication (local users, optional LDAP)

### 4.2 Dashboard Pages
- **Home:** System overview, connection status, key metrics
- **Tags:** Browse, search, filter tags; view live values; manual write
- **Devices:** Add/edit/remove PLC connections; connection status
- **VPN:** Manage peers, view connected clients, generate configs
- **History:** Time-series charts, data export
- **Alerts:** Active alerts, alert history, notification settings
- **Settings:** Network config, time settings, backup/restore, updates

---

## Phase 5: Alerting & Notifications

### 5.1 Alert Engine
Create `alerts/alert_engine.py`:
- Define alert conditions (high/low limits, rate of change, deviation)
- Alert states: Normal, Active, Acknowledged, Cleared
- Alert priorities: Critical, High, Medium, Low, Info
- Deadband and delay settings to prevent flapping
- Alert grouping and escalation rules

### 5.2 Notification Channels
Create `alerts/notifications.py`:
- Email notifications (SMTP with TLS)
- SMS via Twilio API
- Telegram bot integration
- Webhook calls to external systems
- Local buzzer/LED via GPIO (optional)

---

## Phase 6: Security & Hardening

### 6.1 Security Module
Create `security/hardening.py`:
- Firewall rules (iptables/nftables) - allow only required ports
- Fail2ban configuration for brute force protection
- SSL/TLS certificate management (Let's Encrypt or self-signed)
- API authentication with JWT tokens
- Role-based access control (Admin, Operator, Viewer)
- Audit logging of all configuration changes
- Encrypted storage for credentials (using Python keyring or SOPS)

### 6.2 Secure Boot & Integrity
- Read-only root filesystem option
- Application integrity verification
- Secure credential storage
- Automatic security updates

---

## Phase 7: Deployment & Management

### 7.1 Provisioning System
Create `provisioning/setup_wizard.py`:
- First-boot configuration wizard (web-based)
- Network configuration (static IP or DHCP)
- Initial admin user creation
- Cloud registration (optional)
- Device naming and location tagging

### 7.2 Remote Management
Create `management/remote.py`:
- Phone-home capability to central management server
- Remote configuration push
- Remote firmware updates
- Remote diagnostics and log retrieval
- Fleet management API integration

### 7.3 Backup & Restore
Create `management/backup.py`:
- Full configuration backup to encrypted archive
- Scheduled automatic backups
- One-click restore
- Configuration import/export for cloning

---

## Phase 8: Product Viability Analysis

### 8.1 Create Analysis Document
Create `docs/PRODUCT_VIABILITY.md` that evaluates:

**Cost Analysis:**
- Bill of Materials (BOM) for complete unit
- Manufacturing/assembly costs
- Software licensing costs (if any)
- Support and maintenance costs
- Compare to eWON Cosy+ ($700) and eWON Flexy ($1000+)

**Feature Comparison Matrix:**
| Feature | RIVET Pi | eWON Cosy+ | eWON Flexy | Teltonika |
|---------|----------|------------|------------|-----------|
| VPN Remote Access | | | | |
| OPC UA | | | | |
| Modbus TCP/RTU | | | | |
| S7 Protocol | | | | |
| EtherNet/IP | | | | |
| Web Dashboard | | | | |
| MQTT | | | | |
| Data Logging | | | | |
| Alerts | | | | |
| 4G Cellular | | | | |
| Industrial Temp | | | | |
| Certifications | | | | |

**Target Market Analysis:**
- Primary: Small/medium machine builders, system integrators
- Secondary: End users wanting low-cost remote access
- Tertiary: Education and training

**Go-to-Market Strategy:**
- Direct sales via website
- Amazon/eBay for volume
- Distributor partnerships
- Integration with RIVET Pro subscription service

**Risk Assessment:**
- Raspberry Pi supply chain issues
- Support burden for DIY product
- Certification requirements (UL, CE, FCC)
- Competition response
- Liability concerns for industrial use

**Pricing Strategy:**
- Hardware-only kit: $149-199
- Pre-configured unit: $249-299
- With 4G modem: $349-399
- Annual support subscription: $99/year
- RIVET Pro integration: Included with Pro subscription

**MVP Features (v1.0):**
1. WireGuard VPN with web management
2. Modbus TCP polling
3. Basic web dashboard
4. MQTT publishing
5. Email alerts

**Future Roadmap:**
- v1.1: OPC UA, S7 protocol
- v1.2: EtherNet/IP, historical trending
- v1.3: 4G cellular support, Sparkplug B
- v2.0: Industrial enclosure, certifications

---

## Project Structure

```
rivet-pi-gateway/
├── setup.sh                    # Initial system setup
├── requirements.txt            # Python dependencies
├── config/
│   ├── default.yaml           # Default configuration
│   └── schema.json            # Configuration schema
├── src/
│   ├── __init__.py
│   ├── main.py                # Application entry point
│   ├── vpn/
│   │   ├── __init__.py
│   │   └── wireguard_manager.py
│   ├── network/
│   │   ├── __init__.py
│   │   └── bridge_manager.py
│   ├── plc/
│   │   ├── __init__.py
│   │   ├── tag_engine.py
│   │   ├── opcua_client.py
│   │   ├── modbus_client.py
│   │   ├── s7_client.py
│   │   └── ethernet_ip_client.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── mqtt_service.py
│   │   └── export.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routes/
│   │   └── middleware/
│   ├── alerts/
│   │   ├── __init__.py
│   │   ├── alert_engine.py
│   │   └── notifications.py
│   ├── security/
│   │   ├── __init__.py
│   │   └── hardening.py
│   ├── management/
│   │   ├── __init__.py
│   │   ├── backup.py
│   │   └── remote.py
│   └── provisioning/
│       ├── __init__.py
│       └── setup_wizard.py
├── web/                        # React frontend
│   ├── package.json
│   ├── src/
│   └── public/
├── systemd/
│   ├── rivet-gateway.service
│   ├── rivet-api.service
│   └── rivet-mqtt.service
├── scripts/
│   ├── install.sh             # Production installer
│   ├── update.sh              # Update script
│   └── backup.sh              # Backup script
├── tests/
│   ├── test_vpn.py
│   ├── test_plc.py
│   └── test_api.py
├── docs/
│   ├── PRODUCT_VIABILITY.md
│   ├── USER_GUIDE.md
│   ├── API_REFERENCE.md
│   └── DEPLOYMENT.md
└── README.md
```

---

## Implementation Priority

### Week 1: Core Foundation
1. Setup script with system hardening
2. WireGuard VPN manager
3. Basic FastAPI skeleton
4. SQLite database schema

### Week 2: PLC Communication
1. Modbus TCP client (most common)
2. Tag engine with polling
3. Basic API endpoints for tags

### Week 3: Dashboard & Data
1. React frontend scaffold
2. Real-time WebSocket updates
3. MQTT publisher

### Week 4: Polish & Viability
1. Alert engine
2. Complete web dashboard
3. Documentation
4. Product viability analysis
5. Test on real PLCs

---

## Key Dependencies

```
# requirements.txt
fastapi>=0.104.0
uvicorn>=0.24.0
asyncua>=1.0.0
pymodbus>=3.5.0
python-snap7>=1.3
pycomm3>=1.2.0
paho-mqtt>=1.6.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
python-jose>=3.3.0
passlib>=1.7.0
pydantic>=2.5.0
pyyaml>=6.0.0
qrcode>=7.4.0
pillow>=10.0.0
jinja2>=3.1.0
python-multipart>=0.0.6
httpx>=0.25.0
websockets>=12.0
```

---

## Success Criteria

1. **VPN works reliably** - Connect from phone, access PLC on LAN
2. **Read PLC data** - Poll Modbus device, see values in dashboard
3. **Alerts function** - Email notification when value exceeds limit
4. **Survives reboot** - All services auto-start, config persists
5. **Runs 30 days** - Stability test without intervention
6. **Total cost < $150** - Competitive with GL.iNet, fraction of eWON

---

## Commands to Start

```bash
# Clone and enter project
cd ~/rivet-pi-gateway

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run setup
sudo ./setup.sh

# Start development server
python -m src.main
```

---

## Notes for Claude Code

- Use async/await throughout for non-blocking I/O
- Implement proper error handling with retries for PLC communication
- Use Pydantic for all configuration and API models
- Write unit tests for critical functions
- Keep memory footprint low (Pi may have only 1-2GB RAM)
- Log everything but implement log rotation
- Make all timeouts and intervals configurable
- Support graceful shutdown on SIGTERM
- Use supervisor or systemd for process management
