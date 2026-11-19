"""Reading a sorting profile and checking that it is well formed.

A profile is a list of categories. Each category says which pieces it
accepts and has a priority of its own; a piece belongs to the accepting
category with the lowest priority number.

Everything a profile can get wrong on its own (a misspelled key, an
empty field, a duplicate name) is refused here with a message that names
the category. A typo must never silently change what gets sorted where.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PRIORITY = 256
SUPPORTED_NAMING_SCHEMES = ("Rebrickable",)
ANY = "any"

_TOP_KEYS = {"name", "default_naming_scheme", "categories", "overflow_bins"}
_CATEGORY_KEYS = {"name", "priority", "naming_scheme", "accept", "reject", "list", "catch_all"}
_KINDS = ("accept", "list", "catch_all")
_LIST_KEYS = {"source", "entries"}
_ENTRY_KEYS = {"part", "color", "quantity"}
_ACCEPT_KEYS = {"parts", "part_categories", "categories", "colors", "set", "min_price"}
_REJECT_KEYS = {"parts", "colors"}


class ProfileError(ValueError):
    """The profile cannot be used. The message says what to fix."""


@dataclass(frozen=True)
class ListEntry:
    """One line of a list category: how many of a part in a color it wants."""

    part: str
    # Color name or id as written. None means any color.
    color: str | int | None
    quantity: int


@dataclass(frozen=True)
class Category:
    name: str
    priority: int = DEFAULT_PRIORITY
    # Part numbers accepted directly.
    parts: frozenset[str] = frozenset()
    # Catalog part categories ("Bricks", "Technic Pins") accepted whole.
    part_categories: tuple[str, ...] = ()
    # Other categories of this profile whose parts are accepted too.
    categories: tuple[str, ...] = ()
    # Accepted colors, by name or id as written. None means any color.
    colors: tuple[str | int, ...] | None = None
    # A set number: accept exactly the parts and colors of that set.
    set: str | None = None
    rejected_parts: frozenset[str] = frozenset()
    rejected_colors: tuple[str | int, ...] = ()
    # A list category: its entries, or None for any other kind.
    entries: tuple[ListEntry, ...] | None = None
    # Where a list came from (a set, an order file). Kept, not interpreted.
    source: Any = None
    # Accepts every piece no category above it accepted.
    catch_all: bool = False


@dataclass(frozen=True)
class Profile:
    name: str
    categories: tuple[Category, ...]
    overflow_bins: int = 0


def load_profile(source: str | Path | Mapping[str, Any]) -> Profile:
    """Load a profile from a YAML file, YAML text, or an already parsed mapping."""
    if isinstance(source, Path):
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    elif isinstance(source, str):
        document = yaml.safe_load(source)
    else:
        document = source
    if not isinstance(document, Mapping):
        raise ProfileError("a profile must be a mapping with a 'categories' list")
    _check_keys(document, _TOP_KEYS, "profile")

    default_scheme = document.get("default_naming_scheme", "Rebrickable")
    entries = document.get("categories")
    if not isinstance(entries, list) or not entries:
        raise ProfileError("'categories' must be a list with at least one category")

    categories = []
    seen: set[str] = set()
    for position, entry in enumerate(entries, start=1):
        category = _category(entry, position, default_scheme)
        if category.name in seen:
            raise ProfileError(f"two categories are named '{category.name}'")
        seen.add(category.name)
        categories.append(category)

    _refuse_equal_priorities(categories)
    _catch_all_comes_last(categories)

    overflow = document.get("overflow_bins", 0)
    if not isinstance(overflow, int) or isinstance(overflow, bool) or overflow < 0:
        raise ProfileError("'overflow_bins' must be a whole number, 0 or more")
    return Profile(str(document.get("name", "unnamed")), tuple(categories), overflow)


def _category(entry: Any, position: int, default_scheme: str) -> Category:
    if not isinstance(entry, Mapping) or not isinstance(entry.get("name"), str):
        raise ProfileError(f"category {position} must be a mapping with a 'name'")
    name = entry["name"]
    where = f"category '{name}'"
    _check_keys(entry, _CATEGORY_KEYS, where)

    scheme = entry.get("naming_scheme", default_scheme)
    if scheme not in SUPPORTED_NAMING_SCHEMES:
        raise ProfileError(
            f"{where}: naming scheme '{scheme}' is not supported yet "
            f"(supported: {', '.join(SUPPORTED_NAMING_SCHEMES)})"
        )
    priority = entry.get("priority", DEFAULT_PRIORITY)
    if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0:
        raise ProfileError(f"{where}: 'priority' must be a whole number, 0 or more")

    kinds = [kind for kind in _KINDS if kind in entry]
    if len(kinds) != 1:
        found = f"has {' and '.join(kinds)}" if kinds else "has none"
        raise ProfileError(
            f"{where}: needs exactly one of 'accept', 'list' or 'catch_all' ({found})"
        )
    if "reject" in entry and "accept" not in entry:
        raise ProfileError(f"{where}: 'reject' is only allowed next to 'accept'")
    if "list" in entry:
        return _list_category(entry["list"], name, priority, where)
    if "catch_all" in entry:
        if entry["catch_all"] is not True:
            raise ProfileError(f"{where}: 'catch_all' must be true; remove it if unused")
        return Category(name=name, priority=priority, catch_all=True)

    accept = entry.get("accept")
    if not isinstance(accept, Mapping) or not accept:
        raise ProfileError(f"{where}: needs an 'accept' section that accepts something")
    _check_keys(accept, _ACCEPT_KEYS, f"{where}, accept")
    reject = entry.get("reject", {})
    if not isinstance(reject, Mapping):
        raise ProfileError(f"{where}: 'reject' must be a mapping")
    _check_keys(reject, _REJECT_KEYS, f"{where}, reject")

    if "min_price" in accept:
        raise ProfileError(f"{where}: 'min_price' is not supported yet")
    set_num = accept.get("set")
    if set_num is not None:
        if not isinstance(set_num, str) or not set_num:
            raise ProfileError(f"{where}: 'set' must be a set number in quotes, such as \"10497-1\"")
        if {"parts", "part_categories", "categories"} & accept.keys():
            raise ProfileError(f"{where}: a 'set' category cannot also list parts or categories")

    parts = frozenset(_strings(accept, "parts", where))
    part_categories = tuple(_strings(accept, "part_categories", where))
    includes = tuple(_strings(accept, "categories", where))
    if not (parts or part_categories or includes or set_num or "colors" in accept):
        raise ProfileError(f"{where}: 'accept' accepts nothing")

    return Category(
        name=name,
        priority=priority,
        parts=parts,
        part_categories=part_categories,
        categories=includes,
        colors=_colors(accept, where),
        set=set_num,
        rejected_parts=frozenset(_strings(reject, "parts", where)),
        rejected_colors=tuple(_color_list(reject, where)),
    )


def _list_category(section: Any, name: str, priority: int, where: str) -> Category:
    if not isinstance(section, Mapping):
        raise ProfileError(f"{where}: 'list' must be a mapping with 'entries'")
    _check_keys(section, _LIST_KEYS, f"{where}, list")
    raw = section.get("entries")
    if not isinstance(raw, list) or not raw:
        raise ProfileError(f"{where}: 'entries' must be a list with at least one entry")
    entries = []
    for number, item in enumerate(raw, start=1):
        at = f"{where}, entry {number}"
        if not isinstance(item, Mapping):
            raise ProfileError(f"{at}: must be a mapping with 'part', 'color' and 'quantity'")
        _check_keys(item, _ENTRY_KEYS, at)
        missing = [key for key in ("part", "color", "quantity") if key not in item]
        if missing:
            raise ProfileError(f"{at}: needs {', '.join(missing)} (write 'color: any' for any color)")
        part, color, quantity = item["part"], item["color"], item["quantity"]
        if isinstance(part, bool) or not isinstance(part, (str, int)) or part == "":
            raise ProfileError(f"{at}: 'part' must be a part number")
        if isinstance(color, bool) or not isinstance(color, (str, int)):
            raise ProfileError(f"{at}: 'color' must be a color name, id or 'any'")
        if isinstance(color, str) and color.lower() == ANY:
            color = None
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ProfileError(f"{at}: 'quantity' must be a whole number, 1 or more")
        entries.append(ListEntry(str(part), color, quantity))
    return Category(
        name=name,
        priority=priority,
        entries=tuple(entries),
        source=section.get("source"),
    )


def _refuse_equal_priorities(categories: list[Category]) -> None:
    """Every category needs its own priority number, so the order in
    which categories are tried never depends on anything but the profile."""
    used = {category.priority for category in categories}
    first_with: dict[int, Category] = {}
    for category in categories:
        other = first_with.setdefault(category.priority, category)
        if other is category:
            continue
        free = category.priority + 1
        while free in used:
            free += 1
        default = (
            f" ({DEFAULT_PRIORITY} is the default when 'priority' is left out; "
            "at most one category may leave it out)"
            if category.priority == DEFAULT_PRIORITY
            else ""
        )
        raise ProfileError(
            f"categories '{other.name}' and '{category.name}' both have priority "
            f"{category.priority}{default}. Every category needs its own priority; "
            f"{free} is free."
        )


def _catch_all_comes_last(categories: list[Category]) -> None:
    for catch_all in (category for category in categories if category.catch_all):
        for other in categories:
            if other is not catch_all and other.priority > catch_all.priority:
                raise ProfileError(
                    f"catch-all category '{catch_all.name}' must have the largest priority "
                    f"number, but '{other.name}' has {other.priority}"
                )


def _check_keys(mapping: Mapping[str, Any], known: set[str], where: str) -> None:
    unknown = sorted(str(key) for key in mapping if key not in known)
    if unknown:
        raise ProfileError(
            f"{where}: unknown key(s) {', '.join(unknown)} (known: {', '.join(sorted(known))})"
        )


def _strings(section: Mapping[str, Any], key: str, where: str) -> list[str]:
    """A list of names or part numbers. Part numbers written bare in YAML
    arrive as integers; they are the same part as the quoted form."""
    if key not in section:
        return []
    value = section[key]
    if not isinstance(value, list) or not value:
        raise ProfileError(f"{where}: '{key}' must be a list with at least one entry; remove it if unused")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            raise ProfileError(f"{where}: '{key}' contains {item!r}, which is not a name or number")
    return [str(item) for item in value]


def _color_list(section: Mapping[str, Any], where: str) -> list[str | int]:
    if "colors" not in section:
        return []
    value = section["colors"]
    if not isinstance(value, list) or not value:
        raise ProfileError(f"{where}: 'colors' must be a list with at least one entry; remove it if unused")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            raise ProfileError(f"{where}: 'colors' contains {item!r}, which is not a color name or id")
    return list(value)


def _colors(accept: Mapping[str, Any], where: str) -> tuple[str | int, ...] | None:
    value = accept.get("colors", ANY)
    if isinstance(value, str) and value.lower() == ANY:
        return None
    colors = _color_list(accept, where)
    if any(isinstance(color, str) and color.lower() == ANY for color in colors):
        raise ProfileError(f"{where}: write 'colors: any' on its own, not inside a list")
    return tuple(colors)
