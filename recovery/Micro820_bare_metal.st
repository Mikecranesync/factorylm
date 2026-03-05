PROGRAM Prog2
  (* FactoryLM -- Micro820 Minimal Digital I/O v2.0 *)
  (* PLC: 2080-LC20-20QBB *)
  (* Reads switches, drives LEDs, exposes state via tags *)

  (* Read panel switches *)
  auto_mode := _IO_EM_DI_00 AND _IO_EM_DI_03;
  manual_mode := _IO_EM_DI_00 AND NOT _IO_EM_DI_03;
  off_mode := NOT _IO_EM_DI_00;
  e_stop_active := _IO_EM_DI_01;
  sensor_1_active := _IO_EM_DI_05;
  sensor_2_active := _IO_EM_DI_06;

  (* Drive LED outputs based on switch state *)
  _IO_EM_DO_00 := auto_mode;
  _IO_EM_DO_01 := e_stop_active;
  _IO_EM_DO_02 := sensor_1_active OR sensor_2_active;

  (* Heartbeat -- proves PLC is scanning *)
  heartbeat := NOT heartbeat;

  (* System status *)
  system_ready := NOT e_stop_active AND NOT off_mode;

END_PROGRAM
