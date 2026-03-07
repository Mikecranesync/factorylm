"""
V1 Benchmark Test Suite
========================
Deterministic tests for the V1 milestone components:
1. Intent classification (keyword stage)
2. KB chunking (semantic splitter)
3. Diagnosis prompt construction with source citations
4. LLM fallback path coverage

Run with: pytest tests/test_v1_benchmark.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure monorepo root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# 1. Intent Classification — Keyword Stage
# ---------------------------------------------------------------------------

from openclaw.types import Intent
from openclaw.messages.intent import classify_intent, _keyword_classify, _llm_classify


class TestKeywordClassify:
    """Test that keyword scoring returns correct intent scores."""

    @pytest.mark.parametrize("text,expected_intent", [
        ("why did the conveyor stop", Intent.DIAGNOSE),
        ("there's a fault on pump 3", Intent.DIAGNOSE),
        ("motor alarm tripped", Intent.DIAGNOSE),
        ("what went wrong with the VFD", Intent.DIAGNOSE),
        ("diagnose the compressor issue", Intent.DIAGNOSE),
    ])
    def test_diagnose_keywords(self, text, expected_intent):
        scores = _keyword_classify(text.lower())
        assert expected_intent in scores
        assert scores[expected_intent] == max(scores.values())

    @pytest.mark.parametrize("text,expected_intent", [
        ("troubleshoot the drive", Intent.TROUBLESHOOT),
        ("walk me through fixing the motor", Intent.TROUBLESHOOT),
        ("step by step guide for pump repair", Intent.TROUBLESHOOT),
        ("how do i fix the conveyor belt", Intent.TROUBLESHOOT),
    ])
    def test_troubleshoot_keywords(self, text, expected_intent):
        scores = _keyword_classify(text.lower())
        assert expected_intent in scores
        assert scores[expected_intent] == max(scores.values())

    @pytest.mark.parametrize("text,expected_intent", [
        ("what is the system status", Intent.STATUS),
        ("is the PLC online", Intent.STATUS),
        ("check if conveyor is running", Intent.STATUS),
        ("health check", Intent.STATUS),
    ])
    def test_status_keywords(self, text, expected_intent):
        scores = _keyword_classify(text.lower())
        assert expected_intent in scores
        assert scores[expected_intent] == max(scores.values())

    @pytest.mark.parametrize("text,expected_intent", [
        ("show io for cell 1", Intent.IO),
        ("what are the live io values", Intent.IO),
        ("read plc tags", Intent.IO),
        ("show me the inputs and outputs", Intent.IO),
    ])
    def test_io_keywords(self, text, expected_intent):
        scores = _keyword_classify(text.lower())
        assert expected_intent in scores
        assert scores[expected_intent] == max(scores.values())

    @pytest.mark.parametrize("text,expected_intent", [
        ("reconstruct the wiring diagram", Intent.WIRING_RECONSTRUCT),
        ("rebuild wiring from photo", Intent.WIRING_RECONSTRUCT),
        ("no drawings for this panel", Intent.WIRING_RECONSTRUCT),
        ("trace wiring in the cabinet", Intent.WIRING_RECONSTRUCT),
    ])
    def test_wiring_keywords(self, text, expected_intent):
        scores = _keyword_classify(text.lower())
        assert expected_intent in scores
        assert scores[expected_intent] == max(scores.values())

    @pytest.mark.parametrize("text,expected_intent", [
        ("what is this component", Intent.KB_ENRICH_COMPONENT),
        ("identify this part number", Intent.KB_ENRICH_COMPONENT),
        ("nameplate says ABB ACS580", Intent.KB_ENRICH_COMPONENT),
        ("close-up of the data plate", Intent.KB_ENRICH_COMPONENT),
    ])
    def test_kb_enrich_keywords(self, text, expected_intent):
        scores = _keyword_classify(text.lower())
        assert expected_intent in scores
        assert scores[expected_intent] == max(scores.values())


class TestClassifyIntent:
    """Test the full classify_intent function (keyword stage only, no LLM)."""

    def test_no_keywords_no_photo_returns_general(self):
        assert classify_intent("hello there") == Intent.GENERAL

    def test_photo_no_keywords_no_project_returns_kb_enrich(self):
        assert classify_intent("", has_photo=True) == Intent.KB_ENRICH_COMPONENT

    def test_photo_no_keywords_with_project_returns_wiring(self):
        assert classify_intent("", has_photo=True, has_active_project=True) == Intent.WIRING_RECONSTRUCT

    def test_photo_with_kb_keyword_and_project_returns_wiring(self):
        result = classify_intent("close-up of component", has_photo=True, has_active_project=True)
        assert result == Intent.WIRING_RECONSTRUCT

    def test_diagnose_wins_over_general(self):
        assert classify_intent("why did it stop") == Intent.DIAGNOSE

    def test_empty_text_no_photo_returns_general(self):
        assert classify_intent("") == Intent.GENERAL

    def test_multiple_keywords_picks_highest_score(self):
        # "reconstruct the wiring diagram" has "reconstruct" + "wiring diagram" = 2 hits
        result = classify_intent("reconstruct the wiring diagram")
        assert result == Intent.WIRING_RECONSTRUCT


# ---------------------------------------------------------------------------
# 2. KB Chunker
# ---------------------------------------------------------------------------

from kb.chunker import chunk_document, Chunk


class TestChunkDocument:
    """Test semantic document chunking."""

    SAMPLE_DOC = """# Conveyor System Maintenance

## Belt Alignment

The Allen-Bradley PowerFlex 525 VFD controls belt speed.
Check alignment monthly using laser tool.
Misalignment causes premature bearing failure.

## Motor Inspection

The WEG W22 motor requires quarterly inspection.
Check winding resistance and insulation.
Replace bearings every 20,000 hours.

## Troubleshooting

If the VFD shows fault code F081:
1. Check input voltage
2. Verify DC bus voltage
3. Reset and retry
"""

    def test_chunks_are_produced(self):
        chunks = chunk_document(self.SAMPLE_DOC, chunk_size=200, chunk_overlap=50)
        assert len(chunks) > 1

    def test_chunks_have_text(self):
        chunks = chunk_document(self.SAMPLE_DOC, chunk_size=200, chunk_overlap=50)
        for chunk in chunks:
            assert len(chunk.text) > 0

    def test_equipment_extraction(self):
        chunks = chunk_document(self.SAMPLE_DOC, chunk_size=2000)
        all_equipment = set()
        for chunk in chunks:
            all_equipment.update(chunk.metadata.get("equipment", []))
        assert any("PowerFlex" in eq for eq in all_equipment)
        assert any("WEG" in eq for eq in all_equipment)

    def test_section_metadata(self):
        chunks = chunk_document(self.SAMPLE_DOC, chunk_size=200, chunk_overlap=50)
        sections = [c.metadata.get("section") for c in chunks if c.metadata.get("section")]
        assert len(sections) > 0

    def test_small_doc_returns_single_chunk(self):
        chunks = chunk_document("Short document with enough text to pass the filter.", chunk_size=1000)
        assert len(chunks) == 1

    def test_extra_metadata_propagates(self):
        chunks = chunk_document(
            self.SAMPLE_DOC,
            chunk_size=2000,
            extra_metadata={"tags": ["test", "conveyor"]},
        )
        for chunk in chunks:
            assert chunk.metadata.get("tags") == ["test", "conveyor"]

    def test_source_metadata(self):
        chunks = chunk_document(self.SAMPLE_DOC, source="test-file.md")
        for chunk in chunks:
            assert chunk.metadata["source"] == "test-file.md"

    def test_very_short_chunks_filtered(self):
        doc = "Header\n\nA\n\nB\n\nThis is a sufficiently long paragraph for testing purposes."
        chunks = chunk_document(doc, chunk_size=500)
        for chunk in chunks:
            assert len(chunk.text) >= 30


# ---------------------------------------------------------------------------
# 3. Diagnosis Prompt Construction + Source Citation
# ---------------------------------------------------------------------------


class TestDiagnosisPrompt:
    """Test prompt construction with KB context and source citations."""

    def test_import_build_diagnosis_prompt(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "diagnosis"))
        from main import _build_diagnosis_prompt
        prompt = _build_diagnosis_prompt("why stopped?", "Conveyor=OFF, Fault=TRUE")
        assert "why stopped?" in prompt
        assert "Conveyor=OFF" in prompt

    def test_kb_context_included_in_prompt(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "diagnosis"))
        from main import _build_diagnosis_prompt
        kb = "Relevant maintenance knowledge from KB:\n- Check belt tension [source: manual.md]"
        prompt = _build_diagnosis_prompt("why stopped?", "Conveyor=OFF", kb_context=kb)
        assert "maintenance knowledge" in prompt
        assert "manual.md" in prompt

    def test_no_kb_context_still_works(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "diagnosis"))
        from main import _build_diagnosis_prompt
        prompt = _build_diagnosis_prompt("status?", "All OK", kb_context=None)
        assert "status?" in prompt
        assert "maintenance knowledge" not in prompt

    def test_diagnosis_response_has_sources_field(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "diagnosis"))
        from main import DiagnosisResponse
        resp = DiagnosisResponse(
            question="test",
            diagnosis="test diagnosis",
            plc_data={},
            sources=["manual.md", "brain"],
            timestamp="2026-03-07T00:00:00",
            latency_ms=100,
        )
        assert resp.sources == ["manual.md", "brain"]

    def test_diagnosis_response_sources_default_empty(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "diagnosis"))
        from main import DiagnosisResponse
        resp = DiagnosisResponse(
            question="test",
            diagnosis="test",
            timestamp="2026-03-07T00:00:00",
            latency_ms=50,
        )
        assert resp.sources == []


# ---------------------------------------------------------------------------
# 4. Benchmark Golden Answers — Intent Classification
# ---------------------------------------------------------------------------


class TestIntentGoldenSet:
    """Golden test set: real-world technician messages mapped to expected intents.

    These represent the benchmark for V1 quality. If any of these fail,
    the intent classifier has regressed.
    """

    GOLDEN_CASES = [
        # (message, has_photo, has_active_project, expected_intent)
        ("the conveyor stopped and there's a red light", False, False, Intent.DIAGNOSE),
        ("motor is making a grinding noise", False, False, Intent.DIAGNOSE),
        ("VFD showing error code F081", False, False, Intent.DIAGNOSE),
        ("why is pump 3 tripping on overload", False, False, Intent.DIAGNOSE),
        ("walk me through replacing the contactor", False, False, Intent.TROUBLESHOOT),
        ("how do i fix the alignment on this belt", False, False, Intent.TROUBLESHOOT),
        ("is the PLC connected", False, False, Intent.STATUS),
        ("show io for the packaging line", False, False, Intent.IO),
        ("read plc tags for cell 2", False, False, Intent.IO),
        ("rebuild wiring from these photos", False, False, Intent.WIRING_RECONSTRUCT),
        ("no drawings exist for this panel", False, False, Intent.WIRING_RECONSTRUCT),
        ("what is this part", False, False, Intent.KB_ENRICH_COMPONENT),
        ("", True, False, Intent.KB_ENRICH_COMPONENT),
        ("", True, True, Intent.WIRING_RECONSTRUCT),
        ("hey", False, False, Intent.GENERAL),
        ("good morning", False, False, Intent.GENERAL),
    ]

    @pytest.mark.parametrize("text,has_photo,has_project,expected", GOLDEN_CASES,
                             ids=[c[0][:40] or f"photo={c[1]},proj={c[2]}" for c in GOLDEN_CASES])
    def test_golden_intent(self, text, has_photo, has_project, expected):
        result = classify_intent(text, has_photo=has_photo, has_active_project=has_project)
        assert result == expected, f"Expected {expected.value}, got {result.value} for: '{text}'"


# ---------------------------------------------------------------------------
# 5. LLM Fallback Path Coverage
# ---------------------------------------------------------------------------


def _mock_groq_response(intent_name: str, confidence: float = 0.9, status_code: int = 200):
    """Build a mock requests.Response for Groq API."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": f'{{"intent": "{intent_name}", "confidence": {confidence}}}'}}]
    }
    return mock_resp


class TestLLMFallback:
    """Test the LLM fallback path in intent classification (no real API calls)."""

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    @patch("requests.post")
    def test_ambiguous_input_triggers_llm_classify(self, mock_post):
        """Ambiguous text with use_llm_fallback=True reaches the LLM path."""
        mock_post.return_value = _mock_groq_response("DIAGNOSE")
        # "the machine seems off" has no keyword hits
        result = classify_intent("the machine seems off", use_llm_fallback=True)
        assert mock_post.called, "_llm_classify was never called"
        assert result == Intent.DIAGNOSE

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    @patch("requests.post")
    def test_llm_classify_valid_response_used(self, mock_post):
        """_llm_classify returns correct Intent from valid Groq response."""
        mock_post.return_value = _mock_groq_response("TROUBLESHOOT", 0.85)
        result = _llm_classify("can you help me with this pump")
        assert result == Intent.TROUBLESHOOT

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    @patch("requests.post")
    def test_llm_classify_garbage_response_falls_back_to_general(self, mock_post):
        """Invalid intent name from LLM → None → classify_intent returns GENERAL."""
        mock_post.return_value = _mock_groq_response("INVALID_INTENT_XYZ")
        result = classify_intent("something ambiguous", use_llm_fallback=True)
        assert result == Intent.GENERAL

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    @patch("requests.post", side_effect=Exception("connection timeout"))
    def test_llm_classify_exception_no_crash(self, mock_post):
        """LLM call exception → graceful fallback to GENERAL, no crash."""
        result = classify_intent("something ambiguous here", use_llm_fallback=True)
        assert result == Intent.GENERAL
