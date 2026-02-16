# Process 001: Doppler API Key Management Setup

> 📍 **Training Data Document** — This process was built through natural language programming and documented for AI training purposes.

## Metadata

| Field | Value |
|-------|-------|
| **Process ID** | 001 |
| **Date** | 2026-02-04 |
| **Initiated By** | Mike (voice via Telegram) |
| **Executed By** | Clawdbot/Claude |
| **Status** | 🔄 In Progress |

---

## Input (What Mike Said)

> "I need this in my life really bad. The APIs are getting out of control and I need a version that you can control. The easiest, costs me the least, and is most effective."

> "I'd like to set up Doppler using the photograph process... document as many processes as possible going forward because this may be valuable training data."

---

## Analysis (What I Understood)

**Problem:** API keys scattered across multiple .env files, no central management, security risk, hard to rotate.

**Requirements:**
- Easy to use
- Low/no cost
- Effective (solves the problem)
- Controllable (programmatic access)

**Solution Selected:** Doppler (free tier, CLI, no infrastructure to maintain)

---

## Process (Steps Taken)

### Step 1: Research Options
```
Evaluated: HashiCorp Vault, Doppler, Infisical, AWS Secrets Manager, Unkey
Selected: Doppler (best fit for requirements)
```

### Step 2: Install Doppler CLI
```bash
# Add Doppler GPG key and repo
curl -sLf --retry 3 --tlsv1.2 --proto "=https" \
  'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | \
  gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] \
  https://packages.doppler.com/public/cli/deb/debian any-version main" | \
  tee /etc/apt/sources.list.d/doppler-cli.list

apt-get update && apt-get install -y doppler
```

**Result:** Doppler CLI v3.75.2 installed

### Step 3: User Account Creation (Pending)
```
Action Required: Mike signs up at https://doppler.com
Creates project: factorylm
```

### Step 4: Authenticate CLI (Pending)
```bash
doppler login
# Opens browser for OAuth
# Saves token to ~/.doppler/.doppler.yaml
```

### Step 5: Configure Project (Pending)
```bash
doppler setup
# Select project: factorylm
# Select config: dev/staging/prod
```

### Step 6: Migrate Existing Keys (Pending)
```bash
# Export from existing .env
cat /opt/master_of_puppets/.env

# Import to Doppler
doppler secrets set KEY1=value1 KEY2=value2 ...
```

### Step 7: Update Code (Pending)
```bash
# Before (dotenv)
python -c "from dotenv import load_dotenv; load_dotenv()"

# After (doppler)
doppler run -- python your_script.py
```

---

## Output (What Was Produced)

- [x] Doppler CLI installed on VPS
- [x] Documentation created
- [ ] Doppler account created
- [ ] Project configured
- [ ] Keys migrated
- [ ] Code updated

---

## Training Data Format

```json
{
  "id": "process-001",
  "timestamp": "2026-02-04T16:00:00Z",
  "input": {
    "type": "natural_language",
    "source": "telegram_voice",
    "text": "I need API key management, easiest and cheapest solution"
  },
  "reasoning": {
    "problem": "scattered API keys",
    "requirements": ["easy", "cheap", "effective"],
    "options_evaluated": ["vault", "doppler", "infisical", "aws"],
    "selection": "doppler",
    "rationale": "free tier, no infrastructure, good CLI"
  },
  "actions": [
    {"type": "research", "result": "doppler selected"},
    {"type": "install", "command": "apt install doppler", "result": "success"},
    {"type": "document", "result": "this file"}
  ],
  "outcome": {
    "status": "in_progress",
    "blocking": "user account creation"
  }
}
```

---

## Lessons Learned

1. Always check for existing solutions before building custom
2. Free tiers often sufficient for early-stage startups
3. CLI tools > web dashboards for automation
4. Document as you go — future you will thank present you

---

*This document is part of Mike's Brain training data corpus. Every process built through natural language programming is valuable.*
