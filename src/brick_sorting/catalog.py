"""What the resolver needs to know about the part catalog.

The resolver itself only depends on the small `Catalog` interface, so a
caller that already holds the catalog in a database can supply its own.
`CsvCatalog` reads Rebrickable's downloadable CSV files directly
(https://rebrickable.com/downloads/), which is all a desk user needs.
Catalog data comes from Rebrickable.
"""

from __future__ import annotations

import csv
import gzip
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Protocol


class Catalog(Protocol):
    def parts_in_category(self, name: str) -> Collection[str] | None:
        """Part numbers in the named part category, or None if there is no such category."""

    def color_id(self, color: str | int) -> int | None:
        """The id of a color given by name or id, or None if unknown."""

    def set_inventory(self, set_num: str) -> Mapping[tuple[str, int], int] | None:
        """Quantity per (part, color id) of a set, or None if the set is unknown."""


def _rows(directory: Path, name: str, columns: tuple[str, ...]):
    for candidate in (directory / f"{name}.csv", directory / f"{name}.csv.gz"):
        if candidate.exists():
            opener = gzip.open if candidate.suffix == ".gz" else open
            with opener(candidate, "rt", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                missing = [c for c in columns if c not in (reader.fieldnames or ())]
                if missing:
                    raise ValueError(f"{candidate.name}: expected column(s) {', '.join(missing)}")
                yield from reader
            return
    raise FileNotFoundError(
        f"{name}.csv not found in {directory}. Download it from https://rebrickable.com/downloads/"
    )


class CsvCatalog:
    """Part categories and colors from `parts.csv`, `part_categories.csv` and `colors.csv`.

    Columns are found by name, not by position, so extra or reordered
    columns in the files do no harm. Sets are not read; a profile with a
    'set' category needs a catalog that knows set inventories.
    """

    def __init__(self, directory: str | Path) -> None:
        directory = Path(directory)
        names = {row["id"]: row["name"] for row in _rows(directory, "part_categories", ("id", "name"))}
        self._parts: dict[str, set[str]] = {name: set() for name in names.values()}
        for row in _rows(directory, "parts", ("part_num", "part_cat_id")):
            category = names.get(row["part_cat_id"])
            if category is not None:
                self._parts[category].add(row["part_num"])
        self._color_ids: set[int] = set()
        self._color_names: dict[str, int] = {}
        for row in _rows(directory, "colors", ("id", "name")):
            self._color_ids.add(int(row["id"]))
            self._color_names[row["name"].lower()] = int(row["id"])

    def parts_in_category(self, name: str) -> Collection[str] | None:
        return self._parts.get(name)

    def color_id(self, color: str | int) -> int | None:
        if isinstance(color, int):
            return color if color in self._color_ids else None
        return self._color_names.get(color.lower())

    def set_inventory(self, set_num: str) -> Mapping[tuple[str, int], int] | None:
        raise NotImplementedError("CsvCatalog does not read set inventories")
