#!/usr/bin/env python3
class category:
    def __init__(self, name, naming_scheme, priority=256, accepted_parts=[], accepted_colors=[], accepted_categories=[], max_part_quantities=[], rejected_parts=[], rejected_colors=[]):
        self.name = name
        
        # Supported Part Naming Schemes:
        # Rebrickable, Bricklink, BrickOwl, BrickSet, LEGO
        # naming Scheme is for parts & categories
        self.naming_scheme = naming_scheme
        
        # 0 is highest priority, numbers farther from zero are lower priority
        self.priority = priority

        # only accept accepted_parts in accepted_colors AND accepted_categories in accepted_colors
        # 'any' can be used in accepted_parts or accepted_colors. for example:
        # accepted_parts = ['any'] with accepted_colors = ['blue'] would accept any blue part
        # accepted_categories = ['Bricks'] with accepted_colors = ['any'] would accept any color part in the Bricks category

        self.accepted_parts = accepted_parts
        self.accepted_colors = accepted_colors
        self.accepted_categories = accepted_categories

        # optionally limit the quanity of specific parts in this category. 
        # Any part not defined here will have unlimited quantities allowed.
        # max_part_quantities = [('part1_ID', quantity1),('part2_ID', quantity2),etc.]
        self.max_part_quantities = max_part_quantities

        # optionally exclude specific parts OR specific colors
        # This supercedes the accepted_ items such that
        # any parts in both rejected_parts and accepted_parts will be REJECTED
        # any parts in both rejected_colors and accepted_colors will be REJECTED
        self.rejected_parts = rejected_parts
        self.rejected_colors = rejected_colors

        # this will contain a list of all part objects that belong to this category
        self.all_parts =[]

class part:
    ID = ""                         # Part ID
    naming_scheme = "BrickLink"     # naming scheme of Part ID
    volume_multiplier = 1.0         # optionally, tune the volume per piece for more optimal bin packing
    max_quantity = -1               # max quantity of this part that should accepted. -1 is unlimited quantity
    price = -1                      # 