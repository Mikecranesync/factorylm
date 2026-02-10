# VFD Conveyor Wiring Diagram - With Mainline Contactor
**Updated: 2026-02-10 02:01 UTC**

## Mainline Contactor: Schneider Electric LC1D Series
- **Contact Rating:** 10A @ 600V AC max
- **Aux Contacts:** 2NO + 2NC (13-14, 43-44 NO / 21-22, 31-32 NC)
- **Coil Voltage:** CHECK CONTACTOR BODY (not on label)
- **Wire Size:** AWG 14-18 CU

---

## POWER DISTRIBUTION

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INCOMING POWER (220V 1PH)                         │
│                    From Dryer Outlet (NEMA 14-30)                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DISCONNECT SWITCH (30A)                           │
│                         SW-1                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    L1 ───────┼─────── L2
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              MAINLINE CONTACTOR (Schneider LC1D)                     │
│                                                                      │
│    COIL: A1 ←── PLC DO or Manual Switch                             │
│          A2 ←── Neutral/Common                                       │
│                                                                      │
│    POWER CONTACTS:                                                   │
│    L1 IN ──► 1 ──► 2 ──► L1 OUT (to VFD)                           │
│    L2 IN ──► 3 ──► 4 ──► L2 OUT (to VFD)                           │
│                                                                      │
│    AUX CONTACTS (for PLC feedback):                                  │
│    13-14 (NO) ──► PLC DI "Contactor Closed"                         │
│    21-22 (NC) ──► PLC DI "Contactor Open" (optional)                │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    L1 ───────┼─────── L2
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    VFD (GS11N-20P5)                                  │
│                                                                      │
│    INPUT:     L1 ──► L1 terminal                                    │
│               L2 ──► L2 terminal                                    │
│               GND ──► Ground terminal                                │
│                                                                      │
│    OUTPUT:    U (T1) ──► Motor Lead 1                               │
│               V (T2) ──► Motor Lead 2                               │
│               W (T3) ──► Motor Lead 3                               │
│               GND ──► Motor Frame Ground                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MOTOR (1/2 HP 3-Phase)                           │
│                    56C Frame, Inverter Duty                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## CONTROL WIRING (PLC to VFD + Contactor)

```
MICRO820 PLC                    MAINLINE CONTACTOR           VFD TERMINALS
┌──────────────┐               ┌─────────────────┐         ┌─────────────┐
│              │               │                 │         │             │
│  DO0 ────────┼───────────────┼──► A1 (Coil+)   │         │             │
│              │               │                 │         │             │
│  COM ────────┼───────────────┼──► A2 (Coil-)   │         │             │
│              │               │                 │         │             │
│  DI0 ◄───────┼───────────────┼─── 13 (NO aux)  │         │             │
│              │               │     14 ─► 24V   │         │             │
│              │               │                 │         │             │
│  DO1 ────────┼───────────────┼─────────────────┼─────────┼──► FWD      │
│              │               │                 │         │             │
│  DO2 ────────┼───────────────┼─────────────────┼─────────┼──► REV      │
│              │               │                 │         │             │
│  COM ────────┼───────────────┼─────────────────┼─────────┼──► DCM      │
│              │               │                 │         │             │
│  AO0 ────────┼───────────────┼─────────────────┼─────────┼──► VI       │
│              │               │                 │         │  (0-10V)    │
│  AGND ───────┼───────────────┼─────────────────┼─────────┼──► ACM      │
│              │               │                 │         │             │
│  DI1 ◄───────┼───────────────┼─────────────────┼─────────┼─── FA      │
│              │               │                 │         │  (Fault)    │
└──────────────┘               └─────────────────┘         └─────────────┘
```

---

## WIRING SEQUENCE (For Build)

### Step 1: Mainline Contactor
1. Mount contactor in enclosure near VFD
2. Wire L1/L2 from disconnect to contactor input (1, 3)
3. Wire contactor output (2, 4) to VFD L1/L2
4. Wire coil A1 to PLC DO0 (or manual switch for testing)
5. Wire coil A2 to common/neutral

### Step 2: VFD Power
1. Verify contactor output goes to VFD L1, L2
2. Wire ground from disconnect to VFD ground terminal
3. Wire VFD U, V, W to motor
4. Wire motor frame ground

### Step 3: Control Wiring
1. Wire PLC DO1 → VFD FWD terminal
2. Wire PLC DO2 → VFD REV terminal (optional)
3. Wire PLC COM → VFD DCM
4. Wire PLC AO0 → VFD VI (speed reference)
5. Wire PLC AGND → VFD ACM
6. Wire VFD fault relay → PLC DI1

### Step 4: Aux Contacts (Feedback)
1. Wire contactor 13-14 (NO) to PLC input for "contactor closed" status
2. Optional: Wire 21-22 (NC) for "contactor open" status

---

## SAFETY NOTES ⚠️

1. **Verify coil voltage** before powering contactor coil!
2. Contactor rated 10A - adequate for 1/2 HP motor (~3A)
3. Always test contactor operation before connecting motor
4. Use contactor for emergency stop capability

---

## I/O SUMMARY

| PLC Address | Function | Wired To |
|-------------|----------|----------|
| DO0 | Mainline Contactor | Contactor Coil A1 |
| DO1 | VFD Run Forward | VFD FWD |
| DO2 | VFD Run Reverse | VFD REV |
| AO0 | Speed Reference | VFD VI (0-10V) |
| DI0 | Contactor Status | Aux Contact 13-14 |
| DI1 | VFD Fault | VFD FA-FB |

---

*Generated by Jarvis Robot Army - 2026-02-10*
