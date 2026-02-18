"""Persistence layer for wiring reconstruction projects.

CLI mode: JSON files in ~/.wd/projects/<project_id>.json
VPS mode: PostgreSQL (future — Phase 2)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from openclaw.wiring.models import WiringProject

log = logging.getLogger(__name__)

# Default storage directory
WD_HOME = Path.home() / ".wd"
PROJECTS_DIR = WD_HOME / "projects"
ACTIVE_FILE = WD_HOME / "active_project"


def _ensure_dirs() -> None:
    """Create storage directories if they don't exist."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def save_project(project: WiringProject) -> Path:
    """Save a project to JSON file. Returns the file path."""
    _ensure_dirs()
    path = PROJECTS_DIR / f"{project.project_id}.json"
    data = project.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2))
    log.info("Project saved: %s", path)
    return path


def load_project(project_id: str) -> Optional[WiringProject]:
    """Load a project by ID from the JSON store."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return WiringProject.model_validate(data)


def set_active_project(project_id: str) -> None:
    """Set which project is the current active project."""
    _ensure_dirs()
    ACTIVE_FILE.write_text(project_id)


def get_active_project_id() -> Optional[str]:
    """Get the active project ID, if any."""
    if not ACTIVE_FILE.exists():
        return None
    pid = ACTIVE_FILE.read_text().strip()
    return pid if pid else None


def load_active_project() -> Optional[WiringProject]:
    """Load the currently active project."""
    pid = get_active_project_id()
    if not pid:
        return None
    return load_project(pid)


def list_projects() -> list[dict]:
    """List all saved projects (id, name, location, completeness)."""
    _ensure_dirs()
    result = []
    for path in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            proj = WiringProject.model_validate(data)
            result.append({
                "project_id": proj.project_id,
                "panel_name": proj.panel_name,
                "panel_location": proj.panel_location,
                "components": len(proj.components),
                "connections": len(proj.connections),
                "photos": len(proj.photos),
                "completeness": proj.completeness(),
            })
        except Exception as e:
            log.warning("Failed to load %s: %s", path, e)
    return result


def delete_project(project_id: str) -> bool:
    """Delete a project file."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if path.exists():
        path.unlink()
        # Clear active if it was this project
        if get_active_project_id() == project_id:
            ACTIVE_FILE.unlink(missing_ok=True)
        return True
    return False
