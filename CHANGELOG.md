# Changelog

## 0.2.0

Breaking changes to the profile format:

- Every category needs a priority number of its own. Two equal numbers
  are a load error that names both categories and suggests a free
  number, even when the two could never claim the same piece. At most
  one category may leave `priority` out. Profiles from 0.1.0 with equal
  priorities must be renumbered.
- Profiles that use the new keys below are refused by 0.1.0 as unknown
  keys, so they never sort with wants ignored.

New:

- `list` categories: entries of part, color (or `any`) and quantity,
  all for one bin, with an optional `source` that is not interpreted.
- `catch_all: true` categories, which take every piece no category
  above took. A catch-all must have the largest priority number.
- `Resolver.match(part, color, wanted)`: the category, list entry and
  catch-all flag for a piece, given the caller's count of what each
  entry still wants. The library stays stateless.
- `Resolver.entries(category)`: a list's entries and quantities.
- `Resolver.unreachable()` and `Resolver.stale_acknowledgments()`,
  `unreachable_ok: {shadowed_by: [...]}` on a category, and
  `acknowledge_unreachable()` to write one into a profile mapping.
  `compile_profile` raises a `ProfileWarning` for each unacknowledged
  unreachable category and each stale acknowledgment.

Changed:

- `category_of` answers as at the start of a fresh run: every list
  entry wants its full quantity.
- `accept: {set: ...}` is deprecated. It still loads, with a
  `ProfileWarning`, and now wants the set's quantities, like a list.
- An `accept` category whose listed colors are all rejected is refused
  as accepting nothing.

## 0.1.0

First version: profiles with priorities, accept and reject rules, sets,
and a resolver that answers `category_of(part, color)`.
