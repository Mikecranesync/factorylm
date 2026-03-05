(* =========================================================
   MICRO 820 CONTROL PROGRAM — FactoryLM Demo
   =========================================================
   Hardware: 2080-LC20-20QWB
   Inputs:   DI_00-DI_04 (button station)
   Outputs:  DO_00, DO_01, DO_03 (LED indicators)
   Scene:    "From A to B" (Factory I/O)
   Network:  Ethernet 192.168.1.100, Modbus TCP port 502
   =========================================================

   IMPORTANT: All variables below must exist in Global Variables.
   See global_variables.txt for the full list.
   Do NOT declare them locally in a VAR...END_VAR block here.
   ========================================================= *)


(* =========================================================
   SECTION 1: READ PHYSICAL INPUTS
   Map embedded I/O to readable aliases
   ========================================================= *)

(* 3-position selector switch *)
(* LEFT:   DI_00=0, DI_03=0 *)
(* CENTER: DI_00=1, DI_03=0 *)
(* RIGHT:  DI_00=1, DI_03=1 *)

(* E-stop contacts *)
(* Released: DI_01=0, DI_02=1 *)
(* Pressed:  DI_01=1, DI_02=0 *)


(* =========================================================
   SECTION 2: E-STOP SUPERVISION
   Validate NC/NO contacts for proper operation
   ========================================================= *)

(* E-stop is healthy when contacts are complementary *)
(* Fault if both contacts read the same — wiring problem *)
(* E-stop active when NO=1 AND NC=0 *)

IF (_IO_EM_DI_02 XOR _IO_EM_DI_01) THEN
    (* Contacts are complementary — healthy *)
    IF _IO_EM_DI_01 AND NOT _IO_EM_DI_02 THEN
        (* E-stop pressed *)
        e_stop_active := TRUE;
    ELSE
        e_stop_active := FALSE;
    END_IF;
    fault_alarm := FALSE;
ELSE
    (* NC = NO — wiring fault *)
    fault_alarm := TRUE;
    e_stop_active := TRUE;
END_IF;


(* =========================================================
   SECTION 3: MODE SELECTION
   Decode 3-position selector switch
   ========================================================= *)

(* Mode_Off:    LEFT   — DI_00=0, DI_03=0 *)
(* Mode_Manual: CENTER — DI_00=1, DI_03=0 *)
(* Mode_Auto:   RIGHT  — DI_00=1, DI_03=1 *)


(* =========================================================
   SECTION 4: RUN CONTROL
   Pushbutton latch with E-stop reset
   ========================================================= *)

(* Rising edge detection on pushbutton DI_04 *)
IF _IO_EM_DI_04 AND NOT prev_button3 THEN
    (* Button just pressed *)

    IF NOT _IO_EM_DI_00 AND NOT _IO_EM_DI_03 THEN
        (* OFF mode — do nothing *)
        ;
    ELSIF _IO_EM_DI_00 AND NOT _IO_EM_DI_03 THEN
        (* MANUAL mode — toggle run *)
        RunCommand := NOT RunCommand;
    ELSIF _IO_EM_DI_00 AND _IO_EM_DI_03 THEN
        (* AUTO mode — start, stop only via E-stop *)
        RunCommand := TRUE;
    END_IF;
END_IF;

(* Save button state for next scan *)
prev_button3 := _IO_EM_DI_04;

(* E-stop or OFF mode kills run command immediately *)
IF e_stop_active OR fault_alarm OR (NOT _IO_EM_DI_00 AND NOT _IO_EM_DI_03) THEN
    RunCommand := FALSE;
END_IF;


(* =========================================================
   SECTION 5: "FROM A TO B" SCENE LOGIC
   Conveyor + Emitter driven by RunCommand
   Item counter on SensorEnd rising edge
   ========================================================= *)

Conveyor := RunCommand;
Emitter  := RunCommand;

(* Count items arriving at exit sensor *)
IF SensorEnd AND NOT SensorEnd_Prev THEN
    ItemCount := ItemCount + 1;
END_IF;
SensorEnd_Prev := SensorEnd;


(* =========================================================
   SECTION 6: LED INDICATORS
   Map program state to physical outputs
   ========================================================= *)

(* Power LED: ON when not in OFF mode and E-stop OK *)
_IO_EM_DO_00 := _IO_EM_DI_00 AND NOT fault_alarm AND NOT e_stop_active;

(* Fault LED: ON when E-stop active or circuit fault *)
_IO_EM_DO_01 := e_stop_active OR fault_alarm;

(* Aux LED: ON when running *)
_IO_EM_DO_03 := RunCommand AND NOT fault_alarm;

(* All-LEDs diagnostic mode — override individual logic *)
IF all_leds_on THEN
    _IO_EM_DO_00 := TRUE;
    _IO_EM_DO_01 := TRUE;
    _IO_EM_DO_03 := TRUE;
END_IF;


(* =========================================================
   SECTION 7: MODBUS STATUS VARIABLES
   Expose state to LLM / pylogix via coils
   ========================================================= *)

motor_running    := RunCommand;
motor_stopped    := NOT RunCommand;
conveyor_running := RunCommand AND _IO_EM_DI_00 AND _IO_EM_DI_03;  (* Running in AUTO *)
sensor_1_active  := _IO_EM_DI_00 AND NOT _IO_EM_DI_03;            (* Manual mode *)
sensor_2_active  := _IO_EM_DI_00 AND _IO_EM_DI_03;                (* Auto mode *)
(* e_stop_active and fault_alarm already set in Section 2 *)
