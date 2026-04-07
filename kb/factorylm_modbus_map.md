# FactoryLM Modbus Register Map

## Micro820 PLC — 192.168.1.100, Modbus TCP port 502

### Holding Registers

| Register | Name         | Description                                                  |
|----------|-------------|--------------------------------------------------------------|
| HR100    | motor_speed | Current motor speed from GS10 VFD. Range 0–60 Hz (scaled). |
| HR101    | current     | Motor current draw in amps. High = overload or jam.         |
| HR102    | temp        | GS10 VFD drive temperature in °C. Overtemp = fault.        |

### Coils

| Register | Name        | Description                                                      |
|----------|-------------|------------------------------------------------------------------|
| Coil0    | motor_run   | Write 1 to start motor. Check Coil2 (fault) clear first.       |
| Coil1    | motor_stop  | Pulse to 1 for controlled stop. Latches off when complete.      |
| Coil2    | fault       | Set on VFD fault. Must clear before restart. Write 0 to reset. |

## GS10 VFD (Variable Frequency Drive)

- Interface: Modbus RTU RS-485 via PLC bridge (no direct IP)
- Accessed through Micro820 at 192.168.1.100:502
- Controls: Conveyor motor in Factory IO "Sorting by Height" scene
- Speed register: HR100
- Current register: HR101
- Temperature register: HR102
- Fault coil: Coil2

## Factory IO Scene: Sorting by Height

- PLC: Allen-Bradley Micro820 (192.168.1.100)
- VFD: GS10 on RS-485 bus
- Conveyor controlled by motor_run (Coil0) and motor_stop (Coil1)
- Monitor motor_speed (HR100), current (HR101), temp (HR102)
- Fault handling: Read Coil2, resolve cause, write 0 to reset

## Common Fault Conditions

- **Overcurrent**: HR101 elevated → check for jams on conveyor belt
- **Overtemperature**: HR102 elevated → check VFD ventilation
- **Communication loss**: Coil2 set, HR100/101/102 stuck → check RS-485 cable
- **Fault reset procedure**: Fix root cause → Write 0 to Coil2 → Write 1 to Coil0
