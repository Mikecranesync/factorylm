# CCW Setup Guide — Novice Step-by-Step

## What We're Doing
Making your Micro820 PLC talk to pi-factory over Ethernet.
Your ST program is already written. Now we configure CCW so the Pi can read your tags.

> **Why can't we auto-generate this?** CCW project files (.ccwsln) are proprietary binary format. No tool outside of CCW can create them. The only way is through the CCW GUI.

---

## PART A: Move Variables to Global Scope

pylogix can only see **Global Variables**. Your `_IO_EM_*` tags are already global.
These custom ones need to be moved: `prev_button3`, `all_leds_on`, `vfd_write_trig`, `vfd_msg_done`, `read_data`

### A1. Open Global Variables
1. Look at the **left panel** in CCW — this is the "Project Organizer"
2. You'll see your controller name with a tree of items underneath
3. Find and **double-click** on **"Global Variables"** in that tree
4. A spreadsheet-like table opens in the main area

**What you should see:** A table with columns like Name, Data Type, Initial Value.
The `_IO_EM_DI_00`, `_IO_EM_DO_00` etc. should already be listed here.

### A2. Check if your custom variables are already there
1. Scroll through the Global Variables table
2. Look for: `prev_button3`, `all_leds_on`, `vfd_write_trig`, `vfd_msg_done`, `read_data`
3. **If they're ALL already there** — skip to PART B
4. **If any are missing** — continue to A3

### A3. Add missing variables one at a time
For each missing variable, do this:

1. Click on the **first empty row** at the bottom of the Global Variables table
2. In the **Name** column, type the variable name exactly (e.g., `prev_button3`)
3. In the **Data Type** column, select the correct type:

| Variable | Data Type |
|----------|-----------|
| `prev_button3` | BOOL |
| `all_leds_on` | BOOL |
| `vfd_write_trig` | BOOL |
| `vfd_msg_done` | BOOL |
| `read_data` | ARRAY[0..3] OF INT |

4. Leave **Initial Value** as the default (FALSE for BOOL, 0 for INT)
5. Press **Enter** to confirm the row
6. Repeat for the next missing variable

**Note on `read_data`:** This is your VFD register buffer. If CCW doesn't let you type `ARRAY[0..3] OF INT` directly, click the "..." button next to the Data Type cell to open the type picker, then select Array, base type INT, dimension 0 to 3.

### A4. Update your ST program to use the globals
1. In the Project Organizer (left panel), find and **double-click** your program (under "Programs")
2. Your ST code opens in the editor
3. If your variables were previously declared as **local variables** at the top of the program (inside a `VAR ... END_VAR` block), **delete those local declarations** for the ones you just added as globals
4. The code that *uses* the variables stays the same — only the declarations move
5. CCW will now resolve those names from Global Variables instead

---

## PART B: Paste ST Program

### B1. Open (or create) your program
1. In the Project Organizer, expand **"Programs"**
2. If `MainProgram` already exists, **double-click** it
3. If no program exists: right-click **"Programs"** > **Add** > **Program**, name it `MainProgram`

### B2. Paste the code
1. Select all existing code in the editor (Ctrl+A)
2. Delete it (Delete key)
3. Open the file `from_a_to_b.st` from this directory in a text editor
4. Copy the entire contents (Ctrl+A, Ctrl+C)
5. Paste into the CCW ST editor (Ctrl+V)

### B3. Quick sanity check
- Scroll through the code — you should see sections for E-Stop, Mode Selection, Run Control, Scene Logic, LED Indicators, and Modbus Status
- Variable names should appear in **blue** or a different color if CCW recognizes them

---

## PART C: Set Static IP Address

### C1. Open Ethernet configuration
1. In the **Project Organizer** (left panel), look for your controller name at the top of the tree
2. Click the **arrow/triangle** next to it to expand it (if not already expanded)
3. You should see items like "Ethernet", "Embedded I/O", "Programs", etc.
4. **Double-click** on **"Ethernet"**
5. The Ethernet configuration page opens in the main area

### C2. Set the IP address
1. Find the **IP Address** field — type: `192.168.1.100`
2. Find the **Subnet Mask** field — type: `255.255.255.0`
3. Find the **Gateway** field — type: `192.168.1.1`
4. Find the **DHCP** checkbox or dropdown — **uncheck it** (or set to "Static")
5. The page should now show Static mode with your IP filled in

---

## PART D: Build, Download, and Run

### D1. Build the project
1. Go to the top menu bar
2. Click **Build** (or press F7)
3. Look at the **Output** window at the bottom of CCW
4. Wait for it to say **"Build succeeded"** with 0 errors
5. **If there are errors:** Read the error messages. Most common issue is a variable name mismatch between your ST code and the Global Variables table. Fix and rebuild.

### D2. Connect to the PLC (if not already connected)
1. Go to the top menu bar
2. Click **Controller** > **Connect** (or look for a plug icon in the toolbar)
3. CCW should find your PLC over USB
4. If prompted to select a connection, choose the USB one
5. Wait for the status bar to show "Connected" or "Online"

### D3. Download to the PLC
1. Go to the top menu bar
2. Click **Controller** > **Download**
3. A dialog may pop up asking to confirm — click **Yes** or **Download**
4. Wait for the download progress to finish
5. The Output window should say download succeeded

### D4. Switch to Run mode
1. Go to the top menu bar
2. Click **Controller** > **Run**
3. A confirmation dialog may appear — click **Yes**
4. **Watch the PLC hardware:** The RUN LED should change from **flashing green** to **solid green**

### D5. Verify inside CCW before unplugging
1. Look at the status bar at the bottom of CCW — it should say "Run" mode
2. Go back to the Ethernet config (double-click "Ethernet" in Project Organizer)
3. Confirm the IP shows `192.168.1.100`
4. Go to **Global Variables** — you should see your variables updating in real-time if you're in Online Monitor mode

---

## PART E: Ping Test (Still on CCW Laptop)

### E1. Open Command Prompt
1. Press **Windows key + R**
2. Type `cmd` and press **Enter**

### E2. Ping the PLC
```
ping 192.168.1.100
```
- **Good result:** "Reply from 192.168.1.100" four times
- **Bad result:** "Request timed out" — check your Ethernet cable is plugged into the PLC's Ethernet port (not USB), and both ends are connected

**Important:** You need an Ethernet cable from the CCW laptop to the PLC for this ping. If you've only been using USB, plug in Ethernet now.

---

## PART F: Connect Pi-Factory

### F1. Wire it up
Connect an Ethernet cable from the **Micro820's Ethernet port** to the same network switch that pi-factory is on.
If going direct (no switch), connect Ethernet directly from PLC to pi-factory.

### F2. Verify pi-factory subnet
Pi-factory needs an IP in `192.168.1.x` to talk to the PLC at `192.168.1.100`.
```bash
ssh pi@pi-factory.local "hostname -I"
```
If output shows `192.168.1.something` — you're good.
If it shows a different range (like `10.x.x.x`), configure pi-factory's network.

### F3. Ping from pi-factory
```bash
ssh pi@pi-factory.local "ping -c 3 192.168.1.100"
```
You need "3 packets received" before continuing.

### F4. Run the live reader
```bash
ssh pi@pi-factory.local \
  "~/factorylm-cosmos-cookoff/.venv/bin/python3 \
   ~/factorylm-cosmos-cookoff/tools/plc_live_reader.py \
   --host 192.168.1.100"
```

**Healthy output:** A list of tag names (including `all_leds_on`, `prev_button3`, `_IO_EM_DI_00`, etc.) with TRUE/FALSE or number values.

**If the tag list is empty:**
- Variables are still local, not global → redo PART A
- PLC is not in Run mode → redo D4

---

## Troubleshooting

| What You See | What It Means | What To Do |
|-------------|--------------|------------|
| RUN LED flashing green | PLC is in Program mode | Do step D4 (Controller > Run) |
| RUN LED solid green | PLC is running normally | Good — continue |
| RUN LED red | PLC has a fault | Check CCW for fault details, fix and re-download |
| Ping says "timed out" | No network path to PLC | Check cable, check IP config, check subnet |
| pylogix returns empty tags | Variables not global | Redo PART A, re-download |
| "Connection refused" error | Very rare on Micro820 | Check if firewall on Pi is blocking port 44818 |
| Build fails with errors | Code/variable mismatch | Read error messages, fix variable names/types |

---

## Global Variables Reference

See `global_variables.txt` in this directory for the full copy-paste-ready table.
