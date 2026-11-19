"""Turning a profile plus a catalog into answers.

`compile_profile` checks everything that needs the catalog (unknown part
categories and colors, categories that include each other in a circle,
repeated list entries) and returns a `Resolver`. After that, `match` and
`category_of` cannot fail.

The resolver holds no counts. A list category wants a number of each of
its entries; how many each entry still wants is known only to the caller,
who passes it to `match` on every call.
"""

from __future__ import annotations

import copy
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

from brick_sorting.catalog import Catalog
from brick_sorting.profile import Category, Profile, ProfileError, ProfileWarning


class EntryKey(NamedTuple):
    """Names one entry of a list category."""

    part: str
    color: int | None  # catalog color id; None means any color


@dataclass(frozen=True)
class Match:
    """Where a piece goes, and which list entry it counts against."""

    category: str
    entry: EntryKey | None = None  # set only for a list category
    catch_all: bool = False


# wanted(category, entry): how many more pieces that entry still wants.
Wanted = Callable[[str, EntryKey], int]


@dataclass(frozen=True)
class Unreachable:
    """A category that can never receive a piece, because categories with
    a lower priority number accept everything it accepts."""

    category: str
    shadowed_by: tuple[str, ...]  # in priority order
    acknowledged: bool  # the profile's unreachable_ok names exactly these


class _Colors(NamedTuple):
    """The colors a category accepts for one part. `everything_but` True
    means every color except `colors`; False means just `colors`."""

    everything_but: bool
    colors: frozenset[int]

    def overlaps(self, other: _Colors) -> bool:
        if self.everything_but and other.everything_but:
            return True  # two cofinite sets of an open-ended color list
        if self.everything_but:
            return bool(other.colors - self.colors)
        if other.everything_but:
            return bool(self.colors - other.colors)
        return bool(self.colors & other.colors)

    def within(self, other: _Colors) -> bool:
        if self.everything_but:
            # Nothing finite covers every color but a few.
            return other.everything_but and other.colors <= self.colors
        if other.everything_but:
            return not (self.colors & other.colors)
        return self.colors <= other.colors


def _union(sets: list[_Colors]) -> _Colors:
    finite = frozenset().union(*(s.colors for s in sets if not s.everything_but))
    open_ended = [s.colors for s in sets if s.everything_but]
    if not open_ended:
        return _Colors(False, finite)
    return _Colors(True, frozenset.intersection(*open_ended) - finite)


@dataclass(frozen=True)
class _Compiled:
    name: str
    priority: int
    kind: str  # "accept", "list" or "catch_all"
    # accept: the parts accepted. list: the parts that have an entry.
    parts: frozenset[str] = frozenset()
    colors: frozenset[int] | None = None  # accept only. None: any color
    rejected_colors: frozenset[int] = frozenset()
    entries: Mapping[EntryKey, int] | None = None  # list only, in profile order

    def accepts(self, part: str, color: int) -> bool:
        """Accepts this piece if every want were still open."""
        if self.kind == "catch_all":
            return True
        if self.kind == "list":
            return (part, color) in self.entries or (part, None) in self.entries
        return (
            part in self.parts
            and color not in self.rejected_colors
            and (self.colors is None or color in self.colors)
        )

    def colors_for(self, part: str) -> _Colors | None:
        """The colors this category accepts for a part, wants ignored."""
        if self.kind == "catch_all":
            return _Colors(True, frozenset())
        if part not in self.parts:
            return None
        if self.kind == "list":
            if (part, None) in self.entries:
                return _Colors(True, frozenset())
            return _Colors(False, frozenset(k.color for k in self.entries if k.part == part))
        if self.colors is None:
            return _Colors(True, self.rejected_colors)
        return _Colors(False, self.colors - self.rejected_colors)

    def match(self, part: str, color: int | None, wanted: Wanted) -> Match | None | bool:
        """A Match if this category takes the piece; False if it might,
        depending on the unknown color (the piece then goes nowhere);
        None if it does not take it."""
        if self.kind == "catch_all":
            return Match(self.name, catch_all=True)
        if self.kind == "list":
            keys = [EntryKey(part, None)] if color is None else [EntryKey(part, color), EntryKey(part, None)]
            for key in keys:
                if key in self.entries and wanted(self.name, key) > 0:
                    return Match(self.name, key)
            if color is None and any(
                key.part == part and key.color is not None and wanted(self.name, key) > 0
                for key in self.entries
            ):
                return False
            return None
        if color is None:
            if part in self.parts and self.colors is None and not self.rejected_colors:
                return Match(self.name)
            return False if part in self.parts else None
        return Match(self.name) if self.accepts(part, color) else None


class Resolver:
    def __init__(self, profile: Profile, compiled: list[_Compiled]) -> None:
        self.profile = profile
        self._by_priority = sorted(compiled, key=lambda c: c.priority)
        self._by_name = {category.name: category for category in compiled}
        # Category names in profile order. One sort bin each.
        self.categories = tuple(category.name for category in profile.categories)
        self._unreachable = self._find_unreachable()

    def match(self, part: str | int, color: int | None, wanted: Wanted) -> Match | None:
        """The category that takes this piece now, or None if none does.

        Categories are tried from the lowest priority number up. A list
        category takes a piece only while the matching entry still
        wants one: `wanted(category, entry)` must return how many more
        that entry wants (its quantity minus what was delivered or
        reserved so far). A specific color entry is used before an
        'any color' entry of the same part. The returned `Match.entry`
        is the entry to count the piece against.

        `color` is the catalog's color id, or None when unknown. A piece
        of unknown color goes to a category only if it would go there in
        every color; in a list it can only count against an 'any color'
        entry.
        """
        part = str(part)
        for category in self._by_priority:
            result = category.match(part, color, wanted)
            if result is False:
                return None
            if result is not None:
                return result
        return None

    def category_of(self, part: str | int, color: int | None) -> str | None:
        """The category this piece belongs to at the start of a fresh run,
        that is with every list entry still wanting its full quantity.
        None if no category accepts it.

        During a run use `match` instead, which knows about used up wants.
        """
        result = self.match(part, color, self._full_quantity)
        return None if result is None else result.category

    def entries(self, category: str) -> dict[EntryKey, int]:
        """A list category's entries with the quantity each wants, in
        profile order. Empty for categories that are not lists."""
        compiled = self._by_name.get(category)
        if compiled is None:
            raise KeyError(f"no category named '{category}'")
        return dict(compiled.entries or {})

    def _full_quantity(self, category: str, entry: EntryKey) -> int:
        return self._by_name[category].entries[entry]

    def unreachable(self) -> tuple[Unreachable, ...]:
        """Categories that can never receive a piece, because categories
        with lower priority numbers accept every piece they accept.

        Wants are ignored, and a list never shadows anything, since it
        can run out and let pieces through. A list below a rule category
        that accepts all of its entries is reported. Partial overlap (red 2x4
        above any 2x4) is the normal way to write a profile and is never
        reported. `shadowed_by` names every category above that accepts
        some piece this one accepts. `acknowledged` is True when the
        profile's `unreachable_ok` names exactly those categories, so a
        change in what shadows a category brings the warning back.
        """
        return self._unreachable

    def stale_acknowledgments(self) -> tuple[str, ...]:
        """Categories with `unreachable_ok` that are reachable after all.
        The acknowledgment does nothing there and can be removed."""
        unreachable = {item.category for item in self._unreachable}
        return tuple(
            category.name for category in self.profile.categories
            if category.unreachable_ok is not None and category.name not in unreachable
        )

    def _find_unreachable(self) -> tuple[Unreachable, ...]:
        acknowledged = {c.name: c.unreachable_ok for c in self.profile.categories}
        found = []
        for index, category in enumerate(self._by_priority):
            if category.kind == "catch_all":
                continue  # it takes pieces no other category knows of
            # A list can run out and let pieces through, so it never
            # shadows anything.
            above = [other for other in self._by_priority[:index] if other.kind != "list"]
            shadows: set[str] = set()
            covered = True
            for part in category.parts:
                mine = category.colors_for(part)
                theirs = []
                for other in above:
                    colors = other.colors_for(part)
                    if colors is not None and colors.overlaps(mine):
                        theirs.append(colors)
                        shadows.add(other.name)
                if covered and not mine.within(_union(theirs)):
                    covered = False
            if covered:
                names = tuple(other.name for other in above if other.name in shadows)
                found.append(Unreachable(category.name, names, acknowledged[category.name] == set(names)))
        return tuple(found)

    def bins_needed(self) -> int:
        """Sort bins this profile uses: one per category, plus overflow bins."""
        return len(self.categories) + self.profile.overflow_bins

    def check_fits(self, sort_bins: int) -> None:
        if self.bins_needed() > sort_bins:
            raise ProfileError(
                f"profile '{self.profile.name}' needs {self.bins_needed()} bins "
                f"({len(self.categories)} categories plus {self.profile.overflow_bins} overflow) "
                f"but the machine has {sort_bins}"
            )


def compile_profile(profile: Profile, catalog: Catalog) -> Resolver:
    by_name = {category.name: category for category in profile.categories}
    resolved: dict[str, frozenset[str]] = {}

    def parts_of(category: Category, path: tuple[str, ...]) -> frozenset[str]:
        """All parts a category accepts, own rejects already removed.

        `path` is the chain of includes that led here. Only a name that
        is on the chain is a circle; a category reached twice by
        different routes is fine and is computed once.
        """
        if category.name in path:
            circle = " -> ".join((*path[path.index(category.name):], category.name))
            raise ProfileError(f"categories include each other in a circle: {circle}")
        if category.name in resolved:
            return resolved[category.name]
        where = f"category '{category.name}'"
        parts = set(category.parts)
        for name in category.part_categories:
            found = catalog.parts_in_category(name)
            if found is None:
                raise ProfileError(f"{where}: no part category named '{name}' in the catalog")
            parts.update(found)
        for name in category.categories:
            included = by_name.get(name)
            if included is None:
                raise ProfileError(f"{where}: includes '{name}', which is not a category of this profile")
            kind = (
                "set" if included.set is not None
                else "list" if included.entries is not None
                else "catch-all" if included.catch_all
                else None
            )
            if kind is not None:
                raise ProfileError(f"{where}: cannot include the {kind} category '{name}'")
            parts.update(parts_of(included, (*path, category.name)))
        result = frozenset(parts - category.rejected_parts)
        resolved[category.name] = result
        return result

    def color_id(category: Category, color) -> int:
        found = catalog.color_id(color)
        if found is None:
            raise ProfileError(f"category '{category.name}': no color '{color}' in the catalog")
        return found

    def color_ids(category: Category, colors) -> frozenset[int]:
        return frozenset(color_id(category, color) for color in colors)

    def list_entries(category: Category) -> dict[EntryKey, int]:
        entries: dict[EntryKey, int] = {}
        for entry in category.entries:
            color = None if entry.color is None else color_id(category, entry.color)
            key = EntryKey(entry.part, color)
            if key in entries:
                what = "any color" if color is None else f"color {entry.color}"
                raise ProfileError(
                    f"category '{category.name}': part {entry.part} in {what} is listed twice; "
                    "add the quantities into one entry"
                )
            entries[key] = entry.quantity
        return entries

    def set_entries(category: Category) -> dict[EntryKey, int]:
        inventory = catalog.set_inventory(category.set)
        if inventory is None:
            raise ProfileError(f"category '{category.name}': no set '{category.set}' in the catalog")
        colors = None if category.colors is None else color_ids(category, category.colors)
        rejected = color_ids(category, category.rejected_colors)
        return {
            EntryKey(part, color): quantity
            for (part, color), quantity in sorted(inventory.items())
            if part not in category.rejected_parts
            and color not in rejected
            and (colors is None or color in colors)
        }

    compiled = []
    for category in profile.categories:
        if category.catch_all:
            compiled.append(_Compiled(category.name, category.priority, "catch_all"))
            continue
        if category.entries is not None or category.set is not None:
            entries = list_entries(category) if category.set is None else set_entries(category)
            if not entries:
                raise ProfileError(f"category '{category.name}' accepts no piece at all")
            parts = frozenset(key.part for key in entries)
            compiled.append(_Compiled(category.name, category.priority, "list", parts, entries=entries))
            continue
        parts = parts_of(category, ())
        colors = None if category.colors is None else color_ids(category, category.colors)
        rejected = color_ids(category, category.rejected_colors)
        if not parts or (colors is not None and not colors - rejected):
            raise ProfileError(f"category '{category.name}' accepts no piece at all")
        compiled.append(_Compiled(category.name, category.priority, "accept", parts, colors, rejected))

    resolver = Resolver(profile, compiled)
    for item in resolver.unreachable():
        if not item.acknowledged:
            names = ", ".join(f"'{name}'" for name in item.shadowed_by)
            warnings.warn(
                f"category '{item.category}' can never receive a piece: everything it accepts "
                f"is taken first by {names}. If that is meant, acknowledge it with "
                f"'unreachable_ok: {{shadowed_by: [{', '.join(item.shadowed_by)}]}}'.",
                ProfileWarning,
                stacklevel=2,
            )
    for name in resolver.stale_acknowledgments():
        warnings.warn(
            f"category '{name}' has 'unreachable_ok' but can receive pieces; remove it.",
            ProfileWarning,
            stacklevel=2,
        )
    return resolver


def acknowledge_unreachable(document: Mapping[str, Any], item: Unreachable) -> dict[str, Any]:
    """A copy of a profile mapping (as parsed from YAML) in which the
    unreachable category says "I meant this", naming the categories that
    shadow it now. The original mapping is not changed. Saving it, and
    keeping any comments, is up to the caller."""
    result = copy.deepcopy(dict(document))
    for category in result.get("categories") or ():
        if isinstance(category, dict) and category.get("name") == item.category:
            category["unreachable_ok"] = {"shadowed_by": list(item.shadowed_by)}
            return result
    raise ProfileError(f"the profile has no category named '{item.category}'")
