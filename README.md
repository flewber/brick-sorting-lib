# brick-sorting-lib

## Prerequisits

- clone https://github.com/flewber/brick-translator-lib and this repo in the same directory
- follow instructions in https://github.com/flewber/brick-translator-lib readme.md to get that set up
- install `pip3 install pyyaml`
- create sorting_profile.yaml in this repo's directory (see sorting-profile-sample.yaml for an example)

## Generating the Part -> Category Dictionary
run `python3 get-part-mapping.py`
- note: this will only generated the dictionary in memory, not save it anywhere. This is still a work in 
progress with more work to be done including:


## ToDo
- add support for Rebrickable colors
- add support for BrickLink colors
- test sorting-profile.yaml based on all BrickLink naming-scheme
- add more test coverage for various failure cases in user-defined sorting-profiles
- add support for user defining part objects to override defaults (volume multiplier & quantity)
- design mechanism for mapping categories to bins (manual vs auto)
- design mechanism for bins tracking contents, volume, quantity, etc
- confirm that rejected parts get rejected AFTER rolling up parts from accepted_categories
- fix part_translations.json warning