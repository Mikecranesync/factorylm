# Conveyor Lab Security

Conveyor Lab is intended for Factory I/O and bench testing. Do not connect it to production PLCs or uncontrolled machinery.

## Supported Surface

- Local backend and frontend development
- Telegram Mini App development with validated init data in production
- Factory I/O Modbus TCP scenes in a lab network
- Simulator fallback for offline development

## Reporting a Vulnerability

Do not open a public issue for vulnerabilities, secrets, private network details, or customer data. Contact the repository maintainers privately with:

- A short impact summary
- Reproduction steps
- Affected commit or version
- Logs with secrets removed

## Secret Handling

- Never commit `.env` files.
- Never commit Telegram bot tokens.
- Do not paste private plant IPs, VPN details, or customer logs into public issues.
- Use Doppler or local shell environment variables for runtime secrets.

## Hardware Safety

Any feature that can write to hardware-facing outputs must be reviewed as a safety-sensitive change. Production PLC control requires authentication, explicit operator confirmation, interlocks, and a separate deployment review.
