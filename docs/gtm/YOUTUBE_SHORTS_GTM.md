# FactoryLM GTM Strategy — Video Content Engine

**Version:** 1.0
**Date:** 2026-04-07
**Scope:** Full go-to-market via video content — platform strategy, production pipeline, distribution, analytics feedback loop.

---

## Positioning (Locked)

| Element | Value |
|---------|-------|
| One-liner | "AI that lives inside your PLC — for $30/device, not $500K" |
| Category | Agent OS for factory maintenance |
| ICP | SMB manufacturers 50–500 employees with Allen-Bradley PLCs |
| Anti-positioning | Not Augury. Not Fiix. Not another dashboard. Not a chatbot. |
| Price anchor | $30/device/month vs. $500K+ enterprise deployments |

**The category matters.** "Predictive maintenance AI" is crowded and expensive to compete in.
"Agent OS for factory maintenance" is new. Name the category, own the category.

---

## ICP Profile

**Primary:** Maintenance Director / Maintenance Manager
- 15–30 year career, seen every vendor pitch
- Responsible for uptime, not IT
- Judges tools by: does it work when I need it, does it fit in my budget, will my techs use it
- LinkedIn daily for professional content, YouTube for "how to fix X" searches
- Does NOT watch TikTok for work purchasing decisions

**Secondary:** Plant Manager / Operations Manager
- Cares about cost and uptime numbers, not technical depth
- Won't watch a 10-minute tutorial — will watch a 60s proof of ROI

**Tertiary:** PLC Technician / Maintenance Technician
- Influencer, not buyer — but they greenlight or kill tools
- Respects technical depth; will reject anything that "dumbs down" the domain
- Use "outsider engineer test": a competent engineer unfamiliar with FactoryLM should understand the value without feeling talked down to

---

## Platform Strategy

### Priority Order (ICP-driven)

| Priority | Platform | Format | Why |
|----------|----------|--------|-----|
| **1 — Primary** | LinkedIn native video | 1–3 min, 9:16 or 16:9 | ICP is here daily; native video gets 3× organic reach vs. link posts |
| **2 — Search** | YouTube long-form | 5–15 min | High-intent searches: "Allen-Bradley VFD E005 fix", "conveyor jam detection PLC" |
| **3 — Discovery** | YouTube Shorts | 60s | Algorithm top-of-funnel; seeding for search ranking |
| **4 — Awareness** | TikTok / Instagram Reels | 60s | Low ICP conversion; brand awareness only |

**Production model: Shoot once, derive everything.**
1. Produce the LinkedIn master (1–3 min, captions burned in)
2. `cross_post.py` derives: YouTube Short (60s cut), TikTok, Reels, Twitter/X
3. `shorts_pipeline.py` is the derivative formatter — LinkedIn video is the source of truth

### What NOT to Do
- Do not optimize for YouTube Shorts virality at the expense of ICP relevance
- Do not use 11-year-old comprehension as your test. Your buyer knows what a VFD overcurrent fault is.
- Do not post "link in bio" on LinkedIn. Native video only. Links get suppressed by the algorithm.
- Do not post the same caption on every platform. LinkedIn needs context and teaches something.

---

## Content Series Architecture

### 6 Series, 1 Mission

Every piece of content answers one question from the ICP's perspective:
**"Why should I trust FactoryLM with my plant?"**

| Series | ICP Question Answered | Hook Type | Proof Required |
|--------|----------------------|-----------|----------------|
| Before It Breaks | "Will it actually catch faults I'm missing?" | Fault alarm audio | Real hardware demo |
| $500K vs $30 | "Is the ROI real?" | Price shock visual | Competitor comparison + real cost |
| Inside the Machine | "How does it actually work?" | Technical curiosity | System architecture explanation |
| Live Diagnosis | "Does it work in the real world?" | Uncut demo recording | Unedited Telegram conversation |
| Tech Stories | "Can I trust the founder?" | Face-cam authenticity | Founder's actual experience |
| Off the Grid | "What about our firewall / data security?" | Air-gap proof | Live disconnected demo |

### Topic Selection Principles
1. **Problem-led, not product-led.** Start with the fault, the cost, the 3AM call. MIRA is the resolution.
2. **Real hardware only.** Every demo series claim requires footage of the actual hardware responding.
3. **One claim per video.** Shorts that try to prove two things prove neither.
4. **Teach something.** Every post should leave the viewer slightly more informed, even if they don't buy.

---

## Launch Seeding Strategy (Phase 0 — Before Algorithm Helps)

The algorithm needs signal before it distributes. Build that signal manually first.

| Channel | Action | Target Audience | Rule |
|---------|--------|-----------------|------|
| LinkedIn personal | Post each video natively, add technical context | Maintenance directors, plant managers | One post per video, teach something |
| Allen-Bradley Users Group (Facebook, 40K+) | Share "Before It Breaks" VFD episode with context | AB-specific ICP | No spam — add 2–3 sentences of technical context |
| r/PLC (Reddit, 35K) | Post with full technical explanation, video as proof | PLC engineers | Post in the right weekly thread; answer questions in comments |
| r/industrialautomation (Reddit) | Same approach | Automation engineers | |
| r/maintenance (Reddit) | Problem-led framing, not product pitch | Maintenance techs | |
| Direct email outreach | 1 video per week to any prior contacts / warm leads | Warm leads | Not mass email; personal note |

**Goal:** 50+ genuine views on each video in Week 1 before algorithm picks it up.

---

## Full Funnel Architecture

```
LinkedIn native video (1–3 min) ──────────────────────────────┐
  │ Comment CTA: "Full demo in bio"                            │
  ▼                                                            │
YouTube long-form (5–15 min, organic search)                  │ Algorithm
  │ End card: "Free demo → factorylm.com"                      │ seeding
  ▼                                                            │
YouTube Shorts + TikTok + Reels (60s discovery) ──────────────┘
  │ Bio link / CTA
  ▼
Landing page: factorylm.com
  │ Hero video + "Book a Demo" CTA
  ▼
Calendly: calendly.com/mike-cranesync/30min
  │ 30-min discovery call
  ▼
Beta pilot: $30/device × 20 devices = $600/mo
  │ Success → expansion
  ▼
Referral: maintenance director → peer network
```

**Key conversion principle:** Every piece of content serves exactly one step in this funnel.
LinkedIn video → awareness/trust. YouTube long-form → intent/consideration. Calendly → conversion.

---

## Automated Production Pipeline

### Tools Built (see each file for implementation details)

| Tool | Path | Purpose |
|------|------|---------|
| `shorts_pipeline.py` | `factorylm/tools/shorts_pipeline.py` | LinkedIn-first video production: crop, captions, hook card, end card |
| `thumbnail_generator.py` | `factorylm/tools/thumbnail_generator.py` | 1280×720 series thumbnails via Pillow |
| `youtube_uploader.py` | `factorylm/tools/youtube_uploader.py` | YouTube Data API v3 upload + scheduling |
| `cross_post.py` | `factorylm/tools/cross_post.py` | One render → 5 platform derivatives |
| `analytics_reporter.py` | `factorylm/tools/analytics_reporter.py` | Weekly analytics + self-improving calendar |

### Secrets Required (Doppler: factorylm/prd)
- `YOUTUBE_CLIENT_ID` — OAuth client ID
- `YOUTUBE_CLIENT_SECRET` — OAuth client secret
- `YOUTUBE_REFRESH_TOKEN` — Long-lived refresh token
- `YOUTUBE_CHANNEL_ID` — Channel ID (UCxxxxxx)

---

## Analytics & Feedback Loop

### Weekly KPIs

| Metric | Source | Week 4 Target |
|--------|--------|---------------|
| Views per Short | YouTube Analytics | > 500 |
| Click-through rate | YouTube Analytics | > 4% |
| Watch completion | YouTube Analytics | > 70% |
| Calendly clicks | UTM params | > 10/week |
| Demo calls booked | Calendly | > 3/week |
| Cost per demo | Organic = $0 | $0 |

### Self-Improving Calendar

`analytics_reporter.py` runs every Sunday midnight (Cowork task on ALPHA):
1. Pull YouTube Analytics for the past 7 days
2. Rank all 6 series by watch completion rate
3. Top 2 series get 2 slots next week; bottom 1 series gets 1 slot
4. Within each series, pick next uncovered topic from `TOPIC_BACKLOG`
5. Generate Mon/Wed/Fri schedule → post to Telegram `#content-analytics`

High completion rate → more slots → algorithm compounds → not just self-reporting.

---

## What "Done" Looks Like

Evidence-only. No video is "done" until:

1. `shorts_pipeline.py render_short()` produces a 1080×1920, 58–60s MP4
2. `REVIEW_CHECKLIST.md` all boxes checked (technical + human)
3. Thumbnail uploaded (not YouTube auto-generated)
4. Scheduled Mon/Wed/Fri 9AM EST
5. LinkedIn native post written (caption teaches something)
6. First Short live and showing view count in YouTube Studio

---

*Last updated: 2026-04-07 | Owner: Mike Harper | Issues: FAC-18, FAC-19*
