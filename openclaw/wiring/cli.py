"""CLI for the wiring reconstruction tool.

Usage:
    wd init --name "Panel Name" --location "Building 3"
    wd add-photo panel_front.jpg [--tag Q1]
    wd analyze
    wd answer "K1 connects to F1, all phases"
    wd build-diagram [--hires]
    wd test continuity F1.2 M1.U1
    wd test voltage F1.2 M1.U1
    wd enrich K2
    wd list
    wd status
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openclaw.wiring.gaps import find_gaps, generate_next_question, suggest_continuity_test
from openclaw.wiring.models import ProjectBus, TerminalState, WiringProject
from openclaw.wiring.pipeline import (
    build_diagram_spec,
    process_answer,
    process_photo,
    render_diagram,
)
from openclaw.wiring.store import (
    delete_project,
    get_active_project_id,
    list_projects,
    load_active_project,
    save_project,
    set_active_project,
)


def _get_project() -> WiringProject:
    """Load the active project or exit with error."""
    project = load_active_project()
    if not project:
        print("No active project. Run: wd init --name \"Panel Name\"")
        sys.exit(1)
    return project


def _save_and_report(project: WiringProject) -> None:
    """Save the project and print current status."""
    save_project(project)


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a new wiring reconstruction project."""
    project = WiringProject(
        panel_name=args.name,
        panel_location=args.location or "",
    )

    # Add default power buses if requested
    if not args.no_buses:
        project.buses = [
            ProjectBus(name="L1", bus_type="power"),
            ProjectBus(name="L2", bus_type="power"),
            ProjectBus(name="L3", bus_type="power"),
            ProjectBus(name="PE", bus_type="earth"),
        ]

    save_project(project)
    set_active_project(project.project_id)

    print(f"Project created: {project.project_id}")
    print(f"  Panel: {project.panel_name}")
    if project.panel_location:
        print(f"  Location: {project.panel_location}")
    print(f"  Standard: {project.standard.value}")
    print(f"  Buses: {', '.join(b.name for b in project.buses)}")
    print()
    print("Next: wd add-photo <photo.jpg>")


def cmd_add_photo(args: argparse.Namespace) -> None:
    """Add a photo and run the reconstruction pipeline."""
    project = _get_project()

    photo_path = args.photo
    if not Path(photo_path).exists():
        print(f"File not found: {photo_path}")
        sys.exit(1)

    print(f"Processing {photo_path}...")
    result = process_photo(project, photo_path, focus_tag=args.tag)

    save_project(result.project)

    print()
    print(result.summary)
    print()

    if result.diagram_ready:
        print("Diagram is ready! Run: wd build-diagram")
    elif result.next_question:
        print(f"Next step: {result.next_question}")
    if result.continuity_suggestion:
        print(f"Suggestion: {result.continuity_suggestion}")


def cmd_analyze(args: argparse.Namespace) -> None:
    """Show current project status and gap analysis."""
    project = _get_project()

    print(f"=== {project.panel_name} ===")
    print(f"Project: {project.project_id}")
    print(f"Location: {project.panel_location or '(not set)'}")
    print(f"Photos: {len(project.photos)}")
    print(f"Completeness: {project.completeness():.0f}%")
    print()

    # Components
    if project.components:
        print("COMPONENTS:")
        print(f"  {'Tag':<8} {'Type':<20} {'Mfr':<15} {'Part#':<15} {'Conf':<6} {'Terminals'}")
        print(f"  {'---':<8} {'---':<20} {'---':<15} {'---':<15} {'---':<6} {'---'}")
        for tag, comp in sorted(project.components.items()):
            known_terms = sum(1 for t in comp.terminals.values() if t.connected_to)
            total_terms = len(comp.terminals)
            term_str = f"{known_terms}/{total_terms} connected" if total_terms else "none"
            print(
                f"  {tag:<8} {comp.component_type:<20} "
                f"{comp.manufacturer:<15} {comp.part_number:<15} "
                f"{comp.confidence:<6.0%} {term_str}"
            )
    else:
        print("No components discovered yet.")

    print()

    # Connections
    if project.connections:
        print(f"CONNECTIONS ({len(project.connections)}):")
        for conn in project.connections:
            status = "confirmed" if conn.confirmed else f"{conn.confidence:.0%}"
            color = f" [{conn.wire_color}]" if conn.wire_color else ""
            print(f"  {conn.from_ref} --> {conn.to_ref}  ({conn.wire_type}{color}) {status}")
    else:
        print("No connections discovered yet.")

    print()

    # Gaps
    gaps = find_gaps(project)
    if gaps:
        print(f"GAPS ({len(gaps)}):")
        for gap in gaps[:10]:
            print(f"  [{gap.priority:>2}] {gap.description}")
        if len(gaps) > 10:
            print(f"  ... and {len(gaps) - 10} more")

        print()
        next_q = generate_next_question(project)
        if next_q:
            print(f"NEXT QUESTION: {next_q}")
    else:
        print("No gaps — diagram is complete!")


def cmd_answer(args: argparse.Namespace) -> None:
    """Parse a technician's answer and update the project."""
    project = _get_project()

    answer_text = args.text
    print(f"Parsing answer: \"{answer_text}\"")

    result = process_answer(project, answer_text)
    save_project(result.project)

    print()
    print(result.summary)
    if result.next_question:
        print(f"Next: {result.next_question}")


def cmd_build_diagram(args: argparse.Namespace) -> None:
    """Build and render the wiring diagram as PNG."""
    project = _get_project()

    completeness = project.completeness()
    if completeness < 50 and not args.force:
        print(f"Warning: Only {completeness:.0f}% complete. Use --force to build anyway.")
        sys.exit(1)

    # Determine output path
    output = args.output
    if not output:
        safe_name = project.panel_name.replace(" ", "_").lower()
        output = f"{safe_name}_rev{project.revision + 1}.png"

    print(f"Building diagram (rev {project.revision + 1})...")
    render_diagram(project, output, hires=args.hires)
    save_project(project)

    print(f"Diagram saved: {output}")
    print(f"  Components: {len(project.components)}")
    print(f"  Connections: {len(project.connections)}")
    print(f"  Revision: {project.revision}")


def cmd_test(args: argparse.Namespace) -> None:
    """Record an electrical test result."""
    project = _get_project()

    test_type = args.test_type  # "continuity" or "voltage"
    terminal_a = args.terminal_a.upper()
    terminal_b = args.terminal_b.upper()

    if test_type == "continuity":
        print(f"Continuity test: {terminal_a} <-> {terminal_b}")
        result = input("Continuity? (y/n): ").strip().lower()

        if result in ("y", "yes"):
            # Confirm the connection
            project.add_connection(
                from_ref=terminal_a,
                to_ref=terminal_b,
                confidence=1.0,
                confirmed=True,
            )
            print(f"  CONFIRMED: {terminal_a} <-> {terminal_b}")
        else:
            # Remove any inferred connection
            removed = project.remove_connection(terminal_a, terminal_b)
            if removed:
                print(f"  REMOVED inferred connection: {terminal_a} <-> {terminal_b}")
            else:
                print(f"  No connection: {terminal_a} <-> {terminal_b} (noted)")

    elif test_type == "voltage":
        print(f"Voltage test: {terminal_a} <-> {terminal_b}")
        reading = input("Voltage reading (e.g., '24VDC', '120VAC'): ").strip()
        if reading:
            project.notes.append(
                f"Voltage {terminal_a}-{terminal_b}: {reading}"
            )
            # Try to update component ratings
            tag_a = terminal_a.split(".")[0]
            if tag_a in project.components:
                comp = project.components[tag_a]
                if not comp.voltage_rating:
                    comp.voltage_rating = reading
            print(f"  Recorded: {reading} between {terminal_a} and {terminal_b}")

    save_project(project)


def cmd_enrich(args: argparse.Namespace) -> None:
    """Guide data collection for a component not in the KB."""
    project = _get_project()
    tag = args.tag.upper()

    comp = project.components.get(tag)
    if not comp:
        print(f"Component {tag} not found in project.")
        sys.exit(1)

    print(f"=== Enriching {tag} ===")
    print(f"Current: type={comp.component_type}, mfr={comp.manufacturer}, part={comp.part_number}")
    print()
    print("To create a KB entry for this component, I need:")
    print()

    needs = []
    if not comp.manufacturer:
        needs.append("1. Manufacturer (from nameplate photo)")
    if not comp.part_number:
        needs.append("2. Part number (from nameplate photo)")
    if not comp.voltage_rating:
        needs.append("3. Voltage rating")
    if not comp.current_rating:
        needs.append("4. Current rating")
    if len(comp.terminals) < 2:
        needs.append("5. Terminal layout (close-up photo of terminals)")

    if needs:
        for n in needs:
            print(f"  {n}")
        print()
        print("Take a nameplate photo and run: wd add-photo <nameplate.jpg> --tag", tag)
    else:
        print("All data present! This component can be added to the KB.")
        print(f"  Manufacturer: {comp.manufacturer}")
        print(f"  Part number: {comp.part_number}")
        print(f"  Terminals: {', '.join(comp.terminals.keys())}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all saved projects."""
    projects = list_projects()
    active_id = get_active_project_id()

    if not projects:
        print("No projects found. Run: wd init --name \"Panel Name\"")
        return

    print(f"{'Active':<7} {'ID':<14} {'Name':<25} {'Location':<20} {'Comps':<6} {'Complete'}")
    print(f"{'---':<7} {'---':<14} {'---':<25} {'---':<20} {'---':<6} {'---'}")
    for p in projects:
        active = " >>>" if p["project_id"] == active_id else ""
        print(
            f"{active:<7} {p['project_id']:<14} {p['panel_name']:<25} "
            f"{p['panel_location']:<20} {p['components']:<6} {p['completeness']:.0f}%"
        )


def cmd_status(args: argparse.Namespace) -> None:
    """Quick status of the active project."""
    project = _get_project()
    completeness = project.completeness()
    print(f"{project.panel_name} [{project.project_id}]")
    print(f"  {len(project.components)} components, {len(project.connections)} connections, {len(project.photos)} photos")
    print(f"  Completeness: {completeness:.0f}%")

    next_q = generate_next_question(project)
    if next_q:
        print(f"  Next: {next_q}")
    elif completeness >= 80:
        print("  Ready for diagram generation!")


def cmd_export(args: argparse.Namespace) -> None:
    """Export the project as DiagramSpec JSON."""
    project = _get_project()
    spec = build_diagram_spec(project)
    data = spec.model_dump(mode="json", by_alias=True)

    output = args.output or f"{project.project_id}_spec.json"
    Path(output).write_text(json.dumps(data, indent=2))
    print(f"DiagramSpec exported to: {output}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="wd",
        description="Wiring Diagram Reconstruction Tool",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    p_init = sub.add_parser("init", help="Start a new reconstruction project")
    p_init.add_argument("--name", required=True, help="Panel name")
    p_init.add_argument("--location", default="", help="Panel location")
    p_init.add_argument("--no-buses", action="store_true", help="Don't add default L1/L2/L3/PE buses")

    # add-photo
    p_photo = sub.add_parser("add-photo", help="Add a photo and run pipeline")
    p_photo.add_argument("photo", help="Path to photo file")
    p_photo.add_argument("--tag", default=None, help="Focus on a specific component tag")

    # analyze
    sub.add_parser("analyze", help="Show project status and gap analysis")

    # answer
    p_answer = sub.add_parser("answer", help="Parse a technician's answer")
    p_answer.add_argument("text", help="The answer text")

    # build-diagram
    p_build = sub.add_parser("build-diagram", help="Generate wiring diagram PNG")
    p_build.add_argument("--hires", action="store_true", help="High-resolution output")
    p_build.add_argument("--output", "-o", default=None, help="Output file path")
    p_build.add_argument("--force", action="store_true", help="Build even if incomplete")

    # test
    p_test = sub.add_parser("test", help="Record an electrical test result")
    p_test.add_argument("test_type", choices=["continuity", "voltage"])
    p_test.add_argument("terminal_a", help="First terminal (e.g., F1.2)")
    p_test.add_argument("terminal_b", help="Second terminal (e.g., M1.U1)")

    # enrich
    p_enrich = sub.add_parser("enrich", help="Guide KB enrichment for a component")
    p_enrich.add_argument("tag", help="Component tag to enrich")

    # list
    sub.add_parser("list", help="List all projects")

    # status
    sub.add_parser("status", help="Quick status of active project")

    # export
    p_export = sub.add_parser("export", help="Export DiagramSpec JSON")
    p_export.add_argument("--output", "-o", default=None, help="Output file path")

    return parser


def main() -> None:
    """Entry point for the `wd` CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "init": cmd_init,
        "add-photo": cmd_add_photo,
        "analyze": cmd_analyze,
        "answer": cmd_answer,
        "build-diagram": cmd_build_diagram,
        "test": cmd_test,
        "enrich": cmd_enrich,
        "list": cmd_list,
        "status": cmd_status,
        "export": cmd_export,
    }

    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
