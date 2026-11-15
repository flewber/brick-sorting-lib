# brick-sorting-lib

Sorting profiles for brick sorting. A profile describes categories
("red bricks", "everything Technic", "the parts of set 10497"); this
library answers which category a given part in a given color belongs to.

Catalog data (parts, part categories, colors) comes from
[Rebrickable](https://rebrickable.com/downloads/).

## Use

```python
from brick_sorting import CsvCatalog, compile_profile, load_profile
from pathlib import Path

catalog = CsvCatalog("path/to/rebrickable/csv/files")   # parts, part_categories, colors
resolver = compile_profile(load_profile(Path("sorting-profile-sample.yaml")), catalog)

resolver.category_of("3001", 4)     # part number, Rebrickable color id -> category name or None
resolver.category_of("3001", None)  # color unknown: a category only if color cannot matter
resolver.check_fits(24)             # raises if the profile needs more bins than that
```

`compile_profile` accepts any object with `parts_in_category`,
`color_id` and `set_inventory` in place of `CsvCatalog`
(see `src/brick_sorting/catalog.py`).

## Profile format

See `sorting-profile-sample.yaml`. In short:

- A piece goes to the accepting category with the lowest `priority`
  number. A piece no category accepts gets `None`.
- `accept` may list `parts`, catalog `part_categories`, other
  `categories` of the same profile, `colors`, or one `set`.
- `reject` lists `parts` and `colors`, and wins over `accept`.
- Mistakes are errors with a message that names the category: unknown or
  misspelled keys, empty fields, unknown part categories or colors,
  categories that include each other in a circle, and two categories of
  the same priority that could both claim the same piece.

Not supported yet: naming schemes other than Rebrickable, `min_price`,
per-part quantity limits.

## Development

Needs only [uv](https://docs.astral.sh/uv/).

    uv run pytest

## Older prototype

`get-part-mapping.py` and `sorting_profile_lib.py` are the first
prototype. They are superseded by the `brick_sorting` package and are
kept for reference for now.
