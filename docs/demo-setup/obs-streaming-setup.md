# OBS Live Streaming Setup for FactoryLM Conveyor Demo
**Quick setup guide for 24/7 conveyor cam**

---

## PART 1: YouTube Live Setup (5 minutes)

### Step 1: Get Your Stream Key
1. Go to https://studio.youtube.com
2. Click **Create** → **Go live**
3. Select **Stream** (not Webcam)
4. Copy your **Stream key** (looks like: `xxxx-xxxx-xxxx-xxxx-xxxx`)
5. Also copy the **Stream URL**: `rtmp://a.rtmp.youtube.com/live2`

### Step 2: Configure OBS
1. Open OBS Studio
2. Go to **Settings** → **Stream**
3. Service: **YouTube - RTMPS**
4. Server: **Primary YouTube ingest server**
5. Stream Key: **Paste your key from Step 1**
6. Click **Apply** → **OK**

### Step 3: Test Stream
1. Click **Start Streaming** in OBS
2. Go back to YouTube Studio - you should see your feed
3. Click **Go Live** on YouTube when ready to publish

---

## PART 2: OBS WebSocket for Remote Control

OBS 28+ has WebSocket built-in on **port 4455**.

### Enable WebSocket in OBS
1. **Tools** → **WebSocket Server Settings**
2. Check **Enable WebSocket server**
3. Set a password (or leave blank for local only)
4. Default port: **4455**

### Remote Control Commands (Python example)
```python
# pip install obsws-python
import obsws_python as obs

# Connect to OBS
client = obs.ReqClient(host='100.83.251.23', port=4455, password='yourpassword')

# Start streaming
client.start_stream()

# Stop streaming
client.stop_stream()

# Get streaming status
status = client.get_stream_status()
print(f"Streaming: {status.output_active}")

# Switch scenes
client.set_current_program_scene("Conveyor Cam")
```

### From Jarvis VPS (via Tailscale)
```bash
# Travel laptop OBS
ssh hharp@100.83.251.23 'curl -s http://localhost:4455/...'

# Or use Python obsws-python from VPS
python3 -c "
import obsws_python as obs
client = obs.ReqClient(host='100.83.251.23', port=4455)
client.start_stream()
"
```

---

## PART 3: Scene Setup for Conveyor

### Recommended OBS Scenes

**Scene 1: "Conveyor Live"**
- Source: Webcam (pointed at conveyor)
- Overlay: FactoryLM logo (corner)
- Text: "Control via Telegram @JarvisMIO"

**Scene 2: "Split View"**
- Left: Physical conveyor webcam
- Right: Factory I/O simulation
- Overlay: Logo + control instructions

**Scene 3: "Full Factory I/O"**
- Window capture of Factory I/O
- For when physical conveyor is offline

---

## PART 4: 24/7 Streaming Tips

### Auto-restart on crash
```powershell
# Windows Task Scheduler or PowerShell loop
while ($true) {
    Start-Process "C:\Program Files\obs-studio\bin\64bit\obs64.exe" --startstreaming
    Start-Sleep -Seconds 60
}
```

### YouTube 24/7 Stream Settings
- YouTube allows up to 12-hour continuous streams
- For true 24/7: Use **Restream.io** or multiple rotating keys
- Or: Set up auto-restart every 11 hours

### Bandwidth Requirements
- 720p30: ~2.5-4 Mbps upload
- 1080p30: ~4-6 Mbps upload
- 1080p60: ~6-9 Mbps upload

---

## QUICK START TONIGHT

1. **YouTube Studio** → Go Live → Stream → Copy key
2. **OBS** → Settings → Stream → YouTube → Paste key
3. **OBS** → Tools → WebSocket Server → Enable
4. **OBS** → Start Streaming
5. **YouTube** → Go Live

**Test from VPS:**
```bash
ssh hharp@100.83.251.23 "powershell -Command 'Start-Process obs64.exe'"
```

---

## TELEGRAM INTEGRATION (Tomorrow)

Add to @JarvisMIO bot:
- `/stream start` - Start OBS streaming
- `/stream stop` - Stop streaming  
- `/stream status` - Check if live
- `/conveyor start` - Start conveyor + start stream

---

*Created: 2026-02-10 | FactoryLM Live Demo Setup*
