"""FactoryLM CMMS Gist Work Order helper.

Creates portable, CMMS-agnostic work orders as GitHub Gists containing
Markdown + CSV + attachments that any major CMMS can import.
"""

import csv
import io
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from string import Template

TEMPLATE_DIR = Path(__file__).parent / "gist-templates"

CSV_COLUMNS = [
    "work_order_id", "title", "status", "priority", "asset_name",
    "asset_id", "location", "site", "assigned_to", "assigned_team",
    "work_type", "category", "due_date", "created_date", "completed_date",
    "completed_by", "reported_by", "channel", "estimated_hours", "cost",
    "completion_notes", "failure_code", "description", "cmms_system",
    "cmms_external_id",
]

# Counter file for sequential WO IDs within a day
_SEQ_COUNTER_FILE = Path(tempfile.gettempdir()) / "factorylm_wo_seq.txt"


def _next_seq() -> int:
    """Return next sequence number for today, resetting daily."""
    today = datetime.now().strftime("%Y%m%d")
    seq = 1
    if _SEQ_COUNTER_FILE.exists():
        content = _SEQ_COUNTER_FILE.read_text().strip()
        if content.startswith(today + ":"):
            seq = int(content.split(":")[1]) + 1
    _SEQ_COUNTER_FILE.write_text(f"{today}:{seq}")
    return seq


def generate_wo_id() -> str:
    """Generate a work order ID: WO-YYYY-MMDD-NNN."""
    now = datetime.now()
    seq = _next_seq()
    return f"WO-{now.strftime('%Y')}-{now.strftime('%m%d')}-{seq:03d}"


def render_work_order_md(metadata: dict) -> str:
    """Render the Markdown work order template with metadata values."""
    template_path = TEMPLATE_DIR / "work-order.md"
    template_text = template_path.read_text(encoding="utf-8")

    # Build attachments section from metadata if present
    attachments_section = metadata.get("attachments_section", "None")

    values = {col: metadata.get(col, "") for col in CSV_COLUMNS}
    values["attachments_section"] = attachments_section

    # Use string.Template for ${variable} substitution
    tmpl = Template(template_text)
    return tmpl.safe_substitute(values)


def render_work_order_csv(metadata: dict) -> str:
    """Render CSV with header row + single data row."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    writer.writerow([metadata.get(col, "") for col in CSV_COLUMNS])
    return output.getvalue()


def render_attachments_txt(attachments: list[dict]) -> str:
    """Render attachments.txt with type,description,url lines."""
    lines = ["type,description,url"]
    for att in attachments:
        t = att.get("type", "")
        d = att.get("description", "")
        u = att.get("url", "")
        lines.append(f"{t},{d},{u}")
    return "\n".join(lines) + "\n"


def create_work_order_gist(metadata: dict, attachments: list[dict] | None = None) -> dict:
    """Create a GitHub Gist with work order files.

    Returns dict with gist_id and gist_url.
    """
    if not metadata.get("work_order_id"):
        metadata["work_order_id"] = generate_wo_id()

    if not metadata.get("created_date"):
        metadata["created_date"] = datetime.now().isoformat()

    # Build attachments section for Markdown
    if attachments:
        att_lines = []
        for att in attachments:
            att_lines.append(f"- **{att.get('type', 'file')}**: {att.get('description', '')} — {att.get('url', '')}")
        metadata["attachments_section"] = "\n".join(att_lines)

    md_content = render_work_order_md(metadata)
    csv_content = render_work_order_csv(metadata)
    att_content = render_attachments_txt(attachments or [])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = os.path.join(tmpdir, "work-order.md")
        csv_path = os.path.join(tmpdir, "work-order.csv")
        att_path = os.path.join(tmpdir, "attachments.txt")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv_content)
        with open(att_path, "w", encoding="utf-8") as f:
            f.write(att_content)

        wo_id = metadata["work_order_id"]
        title = metadata.get("title", "Untitled")
        description = f"[Jarvis Work Order] {wo_id} — {title}"

        result = subprocess.run(
            ["gh", "gist", "create", "--public",
             "-d", description,
             md_path, csv_path, att_path],
            capture_output=True, text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"gh gist create failed: {result.stderr}")

        gist_url = result.stdout.strip()
        # Extract gist ID from URL (last path segment)
        gist_id = gist_url.rstrip("/").split("/")[-1]

        return {"gist_id": gist_id, "gist_url": gist_url}


def update_work_order_gist(gist_id: str, metadata: dict, attachments: list[dict] | None = None) -> dict:
    """Update an existing work order Gist.

    Uses gh api PATCH to replace file contents in-place.
    Returns dict with gist_id and gist_url.
    """
    if attachments:
        att_lines = []
        for att in attachments:
            att_lines.append(f"- **{att.get('type', 'file')}**: {att.get('description', '')} — {att.get('url', '')}")
        metadata["attachments_section"] = "\n".join(att_lines)

    md_content = render_work_order_md(metadata)
    csv_content = render_work_order_csv(metadata)
    att_content = render_attachments_txt(attachments or [])

    import json
    payload = json.dumps({
        "files": {
            "work-order.md": {"content": md_content},
            "work-order.csv": {"content": csv_content},
            "attachments.txt": {"content": att_content},
        }
    })

    result = subprocess.run(
        ["gh", "api", "--method", "PATCH", f"/gists/{gist_id}",
         "--input", "-"],
        input=payload, capture_output=True, text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"gh gist edit failed: {result.stderr}")

    gist_url = f"https://gist.github.com/{gist_id}"
    return {"gist_id": gist_id, "gist_url": gist_url}
