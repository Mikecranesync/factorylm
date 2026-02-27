(* ============================================================
   From A to B — Factory I/O Scene
   Target: Allen-Bradley Micro 820 (CCW Structured Text)

   Modbus TCP Mapping:
     Coil 0  = Conveyor     (PLC → Factory I/O output)
     Coil 1  = Emitter      (PLC → Factory I/O output)
     Coil 2  = SensorStart  (Factory I/O → PLC input)
     Coil 3  = SensorEnd    (Factory I/O → PLC input)
     Coil 4  = RunCommand   (Remote trigger via Modbus write)
     Reg 100 = ItemCount    (Items that reached the end)

   Logic:
     - RunCommand=TRUE  → Conveyor ON, Emitter ON
     - RunCommand=FALSE → Conveyor OFF, Emitter OFF
     - SensorEnd rising edge → ItemCount := ItemCount + 1
   ============================================================ *)

(* --- Variable Declarations (create these as Global Variables in CCW) ---

   VAR_GLOBAL
     Conveyor    : BOOL := FALSE;   (* Coil 0 — drives the belt *)
     Emitter     : BOOL := FALSE;   (* Coil 1 — spawns items   *)
     SensorStart : BOOL := FALSE;   (* Coil 2 — entry sensor   *)
     SensorEnd   : BOOL := FALSE;   (* Coil 3 — exit sensor    *)
     RunCommand  : BOOL := FALSE;   (* Coil 4 — remote start   *)
     ItemCount   : INT  := 0;       (* Reg 100 — item counter  *)
   END_VAR
*)

(* Local variable for edge detection — declare in MainProgram local vars *)
(* VAR
     SensorEnd_Prev : BOOL := FALSE;
   END_VAR
*)

(* ---- Main Logic ---- *)

(* Drive conveyor and emitter based on RunCommand *)
Conveyor := RunCommand;
Emitter  := RunCommand;

(* Rising-edge detection on SensorEnd: count items arriving at exit *)
IF SensorEnd AND NOT SensorEnd_Prev THEN
  ItemCount := ItemCount + 1;
END_IF;

(* Store previous sensor state for next scan *)
SensorEnd_Prev := SensorEnd;
