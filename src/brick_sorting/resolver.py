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

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import NamedTuple

from brick_sorting.catalog import Catalog
from brick_sorting.profile import Category, Profile, ProfileError


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
        if not parts:
            raise ProfileError(f"category '{category.name}' accepts no piece at all")
        colors = None if category.colors is None else color_ids(category, category.colors)
        rejected = color_ids(category, category.rejected_colors)
        compiled.append(_Compiled(category.name, category.priority, "accept", parts, colors, rejected))

    return Resolver(profile, compiled)
