#!/usr/bin/env python3
import json
import csv

import os
include_dir = os.path.dirname(os.path.realpath(__file__)) + "/../brick-translator-lib/"
import sys
sys.path.append(include_dir)
from translate_lib import *


sorting_profile = {}
# Load JSON data from a file
# with open('sorting-profile.json', 'r') as json_file:
#     sorting_profile = json.load(json_file)

# supporting_translations = []
# naming_scheme = sorting_profile['Part Naming Scheme']
# for translation in REBRICKABLE_SUPPORTED_TRANSLATIONS:
#     supporting_translations.append(translation[0])
    
# if(naming_scheme not in supporting_translations):
#     print("invalid Part Naming Scheme. Supported naming schemes:")
#     print(supporting_translations)
#     exit()

# del sorting_profile['Supported Part Naming Schemes']
# del sorting_profile['Part Naming Scheme']
# categories = list(sorting_profile.keys())
# print(categories)




category_filename = "part_categories.csv"  # File name
category_names = {}
fields = []  # Column names
category_rows = []    # Data rows
category_parts = {}    
# import parts list from downloadable parts.csv
try:
    with open(category_filename, 'r') as csvfile:
        csvreader = csv.reader(csvfile)  # Reader object

        fields = next(csvreader)  # Read header
        for row in csvreader:     # Read rows
            category_rows.append(row)
            category_names[row[0]] = row[1]
            category_parts[row[1]] = []

        total_part_count = csvreader.line_num
        # print("Total no. of rows: %d" % total_part_count)  # Row count
except:
    print("%s not found. Download and extract to %s. Downloads found here: https://rebrickable.com/downloads/" % (part_filename,part_filename))
    exit()

# print(category_names)
# print(category_parts)




part_filename = "parts.csv"  # File name
parts = {}
fields = []  # Column names
part_rows = []    # Data rows
# import parts list from downloadable parts.csv
# try:
with open(part_filename, 'r') as csvfile:
    csvreader = csv.reader(csvfile)  # Reader object
    fields = next(csvreader)  # Read header
    for row in csvreader:     # Read rows
        part_rows.append(row)
        parts[row[0]] = [row[1], category_names[row[2]], row[3]]
        # print(category_names[row[2]])
        # print(category_parts[category_names[row[2]]])
        # print(row[0])
        category_parts[category_names[row[2]]].append(row[0])
        # print(category_parts[category_names[row[2]]])
        # print()
        
    total_part_count = csvreader.line_num
    # print("Total no. of rows: %d" % total_part_count)  # Row count
# except:
#     print("%s not found. Download and extract to %s. Downloads found here: https://rebrickable.com/downloads/" % (part_filename,part_filename))
#     exit()

# print(parts)

# print(category_parts["Bricks"])

# default_categories_file = "#!/usr/bin/env python3\nfrom sorting-profile-lib import *\n"

# for row in category_parts:
#     print(row)
#     default_categories_file += category_names[row[2]] + " = category()\n"
#     default_categories_file += category_names[row[2]] + ".accepted_colors.append('any')\n"
#     default_categories_file += category_names[row[2]] + ".accepted_categories = "
#     default_categories_file += ['Bricks']
#     default_categories_file += "\n"

from sorting_profile_lib import *

category_parts_keys = list(category_parts.keys())
# print(category_parts_keys[0])
categories = []
for key in category_parts_keys:
    new_cat = category(name=key, naming_scheme='Rebrickable', accepted_parts=category_parts[key], accepted_colors=['any'])
    # new_cat.category_name = key
    # print(category_parts[key])
    # cat_keys = list(category_parts[key].keys())
    # new_cat.priority = 256
    # new_cat.accepted_parts = category_parts[key]
    # new_cat.accepted_colors = ['any']
    # new_cat.max_part_quantities = []
    # new_cat.rejected_parts = []
    # new_cat.rejected_colors = []
    # new_cat.accepted_categories = []
    categories.append(new_cat)



import yaml
user_yaml_file = 'sorting-profile.yaml'

with open(user_yaml_file, 'r') as file:
    sortp = yaml.safe_load(file)

sorting_profile = sortp['sorting_profile']
# print(sorting_profile)
sorting_profile_keys = list(sorting_profile.keys())
# print(sorting_profile_keys[0])

user_categories = []

for key in sorting_profile_keys:
    
    cat_keys = list(sorting_profile[key].keys())
    if('naming_scheme' not in cat_keys):
        print("'naming_scheme' field missing in %s from %s" % (sorting_profile[key], user_yaml_file))
        exit()
    new_cat = category(name=key,naming_scheme=sorting_profile[key]['naming_scheme'])
    # print(sorting_profile[key])
    if('priority' in cat_keys):
        new_cat.priority = sorting_profile[key]['priority']
    if('accepted_parts' in cat_keys):
        new_cat.accepted_parts = sorting_profile[key]['accepted_parts']
    if('accepted_colors' in cat_keys):
        new_cat.accepted_colors = sorting_profile[key]['accepted_colors']
    if('max_part_quantities' in cat_keys):
        new_cat.max_part_quantities = sorting_profile[key]['max_part_quantities']
    if('rejected_parts' in cat_keys):
        new_cat.rejected_parts = sorting_profile[key]['rejected_parts']
    if('rejected_colors' in cat_keys):
        new_cat.rejected_colors = sorting_profile[key]['rejected_colors']
    if('accepted_categories' in cat_keys):
        new_cat.accepted_categories = sorting_profile[key]['accepted_categories']
    categories.append(new_cat)


'''
next steps:
7.) split one categories list into multiple: rebrickable_categories, bricklink_categories, user_categories
4.) add support .YAML default_naming_scheme (used when category's individual definition is missing)
6.) swap to using part objects

1.) refine categories
    iterate through each priority, adding accepted_parts from accepted_categories:
        recursive:
            if accepted_category, has accepted_categories, add current category to check list, 
            check accepted_category's accepted_categories, if they are present in the check list,
            categories include each other, throw error and exit
            otherwise, once accepted category found without accepted_categories, add parts to that 
            category's accepted_parts list and return those accepted_parts
    check_list = []
    recurse(category):
        checklist.append(category.name)
        
        if(category.accepted_parts == []):
            do nothing
        else:
            convert category.accepted_parts into parts objects in category.all_parts
            clear category.accepted_parts
        
        if(category.accepted_categories != []):
            for cat in accepted_categories:
                if cat in category.checklist
                    error self reference categories
                    exit()
                else:
                    incoming_parts = recurse(cat)
                    for part in incoming_parts:
                        category.all_parts.append(part)
        return category.all_parts
        
            
        

2.) add support for RB colors
3.) add support for BL colors
4.) create part -> category mappings (based on priority)


'''
    
    
