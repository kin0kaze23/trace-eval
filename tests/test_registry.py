"""Tests for typed converter and judge registries.

This file tests:
- ConverterRegistry and JudgeRegistry classes (unit tests)
- Global singleton initialization (no hidden import side-effects)
- Converter dispatch through the authoritative registry
- Judge ordering via explicit order field (not registration order)
- Unified namespace collision detection
- Registry sealing / read-only behavior
"""

import pytest

from trace_eval.registry import (
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
        reg.register("my-format", aliases=[], converter=dummy)
        # Lookup works with either hyphens or underscores
        assert reg.get("my-format") is dummy
        assert reg.get("my_format") is dummy

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

    def test_canonical_conflicts_with_existing_alias(self):
        """New canonical name that matches an existing alias is rejected."""
        reg = ConverterRegistry()
        dummy1 = lambda p: []  # noqa: E731
        dummy2 = lambda p: []  # noqa: E731
        reg.register("format-a", aliases=["shared"], converter=dummy1)

        with pytest.raises(ValueError, match="conflicts with existing alias"):
            reg.register("shared", aliases=[], converter=dummy2)

    def test_alias_conflicts_with_existing_canonical(self):
        """New alias that matches an existing canonical name is rejected."""
        reg = ConverterRegistry()
        dummy1 = lambda p: []  # noqa: E731
        dummy2 = lambda p: []  # noqa: E731
        reg.register("format-a", aliases=[], converter=dummy1)

        with pytest.raises(ValueError, match="conflicts with existing canonical"):
            reg.register("format-b", aliases=["format-a"], converter=dummy2)

    def test_duplicate_alias_within_registration(self):
        """Duplicate aliases within one registration are rejected."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731

        with pytest.raises(ValueError, match="Duplicate converter alias within registration"):
            reg.register("format-a", aliases=["al", "AL"], converter=dummy)

    def test_alias_equivalent_to_canonical_rejected(self):
        """Alias that normalizes to the same name as canonical is rejected."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731

        # "claude_code" normalizes to "claude_code" which equals canonical "claude-code" normalized
        with pytest.raises(ValueError, match="normalizes to the same name as canonical"):
            reg.register("claude-code", aliases=["claude_code"], converter=dummy)

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

    def test_all_aliases_returns_declared_names(self):
        """all_aliases returns original alias strings mapped to declared canonical names."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("My-Format", aliases=["mf", "my_fmt"], converter=dummy)

        aliases = reg.all_aliases
        # Keys are the original alias strings as registered
        assert aliases["mf"] == "My-Format"
        assert aliases["my_fmt"] == "My-Format"

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


# ---------------------------------------------------------------------------
# ConverterRegistry sealing tests
# ---------------------------------------------------------------------------


class TestConverterRegistrySealing:
    """Test that sealed registries reject further registrations."""

    def test_seal_prevents_registration(self):
        """Sealed registry raises RuntimeError on register()."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("a", aliases=[], converter=dummy)
        reg.seal()

        with pytest.raises(RuntimeError, match="registry is sealed"):
            reg.register("b", aliases=[], converter=dummy)

    def test_is_sealed_property(self):
        """is_sealed reflects seal state."""
        reg = ConverterRegistry()
        assert reg.is_sealed is False
        reg.seal()
        assert reg.is_sealed is True

    def test_sealed_registry_still_readable(self):
        """Sealed registry still supports lookups."""
        reg = ConverterRegistry()
        dummy = lambda p: []  # noqa: E731
        reg.register("a", aliases=["al"], converter=dummy)
        reg.seal()

        assert reg.get("a") is dummy
        assert reg.get("al") is dummy
        assert reg.is_supported("a") is True
        assert len(reg) == 1


# ---------------------------------------------------------------------------
# Global converter registry tests (no hidden import side-effects)
# ---------------------------------------------------------------------------


class TestGlobalConverterRegistry:
    """Test the global CONVERTER_REGISTRY singleton.

    These tests import the populated registry directly from convert.py,
    which owns the registrations. No CLI import is required.
    """

    @pytest.fixture(autouse=True)
    def _load_registry(self):
        """Import the populated registry (triggers registration once)."""
        # Importing convert.py populates CONVERTER_REGISTRY
        from trace_eval.convert import CONVERTER_REGISTRY as reg

        self.reg = reg

    def test_has_claude_code(self):
        """Global registry has claude-code converter."""
        assert "claude-code" in self.reg
        assert self.reg.is_supported("claude-code")

    def test_has_openclaw(self):
        """Global registry has openclaw converter."""
        assert "openclaw" in self.reg

    def test_has_cursor(self):
        """Global registry has cursor converter."""
        assert "cursor" in self.reg

    def test_aliases_work(self):
        """Claude Code aliases work."""
        assert self.reg.is_supported("claude_code")

    def test_three_entries(self):
        """Global registry has exactly 3 entries."""
        assert len(self.reg) == 3

    def test_is_sealed(self):
        """Built-in converter registry is sealed."""
        assert self.reg.is_sealed is True

    def test_cannot_register_after_seal(self):
        """Cannot register new converters on sealed built-in."""
        dummy = lambda p: []  # noqa: E731
        with pytest.raises(RuntimeError, match="registry is sealed"):
            self.reg.register("new-format", aliases=[], converter=dummy)

    def test_convert_dispatches_through_registry(self):
        """convert() dispatches through CONVERTER_REGISTRY, not legacy dict."""
        from pathlib import Path
        from unittest.mock import patch

        from trace_eval.convert import CONVERTER_REGISTRY, convert

        sentinel = lambda p: [{"event": "sentinel"}]  # noqa: E731

        # Monkeypatch the registry's get() to return our sentinel
        original_get = CONVERTER_REGISTRY.get

        def mock_get(name: str):
            if name == "test-format":
                return sentinel
            return original_get(name)

        with patch.object(CONVERTER_REGISTRY, "get", side_effect=mock_get):
            result = convert(Path("dummy.jsonl"), fmt="test-format")

        assert result == [{"event": "sentinel"}]


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

    def test_get_judge_dict_uses_order_not_registration(self):
        """get_judge_dict returns judges in order field order, not registration order."""
        reg = JudgeRegistry()
        d1 = lambda events: "first"  # noqa: E731
        d2 = lambda events: "second"  # noqa: E731
        d3 = lambda events: "third"  # noqa: E731

        # Register in reverse order
        reg.register("c", judge=d3, order=2)
        reg.register("a", judge=d1, order=0)
        reg.register("b", judge=d2, order=1)

        jd = reg.get_judge_dict()
        assert list(jd.keys()) == ["a", "b", "c"]
        assert jd["a"]([]) == "first"
        assert jd["b"]([]) == "second"
        assert jd["c"]([]) == "third"

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


# ---------------------------------------------------------------------------
# JudgeRegistry sealing tests
# ---------------------------------------------------------------------------


class TestJudgeRegistrySealing:
    """Test that sealed registries reject further registrations."""

    def test_seal_prevents_registration(self):
        """Sealed registry raises RuntimeError on register()."""
        reg = JudgeRegistry()
        dummy = lambda events: None  # noqa: E731
        reg.register("a", judge=dummy)
        reg.seal()

        with pytest.raises(RuntimeError, match="registry is sealed"):
            reg.register("b", judge=dummy)

    def test_is_sealed_property(self):
        """is_sealed reflects seal state."""
        reg = JudgeRegistry()
        assert reg.is_sealed is False
        reg.seal()
        assert reg.is_sealed is True

    def test_sealed_registry_still_readable(self):
        """Sealed registry still supports lookups."""
        reg = JudgeRegistry()
        dummy = lambda events: None  # noqa: E731
        reg.register("a", judge=dummy)
        reg.seal()

        assert reg.get("a") is dummy
        assert reg.is_registered("a") is True
        assert len(reg) == 1


# ---------------------------------------------------------------------------
# Global judge registry tests (no hidden import side-effects)
# ---------------------------------------------------------------------------


class TestGlobalJudgeRegistry:
    """Test the global JUDGE_REGISTRY singleton.

    These tests import the populated registry directly from
    trace_eval.judges.registry, which owns the registrations.
    No CLI import is required.
    """

    @pytest.fixture(autouse=True)
    def _load_registry(self):
        """Import the populated registry (triggers registration once)."""
        from trace_eval.judges.registry import JUDGE_REGISTRY as reg

        self.reg = reg

    def test_has_reliability(self):
        """Global registry has reliability judge."""
        assert "reliability" in self.reg

    def test_has_efficiency(self):
        """Global registry has efficiency judge."""
        assert "efficiency" in self.reg

    def test_has_retrieval(self):
        """Global registry has retrieval judge."""
        assert "retrieval" in self.reg

    def test_has_tool_discipline(self):
        """Global registry has tool_discipline judge."""
        assert "tool_discipline" in self.reg

    def test_has_context(self):
        """Global registry has context judge."""
        assert "context" in self.reg

    def test_five_entries(self):
        """Global registry has exactly 5 entries."""
        assert len(self.reg) == 5

    def test_ordered_keys_stable(self):
        """ordered_keys returns dimensions in stable order."""
        keys = self.reg.ordered_keys
        assert keys == ["reliability", "efficiency", "retrieval", "tool_discipline", "context"]

    def test_get_judge_dict_callable(self):
        """get_judge_dict returns callable judges."""
        jd = self.reg.get_judge_dict()
        assert callable(jd["reliability"])
        assert callable(jd["efficiency"])
        assert callable(jd["retrieval"])
        assert callable(jd["tool_discipline"])
        assert callable(jd["context"])

    def test_is_sealed(self):
        """Built-in judge registry is sealed."""
        assert self.reg.is_sealed is True

    def test_cannot_register_after_seal(self):
        """Cannot register new judges on sealed built-in."""
        dummy = lambda events: None  # noqa: E731
        with pytest.raises(RuntimeError, match="registry is sealed"):
            self.reg.register("new-dimension", judge=dummy)

    def test_judge_dict_order_matches_ordered_keys(self):
        """get_judge_dict order matches ordered_keys order."""
        jd = self.reg.get_judge_dict()
        assert list(jd.keys()) == self.reg.ordered_keys

    def test_no_cli_import_required(self):
        """Populated judge registry can be imported without importing CLI."""
        import sys

        # Temporarily remove trace_eval.cli from imported modules if present
        cli_module = sys.modules.pop("trace_eval.cli", None)
        try:
            # Re-import should work without CLI
            from importlib import reload

            from trace_eval.judges import registry as judges_registry_mod

            reload(judges_registry_mod)
            assert len(judges_registry_mod.JUDGE_REGISTRY) == 5
        finally:
            # Restore CLI module if it was present
            if cli_module is not None:
                sys.modules["trace_eval.cli"] = cli_module


class TestRegistryModuleStructure:
    """Test that registry.py contains only classes, no populated singletons."""

    def test_registry_module_has_no_singletons(self):
        """trace_eval.registry does not export CONVERTER_REGISTRY or JUDGE_REGISTRY."""
        import trace_eval.registry as reg_mod

        assert not hasattr(reg_mod, "CONVERTER_REGISTRY"), (
            "CONVERTER_REGISTRY should not be in trace_eval.registry — import from trace_eval.convert instead"
        )
        assert not hasattr(reg_mod, "JUDGE_REGISTRY"), (
            "JUDGE_REGISTRY should not be in trace_eval.registry — import from trace_eval.judges.registry instead"
        )

    def test_registry_module_has_classes(self):
        """trace_eval.registry exports ConverterRegistry and JudgeRegistry classes."""
        from trace_eval.registry import ConverterRegistry, JudgeRegistry

        assert ConverterRegistry is not None
        assert JudgeRegistry is not None
