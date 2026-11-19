from pathlib import Path

import pytest

from brick_sorting import CsvCatalog, ProfileError, compile_profile, load_profile

RED, BLUE, BLACK = 4, 1, 0


class FakeCatalog:
    categories = {
        "Bricks": {"3001", "3004", "3010"},
        "Tiles": {"3070b", "101645"},
        "Plates": {"3020"},
    }
    colors = {"red": RED, "blue": BLUE, "black": BLACK}
    sets = {"1234-1": {("3001", RED): 2, ("3020", BLUE): 1}}

    def parts_in_category(self, name):
        return self.categories.get(name)

    def color_id(self, color):
        if isinstance(color, int):
            return color if color in self.colors.values() else None
        return self.colors.get(color.lower())

    def set_inventory(self, set_num):
        return self.sets.get(set_num)


def resolver(text):
    return compile_profile(load_profile(text), FakeCatalog())


def test_every_listed_part_is_accepted_not_every_other_one():
    r = resolver("""
categories:
  - name: mixed
    accept: {parts: [1, 2, 3, 4, 5, 6]}
""")
    assert [r.category_of(str(n), RED) for n in range(1, 7)] == ["mixed"] * 6


def test_part_numbers_match_whether_written_as_numbers_or_text():
    r = resolver("""
categories:
  - name: a
    accept: {parts: [3001, "3070b"]}
""")
    assert r.category_of(3001, RED) == r.category_of("3001", RED) == "a"
    assert r.category_of("3070b", RED) == "a"


def test_colors_are_applied():
    r = resolver("""
categories:
  - name: blue bricks
    accept: {part_categories: [Bricks], colors: [Blue]}
""")
    assert r.category_of("3001", BLUE) == "blue bricks"
    assert r.category_of("3001", RED) is None


def test_colors_may_be_given_by_id_and_any_means_any():
    r = resolver("""
categories:
  - name: red
    priority: 1
    accept: {parts: [3001], colors: [4]}
  - name: rest
    priority: 2
    accept: {parts: [3001], colors: any}
""")
    assert r.category_of("3001", RED) == "red"
    assert r.category_of("3001", BLACK) == "rest"


def test_reject_wins_over_accept_including_parts_from_a_category():
    r = resolver("""
categories:
  - name: tiles
    accept: {parts: [3001], part_categories: [Tiles]}
    reject: {parts: [101645, 3001], colors: [Black]}
""")
    assert r.category_of("3070b", RED) == "tiles"
    assert r.category_of("101645", RED) is None
    assert r.category_of("3001", RED) is None
    assert r.category_of("3070b", BLACK) is None


def test_lowest_priority_number_wins():
    r = resolver("""
categories:
  - name: everything brick
    priority: 5
    accept: {part_categories: [Bricks]}
  - name: just 2x4
    priority: 1
    accept: {parts: [3001]}
""")
    assert r.category_of("3001", RED) == "just 2x4"
    assert r.category_of("3004", RED) == "everything brick"


def test_equal_priorities_are_an_error_naming_both_and_a_free_number():
    with pytest.raises(ProfileError, match="'a' and 'b' both have priority 2.*3 is free"):
        resolver("""
categories:
  - name: a
    priority: 2
    accept: {parts: [3001, 3004]}
  - name: b
    priority: 2
    accept: {part_categories: [Bricks]}
""")


def test_equal_priorities_are_an_error_even_when_colors_keep_them_apart():
    # Before 0.2.0 this was allowed, since no piece could go to both.
    with pytest.raises(ProfileError, match="'red bricks' and 'blue bricks'.*4 is free"):
        resolver("""
categories:
  - name: red bricks
    priority: 2
    accept: {part_categories: [Bricks], colors: [Red]}
  - name: blue bricks
    priority: 2
    accept: {part_categories: [Bricks], colors: [Blue]}
  - name: plates
    priority: 3
    accept: {part_categories: [Plates]}
""")


def test_at_most_one_category_may_leave_priority_out():
    with pytest.raises(ProfileError, match="'a' and 'b' both have priority 256.*left out"):
        resolver("""
categories:
  - name: a
    accept: {parts: [3001]}
  - name: b
    accept: {parts: [3020]}
""")


def test_including_categories_in_any_order_and_through_a_diamond():
    r = resolver("""
categories:
  - name: top
    priority: 0
    accept: {categories: [left, right], colors: [Red]}
  - name: left
    priority: 1
    accept: {categories: [base], parts: [3020]}
  - name: right
    priority: 2
    accept: {categories: [base]}
    reject: {parts: [3004]}
  - name: base
    priority: 3
    accept: {part_categories: [Bricks]}
""")
    assert r.category_of("3004", RED) == "top"       # through left
    assert r.category_of("3020", RED) == "top"
    assert r.category_of("3004", BLUE) == "left"
    assert r.category_of("3010", BLUE) == "left"


def test_an_included_categorys_own_rejects_carry_over():
    r = resolver("""
categories:
  - name: outer
    priority: 0
    accept: {categories: [inner]}
  - name: inner
    priority: 1
    accept: {part_categories: [Bricks]}
    reject: {parts: [3010]}
""")
    assert r.category_of("3001", RED) == "outer"
    assert r.category_of("3010", RED) is None


def test_a_circle_of_includes_is_an_error_that_shows_the_circle():
    with pytest.raises(ProfileError, match="a -> b -> a"):
        resolver("""
categories:
  - name: a
    accept: {categories: [b]}
  - name: b
    priority: 1
    accept: {categories: [a]}
""")


@pytest.mark.parametrize(
    "text, message",
    [
        ("categories:\n  - name: a\n    accpeted_parts: [3002]\n    accept: {parts: [1]}", "accpeted_parts"),
        ("categories:\n  - name: a\n    accept: {part: [1]}", "unknown key.*part"),
        ("categories:\n  - name: a\n    accept: {parts: [1]}\nsorting_profile: {}", "sorting_profile"),
        ("categories:\n  - name: a\n    accept: {parts: }", "at least one entry"),
        ("categories:\n  - name: a\n    accept: {parts: 3001}", "must be a list"),
        ("categories:\n  - name: a\n    accept: {}", "accept"),
        ("categories:\n  - name: a", "accept"),
        ("categories:\n  - name: a\n    accept: {parts: [1]}\n  - name: a\n    accept: {parts: [2]}", "named 'a'"),
        ("categories: []", "at least one category"),
        ("categories:\n  - name: a\n    priority: high\n    accept: {parts: [1]}", "priority"),
        ("categories:\n  - name: a\n    naming_scheme: BrickLink\n    accept: {parts: [1]}", "not supported yet"),
        ("categories:\n  - name: a\n    accept: {min_price: 0.5}", "not supported yet"),
        ("categories:\n  - name: a\n    accept: {parts: [1], colors: [any]}", "on its own"),
        ("categories:\n  - name: a\n    accept: {part_categories: [Brix]}", "no part category named 'Brix'"),
        ("categories:\n  - name: a\n    accept: {categories: [ghost]}", "'ghost'"),
        ("categories:\n  - name: a\n    accept: {parts: [1], colors: [Mauve]}", "no color 'Mauve'"),
        ("categories:\n  - name: a\n    accept: {parts: [1]}\n    reject: {parts: [1]}", "accepts no piece"),
        ("categories:\n  - name: a\n    accept: {set: \"9999-1\"}", "no set '9999-1'"),
    ],
)
def test_mistakes_are_refused_with_a_message_that_names_them(text, message):
    with pytest.raises(ProfileError, match=message):
        resolver(text)


def test_categories_do_not_share_state():
    r = resolver("""
categories:
  - name: a
    priority: 1
    accept: {parts: [3001]}
  - name: b
    priority: 2
    accept: {parts: [3020]}
""")
    assert r.category_of("3020", RED) == "b" and r.category_of("3001", RED) == "a"
    first, second = r.profile.categories
    assert first.parts == {"3001"} and second.parts == {"3020"}
    assert not first.rejected_parts and not second.rejected_parts


def test_set_category_accepts_exactly_the_sets_parts_in_the_sets_colors():
    r = resolver("""
categories:
  - name: my set
    priority: 0
    accept: {set: "1234-1"}
  - name: bricks
    priority: 1
    accept: {part_categories: [Bricks]}
""")
    assert r.category_of("3001", RED) == "my set"
    assert r.category_of("3001", BLUE) == "bricks"
    assert r.category_of("3020", BLUE) == "my set"
    assert r.category_of("3020", RED) is None


def test_unknown_color_gets_an_answer_only_when_color_cannot_matter():
    r = resolver("""
categories:
  - name: red 2x4
    priority: 1
    accept: {parts: [3001], colors: [Red]}
  - name: bricks
    priority: 2
    accept: {part_categories: [Bricks]}
""")
    assert r.category_of("3004", None) == "bricks"
    assert r.category_of("3001", None) is None
    assert r.category_of("3020", None) is None


def test_bin_count():
    r = resolver("""
categories:
  - name: a
    accept: {parts: [1]}
  - name: b
    priority: 1
    accept: {parts: [2]}
overflow_bins: 1
""")
    assert r.categories == ("a", "b") and r.bins_needed() == 3
    r.check_fits(24)
    with pytest.raises(ProfileError, match="needs 3 bins"):
        r.check_fits(2)


def test_sample_profile_loads_against_csv_files(tmp_path):
    (tmp_path / "part_categories.csv").write_text("id,name\n11,Bricks\n19,Tiles\n")
    (tmp_path / "parts.csv").write_text(
        "part_num,name,part_cat_id,part_material\n"
        "3001,Brick 2 x 4,11,Plastic\n3004,Brick 1 x 2,11,Plastic\n"
        "3070b,Tile 1 x 1,19,Plastic\n101645,Tile odd,19,Plastic\n96489,Something,19,Plastic\n"
    )
    (tmp_path / "colors.csv").write_text(
        "id,name,rgb,is_trans\n0,Black,05131D,f\n1,Blue,0055BF,f\n4,Red,C91A09,f\n"
    )
    sample = Path(__file__).parent.parent / "sorting-profile-sample.yaml"
    r = compile_profile(load_profile(sample), CsvCatalog(tmp_path))
    assert r.category_of("3001", 4) == "bricks and tiles in red"
    assert r.category_of("3001", 1) == "blue 2x4 and 1x2 bricks"
    assert r.category_of("3001", 0) is None
    assert r.category_of("101645", 4) is None
    assert r.category_of("3070b", 0) == "tiles"
    assert r.bins_needed() == 5
