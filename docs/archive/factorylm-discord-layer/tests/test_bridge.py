"""Tests for the Telegram <-> Discord message bridge."""

from __future__ import annotations

from factorylm.relay.bridge import DEFAULT_COLOR, SEVERITY_COLORS, MessageBridge


class TestTelegramToDiscord:
    def test_bold_conversion(self):
        result = MessageBridge.telegram_to_discord("*bold text*")
        assert result == "**bold text**"

    def test_italic_conversion(self):
        result = MessageBridge.telegram_to_discord("_italic text_")
        assert result == "*italic text*"

    def test_code_preserved(self):
        result = MessageBridge.telegram_to_discord("`code`")
        assert result == "`code`"

    def test_code_block_preserved(self):
        result = MessageBridge.telegram_to_discord("```python\nprint('hello')\n```")
        assert result == "```python\nprint('hello')\n```"

    def test_html_stripped(self):
        result = MessageBridge.telegram_to_discord("<b>bold</b> and <i>italic</i>")
        assert result == "bold and italic"

    def test_mixed_formatting(self):
        result = MessageBridge.telegram_to_discord("*bold* and _italic_ and `code`")
        assert "**bold**" in result
        assert "*italic*" in result
        assert "`code`" in result

    def test_bold_inside_code_not_converted(self):
        result = MessageBridge.telegram_to_discord("`*not bold*`")
        assert result == "`*not bold*`"

    def test_plain_text_unchanged(self):
        result = MessageBridge.telegram_to_discord("just plain text")
        assert result == "just plain text"

    def test_empty_string(self):
        result = MessageBridge.telegram_to_discord("")
        assert result == ""


class TestTruncate:
    def test_short_text_unchanged(self):
        result = MessageBridge.truncate("short text", limit=100)
        assert result == "short text"

    def test_exact_limit_unchanged(self):
        text = "x" * 1900
        result = MessageBridge.truncate(text, limit=1900)
        assert result == text

    def test_long_text_truncated(self):
        text = "x" * 2000
        result = MessageBridge.truncate(text, limit=1900)
        assert len(result) <= 1900
        assert "truncated" in result
        assert "chars omitted" in result

    def test_truncation_on_newline_boundary(self):
        lines = ["line " + str(i) for i in range(200)]
        text = "\n".join(lines)
        result = MessageBridge.truncate(text, limit=100)
        # Should end at a newline boundary, not mid-word
        before_suffix = result.split("\n...[truncated")[0]
        assert before_suffix.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"))

    def test_truncation_suffix_shows_char_count(self):
        text = "a" * 2000
        result = MessageBridge.truncate(text, limit=1900)
        # Extract the number from the suffix
        import re

        match = re.search(r"(\d+) chars omitted", result)
        assert match is not None
        omitted = int(match.group(1))
        assert omitted > 0

    def test_no_newline_falls_back_to_limit(self):
        text = "x" * 2000  # no newlines
        result = MessageBridge.truncate(text, limit=100)
        assert len(result) <= 100
        assert "truncated" in result


class TestBuildEmbed:
    def test_basic_embed(self):
        embed = MessageBridge.build_embed("Test Title", "Test Description")
        assert embed["title"] == "Test Title"
        assert embed["description"] == "Test Description"
        assert embed["color"] == DEFAULT_COLOR

    def test_embed_with_fields(self):
        fields = [
            {"name": "Field 1", "value": "Value 1", "inline": True},
            {"name": "Field 2", "value": "Value 2"},
        ]
        embed = MessageBridge.build_embed("Title", fields=fields)
        assert len(embed["fields"]) == 2
        assert embed["fields"][0]["inline"] is True
        assert embed["fields"][1]["inline"] is False  # default

    def test_embed_custom_color(self):
        embed = MessageBridge.build_embed("Title", color=0xFF0000)
        assert embed["color"] == 0xFF0000

    def test_embed_no_description(self):
        embed = MessageBridge.build_embed("Title")
        assert "description" not in embed

    def test_embed_no_fields(self):
        embed = MessageBridge.build_embed("Title")
        assert "fields" not in embed


class TestBuildAlertEmbed:
    def test_info_severity(self):
        embed = MessageBridge.build_alert_embed("Tony", "All good", "info")
        assert embed["color"] == SEVERITY_COLORS["info"]  # green
        assert embed["title"] == "Alert: INFO"

    def test_warning_severity(self):
        embed = MessageBridge.build_alert_embed("Ultron", "Watch out", "warning")
        assert embed["color"] == SEVERITY_COLORS["warning"]  # yellow

    def test_critical_severity(self):
        embed = MessageBridge.build_alert_embed("Jarvis", "PLC down!", "critical")
        assert embed["color"] == SEVERITY_COLORS["critical"]  # red

    def test_unknown_severity_uses_default(self):
        embed = MessageBridge.build_alert_embed("Tony", "Hmm", "unknown")
        assert embed["color"] == DEFAULT_COLOR

    def test_has_timestamp(self):
        embed = MessageBridge.build_alert_embed("Tony", "Test")
        assert "timestamp" in embed

    def test_has_agent_footer(self):
        embed = MessageBridge.build_alert_embed("Tony", "Test")
        assert embed["footer"]["text"] == "Agent: Tony"

    def test_case_insensitive_severity(self):
        embed = MessageBridge.build_alert_embed("Tony", "Test", "WARNING")
        assert embed["color"] == SEVERITY_COLORS["warning"]
