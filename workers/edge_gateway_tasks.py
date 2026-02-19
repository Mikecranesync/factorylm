"""
Edge Gateway Celery Tasks
==========================
Periodic tasks for monitoring and polling the Raspberry Pi edge gateway.
Handles health monitoring and PLC register polling with InfluxDB logging.
"""

import os
import time
import logging
from datetime import datetime
from celery import shared_task

# Import our integration and observability
from integrations.edge_gateway import connect_to_edge, read_plc_registers, health_check
from observability.metrics import write_metric

logger = logging.getLogger(__name__)

# Configuration
POLLING_ENABLED = os.getenv('EDGE_POLLING_ENABLED', 'false').lower() == 'true'
EDGE_GATEWAY_IP = os.getenv('EDGE_GATEWAY_IP')
INFLUX_SENSORS_BUCKET = os.getenv('INFLUX_SENSORS_BUCKET', 'sensors')

# PLC register mapping — Allen-Bradley Micro 820
# Holding registers 100-105 (see services/plc-modbus/CLAUDE.md)
PLC_REGISTERS = {
    "motor_speed":     {"register": 100, "count": 1, "type": "int",   "scale": 1.0},
    "motor_current":   {"register": 101, "count": 1, "type": "float", "scale": 0.01},
    "temperature":     {"register": 102, "count": 1, "type": "float", "scale": 0.1},
    "pressure":        {"register": 103, "count": 1, "type": "float", "scale": 1.0},
    "conveyor_speed":  {"register": 104, "count": 1, "type": "int",   "scale": 1.0},
    "error_code":      {"register": 105, "count": 1, "type": "int",   "scale": 1.0},
}


@shared_task(name="edge_gateway.health_check")
def edge_gateway_health_check():
    """
    Health check task - runs every minute.
    Tests connectivity and basic functionality.
    """
    start_time = time.time()
    
    try:
        logger.info("Starting edge gateway health check")
        
        # Check if gateway IP is configured
        if not EDGE_GATEWAY_IP:
            error_msg = "EDGE_GATEWAY_IP not configured"
            logger.error(error_msg)
            
            # Write error metric
            write_metric(
                measurement="edge_gateway_health",
                tags={
                    "status": "error",
                    "component": "edge_gateway",
                    "error_type": "configuration"
                },
                fields={
                    "uptime": 0,
                    "latency_ms": 0,
                    "error_count": 1
                }
            )
            return {"status": "error", "error": error_msg}
        
        # Perform health check
        result = health_check(EDGE_GATEWAY_IP)
        duration_ms = (time.time() - start_time) * 1000
        
        # Extract metrics for InfluxDB
        status = result.get("status", "unknown")
        connectivity = result.get("connectivity", {})
        modbus_test = result.get("modbus_test", {})
        
        # Write health metrics to InfluxDB
        write_metric(
            measurement="edge_gateway_health",
            tags={
                "status": status,
                "component": "edge_gateway",
                "ip": EDGE_GATEWAY_IP
            },
            fields={
                "uptime": 1 if status == "healthy" else 0,
                "latency_ms": connectivity.get("latency_ms", 0),
                "duration_ms": duration_ms,
                "error_count": 0 if status == "healthy" else 1,
                "modbus_latency_ms": modbus_test.get("latency_ms", 0),
                "modbus_success": 1 if modbus_test.get("status") == "success" else 0
            }
        )
        
        # Log result
        if status == "healthy":
            logger.info(f"Edge gateway health check passed (latency: {connectivity.get('latency_ms', 0):.1f}ms)")
        else:
            logger.warning(f"Edge gateway health check failed: {result.get('error', 'unknown')}")
        
        return result
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        error_msg = f"Health check task failed: {str(e)}"
        logger.error(error_msg)
        
        # Write error metric
        write_metric(
            measurement="edge_gateway_health",
            tags={
                "status": "error",
                "component": "edge_gateway",
                "error_type": "task_exception"
            },
            fields={
                "uptime": 0,
                "latency_ms": 0,
                "duration_ms": duration_ms,
                "error_count": 1
            }
        )
        
        return {"status": "error", "error": error_msg}


@shared_task(name="edge_gateway.poll_registers")
def edge_gateway_poll_registers():
    """
    Poll PLC registers task - runs every 5 seconds when enabled.
    Collects all configured registers and logs to InfluxDB sensors bucket.
    """
    if not POLLING_ENABLED:
        logger.debug("Edge gateway polling disabled")
        return {"status": "disabled"}
    
    if not EDGE_GATEWAY_IP:
        logger.error("EDGE_GATEWAY_IP not configured for polling")
        return {"status": "error", "error": "no_ip_configured"}
    
    start_time = time.time()
    results = {"timestamp": datetime.now().isoformat(), "registers": {}, "errors": []}
    
    try:
        logger.debug("Polling PLC registers via edge gateway")
        
        # Poll each configured register group
        for name, config in PLC_REGISTERS.items():
            register = config["register"]
            count = config["count"]
            scale = config.get("scale", 1.0)
            data_type = config.get("type", "float")
            
            # Read register(s)
            read_result = read_plc_registers(register, count, ip=EDGE_GATEWAY_IP)
            
            if read_result.get("status") == "success":
                values = read_result.get("values", [])
                
                if values:
                    # Handle different data types and scaling
                    if data_type == "float" and len(values) >= 1:
                        processed_value = float(values[0]) * scale
                    elif data_type == "int" and len(values) >= 1:
                        if count == 2 and len(values) >= 2:
                            # 32-bit integer from two 16-bit registers
                            processed_value = (values[0] << 16) + values[1]
                        else:
                            processed_value = int(values[0]) * scale
                    else:
                        processed_value = values[0] * scale
                    
                    results["registers"][name] = processed_value
                    
                    # Write to InfluxDB sensors bucket
                    write_metric(
                        measurement="plc_registers",
                        tags={
                            "register_name": name,
                            "register_addr": register,
                            "data_type": data_type,
                            "edge_ip": EDGE_GATEWAY_IP
                        },
                        fields={
                            "value": processed_value,
                            "raw_value": values[0] if values else 0,
                            "latency_ms": read_result.get("latency_ms", 0),
                            "success": 1
                        }
                    )
                    
                    logger.debug(f"Polled {name}: {processed_value}")
                    
                else:
                    error_msg = f"No values returned for {name}"
                    results["errors"].append(error_msg)
                    logger.warning(error_msg)
                    
                    # Write error metric
                    write_metric(
                        measurement="plc_registers",
                        tags={
                            "register_name": name,
                            "register_addr": register,
                            "error_type": "no_values",
                            "edge_ip": EDGE_GATEWAY_IP
                        },
                        fields={
                            "value": 0,
                            "latency_ms": read_result.get("latency_ms", 0),
                            "success": 0,
                            "error_count": 1
                        }
                    )
            else:
                error_msg = f"Failed to read {name}: {read_result.get('error', 'unknown')}"
                results["errors"].append(error_msg)
                logger.warning(error_msg)
                
                # Write error metric
                write_metric(
                    measurement="plc_registers",
                    tags={
                        "register_name": name,
                        "register_addr": register,
                        "error_type": "read_failed",
                        "edge_ip": EDGE_GATEWAY_IP
                    },
                    fields={
                        "value": 0,
                        "latency_ms": read_result.get("latency_ms", 0),
                        "success": 0,
                        "error_count": 1
                    }
                )
        
        # Overall polling metrics
        duration_ms = (time.time() - start_time) * 1000
        success_count = len(results["registers"])
        error_count = len(results["errors"])
        
        write_metric(
            measurement="edge_gateway_polling",
            tags={
                "edge_ip": EDGE_GATEWAY_IP,
                "status": "completed"
            },
            fields={
                "duration_ms": duration_ms,
                "success_count": success_count,
                "error_count": error_count,
                "total_registers": len(PLC_REGISTERS)
            }
        )
        
        logger.debug(f"Polling completed: {success_count} success, {error_count} errors, {duration_ms:.1f}ms")
        
        return results
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        error_msg = f"Polling task failed: {str(e)}"
        logger.error(error_msg)
        
        # Write error metric
        write_metric(
            measurement="edge_gateway_polling",
            tags={
                "edge_ip": EDGE_GATEWAY_IP or "unknown",
                "status": "error",
                "error_type": "task_exception"
            },
            fields={
                "duration_ms": duration_ms,
                "success_count": 0,
                "error_count": 1,
                "total_registers": len(PLC_REGISTERS)
            }
        )
        
        return {"status": "error", "error": error_msg}


@shared_task(name="edge_gateway.test_connectivity")
def edge_gateway_test_connectivity():
    """
    Manual connectivity test task.
    Can be called on-demand to test edge gateway connection.
    """
    if not EDGE_GATEWAY_IP:
        return {"status": "error", "error": "EDGE_GATEWAY_IP not configured"}
    
    try:
        result = connect_to_edge(EDGE_GATEWAY_IP)
        logger.info(f"Connectivity test result: {result.get('status')}")
        return result
    except Exception as e:
        error_msg = f"Connectivity test failed: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "error": error_msg}


@shared_task(name="edge_gateway.read_register_group")
def edge_gateway_read_register_group(register_start: int, count: int, slave_id: int = 1):
    """
    Manual task to read a specific group of registers.
    
    Args:
        register_start: Starting register address
        count: Number of registers to read
        slave_id: Modbus slave ID
    
    Returns:
        Dict with register values and timing
    """
    if not EDGE_GATEWAY_IP:
        return {"status": "error", "error": "EDGE_GATEWAY_IP not configured"}
    
    try:
        result = read_plc_registers(register_start, count, slave_id, EDGE_GATEWAY_IP)
        logger.info(f"Read registers {register_start}-{register_start+count-1}: {result.get('status')}")
        return result
    except Exception as e:
        error_msg = f"Register read failed: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "error": error_msg}


# Task routing for better organization
def get_edge_gateway_tasks():
    """Return list of edge gateway task names for registration."""
    return [
        "edge_gateway.health_check",
        "edge_gateway.poll_registers",
        "edge_gateway.test_connectivity",
        "edge_gateway.read_register_group"
    ]