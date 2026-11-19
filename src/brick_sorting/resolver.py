"""Turning a profile plus a catalog into answers.

`compile_profile` checks everything that needs the catalog (unknown part
categories and colors, categories that include each other in a circle)
and returns a `Resolver`. After that, `category_of` cannot fail.
"""

from __future__ import annotations

from dataclasses import dataclass

from brick_sorting.catalog import Catalog
from brick_sorting.profile import Category, Profile, ProfileError


@dataclass(frozen=True)
class _Compiled:
    name: str
    priority: int
    # Exactly one of `parts` and `pairs` is in use.
    parts: frozenset[str]
    colors: frozenset[int] | None      # None: any color
    rejected_colors: frozenset[int]
    pairs: frozenset[tuple[str, int]] | None  # a set category

    def accepts(self, part: str, color: int) -> bool:
        if self.pairs is not None:
            return (part, color) in self.pairs
        return (
            part in self.parts
            and color not in self.rejected_colors
            and (self.colors is None or color in self.colors)
        )

    def accepts_whatever_the_color(self, part: str) -> bool:
        return (
            self.pairs is None
            and part in self.parts
            and self.colors is None
            and not self.rejected_colors
        )

    def might_accept(self, part: str) -> bool:
        if self.pairs is not None:
            return any(p == part for p, _ in self.pairs)
        return part in self.parts


class Resolver:
    def __init__(self, profile: Profile, compiled: list[_Compiled]) -> None:
        self.profile = profile
        self._by_priority = sorted(compiled, key=lambda c: c.priority)
        # Category names in profile order. One sort bin each.
        self.categories = tuple(category.name for category in profile.categories)

    def category_of(self, part: str | int, color: int | None) -> str | None:
        """The category this piece belongs to, or None if no category wants it.

        `color` is the catalog's color id. Pass None when the color is
        not known: the answer is then a category only if the piece would
        land there in every color, and None otherwise.
        """
        part = str(part)
        for category in self._by_priority:
            if color is None:
                if category.accepts_whatever_the_color(part):
                    return category.name
                if category.might_accept(part):
                    return None
            elif category.accepts(part, color):
                return category.name
        return None

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
            if included.set is not None:
                raise ProfileError(f"{where}: cannot include the set category '{name}'")
            parts.update(parts_of(included, (*path, category.name)))
        result = frozenset(parts - category.rejected_parts)
        resolved[category.name] = result
        return result

    def color_ids(category: Category, colors) -> frozenset[int]:
        ids = set()
        for color in colors:
            found = catalog.color_id(color)
            if found is None:
                raise ProfileError(f"category '{category.name}': no color '{color}' in the catalog")
            ids.add(found)
        return frozenset(ids)

    compiled = []
    for category in profile.categories:
        pairs = None
        if category.set is not None:
            inventory = catalog.set_inventory(category.set)
            if inventory is None:
                raise ProfileError(f"category '{category.name}': no set '{category.set}' in the catalog")
            pairs = frozenset(inventory)
        parts = parts_of(category, ()) if pairs is None else frozenset()
        colors = None if category.colors is None else color_ids(category, category.colors)
        rejected = color_ids(category, category.rejected_colors)
        if pairs is not None:
            pairs = frozenset(
                (part, color) for part, color in pairs
                if part not in category.rejected_parts
                and color not in rejected
                and (colors is None or color in colors)
            )
        if not parts and not pairs:
            raise ProfileError(f"category '{category.name}' accepts no piece at all")
        compiled.append(_Compiled(category.name, category.priority, parts, colors, rejected, pairs))

    return Resolver(profile, compiled)

