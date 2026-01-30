"""
GPIO Pin Mapping Configuration for Raspberry Pi
Defines the relationship between Modbus coils and physical GPIO pins

Usage:
    from gpio_mapping import get_config, SCENE_CONFIGS
    config = get_config("sorting_basic")
"""

# Raspberry Pi GPIO pin layout (BCM numbering)
# Use 'pinout' command on Pi to view physical layout
#
# Physical Pin -> BCM GPIO
# Pin 11 -> GPIO17
# Pin 13 -> GPIO27
# Pin 15 -> GPIO22
# Pin 16 -> GPIO23
# Pin 18 -> GPIO24
# Pin 29 -> GPIO5
# Pin 31 -> GPIO6
# Pin 33 -> GPIO13
# Pin 35 -> GPIO19
# Pin 37 -> GPIO26

# Default Factory I/O simulation mapping
DEFAULT_CONFIG = {
    "name": "Factory I/O Default",
    "description": "Basic simulation with buttons and LEDs",
    "inputs": [
        {"coil": 0, "gpio": 17, "name": "Start_Button", "active_high": True},
        {"coil": 1, "gpio": 27, "name": "Stop_Button", "active_high": True},
        {"coil": 2, "gpio": 22, "name": "E_Stop_NC", "active_high": False},
        {"coil": 3, "gpio": 23, "name": "Sensor_1", "active_high": True},
        {"coil": 4, "gpio": 24, "name": "Sensor_2", "active_high": True},
    ],
    "outputs": [
        {"coil": 10, "gpio": 5, "name": "LED_Run", "active_high": True},
        {"coil": 11, "gpio": 6, "name": "LED_Stop", "active_high": True},
        {"coil": 12, "gpio": 13, "name": "LED_Fault", "active_high": True},
        {"coil": 13, "gpio": 19, "name": "Motor_Enable", "active_high": True},
        {"coil": 14, "gpio": 26, "name": "Valve_1", "active_high": True},
    ],
    "holding_registers": [
        {"address": 0, "name": "Motor_Speed", "min": 0, "max": 100},
        {"address": 1, "name": "Setpoint", "min": 0, "max": 1000},
    ]
}

# Scene-specific configurations (match Factory I/O scenes)
SCENE_CONFIGS = {
    "sorting_basic": {
        "name": "Sorting Station Basic",
        "description": "Basic sorting conveyor with vision sensor",
        "inputs": [
            {"coil": 0, "gpio": 17, "name": "At_Entry", "active_high": True},
            {"coil": 1, "gpio": 27, "name": "At_Exit", "active_high": True},
            {"coil": 2, "gpio": 22, "name": "Vision_Blue", "active_high": True},
            {"coil": 3, "gpio": 23, "name": "Vision_Green", "active_high": True},
            {"coil": 4, "gpio": 24, "name": "Vision_Metal", "active_high": True},
        ],
        "outputs": [
            {"coil": 10, "gpio": 5, "name": "Entry_Conveyor", "active_high": True},
            {"coil": 11, "gpio": 6, "name": "Exit_Conveyor", "active_high": True},
            {"coil": 12, "gpio": 13, "name": "Pusher_1", "active_high": True},
            {"coil": 13, "gpio": 19, "name": "Pusher_2", "active_high": True},
            {"coil": 14, "gpio": 26, "name": "Pusher_3", "active_high": True},
        ],
    },
    "pick_and_place": {
        "name": "Pick and Place Basic",
        "description": "XZ pick and place with gripper",
        "inputs": [
            {"coil": 0, "gpio": 17, "name": "Part_Present", "active_high": True},
            {"coil": 1, "gpio": 27, "name": "X_Home", "active_high": True},
            {"coil": 2, "gpio": 22, "name": "X_End", "active_high": True},
            {"coil": 3, "gpio": 23, "name": "Z_Home", "active_high": True},
            {"coil": 4, "gpio": 24, "name": "Z_End", "active_high": True},
            {"coil": 5, "gpio": 25, "name": "Gripper_Closed", "active_high": True},
        ],
        "outputs": [
            {"coil": 10, "gpio": 5, "name": "X_Move_Plus", "active_high": True},
            {"coil": 11, "gpio": 6, "name": "X_Move_Minus", "active_high": True},
            {"coil": 12, "gpio": 13, "name": "Z_Move_Plus", "active_high": True},
            {"coil": 13, "gpio": 19, "name": "Z_Move_Minus", "active_high": True},
            {"coil": 14, "gpio": 26, "name": "Gripper_Close", "active_high": True},
            {"coil": 15, "gpio": 16, "name": "Conveyor", "active_high": True},
        ],
    },
    "assembler": {
        "name": "Assembler Basic",
        "description": "Assembly station with feeders and clamp",
        "inputs": [
            {"coil": 0, "gpio": 17, "name": "Part_In_Position", "active_high": True},
            {"coil": 1, "gpio": 27, "name": "Base_Sensor", "active_high": True},
            {"coil": 2, "gpio": 22, "name": "Lid_Sensor", "active_high": True},
            {"coil": 3, "gpio": 23, "name": "Clamp_Open", "active_high": True},
            {"coil": 4, "gpio": 24, "name": "Clamp_Closed", "active_high": True},
        ],
        "outputs": [
            {"coil": 10, "gpio": 5, "name": "Conveyor", "active_high": True},
            {"coil": 11, "gpio": 6, "name": "Base_Feeder", "active_high": True},
            {"coil": 12, "gpio": 13, "name": "Lid_Feeder", "active_high": True},
            {"coil": 13, "gpio": 19, "name": "Clamp_Close", "active_high": True},
            {"coil": 14, "gpio": 26, "name": "Clamp_Open", "active_high": True},
        ],
    },
    "level_control": {
        "name": "Level Control",
        "description": "Tank level control with pump and valve",
        "inputs": [
            {"coil": 0, "gpio": 17, "name": "Level_High", "active_high": True},
            {"coil": 1, "gpio": 27, "name": "Level_Low", "active_high": True},
            {"coil": 2, "gpio": 22, "name": "Flow_Sensor", "active_high": True},
        ],
        "outputs": [
            {"coil": 10, "gpio": 5, "name": "Pump_Start", "active_high": True},
            {"coil": 11, "gpio": 6, "name": "Inlet_Valve", "active_high": True},
            {"coil": 12, "gpio": 13, "name": "Outlet_Valve", "active_high": True},
        ],
        "holding_registers": [
            {"address": 0, "name": "Level_Setpoint", "min": 0, "max": 100},
            {"address": 1, "name": "Current_Level", "min": 0, "max": 100},
            {"address": 2, "name": "Flow_Rate", "min": 0, "max": 1000},
        ]
    },
    "micro820_mirror": {
        "name": "Micro 820 Mirror",
        "description": "Mirror the Micro 820 I/O layout",
        "inputs": [
            {"coil": 7, "gpio": 17, "name": "DI_00_3pos_Center", "active_high": True},
            {"coil": 8, "gpio": 27, "name": "DI_01_Estop_NO", "active_high": True},
            {"coil": 9, "gpio": 22, "name": "DI_02_Estop_NC", "active_high": True},
            {"coil": 10, "gpio": 23, "name": "DI_03_3pos_Right", "active_high": True},
            {"coil": 11, "gpio": 24, "name": "DI_04_Pushbutton", "active_high": True},
        ],
        "outputs": [
            {"coil": 15, "gpio": 5, "name": "DO_00_LED_Power", "active_high": True},
            {"coil": 16, "gpio": 6, "name": "DO_01_LED_Fault", "active_high": True},
            {"coil": 17, "gpio": 13, "name": "DO_03_LED_Aux", "active_high": True},
        ],
    }
}


def get_config(scene_name: str = None) -> dict:
    """
    Get configuration for a specific scene or default.

    Args:
        scene_name: Name of the Factory I/O scene or None for default

    Returns:
        Configuration dictionary with inputs, outputs, and optional holding_registers
    """
    if scene_name and scene_name in SCENE_CONFIGS:
        return SCENE_CONFIGS[scene_name]
    return DEFAULT_CONFIG


def list_scenes() -> list:
    """Return list of available scene configurations"""
    return list(SCENE_CONFIGS.keys())


def print_config(config: dict):
    """Print configuration in readable format"""
    print(f"\n{config.get('name', 'Configuration')}")
    print(f"{config.get('description', '')}")
    print("-" * 50)

    print("\nInputs:")
    for inp in config.get('inputs', []):
        print(f"  Coil {inp['coil']:2d} <- GPIO {inp['gpio']:2d} : {inp['name']}")

    print("\nOutputs:")
    for out in config.get('outputs', []):
        print(f"  Coil {out['coil']:2d} -> GPIO {out['gpio']:2d} : {out['name']}")

    if 'holding_registers' in config:
        print("\nHolding Registers:")
        for reg in config['holding_registers']:
            print(f"  Addr {reg['address']:3d} : {reg['name']} ({reg['min']}-{reg['max']})")


if __name__ == "__main__":
    import sys

    print("Available Factory I/O Scene Configurations:")
    print("=" * 50)

    if len(sys.argv) > 1:
        scene = sys.argv[1]
        if scene in SCENE_CONFIGS:
            print_config(get_config(scene))
        else:
            print(f"Unknown scene: {scene}")
            print(f"Available: {', '.join(list_scenes())}")
    else:
        print(f"\nScenes: {', '.join(list_scenes())}")
        print("\nDefault configuration:")
        print_config(DEFAULT_CONFIG)
        print("\nUsage: python gpio_mapping.py <scene_name>")
