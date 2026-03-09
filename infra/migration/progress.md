# Migration Progress

**Last Updated:** 2026-03-08
**Author:** Mike
**Status:** In progress — VPS extraction underway

---

## VPS Extraction

- [ ] Hostinger: inventory complete
- [ ] Hostinger: configs backed up
- [ ] Hostinger: workspace/SOUL.md extracted
- [ ] Hostinger: Rivet-PRO data extracted
- [ ] Hostinger: ready for decommission
- [x] DigitalOcean: inventory complete
- [ ] DigitalOcean: configs backed up
- [ ] DigitalOcean: workspace/SOUL.md extracted
- [ ] DigitalOcean: Vector/Axiom config extracted
- [ ] DigitalOcean: ready for decommission

## Telegram Polling Migration (VPS → CHARLIE)

- [x] Confirmed `telegram_bot.py` already uses `run_polling()` — no code changes needed
- [x] Architecture docs updated (CLUSTER.md, ENDPOINT_MAP.md, JARVIS_NODES)
- [x] VPS node deprecated in Mission Control backend
- [x] Deploy bot on CHARLIE — @Tony_Macaroni_bot using MACARONI token + Groq LLM
- [x] OpenClaw on VPS kept running (separate token, no conflict)
- [ ] Verify end-to-end: Telegram message → @Tony_Macaroni_bot → CHARLIE → response
- [ ] Monitor for 1 week before full VPS decommission

## Local Setup

- [ ] Docker Compose created (`infra/local/docker-compose.yml`)
- [ ] Postgres running locally
- [ ] Matrix API running locally
- [ ] PLC simulator running locally
- [ ] OpenClaw bot running locally (already works)
- [ ] HMIs accessible locally
- [ ] Ollama running locally
- [ ] `docs/local_setup.md` written

## Minimal VPS (Hetzner)

- [ ] SSH key + root password changed
- [ ] Tailscale installed
- [ ] Caddy installed and configured
- [ ] Telegram webhook forwarding tested
- [ ] Optional: Cloudflare Tunnel configured
- [ ] No extra services running (verified)

## Repo Cleanup

- [ ] Each major app has "deployment profile" in README
- [ ] `docs/local_setup.md` created
- [ ] `docs/infra_overview.md` created
- [ ] `README.md` updated with "Local quickstart"

---

## Estimated Effort

| Task | Est. Hours | Status |
|------|-----------|--------|
| VPS inventory | 1 | ✅ Done |
| Target architecture | 1 | ✅ Done |
| Hostinger extraction | 2 | Not started |
| DigitalOcean extraction | 2 | Not started |
| Local Docker Compose | 3 | Not started |
| Hetzner minimal setup | 2 | Not started |
| Local setup docs | 2 | Not started |
| Repo cleanup | 2 | Not started |
| Decommission Hostinger | 1 | Not started |
| Decommission DigitalOcean | 1 | Not started |
| **Total** | **~17** | |

## Cosmos Cookoff MVP

- [ ] Matrix API boots and HMI reachable at http://localhost:8000
- [ ] Factory I/O bridge successfully reads and posts tags
- [ ] Cosmos watcher polls and attaches insights to incidents
- [ ] HMI displays incident + Cosmos insight
- [ ] End-to-end demo completed (sim mode)
- [ ] End-to-end demo completed (Factory I/O mode)
