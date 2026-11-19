# brick-sorting-lib

Sorting profiles for brick sorting. A profile describes categories
("red bricks", "everything Technic", "the parts of set 10497"); this
library answers which category a given part in a given color belongs to,
and, for categories that want a number of each part, whether they still
want it.

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

### Wants: list categories during a run

A list category wants a number of each of its entries. The library
keeps no counts. The caller tracks how many each entry still wants and
passes a lookup on every call:

```python
def wanted(category, entry):        # entry is an EntryKey(part, color id or None)
    return resolver.entries(category)[entry] - delivered[category, entry]

match = resolver.match("3001", 4, wanted)   # Match or None
match.category                      # where the piece goes
match.entry                         # the list entry to count it against, or None
match.catch_all                     # True if only the catch-all took it
```

When an entry wants no more, its pieces go to the next category by
priority. `category_of` answers as at the start of a fresh run, with
every entry wanting its full quantity; use `match` during a run.

### Categories that can never receive a piece

`resolver.unreachable()` lists categories whose every piece is taken by
categories with lower priority numbers, with the categories that shadow
each one. `compile_profile` warns about each (a `ProfileWarning`) unless
the profile acknowledges it:

```yaml
  - name: red bricks, kept for later
    priority: 4
    accept: {part_categories: [Bricks], colors: [Red]}
    unreachable_ok: {shadowed_by: [bricks]}
```

The acknowledgment holds only while it names exactly the categories that
shadow the category, so an edit that changes them brings the warning
back. `acknowledge_unreachable(document, item)` returns a copy of a
parsed profile with the acknowledgment written in.

## Profile format

See `sorting-profile-sample.yaml`. In short:

- Every category has its own `priority` number; a piece goes to the
  accepting category with the lowest number. At most one category may
  leave `priority` out (it then gets 256). A piece no category accepts
  gets `None`.
- A category has exactly one of:
  - `accept`: rules. It may list `parts`, catalog `part_categories`,
    other `categories` of the same profile, and `colors`. `reject` lists
    `parts` and `colors`, and wins over `accept`.
  - `list`: `entries` of `part`, `color` (a name, an id or `any`) and
    `quantity` (1 or more), all for one bin, plus an optional `source`
    that is kept for the caller and not interpreted. The same part and
    color may appear once; a part may appear once in a color and once
    with `any`, and a piece is then counted against its color first.
  - `catch_all: true`: every piece no category above took. It must have
    the largest priority number.
- `accept: {set: "1234-1"}` still loads but is deprecated: it now wants
  the set's quantities, like a list. Import the set as a `list` instead.
- Mistakes are errors with a message that names the category: unknown or
  misspelled keys, empty fields, unknown part categories or colors,
  categories that include each other in a circle, two categories with
  the same priority, and repeated list entries.

Not supported yet: naming schemes other than Rebrickable, `min_price`,
per-part quantities on `accept` categories.

## Development

Needs only [uv](https://docs.astral.sh/uv/).

    uv run pytest
