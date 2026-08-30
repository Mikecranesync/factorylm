from pathlib import Path


def test_brain_server_source_has_no_conflict_markers_and_compiles() -> None:
    source_path = Path(__file__).parents[1] / "services" / "mcp" / "brain_server.py"
    source = source_path.read_text(encoding="utf-8")

    for marker in ("<<<<<<<", "=======", ">>>>>>>"):
        assert marker not in source

    compile(source, str(source_path), "exec")
    assert "from kb.chunker import chunk_file" in source
    assert 'chunk_file(file_path, extra_metadata={"tags": tags})' in source
