"""Categories that can never receive a piece, and the "I meant this" acknowledgment."""

import warnings

import pytest
import yaml

from brick_sorting import (
    ProfileError,
    ProfileWarning,
    Unreachable,
    acknowledge_unreachable,
    compile_profile,
    load_profile,
)
from test_profiles import FakeCatalog, resolver


def quiet(text):
    """Compile and fail if any warning is raised."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return resolver(text)


SHADOWED = """
categories:
  - name: any 2x4
    priority: 1
    accept: {parts: [3001]}
  - name: red 2x4
    priority: 2
    accept: {parts: [3001], colors: [Red]}
"""


def test_a_category_shadowed_completely_is_reported_and_warned():
    with pytest.warns(ProfileWarning, match="'red 2x4' can never receive a piece.*'any 2x4'"):
        r = resolver(SHADOWED)
    assert r.unreachable() == (Unreachable("red 2x4", ("any 2x4",), False),)


def test_partial_overlap_is_never_reported():
    r = quiet("""
categories:
  - name: red 2x4
    priority: 1
    accept: {parts: [3001], colors: [Red]}
  - name: any 2x4
    priority: 2
    accept: {parts: [3001]}
""")
    assert r.unreachable() == ()


def test_several_categories_together_can_shadow_one():
    with pytest.warns(ProfileWarning, match="'all bricks'.*'red bricks', 'other bricks'"):
        r = resolver("""
categories:
  - name: red bricks
    priority: 1
    accept: {part_categories: [Bricks], colors: [Red]}
  - name: plates
    priority: 2
    accept: {part_categories: [Plates]}
  - name: other bricks
    priority: 3
    accept: {part_categories: [Bricks]}
    reject: {colors: [Red]}
  - name: all bricks
    priority: 4
    accept: {parts: [3001, 3004]}
""")
    # 'plates' is above but shares no piece, so it is not named.
    assert r.unreachable() == (Unreachable("all bricks", ("red bricks", "other bricks"), False),)


def test_a_rejected_color_leaves_room_for_a_category_below():
    r = quiet("""
categories:
  - name: bricks but black
    priority: 1
    accept: {part_categories: [Bricks]}
    reject: {colors: [Black]}
  - name: black 2x4
    priority: 2
    accept: {parts: [3001], colors: [Black]}
""")
    assert r.unreachable() == ()
    with pytest.warns(ProfileWarning, match="'red 2x4'"):
        r = resolver("""
categories:
  - name: bricks but black
    priority: 1
    accept: {part_categories: [Bricks]}
    reject: {colors: [Black]}
  - name: red 2x4
    priority: 2
    accept: {parts: [3001], colors: [Red]}
""")
    assert [item.category for item in r.unreachable()] == ["red 2x4"]


def test_any_color_below_a_few_listed_colors_is_reachable():
    r = quiet("""
categories:
  - name: red and blue
    priority: 1
    accept: {parts: [3001], colors: [Red, Blue, Black]}
  - name: 2x4
    priority: 2
    accept: {parts: [3001]}
""")
    assert r.unreachable() == ()


def test_wants_are_ignored_so_a_list_never_shadows():
    r = quiet("""
categories:
  - name: first set
    priority: 1
    list: {entries: [{part: "3001", color: any, quantity: 2}]}
  - name: second set
    priority: 2
    list: {entries: [{part: "3001", color: Red, quantity: 3}]}
  - name: red 2x4
    priority: 3
    accept: {parts: [3001], colors: [Red]}
""")
    assert r.unreachable() == ()


def test_a_list_below_a_rule_category_that_takes_all_its_entries_is_reported():
    with pytest.warns(ProfileWarning, match="'order'"):
        r = resolver("""
categories:
  - name: bricks
    priority: 1
    accept: {part_categories: [Bricks]}
  - name: order
    priority: 2
    list:
      entries:
        - {part: "3001", color: Red, quantity: 3}
        - {part: "3004", color: any, quantity: 3}
""")
    assert r.unreachable() == (Unreachable("order", ("bricks",), False),)
    # An entry the rule category does not take makes the list reachable.
    quiet("""
categories:
  - name: bricks
    priority: 1
    accept: {part_categories: [Bricks]}
  - name: order
    priority: 2
    list:
      entries:
        - {part: "3001", color: Red, quantity: 3}
        - {part: "3020", color: Blue, quantity: 3}
""")


def test_a_catch_all_is_never_reported():
    r = quiet("""
categories:
  - name: bricks
    priority: 1
    accept: {part_categories: [Bricks, Tiles, Plates]}
  - name: rest
    priority: 2
    catch_all: true
""")
    assert r.unreachable() == ()


ACKNOWLEDGED = SHADOWED + "    unreachable_ok: {shadowed_by: [any 2x4]}\n"


def test_an_acknowledgment_naming_the_shadowing_categories_silences_the_warning():
    r = quiet(ACKNOWLEDGED)
    assert r.unreachable() == (Unreachable("red 2x4", ("any 2x4",), True),)
    assert r.stale_acknowledgments() == ()


def test_the_warning_returns_when_a_different_set_of_categories_shadows():
    text = ACKNOWLEDGED.replace("categories:\n", """categories:
  - name: red parts
    priority: 0
    accept: {parts: [3001, 3020], colors: [Red]}
""")
    with pytest.warns(ProfileWarning, match="'red 2x4'.*'red parts', 'any 2x4'"):
        r = resolver(text)
    assert r.unreachable() == (Unreachable("red 2x4", ("red parts", "any 2x4"), False),)


def test_an_acknowledgment_on_a_reachable_category_is_reported_as_stale():
    with pytest.warns(ProfileWarning, match="'blue 2x4' has 'unreachable_ok' but can receive"):
        r = resolver("""
categories:
  - name: red 2x4
    priority: 1
    accept: {parts: [3001], colors: [Red]}
  - name: blue 2x4
    priority: 2
    accept: {parts: [3001], colors: [Blue]}
    unreachable_ok: {shadowed_by: [red 2x4]}
""")
    assert r.unreachable() == ()
    assert r.stale_acknowledgments() == ("blue 2x4",)


@pytest.mark.parametrize(
    "value, message",
    [
        ("true", "shadowed_by"),
        ("{shadowed_by: []}", "shadowed_by"),
        ("{shadowed_by: any 2x4}", "shadowed_by"),
        ("{shadowed_by: [1]}", "shadowed_by"),
        ("{by: [any 2x4]}", "unknown key.*by"),
    ],
)
def test_malformed_acknowledgments_are_refused(value, message):
    with pytest.raises(ProfileError, match=message):
        resolver(SHADOWED + f"    unreachable_ok: {value}\n")


def test_acknowledge_unreachable_writes_the_acknowledgment_into_a_copy():
    document = yaml.safe_load(SHADOWED)
    original = yaml.safe_load(SHADOWED)
    with pytest.warns(ProfileWarning):
        r = compile_profile(load_profile(document), FakeCatalog())
    acknowledged = acknowledge_unreachable(document, r.unreachable()[0])
    assert document == original
    assert acknowledged["categories"][1]["unreachable_ok"] == {"shadowed_by": ["any 2x4"]}
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        again = compile_profile(load_profile(acknowledged), FakeCatalog())
    assert again.unreachable()[0].acknowledged


def test_acknowledge_unreachable_needs_the_category_in_the_profile():
    with pytest.raises(ProfileError, match="no category named 'ghost'"):
        acknowledge_unreachable(yaml.safe_load(SHADOWED), Unreachable("ghost", ("x",), False))
