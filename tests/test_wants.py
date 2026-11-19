"""List categories, catch-all categories and `match` with wants passed in."""

import pytest

from brick_sorting import EntryKey, Match, ProfileError, load_profile
from test_profiles import BLACK, BLUE, RED, resolver

ORDER = """
categories:
  - name: order
    priority: 1
    list:
      source: {order: "order-2026-11.xml"}
      entries:
        - {part: "3001", color: Red, quantity: 50}
        - {part: 3001, color: 1, quantity: 30}
        - {part: "3004", color: any, quantity: 20}
  - name: bricks
    priority: 2
    accept: {part_categories: [Bricks]}
"""


def full(r):
    return lambda category, entry: r.entries(category)[entry]


def test_entries_lists_quantities_in_profile_order_with_color_ids():
    r = resolver(ORDER)
    assert list(r.entries("order").items()) == [
        (EntryKey("3001", RED), 50),
        (EntryKey("3001", BLUE), 30),
        (EntryKey("3004", None), 20),
    ]
    assert r.entries("bricks") == {}
    with pytest.raises(KeyError):
        r.entries("nothing")


def test_source_is_kept_and_not_interpreted():
    profile = load_profile(ORDER)
    assert profile.categories[0].source == {"order": "order-2026-11.xml"}


def test_a_list_takes_pieces_while_wanted_then_they_fall_through():
    r = resolver(ORDER)
    red = EntryKey("3001", RED)
    wanted = {("order", red): 1}
    assert r.match("3001", RED, lambda c, e: wanted.get((c, e), 0)) == Match("order", red)
    wanted[("order", red)] = 0
    assert r.match("3001", RED, lambda c, e: wanted.get((c, e), 0)) == Match("bricks")


def test_one_list_holds_several_colors_of_a_part_each_with_its_own_want():
    r = resolver(ORDER)
    only_blue = {("order", EntryKey("3001", BLUE)): 30}
    lookup = lambda c, e: only_blue.get((c, e), 0)  # noqa: E731
    assert r.match("3001", BLUE, lookup) == Match("order", EntryKey("3001", BLUE))
    assert r.match("3001", RED, lookup) == Match("bricks")


def test_a_specific_color_entry_is_used_before_the_any_color_entry():
    r = resolver("""
categories:
  - name: list
    priority: 1
    list:
      entries:
        - {part: "3001", color: Red, quantity: 2}
        - {part: "3001", color: any, quantity: 5}
""")
    wanted = {EntryKey("3001", RED): 2, EntryKey("3001", None): 5}
    lookup = lambda c, e: wanted[e]  # noqa: E731
    assert r.match("3001", RED, lookup).entry == EntryKey("3001", RED)
    assert r.match("3001", BLUE, lookup).entry == EntryKey("3001", None)
    wanted[EntryKey("3001", RED)] = 0
    assert r.match("3001", RED, lookup).entry == EntryKey("3001", None)
    wanted[EntryKey("3001", None)] = 0
    assert r.match("3001", RED, lookup) is None


def test_unknown_color_counts_only_against_an_any_color_entry():
    r = resolver(ORDER)
    everything = full(r)
    assert r.match("3004", None, everything) == Match("order", EntryKey("3004", None))
    # 3001 has only specific colors in the list: no answer while they are wanted.
    assert r.match("3001", None, everything) is None
    # Once they are used up the list cannot take it in any color, so the
    # next category decides as if the list were not there.
    assert r.match("3001", None, lambda c, e: 0) == Match("bricks")


def test_two_lists_wanting_the_same_part_fill_in_priority_order():
    r = resolver("""
categories:
  - name: first set
    priority: 1
    list: {entries: [{part: "3001", color: Red, quantity: 2}]}
  - name: second set
    priority: 2
    list: {entries: [{part: "3001", color: Red, quantity: 3}]}
""")
    key = EntryKey("3001", RED)
    wanted = {"first set": 2, "second set": 3}
    lookup = lambda c, e: wanted[c]  # noqa: E731
    assert r.match("3001", RED, lookup) == Match("first set", key)
    wanted["first set"] = 0
    assert r.match("3001", RED, lookup) == Match("second set", key)
    wanted["second set"] = 0
    assert r.match("3001", RED, lookup) is None


def test_category_of_answers_as_at_the_start_of_a_fresh_run():
    r = resolver(ORDER)
    assert r.category_of("3001", RED) == "order"
    assert r.category_of("3001", BLACK) == "bricks"
    assert r.category_of("3004", None) == "order"


def test_an_ordinary_category_matches_with_no_entry():
    r = resolver(ORDER)
    assert r.match("3010", RED, lambda c, e: 0) == Match("bricks", None, False)


CATCH_ALL = """
categories:
  - name: red 2x4
    priority: 1
    accept: {parts: [3001], colors: [Red]}
  - name: rest
    priority: 9
    catch_all: true
"""


def test_catch_all_takes_every_piece_no_category_above_took():
    r = resolver(CATCH_ALL)
    nothing = lambda c, e: 0  # noqa: E731
    assert r.match("3001", RED, nothing) == Match("red 2x4")
    assert r.match("3001", BLUE, nothing) == Match("rest", None, True)
    assert r.match("99999", BLACK, nothing) == Match("rest", None, True)
    assert r.match("3020", None, nothing) == Match("rest", None, True)
    # Color unknown but it decides between two bins: still no answer.
    assert r.match("3001", None, nothing) is None
    assert r.category_of("3020", BLUE) == "rest"
    assert r.bins_needed() == 2


def test_catch_all_may_leave_priority_out():
    r = resolver("""
categories:
  - name: a
    priority: 1
    accept: {parts: [3001]}
  - name: rest
    catch_all: true
""")
    assert r.category_of("3020", RED) == "rest"


@pytest.mark.parametrize(
    "text, message",
    [
        ("  - name: x\n    accept: {parts: [1]}\n    list: {entries: [{part: 1, color: any, quantity: 1}]}",
         "exactly one of.*has accept and list"),
        ("  - name: x\n    priority: 3", "exactly one of.*has none"),
        ("  - name: x\n    catch_all: true\n    accept: {parts: [1]}", "exactly one of"),
        ("  - name: x\n    list: {entries: [{part: 1, color: any, quantity: 1}]}\n    reject: {parts: [1]}",
         "'reject' is only allowed next to 'accept'"),
        ("  - name: x\n    catch_all: yes please", "'catch_all' must be true"),
        ("  - name: x\n    catch_all: false", "'catch_all' must be true"),
        ("  - name: x\n    list: [1, 2]", "'list' must be a mapping"),
        ("  - name: x\n    list: {entries: []}", "at least one entry"),
        ("  - name: x\n    list: {source: {set: 1}}", "at least one entry"),
        ("  - name: x\n    list: {entries: [{part: 1, color: any, quantity: 1}], from: x}", "unknown key.*from"),
        ("  - name: x\n    list: {entries: [{part: 1, color: any, qty: 1}]}", "entry 1: unknown key.*qty"),
        ("  - name: x\n    list: {entries: [{part: 1, quantity: 1}]}", "entry 1: needs color.*color: any"),
        ("  - name: x\n    list: {entries: [3001]}", "entry 1: must be a mapping"),
        ("  - name: x\n    list: {entries: [{part: 1, color: any, quantity: 0}]}", "1 or more"),
        ("  - name: x\n    list: {entries: [{part: 1, color: any, quantity: true}]}", "1 or more"),
        ("  - name: x\n    list: {entries: [{part: 1, color: any, quantity: 2.5}]}", "1 or more"),
        ("  - name: x\n    list: {entries: [{part: [1], color: any, quantity: 1}]}", "'part' must be"),
        ("  - name: x\n    list: {entries: [{part: 1, color: [Red], quantity: 1}]}", "'color' must be"),
        ("  - name: x\n    list: {entries: [{part: 1, color: Mauve, quantity: 1}]}", "no color 'Mauve'"),
        ("  - name: x\n    list: {entries: [{part: 1, color: Red, quantity: 1}, {part: '1', color: 4, quantity: 2}]}",
         "part 1 in color 4 is listed twice"),
        ("  - name: x\n    list: {entries: [{part: 1, color: any, quantity: 1}, {part: 1, color: ANY, quantity: 2}]}",
         "part 1 in any color is listed twice"),
        ("  - name: x\n    priority: 1\n    list: {entries: [{part: 1, color: any, quantity: 1}]}\n"
         "  - name: y\n    priority: 2\n    accept: {categories: [x]}", "cannot include the list category 'x'"),
        ("  - name: x\n    priority: 2\n    catch_all: true\n"
         "  - name: y\n    priority: 1\n    accept: {categories: [x]}", "cannot include the catch-all category 'x'"),
        ("  - name: x\n    priority: 2\n    catch_all: true\n"
         "  - name: y\n    priority: 3\n    accept: {parts: [1]}", "catch-all category 'x' must have the largest.*'y' has 3"),
        ("  - name: x\n    priority: 2\n    catch_all: true\n"
         "  - name: y\n    priority: 3\n    catch_all: true", "catch-all category 'x' must have the largest"),
    ],
)
def test_list_and_catch_all_mistakes_are_refused(text, message):
    with pytest.raises(ProfileError, match=message):
        resolver("categories:\n" + text + "\n")


def test_a_list_may_hold_a_part_in_a_specific_color_and_in_any_color():
    r = resolver("""
categories:
  - name: x
    list:
      entries:
        - {part: "3001", color: Red, quantity: 1}
        - {part: "3001", color: any, quantity: 1}
""")
    assert len(r.entries("x")) == 2
