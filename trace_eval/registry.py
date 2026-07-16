"""Typed registries for converters and judges.

Provides deterministic lookup, alias normalization, duplicate rejection,
and clear error messages for unsupported formats.

This module contains registry classes and entry types only.
Populated singletons live in their owning modules:

- ``trace_eval.convert.CONVERTER_REGISTRY`` — converter registry
- ``trace_eval.judges.registry.JUDGE_REGISTRY`` — judge registry

Usage::

    from trace_eval.convert import CONVERTER_REGISTRY
    converter = CONVERTER_REGISTRY.get("claude-code")

    from trace_eval.judges.registry import JUDGE_REGISTRY
    judge = JUDGE_REGISTRY.get("reliability")
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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
        return normalized in {a.lower().replace("-", "_").replace(" ", "_") for a in self.aliases}


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
        self._sealed: bool = False

    def seal(self) -> None:
        """Seal the registry to prevent further registrations.

        After sealing, register() raises RuntimeError.
        Unsealing is intentional only for tests building fresh instances.
        """
        self._sealed = True

    @property
    def is_sealed(self) -> bool:
        """Return whether the registry is sealed."""
        return self._sealed

    def register(
        self,
        canonical_name: str,
        aliases: tuple[str, ...] | list[str],
        converter: Callable[[Path], list[dict]],
        description: str = "",
    ) -> None:
        """Register a converter. Raises ValueError on any name collision.

        Collision checks (all using normalized names):
        - canonical vs existing canonical
        - alias vs existing alias
        - new canonical vs existing alias
        - new alias vs existing canonical
        - duplicate aliases within one registration
        - alias that normalizes to the new entry's own canonical name
        """
        if self._sealed:
            raise RuntimeError(f"Cannot register {canonical_name!r}: registry is sealed")
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
                f"Duplicate converter canonical name: {canonical_name!r} (already registered as {existing!r})"
            )

        # Check new canonical vs existing alias
        if canonical_norm in self._alias_map:
            existing_canonical = self._alias_map[canonical_norm]
            raise ValueError(
                f"Converter canonical name {canonical_name!r} conflicts with existing alias "
                f"(already claimed by {existing_canonical!r})"
            )

        # Normalize all aliases and check for collisions
        normalized_aliases: list[str] = []
        for alias in aliases:
            alias_norm = alias.lower().replace("-", "_").replace(" ", "_")

            # Check alias equivalent to own canonical name
            if alias_norm == canonical_norm:
                raise ValueError(
                    f"Converter alias {alias!r} normalizes to the same name as "
                    f"canonical {canonical_name!r} — lookup works via hyphen/underscore "
                    f"normalization without an explicit alias"
                )

            # Check duplicate alias within this registration
            if alias_norm in normalized_aliases:
                raise ValueError(f"Duplicate converter alias within registration: {alias!r}")

            # Check alias vs existing alias
            if alias_norm in self._alias_map:
                existing_canonical = self._alias_map[alias_norm]
                raise ValueError(f"Duplicate converter alias: {alias!r} (already claimed by {existing_canonical!r})")

            # Check alias vs existing canonical
            if alias_norm in self._entries:
                existing = self._entries[alias_norm].canonical_name
                raise ValueError(f"Converter alias {alias!r} conflicts with existing canonical name {existing!r}")

            normalized_aliases.append(alias_norm)

        # Register
        self._entries[canonical_norm] = entry
        self._order.append(canonical_norm)
        for alias_norm in normalized_aliases:
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
        raise KeyError(f"Unknown converter format: {name!r}. Supported formats: {supported}")

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
        """Return all aliases mapped to their declared canonical names.

        Keys are the original alias strings as registered. Values are the
        declared canonical names (not internal normalized keys).
        """
        result: dict[str, str] = {}
        for entry in self._entries.values():
            for alias in entry.aliases:
                result[alias] = entry.canonical_name
        return result

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
            object.__setattr__(self, "display_label", self.dimension_key.replace("_", " ").title())


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
        self._sealed: bool = False

    def seal(self) -> None:
        """Seal the registry to prevent further registrations.

        After sealing, register() raises RuntimeError.
        """
        self._sealed = True

    @property
    def is_sealed(self) -> bool:
        """Return whether the registry is sealed."""
        return self._sealed

    def register(
        self,
        dimension_key: str,
        judge: Callable[[list], object],
        display_label: str = "",
        order: int = 0,
    ) -> None:
        """Register a judge. Raises ValueError on duplicate dimension key."""
        if self._sealed:
            raise RuntimeError(f"Cannot register {dimension_key!r}: registry is sealed")

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
            raise KeyError(f"Unknown judge dimension: {dimension_key!r}. Available dimensions: {available}")
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
            k
            for k, _ in sorted(
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
        """Return {dimension_key: judge_callable} in stable output order.

        Order is determined by the ``order`` field on each entry, then
        alphabetically by dimension key. This is independent of
        registration order and matches the contract expected by
        compute_scorecard().
        """
        return {k: self._entries[k].judge for k in self.ordered_keys}

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, dimension_key: str) -> bool:
        return dimension_key in self._entries
