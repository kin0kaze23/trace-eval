"""Tests for typed converter and judge registries."""

from __future__ import annotations

import pytest

from trace_eval.registry import (
    CONVERTER_REGISTRY,
    JUDGE_REGISTRY,
    ConverterEntry,
    ConverterRegistry,
    JudgeEntry,
    JudgeRegistry,
)


# ---------------------------------------------------------------------------
# ConverterRegistry tests
# ---------------------------------------------------------------------------


class TestConverterRegistry:
    """Test the ConverterRegistry class."""

    def test_register_and_get(self):
        """Register a converter and retrieve it by canonical name."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("test-format", aliases=["tf"], converter=dummy)

        assert reg.get("test-format") is dummy
        assert reg.get("tf") is dummy

    def test_canonical_name_lookup(self):
        """Canonical name lookup works."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("my-format", aliases=[], converter=dummy)
        assert reg.get("my-format") is dummy

    def test_alias_lookup(self):
        """Alias lookup works."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("my-format", aliases=["mf", "my_fmt"], converter=dummy)
        assert reg.get("mf") is dummy
        assert reg.get("my_fmt") is dummy

    def test_case_insensitive_lookup(self):
        """Lookup is case-insensitive."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("My-Format", aliases=["MyAlias"], converter=dummy)
        assert reg.get("my-format") is dummy
        assert reg.get("MY-FORMAT") is dummy
        assert reg.get("myalias") is dummy

    def test_hyphen_underscore_equivalence(self):
        """Hyphens and underscores are equivalent in lookup."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("claude-code", aliases=["claude_code"], converter=dummy)
        assert reg.get("claude_code") is dummy
        assert reg.get("claude-code") is dummy

    def test_unknown_format_raises_key_error(self):
        """Unknown format raises KeyError with supported formats."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("known", aliases=[], converter=dummy)

        with pytest.raises(KeyError, match="Unknown converter format: 'unknown'"):
            reg.get("unknown")

    def test_duplicate_canonical_name_rejected(self):
        """Duplicate canonical names are rejected."""
        reg = ConverterRegistry()
        dummy1 = lambda p: []  # noqa: E731
        dummy2 = lambda p: []  # noqa: E731
        reg.register("format-a", aliases=[], converter=dummy1)

        with pytest.raises(ValueError, match="Duplicate converter canonical name"):
            reg.register("format-a", aliases=[], converter=dummy2)

    def test_duplicate_alias_rejected(self):
        """Duplicate aliases across entries are rejected."""
        reg = ConverterRegistry()
        dummy1 = lambda p: []  # noqa: E731
        dummy2 = lambda p: []  # noqa: E731
        reg.register("format-a", aliases=["shared"], converter=dummy1)

        with pytest.raises(ValueError, match="Duplicate converter alias: 'shared'"):
            reg.register("format-b", aliases=["shared"], converter=dummy2)

    def test_is_supported(self):
        """is_supported returns True for registered formats."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("fmt", aliases=["al"], converter=dummy)

        assert reg.is_supported("fmt") is True
        assert reg.is_supported("al") is True
        assert reg.is_supported("nope") is False

    def test_contains(self):
        """__contains__ works via is_supported."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("fmt", aliases=[], converter=dummy)

        assert "fmt" in reg
        assert "nope" not in reg

    def test_canonical_names_order(self):
        """canonical_names returns names in registration order."""
        reg = ConverterRegistry()
        d1 = lambda p: []  # noqa: E731
        d2 = lambda p: []  # noqa: E731
        d3 = lambda p: []  # noqa: E731
        reg.register("c", aliases=[], converter=d1)
        reg.register("a", aliases=[], converter=d2)
        reg.register("b", aliases=[], converter=d3)

        assert reg.canonical_names == ["c", "a", "b"]

    def test_all_aliases(self):
        """all_aliases returns alias -> canonical mapping."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("canonical", aliases=["al1", "al2"], converter=dummy)

        aliases = reg.all_aliases
        assert aliases["al1"] == "canonical"
        assert aliases["al2"] == "canonical"

    def test_entries_returns_all(self):
        """entries() returns all registered entries."""
        reg = ConverterRegistry()
        d1 = lambda p: []  # noqa: E731
        d2 = lambda p: []  # noqa: E731
        reg.register("a", aliases=[], converter=d1, description="A")
        reg.register("b", aliases=[], converter=d2, description="B")

        entries = reg.entries()
        assert len(entries) == 2
        assert entries[0].canonical_name == "a"
        assert entries[1].canonical_name == "b"

    def test_len(self):
        """__len__ returns number of registered entries."""
        reg = ConverterRegistry()
        assert len(reg) == 0

        dummy = lambda p: []  # noqa: E731
        reg.register("a", aliases=[], converter=dummy)
        assert len(reg) == 1

        reg.register("b", aliases=[], converter=dummy)
        assert len(reg) == 2

    def test_converter_entry_matches(self):
        """ConverterEntry.matches() checks canonical and alias."""
        entry = ConverterEntry(
            canonical_name="test",
            aliases=["al"],
            converter=lambda p: [],
        )
        assert entry.matches("test") is True
        assert entry.matches("al") is True
        assert entry.matches("nope") is False


class TestGlobalConverterRegistry:
    """Test the global CONVERTER_REGISTRY singleton."""

    def test_has_claude_code(self):
        """Global registry has claude-code converter."""
        assert "claude-code" in CONVERTER_REGISTRY
        assert CONVERTER_REGISTRY.is_supported("claude-code")

    def test_has_openclaw(self):
        """Global registry has openclaw converter."""
        assert "openclaw" in CONVERTER_REGISTRY

    def test_has_cursor(self):
        """Global registry has cursor converter."""
        assert "cursor" in CONVERTER_REGISTRY

    def test_aliases_work(self):
        """Claude Code aliases work."""
        assert CONVERTER_REGISTRY.is_supported("claude_code")

    def test_three_entries(self):
        """Global registry has exactly 3 entries."""
        assert len(CONVERTER_REGISTRY) == 3


# ---------------------------------------------------------------------------
# JudgeRegistry tests
# ---------------------------------------------------------------------------


class TestJudgeRegistry:
    """Test the JudgeRegistry class."""

    def test_register_and_get(self):
        """Register a judge and retrieve it by dimension key."""
        reg = JudgeRegistry()
        dummy = lambda events: None  # noqa: E731
        reg.register("reliability", judge=dummy)

        assert reg.get("reliability") is dummy

    def test_unknown_dimension_raises_key_error(self):
        """Unknown dimension raises KeyError with available dimensions."""
        reg = JudgeRegistry()
        dummy = lambda events: None  # noqa: E731
        reg.register("reliability", judge=dummy)

        with pytest.raises(KeyError, match="Unknown judge dimension: 'unknown'"):
            reg.get("unknown")

    def test_duplicate_dimension_rejected(self):
        """Duplicate dimension keys are rejected."""
        reg = JudgeRegistry()
        d1 = lambda events: None  # noqa: E731
        d2 = lambda events: None  # noqa: E731
        reg.register("dim", judge=d1)

        with pytest.raises(ValueError, match="Duplicate judge dimension key"):
            reg.register("dim", judge=d2)

    def test_is_registered(self):
        """is_registered returns True for registered dimensions."""
        reg = JudgeRegistry()
        dummy = lambda events: None  # noqa: E731
        reg.register("dim", judge=dummy)

        assert reg.is_registered("dim") is True
        assert reg.is_registered("nope") is False

    def test_contains(self):
        """__contains__ works via is_registered."""
        reg = JudgeRegistry()
        dummy = lambda events: None  # noqa: E731
        reg.register("dim", judge=dummy)

        assert "dim" in reg
        assert "nope" not in reg

    def test_dimension_keys_order(self):
        """dimension_keys returns keys in registration order."""
        reg = JudgeRegistry()
        d1 = lambda events: None  # noqa: E731
        d2 = lambda events: None  # noqa: E731
        d3 = lambda events: None  # noqa: E731
        reg.register("c", judge=d1)
        reg.register("a", judge=d2)
        reg.register("b", judge=d3)

        assert reg.dimension_keys == ["c", "a", "b"]

    def test_ordered_keys_by_order_field(self):
        """ordered_keys sorts by order field, then alphabetically."""
        reg = JudgeRegistry()
        d1 = lambda events: None  # noqa: E731
        d2 = lambda events: None  # noqa: E731
        d3 = lambda events: None  # noqa: E731
        reg.register("b", judge=d1, order=2)
        reg.register("a", judge=d2, order=0)
        reg.register("c", judge=d3, order=1)

        assert reg.ordered_keys == ["a", "c", "b"]

    def test_ordered_keys_tie_breaks_alpha(self):
        """ordered_keys breaks ties alphabetically."""
        reg = JudgeRegistry()
        d1 = lambda events: None  # noqa: E731
        d2 = lambda events: None  # noqa: E731
        reg.register("b", judge=d1, order=0)
        reg.register("a", judge=d2, order=0)

        assert reg.ordered_keys == ["a", "b"]

    def test_get_judge_dict(self):
        """get_judge_dict returns {key: judge} in registration order."""
        reg = JudgeRegistry()
        d1 = lambda events: "a"  # noqa: E731
        d2 = lambda events: "b"  # noqa: E731
        reg.register("x", judge=d1)
        reg.register("y", judge=d2)

        jd = reg.get_judge_dict()
        assert list(jd.keys()) == ["x", "y"]
        assert jd["x"]([]) == "a"
        assert jd["y"]([]) == "b"

    def test_entries_returns_all(self):
        """entries() returns all registered entries."""
        reg = JudgeRegistry()
        d1 = lambda events: None  # noqa: E731
        d2 = lambda events: None  # noqa: E731
        reg.register("a", judge=d1, display_label="A")
        reg.register("b", judge=d2, display_label="B")

        entries = reg.entries()
        assert len(entries) == 2
        assert entries[0].dimension_key == "a"
        assert entries[1].dimension_key == "b"

    def test_ordered_entries_by_order(self):
        """ordered_entries() returns entries sorted by order field."""
        reg = JudgeRegistry()
        d1 = lambda events: None  # noqa: E731
        d2 = lambda events: None  # noqa: E731
        reg.register("b", judge=d1, order=2)
        reg.register("a", judge=d2, order=0)

        entries = reg.ordered_entries()
        assert entries[0].dimension_key == "a"
        assert entries[1].dimension_key == "b"

    def test_len(self):
        """__len__ returns number of registered entries."""
        reg = JudgeRegistry()
        assert len(reg) == 0

        dummy = lambda events: None  # noqa: E731
        reg.register("a", judge=dummy)
        assert len(reg) == 1

    def test_judge_entry_display_label_auto_generated(self):
        """JudgeEntry auto-generates display_label from dimension_key."""
        entry = JudgeEntry(
            dimension_key="tool_discipline",
            judge=lambda events: None,
        )
        assert entry.display_label == "Tool Discipline"

    def test_judge_entry_display_label_explicit(self):
        """JudgeEntry uses explicit display_label when provided."""
        entry = JudgeEntry(
            dimension_key="dim",
            judge=lambda events: None,
            display_label="My Label",
        )
        assert entry.display_label == "My Label"


class TestGlobalJudgeRegistry:
    """Test the global JUDGE_REGISTRY singleton."""

    def test_has_reliability(self):
        """Global registry has reliability judge."""
        assert "reliability" in JUDGE_REGISTRY

    def test_has_efficiency(self):
        """Global registry has efficiency judge."""
        assert "efficiency" in JUDGE_REGISTRY

    def test_has_retrieval(self):
        """Global registry has retrieval judge."""
        assert "retrieval" in JUDGE_REGISTRY

    def test_has_tool_discipline(self):
        """Global registry has tool_discipline judge."""
        assert "tool_discipline" in JUDGE_REGISTRY

    def test_has_context(self):
        """Global registry has context judge."""
        assert "context" in JUDGE_REGISTRY

    def test_five_entries(self):
        """Global registry has exactly 5 entries."""
        assert len(JUDGE_REGISTRY) == 5

    def test_ordered_keys_stable(self):
        """ordered_keys returns dimensions in stable order."""
        keys = JUDGE_REGISTRY.ordered_keys
        assert keys == ["reliability", "efficiency", "retrieval", "tool_discipline", "context"]

    def test_get_judge_dict_callable(self):
        """get_judge_dict returns callable judges."""
        jd = JUDGE_REGISTRY.get_judge_dict()
        assert callable(jd["reliability"])
        assert callable(jd["efficiency"])
        assert callable(jd["retrieval"])
        assert callable(jd["tool_discipline"])
        assert callable(jd["context"])
