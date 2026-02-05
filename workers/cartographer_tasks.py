from typing import Dict
"""
THE CARTOGRAPHER - Celery Tasks
================================
Maps codebases and tracks dependencies.
Converted from HTTP server (port 8095) to Celery worker.
"""

from pathlib import Path
import sys
sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call, track_api_call


class Cartographer(BaseAgent):
    """Maps codebase structure and dependencies."""
    
    def __init__(self):
        super().__init__("Cartographer")
    
    def map_codebase(self, path: str) -> dict:
        """Map a codebase directory."""
        self.logger.info(f"Mapping codebase: {path}")
        
        p = Path(path)
        if not p.exists():
            return {"error": f"Path not found: {path}"}
        
        files = list(p.rglob("*.py"))
        
        return {
            "path": path,
            "python_files": len(files),
            "files": [str(f.relative_to(p)) for f in files[:20]]  # First 20
        }
    
    def find_dependencies(self, module: str) -> dict:
        """Find dependencies of a module."""
        self.logger.info(f"Finding dependencies: {module}")
        
        # TODO: Implement dependency analysis
        return {
            "module": module,
            "dependencies": [],
            "message": "Dependency analysis pending implementation"
        }


cartographer = Cartographer()


@app.task(bind=True, name='cartographer.map_codebase')
@with_token_tracking('cartographer')
def map_codebase(self, path: str) -> dict:
    """Map a codebase directory."""
    cartographer.log_start('map_codebase', path=path)
    
    try:
        result = cartographer.map_codebase(path)
        cartographer.log_complete('map_codebase', result)
        return result
    except Exception as e:
        cartographer.log_error('map_codebase', e)
        raise


@app.task(bind=True, name='cartographer.find_dependencies')
@with_token_tracking('cartographer')
def find_dependencies(self, module: str) -> dict:
    """Find dependencies of a module."""
    cartographer.log_start('find_dependencies', module=module)
    
    try:
        result = cartographer.find_dependencies(module)
        cartographer.log_complete('find_dependencies', result)
        return result
    except Exception as e:
        cartographer.log_error('find_dependencies', e)
        raise


@app.task(bind=True, name='cartographer.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health(self) -> dict:
    """Health check."""
    return {"status": "ok", "agent": "Cartographer"}


# ============== LAPTOP REMOTE EXECUTION ==============

from integrations.laptop_remote import get_laptop_client, execute_on_laptop


@app.task(bind=True, name='cartographer.execute_on_laptop')
@with_token_tracking('cartographer')
def execute_on_plc_laptop(self, prompt: str, sync: bool = False, **kwargs) -> Dict:
    """
    Execute Claude Code on PLC laptop for GUI/hardware tasks.
    
    Use for:
    - Factory I/O simulations
    - TIA Portal code generation
    - PLC programming that needs local tools
    - USB/Serial adapter access
    
    Args:
        prompt: What to ask Claude to do
        sync: Wait for completion (True) or return immediately (False)
        **kwargs: allowed_tools, timeout_seconds, save_output_to
    """
    cartographer.log_start('execute_on_laptop', prompt_preview=prompt[:100])
    
    result = execute_on_laptop(prompt, laptop="plc-laptop", sync=sync, **kwargs)
    
    cartographer.log_complete('execute_on_laptop', result)
    return result


@app.task(bind=True, name='cartographer.factory_io_simulation')
@with_token_tracking('cartographer')
def run_factory_io_simulation(self, scene: str, duration_seconds: int = 60, export_data: bool = True) -> Dict:
    """
    Run a Factory I/O simulation on PLC laptop.
    
    Args:
        scene: Scene name to load (e.g., "Sorting by Height", "Pick and Place")
        duration_seconds: How long to run simulation
        export_data: Export sensor data to CSV
    """
    cartographer.log_start('factory_io_simulation', scene=scene)
    
    prompt = f"""
    1. Open Factory I/O application
    2. Load the scene: "{scene}"
    3. Start the simulation
    4. Let it run for {duration_seconds} seconds
    5. Take a screenshot of the simulation
    {"6. Export sensor data to CSV" if export_data else ""}
    7. Stop the simulation
    8. Save all files to ~/FactoryLM-Sync/plc-programs/factory-io/{scene.replace(' ', '-').lower()}/
    """
    
    result = execute_on_laptop(
        prompt,
        laptop="plc-laptop",
        sync=True,
        timeout_seconds=duration_seconds + 120,
        allowed_tools=["Computer", "Write"],
    )
    
    cartographer.log_complete('factory_io_simulation', result)
    return result


@app.task(bind=True, name='cartographer.generate_plc_code')
@with_token_tracking('cartographer')
def generate_plc_code(self, spec: Dict) -> Dict:
    """
    Generate PLC code using TIA Portal on laptop.
    
    Args:
        spec: Code specification including:
            - project_name: TIA project name
            - plc_type: "S7-1200", "S7-1500", etc.
            - function_blocks: List of FB specifications
            - language: "SCL", "LAD", "FBD"
    """
    cartographer.log_start('generate_plc_code', spec=spec)
    
    project_name = spec.get('project_name', 'FactoryLM_Generated')
    plc_type = spec.get('plc_type', 'S7-1200')
    language = spec.get('language', 'SCL')
    blocks = spec.get('function_blocks', [])
    
    blocks_desc = "\n".join([
        f"   - {fb.get('name', 'FB1')}: {fb.get('description', 'Function block')}"
        for fb in blocks
    ])
    
    prompt = f"""
    Use TIA Portal to generate PLC code:
    
    Project: {project_name}
    PLC Type: {plc_type}
    Language: {language}
    
    Create these function blocks:
    {blocks_desc}
    
    Steps:
    1. Open TIA Portal
    2. Create new project "{project_name}" for {plc_type}
    3. Create each function block with proper inputs/outputs
    4. Write the logic in {language}
    5. Compile and check for errors
    6. Export project archive
    7. Save to ~/FactoryLM-Sync/plc-programs/tia-projects/{project_name}/
    """
    
    result = execute_on_laptop(
        prompt,
        laptop="plc-laptop",
        sync=True,
        timeout_seconds=900,  # 15 min for TIA Portal work
        allowed_tools=["Computer", "Write", "Read"],
    )
    
    cartographer.log_complete('generate_plc_code', result)
    return result
