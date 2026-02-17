"""Photo-to-wiring-diagram reconstruction system.

Tag-first, KB-anchored pipeline: photo + component tag → knowledge base
lookup → gap analysis → targeted questions → IEC 60617 diagram.
"""

from openclaw.wiring.models import (
    ComponentRecord,
    TerminalState,
    WiringConnection,
    WiringProject,
)
from openclaw.wiring.pipeline import (
    PipelineResult,
    build_diagram_spec,
    process_answer,
    process_photo,
    render_diagram,
)

__all__ = [
    "ComponentRecord",
    "PipelineResult",
    "TerminalState",
    "WiringConnection",
    "WiringProject",
    "build_diagram_spec",
    "process_answer",
    "process_photo",
    "render_diagram",
]
