# Pi-Gateway

Industrial IoT gateway software - an eWON replacement for Raspberry Pi.

## Features

- **VPN Remote Access**: WireGuard-based secure tunneling to PLC networks
- **PLC Data Collection**: OPC UA, Modbus TCP/RTU, Siemens S7, EtherNet/IP
- **Web Dashboard**: React-based management interface
- **Cloud Integration**: MQTT/REST API with Sparkplug B support
- **Alerting**: Multi-channel notifications (Email, SMS, Telegram, Webhook)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for dashboard)
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/Mikecranesync/pi-gateway.git
cd pi-gateway

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: .\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your settings

# Run the application
python -m uvicorn src.api.main:app --reload --port 8000
```

### Dashboard (Frontend)

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## API Documentation

When running, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
pi-gateway/
├── src/                    # Python backend
│   ├── api/                # FastAPI application
│   ├── plc/                # PLC communication clients
│   ├── data/               # Database & MQTT
│   ├── alerts/             # Alert engine
│   └── vpn/                # WireGuard management
├── web/                    # React frontend
├── tests/                  # Test suite
├── config/                 # Configuration files
└── docs/                   # Documentation
```

## Supported PLCs

| Protocol | Library | Supported Devices |
|----------|---------|-------------------|
| Modbus TCP/RTU | pymodbus | Any Modbus device |
| OPC UA | asyncua | Any OPC UA server |
| Siemens S7 | python-snap7 | S7-300, S7-400, S7-1200, S7-1500 |
| EtherNet/IP | pycomm3 | Allen-Bradley ControlLogix, CompactLogix, Micro800 |

## Configuration

See `.env.example` for all configuration options.

### Device Configuration

Devices and tags are configured in `config/default.yaml`:

```yaml
devices:
  - id: plc-1
    name: "Main PLC"
    protocol: modbus_tcp
    host: 192.168.1.100
    port: 502
    tags:
      - name: temperature
        address: 40001
        type: float32
        poll_rate: 1000
```

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check src/

# Type checking
mypy src/

# Format
black src/
```

## Deployment

### Raspberry Pi

```bash
# On Pi
git clone https://github.com/Mikecranesync/pi-gateway.git
cd pi-gateway
sudo ./scripts/install.sh
```

### Docker (Coming Soon)

```bash
docker-compose up -d
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Support

- [Documentation](docs/)
- [Issues](https://github.com/Mikecranesync/pi-gateway/issues)
