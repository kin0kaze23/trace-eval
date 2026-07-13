"""Typed registries for converters and judges.

Provides deterministic lookup, alias normalization, duplicate rejection,
and clear error messages for unsupported formats.

Usage:
    from trace_eval.registry import CONVERTER_REGISTRY, JUDGE_REGISTRY

    # Converter lookup
    converter = CONVERTER_REGISTRY.get("claude-code")
    events = converter(input_path)

    # Judge lookup
    judge = JUDGE_REGISTRY.get("reliability")
    result = judge(events)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Converter registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConverterEntry:
    """A registered converter for a specific input format."""

    canonical_name: str
    aliases: tuple[str, ...]
    converter: Callable[[Path], list[dict]]
    description: str = ""

    def matches(self, name: str) -> bool:
        """Check if a name matches this converter (canonical or alias)."""
        normalized = name.lower().replace("-", "_").replace(" ", "_")
        canonical_norm = self.canonical_name.lower().replace("-", "_").replace(" ", "_")
        if normalized == canonical_norm:
            return True
        return normalized in {
            a.lower().replace("-", "_").replace(" ", "_") for a in self.aliases
        }


class ConverterRegistry:
    """Typed registry for trace format converters.

    Features:
        - Deterministic lookup by canonical name or alias
        - Duplicate canonical name rejection
        - Duplicate alias rejection across entries
        - Clear error for unsupported formats
    """

    def __init__(self) -> None:
        self._entries: dict[str, ConverterEntry] = {}
        self._alias_map: dict[str, str] = {}  # alias -> canonical_name
        self._order: list[str] = []  # insertion order for determinism

    def register(
        self,
        canonical_name: str,
        aliases: tuple[str, ...] | list[str],
        converter: Callable[[Path], list[dict]],
        description: str = "",
    ) -> None:
        """Register a converter. Raises ValueError on duplicate names/aliases."""
        entry = ConverterEntry(
            canonical_name=canonical_name,
            aliases=tuple(aliases),
            converter=converter,
            description=description,
        )

        canonical_norm = canonical_name.lower().replace("-", "_").replace(" ", "_")

        # Check duplicate canonical name
        if canonical_norm in self._entries:
            existing = self._entries[canonical_norm].canonical_name
            raise ValueError(
                f"Duplicate converter canonical name: {canonical_name!r} "
                f"(already registered as {existing!r})"
            )

        # Check duplicate aliases
        for alias in aliases:
            alias_norm = alias.lower().replace("-", "_").replace(" ", "_")
            if alias_norm in self._alias_map:
                existing_canonical = self._alias_map[alias_norm]
                raise ValueError(
                    f"Duplicate converter alias: {alias!r} "
                    f"(already claimed by {existing_canonical!r})"
                )

        # Register
        self._entries[canonical_norm] = entry
        self._order.append(canonical_norm)
        for alias in aliases:
            alias_norm = alias.lower().replace("-", "_").replace(" ", "_")
            self._alias_map[alias_norm] = canonical_norm

    def get(self, name: str) -> Callable[[Path], list[dict]]:
        """Get a converter by canonical name or alias.

        Raises KeyError with clear error if not found.
        """
        normalized = name.lower().replace("-", "_").replace(" ", "_")

        # Direct canonical match
        if normalized in self._entries:
            return self._entries[normalized].converter

        # Alias match
        if normalized in self._alias_map:
            canonical = self._alias_map[normalized]
            return self._entries[canonical].converter

        supported = sorted(self._entries.keys())
        raise KeyError(
            f"Unknown converter format: {name!r}. "
            f"Supported formats: {supported}"
        )

    def is_supported(self, name: str) -> bool:
        """Check if a format name is supported."""
        try:
            self.get(name)
            return True
        except KeyError:
            return False

    @property
    def canonical_names(self) -> list[str]:
        """Return canonical names in registration order."""
        return [self._entries[k].canonical_name for k in self._order]

    @property
    def all_aliases(self) -> dict[str, str]:
        """Return all aliases mapped to their canonical names."""
        return dict(self._alias_map)

    def entries(self) -> list[ConverterEntry]:
        """Return all entries in registration order."""
        return [self._entries[k] for k in self._order]

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        return self.is_supported(name)


# ---------------------------------------------------------------------------
# Judge registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JudgeEntry:
    """A registered scoring judge for a specific dimension."""

    dimension_key: str
    judge: Callable[[list], object]  # Callable[[list[Event]], JudgeResult]
    display_label: str = ""
    order: int = 0  # Lower runs first; used for stable output ordering

    def __post_init__(self) -> None:
        if not self.display_label:
            # Auto-generate from dimension key
            object.__setattr__(
                self, "display_label", self.dimension_key.replace("_", " ").title()
            )


class JudgeRegistry:
    """Typed registry for scoring judges.

    Features:
        - Deterministic execution order (by `order` field)
        - Duplicate dimension key rejection
        - Stable output order regardless of registration order
    """

    def __init__(self) -> None:
        self._entries: dict[str, JudgeEntry] = {}
        self._order: list[str] = []  # insertion order

    def register(
        self,
        dimension_key: str,
        judge: Callable[[list], object],
        display_label: str = "",
        order: int = 0,
    ) -> None:
        """Register a judge. Raises ValueError on duplicate dimension key."""
        if dimension_key in self._entries:
            existing = self._entries[dimension_key]
            raise ValueError(
                f"Duplicate judge dimension key: {dimension_key!r} "
                f"(already registered with label {existing.display_label!r})"
            )

        entry = JudgeEntry(
            dimension_key=dimension_key,
            judge=judge,
            display_label=display_label,
            order=order,
        )
        self._entries[dimension_key] = entry
        self._order.append(dimension_key)

    def get(self, dimension_key: str) -> Callable[[list], object]:
        """Get a judge by dimension key.

        Raises KeyError with clear error if not found.
        """
        if dimension_key not in self._entries:
            available = sorted(self._entries.keys())
            raise KeyError(
                f"Unknown judge dimension: {dimension_key!r}. "
                f"Available dimensions: {available}"
            )
        return self._entries[dimension_key].judge

    def is_registered(self, dimension_key: str) -> bool:
        """Check if a dimension key is registered."""
        return dimension_key in self._entries

    @property
    def dimension_keys(self) -> list[str]:
        """Return dimension keys in registration order."""
        return list(self._order)

    @property
    def ordered_keys(self) -> list[str]:
        """Return dimension keys sorted by order field (stable output order)."""
        return [
            k for k, _ in sorted(
                self._entries.items(),
                key=lambda item: (item[1].order, item[0]),
            )
        ]

    def entries(self) -> list[JudgeEntry]:
        """Return all entries in registration order."""
        return [self._entries[k] for k in self._order]

    def ordered_entries(self) -> list[JudgeEntry]:
        """Return all entries sorted by order field."""
        return [
            self._entries[k]
            for k, _ in sorted(
                self._entries.items(),
                key=lambda item: (item[1].order, item[0]),
            )
        ]

    def get_judge_dict(self) -> dict[str, Callable[[list], object]]:
        """Return {dimension_key: judge_callable} in registration order.

        This is the format expected by compute_scorecard().
        """
        return {k: self._entries[k].judge for k in self._order}

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, dimension_key: str) -> bool:
        return dimension_key in self._entries


# ---------------------------------------------------------------------------
# Global singleton instances
# ---------------------------------------------------------------------------

CONVERTER_REGISTRY = ConverterRegistry()
JUDGE_REGISTRY = JudgeRegistry()
