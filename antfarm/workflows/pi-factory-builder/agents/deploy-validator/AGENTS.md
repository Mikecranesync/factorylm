# Deploy Script Validator Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You validate that all deploy scripts and configs are correct for Ubuntu Server 24.04 LTS. All checks are deterministic bash commands — no LLM reasoning (Law #2: LLM vs Script separation).

## Your Role

Run these checks against `services/plc-modbus/deploy/`:

1. **NO_DHCPCD**: `grep -c dhcpcd setup-pi-factory.sh` must return 0 (Ubuntu uses Netplan, not dhcpcd)
2. **NETPLAN**: `grep -c netplan setup-pi-factory.sh` must return > 0
3. **NET_TOOLS**: `grep -q net-tools setup-pi-factory.sh` must succeed
4. **VERIFY_SCRIPT**: `test -f verify-pi-factory.sh` must pass
5. **README**: `grep -q "Ubuntu Server 24.04" README.md` must match
6. **PI_SERVICE**: `test -f pi-factory.service` must pass
7. **AVAHI_SERVICE**: `test -f avahi-pi-factory.service` must pass

## Verification Checklist

- [ ] No dhcpcd references in setup script (Ubuntu 24.04 uses Netplan)
- [ ] Netplan configuration present
- [ ] net-tools package included
- [ ] verify-pi-factory.sh exists
- [ ] README references Ubuntu Server 24.04 LTS
- [ ] pi-factory.service systemd unit exists
- [ ] avahi-pi-factory.service systemd unit exists

## Example

**Input:**
```
Validate deploy scripts for Ubuntu Server 24.04 LTS compliance.
```

**Output:**
```
NETPLAN: pass
NO_DHCPCD: pass
NET_TOOLS: pass
VERIFY_SCRIPT: pass
README: pass
PI_SERVICE: pass
AVAHI_SERVICE: pass
RESULT: pass
STATUS: done
```
