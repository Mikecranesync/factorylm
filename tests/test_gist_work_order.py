"""Tests for cmms.gist_work_order module."""

import re
import unittest
from unittest.mock import patch, MagicMock

import sys
import os

# Ensure the repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cmms.gist_work_order import (
    CSV_COLUMNS,
    generate_wo_id,
    render_work_order_md,
    render_work_order_csv,
    render_attachments_txt,
    create_work_order_gist,
)

SAMPLE_METADATA = {
    "work_order_id": "WO-2026-0217-001",
    "title": "Motor Bearing Failure — Conveyor Line 3",
    "description": "Bearing noise detected on conveyor drive motor M3. "
                   "Vibration reading 12mm/s (threshold 8mm/s).",
    "status": "open",
    "priority": "high",
    "asset_name": "Conveyor Drive Motor",
    "asset_id": "M3-CONV-L3",
    "location": "Production Hall A",
    "site": "Lakeland Plant",
    "assigned_to": "Mike Crane",
    "work_type": "Corrective",
    "category": "Mechanical",
    "channel": "Telegram",
    "reported_by": "Vibration Monitor",
    "estimated_hours": "4",
    "failure_code": "BEAR-WEAR",
}

SAMPLE_ATTACHMENTS = [
    {"type": "photo", "description": "Motor nameplate", "url": "https://example.com/photo1.jpg"},
    {"type": "diagram", "description": "Conveyor drive wiring", "url": "https://example.com/diagram1.png"},
]


class TestRenderWorkOrderMd(unittest.TestCase):
    def test_render_work_order_md(self):
        """Renders template and checks key fields are present."""
        md = render_work_order_md(SAMPLE_METADATA)
        self.assertIn("WO-2026-0217-001", md)
        self.assertIn("Motor Bearing Failure", md)
        self.assertIn("open", md)
        self.assertIn("high", md)
        self.assertIn("Conveyor Drive Motor", md)
        self.assertIn("M3-CONV-L3", md)
        self.assertIn("Lakeland Plant", md)
        self.assertIn("BEAR-WEAR", md)
        # Check structure
        self.assertIn("## Summary", md)
        self.assertIn("## Details", md)
        self.assertIn("## Attachments", md)


class TestRenderWorkOrderCsv(unittest.TestCase):
    def test_render_work_order_csv(self):
        """Validates header + data row and column count = 25."""
        csv_text = render_work_order_csv(SAMPLE_METADATA)
        lines = csv_text.strip().split("\n")
        self.assertEqual(len(lines), 2, "CSV should have header + 1 data row")

        header_cols = lines[0].split(",")
        self.assertEqual(len(header_cols), 25, f"Expected 25 columns, got {len(header_cols)}")

        # Verify header matches canonical column list
        self.assertEqual(header_cols, CSV_COLUMNS)

        # Verify data row has values
        self.assertIn("WO-2026-0217-001", lines[1])
        self.assertIn("open", lines[1])
        self.assertIn("high", lines[1])


class TestRenderAttachmentsTxt(unittest.TestCase):
    def test_render_attachments_txt(self):
        """Validates type,description,url format."""
        txt = render_attachments_txt(SAMPLE_ATTACHMENTS)
        lines = txt.strip().split("\n")
        self.assertEqual(lines[0], "type,description,url")
        self.assertEqual(len(lines), 3, "Header + 2 attachment lines")
        self.assertIn("photo,Motor nameplate,https://example.com/photo1.jpg", lines[1])
        self.assertIn("diagram,Conveyor drive wiring,https://example.com/diagram1.png", lines[2])


class TestAutoGenerateWoId(unittest.TestCase):
    def test_auto_generate_wo_id(self):
        """Checks WO-YYYY-MMDD-NNN format."""
        wo_id = generate_wo_id()
        pattern = r"^WO-\d{4}-\d{4}-\d{3}$"
        self.assertRegex(wo_id, pattern, f"WO ID '{wo_id}' doesn't match expected format")
        # Verify year is current
        self.assertTrue(wo_id.startswith("WO-20"))


class TestCreateWorkOrderGist(unittest.TestCase):
    @patch("cmms.gist_work_order.subprocess.run")
    def test_create_work_order_gist(self, mock_run):
        """Integration test — mocks subprocess for gh CLI."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://gist.github.com/Mikecranesync/abc123def456\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = create_work_order_gist(SAMPLE_METADATA.copy(), SAMPLE_ATTACHMENTS)

        self.assertEqual(result["gist_id"], "abc123def456")
        self.assertIn("gist.github.com", result["gist_url"])

        # Verify gh was called with correct args
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "gh")
        self.assertEqual(call_args[1], "gist")
        self.assertEqual(call_args[2], "create")
        self.assertEqual(call_args[3], "--public")

        # Check description contains [Jarvis Work Order]
        desc_idx = call_args.index("-d") + 1
        self.assertIn("[Jarvis Work Order]", call_args[desc_idx])


if __name__ == "__main__":
    unittest.main()
