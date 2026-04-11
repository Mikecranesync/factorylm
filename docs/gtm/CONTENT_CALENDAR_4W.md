# FactoryLM Content Calendar — 4-Week Launch Sprint

**FAC-18 Deliverable**
**Platform Priority:** LinkedIn native video (primary) → YouTube long-form → YouTube Shorts → TikTok/Reels
**Cadence:** Mon / Wed / Fri, 9 AM EST
**ICP:** Plant managers, maintenance directors, Allen-Bradley users at 50–500 person manufacturers

---

## Hashtag Bank

```
#industrialAI #PLC #maintenance #manufacturing #Industry40
#factoryautomation #predictivemaintenance #AllenBradley #VFD
#industrialIoT #CMMS #factoryfloor #maintenancetech
```

**Per post:** Use 5–7 from the above. Always include `#PLC` and `#maintenance`.

---

## Series Map

| Series | Color | Hook Type | ICP Trigger |
|--------|-------|-----------|-------------|
| Before It Breaks | Safety orange #F97316 | Fault alarm sound | Pain: unplanned downtime |
| $500K vs $30 | Agent green #22C55E | Price shock visual | Pain: budget for enterprise tools |
| Inside the Machine | Industrial blue #1E3A8A | PLC wiring closeup | Curiosity: how does it work |
| Live Diagnosis | Alert red #EF4444 | Uncut screen recording | Drama: real fault, real fix |
| Tech Stories | Founder purple #8B5CF6 | Face-cam | Trust: founder credibility |
| Off the Grid | Steel grey #6B7280 | Air-gap demo | Fear: cloud dependency / security |

---

## Week 1 — Establish Category

**Goal:** First impression. Define the category ("Agent OS for factory maintenance") and prove the core claim.

| Day | Series | Title | Hook (0–3s) | Production Source | CTA |
|-----|--------|-------|-------------|-------------------|-----|
| Mon | Before It Breaks | VFD Fault E005: What It Means & How AI Fixes It | E005 alarm audio + fault code on screen | Cosmos Cookoff recording | "Full demo at factorylm.com" |
| Wed | $500K vs $30 | They Quoted $500K. We Charge $30. | Competitor price quote screenshot (blurred) | Pitch deck slide 7 competitor analysis | "See what $30 gets you → link in bio" |
| Fri | Live Diagnosis | Live: AI Diagnoses Conveyor Jam in 1.8 Seconds | Uncut screen — jam happens, Telegram fires | Cosmos Cookoff demo recording | "Real hardware. Real result. factorylm.com" |

**LinkedIn caption template (Week 1 Mon):**
```
Your VFD just threw E005.

Most techs google it. Some call the vendor. Some wait for the manual.

FactoryLM reads the motor current register, cross-references 25,000 
maintenance cases, and sends the fix to your phone in under 2 seconds.

Same fault. Different outcome.

→ factorylm.com for a free demo

#PLC #maintenance #VFD #industrialAI #manufacturing
```

---

## Week 2 — Build Authority

**Goal:** Education. Show the ICP HOW it works. Build the "this person knows their stuff" credibility.

| Day | Series | Title | Hook (0–3s) | Production Source | CTA |
|-----|--------|-------|-------------|-------------------|-----|
| Mon | Inside the Machine | Your PLC Already Knows the Answer | Ladder rung closeup, register values scrolling | story_pipeline.py + PLC b-roll | "The PLC already knows. Now it can think." |
| Wed | Tech Stories | The 3AM Call That Made Me Build This | Face-cam — phone rings at 3AM | story_pipeline.py voice-over | "15 years of 3AM calls. Then I built the fix." |
| Fri | Before It Breaks | Motor Overheating? AI Spots It 6 Hours Early | Thermal reading climbing toward red | MIRA demo footage + narration | "Catch it before it fails → factorylm.com" |

---

## Week 3 — Social Proof

**Goal:** Trust. Show the tool working in the real world, with real technicians.

| Day | Series | Title | Hook (0–3s) | Production Source | CTA |
|-----|--------|-------|-------------|-------------------|-----|
| Mon | Live Diagnosis | Technician Sends Photo. AI Sends Fix. (Real Telegram) | Phone notification sound + chat opening | telegram_overlay.py demo | "Photo in. Fix out. Under 3 seconds." |
| Wed | $500K vs $30 | Augury Needs 6 Months to Deploy. We Need 6 Minutes. | Timer counting up to "6 months" | Competitive analysis + demo footage | "6 minutes vs 6 months. factorylm.com" |
| Fri | Off the Grid | AI Diagnosis With Zero Internet | Ethernet cable being unplugged live | Edge inference demo (air-gapped) | "Works air-gapped. Data never leaves the floor." |

---

## Week 4 — Drive Conversions

**Goal:** Close. Every piece points to Calendly. Urgency: beta spots, early adopter pricing.

| Day | Series | Title | Hook (0–3s) | Production Source | CTA |
|-----|--------|-------|-------------|-------------------|-----|
| Mon | Inside the Machine | 25,000 Maintenance Answers. In Your Factory. Offline. | KB size visualization — counter spinning up | MIRA knowledge base b-roll | "Book a 30-min demo → calendly.com/mike-cranesync/30min" |
| Wed | Tech Stories | 15 Years of 3AM Calls. Then I Built the Fix. | Face-cam — tired engineer at desk | story_pipeline.py | "I built what I wish I had. Now it's yours." |
| Fri | Before It Breaks | How We Stopped a $40K Downtime Event (With $30) | Dollar bill vs downtime cost graphic | Cosmos Cookoff ROI calculation | "Beta spots open. $30/device. factorylm.com" |

---

## Topic Backlog (post Week 4)

### Before It Breaks
- Bearing fault detection via vibration register
- E-stop nuisance trip root cause
- PLC fault code 101: what it actually means
- Lubrication interval AI — over-greasing kills bearings

### $500K vs $30
- vs Fiix CMMS: licensing vs $30/device
- vs hiring a second tech: $60K/yr vs $600/mo
- vs unplanned downtime: average $260K/hr in auto manufacturing

### Inside the Machine
- What Modbus registers actually tell you
- How edge inference works (no GPU required)
- The difference between predictive and preventive maintenance

### Live Diagnosis
- MIRA nameplate photo → part lookup → fix
- Multi-fault: two alarms at once, AI prioritizes
- Night shift: AI handles fault at 2AM with no tech on floor

### Tech Stories
- The PLC that talked back
- Building alone for 18 months
- Why enterprise AI costs $500K (and why it doesn't have to)

### Off the Grid
- Factory firewall compliance walkthrough
- OSHA data sovereignty requirements
- Works during internet outage — 3-day offline test

---

## Filming Checklist

- [ ] **Cosmos Cookoff recording** — source for Weeks 1 Fri, 3 Mon (jam detection, Telegram overlay)
- [ ] **PLC b-roll** — ladder logic, register readout, wiring closeup (Weeks 2 Mon, 4 Mon)
- [ ] **Thermal / sensor reading** — motor temp climbing (Week 2 Fri)
- [ ] **Face-cam** — Weeks 2 Wed, 4 Wed (founder story)
- [ ] **Air-gap demo** — unplug ethernet, run diagnosis (Week 3 Fri)
- [ ] **Competitor price visual** — blurred quote screenshot (Week 1 Wed)
- [ ] **ROI graphic** — $40K downtime vs $30/device (Week 4 Fri)

---

## Distribution SOP

1. **Render** LinkedIn master via `shorts_pipeline.py render_short()`
2. **Review** against `REVIEW_CHECKLIST.md` (5 min human gate)
3. **Derive** all platform formats via `cross_post.py repurpose_short()`
4. **Upload** to YouTube via `youtube_uploader.py upload_short()` — scheduled Mon/Wed/Fri 9AM EST
5. **Post** LinkedIn natively (upload the file, not a YouTube link)
6. **Seed** relevant Reddit/Facebook communities with context post (not just a link)
7. **Monitor** via `analytics_reporter.py` — Sunday midnight auto-report to Telegram

---

*Last updated: 2026-04-07 | Owner: Mike Harper | Issues: FAC-18*
