# Hetzner Minimal VPS Setup (the ONE Public Endpoint)

**Last Updated:** 2026-02-13  
**Status:** Target infrastructure

---

## Goal

This VPS does **ONE thing**: receive public web traffic and forward it to the local machine via secure tunnel. No heavy services, no databases, no background agents.

---

## Connection

```bash
ssh root@46.225.103.156
```

---

## Initial Setup (One-Time)

```bash
# 1. Change root password
passwd

# 2. Add SSH key
mkdir -p ~/.ssh
echo "YOUR_PUBLIC_KEY" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 3. Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up

# 4. Install Caddy (reverse proxy with automatic HTTPS)
apt update && apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# 5. Configure Caddy (example)
cat > /etc/caddy/Caddyfile << 'EOF'
# FactoryLM minimal reverse proxy
# Forward to local machine via Tailscale

your-domain.com {
    reverse_proxy http://TAILSCALE_IP:8000
}

# Telegram webhook endpoint
your-domain.com/webhook/telegram {
    reverse_proxy http://TAILSCALE_IP:18800
}
EOF

# 6. Start Caddy
systemctl enable caddy
systemctl start caddy
```

---

## What Should NOT Run Here

- ❌ OpenClaw / clawdbot (runs locally now)
- ❌ Ollama / any LLM
- ❌ Postgres / any database
- ❌ Vector / log shippers (ship directly from local)
- ❌ Background agents of any kind

---

## What CAN Run Here

- ✅ Caddy reverse proxy
- ✅ Tailscale daemon
- ✅ Optional: Cloudflare Tunnel client (if using CF instead of Tailscale for public traffic)
- ✅ Optional: tiny static site for public landing page

---

## Verification

```bash
# Check only Caddy and Tailscale are running
systemctl list-units --type=service --state=running | grep -E "caddy|tailscale"

# Should see exactly 2 services (plus system defaults)
# If you see anything else, investigate and remove it
```
