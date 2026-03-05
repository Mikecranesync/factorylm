PROGRAM Prog2
  (* ================================================================ *)
  (* FactoryLM — Micro820 Complete Program v1.6                       *)
  (* PLC: 2080-LC20-20QBB  |  Target IP: 192.168.1.100               *)
  (* v1.5 fix: FB calls once per scan outside CASE                    *)
  (* v1.6 fix: VAR block for internal-only variables (no GUI needed)  *)
  (* ================================================================ *)

  VAR
    SensorEnd_Prev  : BOOL := FALSE;  (* rising edge helper *)
    button_rising   : BOOL := FALSE;  (* pushbutton edge    *)
    prev_button3    : BOOL := FALSE;  (* previous DI_04     *)
    auto_mode       : BOOL := FALSE;  (* selector AUTO      *)
    manual_mode     : BOOL := FALSE;  (* selector MANUAL    *)
    off_mode        : BOOL := FALSE;  (* selector OFF       *)
  END_VAR

  (* ================================================================ *)
  (* SECTION 1 — E-STOP SUPERVISION (highest priority)               *)
  (* ================================================================ *)
  IF (_IO_EM_DI_01 XOR _IO_EM_DI_02) THEN
    IF _IO_EM_DI_01 AND NOT _IO_EM_DI_02 THEN
      e_stop_active := TRUE;
    ELSE
      e_stop_active := FALSE;
    END_IF;
  ELSE
    fault_alarm := TRUE;
    e_stop_active := TRUE;
  END_IF;

  (* ================================================================ *)
  (* SECTION 2 — PANEL I/O MAPPING                                   *)
  (* ================================================================ *)
  sensor_1_active := _IO_EM_DI_05;
  sensor_2_active := _IO_EM_DI_06;
  auto_mode := _IO_EM_DI_00 AND _IO_EM_DI_03;
  manual_mode := _IO_EM_DI_00 AND NOT _IO_EM_DI_03;
  off_mode := NOT _IO_EM_DI_00;
  button_rising := _IO_EM_DI_04 AND NOT prev_button3;
  prev_button3 := _IO_EM_DI_04;

  (* ================================================================ *)
  (* SECTION 3 — CONVEYOR STATE MACHINE                              *)
  (* NOTE: No FB calls inside CASE — timers called once after END_CASE *)
  (* ================================================================ *)
  CASE conv_state OF

    0: (* IDLE *)
      motor_running := FALSE;
      conveyor_running := FALSE;
      _IO_EM_DO_03 := FALSE;
      motor_speed := 0;
      IF button_rising AND NOT off_mode
         AND NOT e_stop_active AND NOT fault_alarm THEN
        conv_state := 1;
      END_IF;

    1: (* STARTING *)
      motor_running := TRUE;
      _IO_EM_DO_03 := TRUE;
      IF e_stop_active OR fault_alarm THEN
        conv_state := 4;
      ELSIF start_timer.Q THEN
        conveyor_running := TRUE;
        conv_state := 2;
      END_IF;

    2: (* RUNNING *)
      motor_running := TRUE;
      conveyor_running := TRUE;
      _IO_EM_DO_03 := TRUE;
      IF e_stop_active OR fault_alarm THEN
        conv_state := 4;
      ELSIF off_mode THEN
        conv_state := 3;
      ELSIF manual_mode AND button_rising THEN
        conv_state := 3;
      END_IF;
      IF sensor_2_active AND NOT SensorEnd_Prev THEN
        item_count := item_count + 1;
      END_IF;
      SensorEnd_Prev := sensor_2_active;
      motor_speed := conveyor_speed_cmd;
      _IO_EM_AO_00 := motor_speed;

    3: (* STOPPING *)
      motor_running := FALSE;
      motor_speed := 0;
      _IO_EM_AO_00 := 0;
      IF e_stop_active OR fault_alarm THEN
        conv_state := 4;
      ELSIF stop_timer.Q THEN
        conveyor_running := FALSE;
        _IO_EM_DO_03 := FALSE;
        conv_state := 0;
      END_IF;

    4: (* FAULT *)
      motor_running := FALSE;
      conveyor_running := FALSE;
      _IO_EM_DO_03 := FALSE;
      motor_speed := 0;
      _IO_EM_AO_00 := 0;
      IF e_stop_active THEN
        error_code := 6;
      ELSIF fault_alarm THEN
        error_code := 7;
      END_IF;
      IF button_rising AND NOT e_stop_active AND NOT off_mode THEN
        fault_alarm := FALSE;
        error_code := 0;
        conv_state := 0;
      END_IF;

  ELSE
    conv_state := 0;
  END_CASE;

  (* ================================================================ *)
  (* TIMER CALLS — called once per scan outside CASE block            *)
  (* ================================================================ *)
  start_timer(IN := (conv_state = 1), PT := T#3000ms);
  stop_timer(IN := (conv_state = 3), PT := T#2000ms);

  (* ================================================================ *)
  (* SECTION 4 — LED INDICATORS                                      *)
  (* ================================================================ *)
  IF ALL_LEDS_ON THEN
    _IO_EM_DO_00 := TRUE;
    _IO_EM_DO_01 := TRUE;
    _IO_EM_DO_02 := TRUE;
  ELSE
    _IO_EM_DO_00 := NOT off_mode AND NOT e_stop_active;
    _IO_EM_DO_01 := e_stop_active OR fault_alarm;
    _IO_EM_DO_02 := conveyor_running AND NOT fault_alarm;
  END_IF;

  (* ================================================================ *)
  (* SECTION 5 — VFD MODBUS RTU POLLING                              *)
  (* Syntax verified against real working Prog2.stf                   *)
  (* ================================================================ *)
  read_local_cfg.Channel := 2;
  read_local_cfg.TriggerType := 0;
  read_local_cfg.Cmd := 3;
  read_local_cfg.ElementCnt := 4;
  read_target_cfg.Addr := 8451;
  read_target_cfg.Node := 1;

  vfd_poll_timer(IN := NOT vfd_write_trig, PT := T#1000ms);

  IF vfd_poll_timer.Q AND NOT vfd_write_trig THEN
    vfd_write_trig := TRUE;
    vfd_msg_done := FALSE;
  END_IF;

  mb_read_status(IN := vfd_write_trig, LocalCfg := read_local_cfg,
                 TargetCfg := read_target_cfg, LocalAddr := read_data);

  IF vfd_write_trig AND NOT vfd_msg_done THEN
    IF mb_read_status.Q THEN
      vfd_frequency := read_data(1);
      vfd_current := read_data(2);
      vfd_dc_bus := read_data(3);
      vfd_voltage := read_data(4);
      vfd_comm_ok := TRUE;
      vfd_comm_err := FALSE;
      vfd_msg_done := TRUE;
      vfd_write_trig := FALSE;
    END_IF;
    IF mb_read_status.Error THEN
      vfd_comm_ok := FALSE;
      vfd_comm_err := TRUE;
      vfd_fault_code := error_code;
      vfd_msg_done := TRUE;
      vfd_write_trig := FALSE;
    END_IF;
  END_IF;

  vfd_err_timer(IN := vfd_comm_err, PT := T#5000ms);
  IF vfd_err_timer.Q THEN
    vfd_comm_err := FALSE;
  END_IF;

  (* ================================================================ *)
  (* SECTION 6 — DIAGNOSTICS                                         *)
  (* ================================================================ *)
  heartbeat := NOT heartbeat;
  cycle_count := cycle_count + 1;
  uptime_timer(IN := NOT uptime_timer.Q, PT := T#1000ms);
  IF uptime_timer.Q THEN
    uptime_seconds := uptime_seconds + 1;
  END_IF;
  system_ready := NOT fault_alarm AND NOT e_stop_active AND (conv_state = 2);
  motor_stopped := NOT motor_running;

  (* ================================================================ *)
  (* SECTION 7 — ANALOG SPEED REFERENCE                              *)
  (* ================================================================ *)
  conveyor_speed_cmd := _IO_EM_AI_00;
  conveyor_speed := conveyor_speed_cmd;

END_PROGRAM
