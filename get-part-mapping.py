#!/usr/bin/env python3
import json
import csv

import os
include_dir = os.path.dirname(os.path.realpath(__file__)) + "/../brick-translator-lib/"
import sys
sys.path.append(include_dir)
from translate_lib import *


rebrickable_category_filename = "part_categories.csv"  # File name
rebrickable_category_names = {}     # dictionary rebrickable category ID -> rebricable category name
fields = []  # Column names
rebrickable_category_rows = []    # array of data within rebrickable_category_filename
rebrickable_category_parts = {}   # dictionary rebrickable category name -> list of rebrickable part IDs in that category
# import parts list from downloadable parts.csv
# Use Category names as keys when initializing dictionary
try:
    with open(rebrickable_category_filename, 'r') as csvfile:
        csvreader = csv.reader(csvfile)  # Reader object

        fields = next(csvreader)  # Read header
        for row in csvreader:     # Read rows
            rebrickable_category_rows.append(row)
            rebrickable_category_names[row[0]] = row[1]
            # print("row[0]: %s    row[1]: %s" % (row[0], row[1]))

            # initalize dictionary using category names as the key
            # each category name will point to an array of all part IDs belonging to that category
            rebrickable_category_parts[row[1]] = []

        total_part_count = csvreader.line_num
        # print("Total no. of rows: %d" % total_part_count)  # Row count
except:
    print("%s not found. Download and extract to %s. Downloads found here: https://rebrickable.com/downloads/" % (rebrickable_category_filename,rebrickable_category_filename))
    exit()



rebrickable_part_filename = "parts.csv"  # File name
rebrickable_parts = {}  # dictionary rebrickable part ID -> array with part metadata
fields = []  # Column names
part_rows = []    # Data from parts.csv

# import parts list from downloadable parts.csv
# try:
with open(rebrickable_part_filename, 'r') as csvfile:
    csvreader = csv.reader(csvfile)  # Reader object
    fields = next(csvreader)  # Read header
    for row in csvreader:     # Read rows
        part_rows.append(row)
        rebrickable_category_name = rebrickable_category_names[row[2]]
        rebrickable_parts[row[0]] = [row[1], rebrickable_category_name, row[3]]
        
        # add part ID to array of part for its category
        rebrickable_category_parts[rebrickable_category_name].append(row[0])
        
    total_part_count = csvreader.line_num

# import "category" and "part" classes
from sorting_profile_lib import *

rebrickable_category_parts_keys = list(rebrickable_category_parts.keys()) # get a list of all
# print(rebrickable_category_parts_keys[0])

rebrickable_category_objects = [] # array of category objects for each rebrickable category
for key in rebrickable_category_parts_keys:
    new_cat = category(name=key, naming_scheme='Rebrickable', accepted_parts=rebrickable_category_parts[key], accepted_colors=['any'])
    rebrickable_category_objects.append(new_cat)



import yaml
user_yaml_file = 'sorting-profile.yaml'

with open(user_yaml_file, 'r') as file:
    yaml_contents = yaml.safe_load(file)

# extract user sorting profile from yaml contents
user_sorting_profile = yaml_contents['sorting_profile']

# check if default naming scheme is defined for the file
if('default_naming_scheme' in list(yaml_contents.keys())):
    user_default_naming_scheme = yaml_contents['default_naming_scheme']
else:
    user_default_naming_scheme = False

# print(user_sorting_profile)
user_sorting_profile_keys = list(user_sorting_profile.keys())
# print(user_sorting_profile_keys[0])

user_category_objects = []  # list of category objects for each user-defined category

# for each user category, generate category object and append to user_category_objects
for key in user_sorting_profile_keys:
    
    category_fields = list(user_sorting_profile[key].keys())

    # every category requires a naming scheme to be defined
    if('naming_scheme' not in category_fields):
        if(user_default_naming_scheme):
            new_cat = category(name=key,naming_scheme=user_default_naming_scheme)
        else:
            print("'naming_scheme' field missing in %s from %s" % (key, user_yaml_file))
            print("'default_naming_scheme' is also not specified in %s" % (user_yaml_file))
            exit()
    else:
        new_cat = category(name=key,naming_scheme=user_sorting_profile[key]['naming_scheme'])


    # extract all other optional fields from user's category
    if('priority' in category_fields):
        new_cat.priority = user_sorting_profile[key]['priority']
    if('accepted_parts' in category_fields):
        new_cat.accepted_parts = user_sorting_profile[key]['accepted_parts']
    if('accepted_colors' in category_fields):
        new_cat.accepted_colors = user_sorting_profile[key]['accepted_colors']
    if('max_part_quantities' in category_fields):
        new_cat.max_part_quantities = user_sorting_profile[key]['max_part_quantities']
    if('rejected_parts' in category_fields):
        new_cat.rejected_parts = user_sorting_profile[key]['rejected_parts']
    if('rejected_colors' in category_fields):
        new_cat.rejected_colors = user_sorting_profile[key]['rejected_colors']
    if('accepted_categories' in category_fields):
        new_cat.accepted_categories = user_sorting_profile[key]['accepted_categories']
        # print("ac: %s" % new_cat.accepted_categories)
    user_category_objects.append(new_cat)

# add all category objects into one list
all_category_objects = user_category_objects
for cat in rebrickable_category_objects:
    all_category_objects.append(cat)



# function to convert part IDs from a category's accepted_parts list into 
# part objects in the category's 'all_parts' list
def  update_part_objects(cat1):
    # print(cat.accepted_parts)
    all_parts = []
    for cat_part in cat1.accepted_parts:
        # only include parts not listed in rejected_parts
        # print(cat_part)
        if(cat_part not in cat1.rejected_parts):
            cat1.all_parts.append(part(id=cat_part,naming_scheme=cat1.naming_scheme))
        cat1.accepted_parts.remove(cat_part)
        # if(cat_part in cat1.accepted_parts):
            # print("WTF?!")
    # print(cat1.accepted_parts)
    # return all_parts

# recursive function to add all parts from a category's accepted_categories to the 
# category's "all_parts" field
def process_category(cat, checklist):
    
    checklist.append(cat.name)  # checklist needed to ensure no circular category inclusions
    if(cat.accepted_parts != []):
        if(cat.accepted_parts == None):
            print("Error: accepted_parts is empty in %s. empty fields must be removed entirely." % cat.name)
            exit()
        # convert cat.accepted_parts into parts objects in cat.all_parts
        # cat.all_parts = 
        update_part_objects(cat)
        # cat.accepted_parts = []
        # print(cat.accepted_parts)
    
    if(cat.accepted_categories != []):
        if(cat.accepted_categories == None):
            print("Error: accepted_categories is empty in %s. empty fields must be removed entirely." % cat.name)
            exit()
        # print("accepted_categories: %s" % cat.accepted_categories)
        for accepted_cat in cat.accepted_categories:
            if accepted_cat in checklist:
                print("error self reference in accepted_categories section of %s" % accepted_cat)
                print("catergory reference stack: %s" % checklist)
                exit()
            else:
                # search for referenced category
                found = False
                for cat0 in all_category_objects:
                    if(cat0.name == accepted_cat):
                        found = True
                        incoming_parts = process_category(cat0, checklist)
                        for part in incoming_parts:
                            cat.all_parts.append(part)
                if(found == False):
                    print("in %s, invalid accepted_category: %s" % (cat.name, accepted_cat))
                cat.accepted_categories.remove(accepted_cat)
        
    return cat.all_parts

# for cat in all_category_objects:
#     print(cat.all_parts)

# print()

for cat in all_category_objects:
    # print("cat: %s" % cat.name)
    checklist = []
    process_category(cat, checklist)

# for cat in all_category_objects:
#     print(cat.all_parts)

# Sorting the list by age
all_category_objects_sorted = sorted(all_category_objects, key=lambda cat: cat.priority)


previous_priority = -1
same_priority_parts = []
all_priority_parts = []
part_to_category_dict = {}
for cat in all_category_objects_sorted:

    # group categories by priority to determine whether to throw errors or warnings on duplicate pieces
    if(previous_priority < cat.priority):
        all_priority_parts += same_priority_parts
        same_priority_parts = []
        previous_priority = cat.priority

    for cat_part in cat.all_parts:
        # print(cat_part.id)
        if(cat_part in same_priority_parts):
            print("Error: Duplicate part in multiple categories with identical priorities.")
            print("Part: %s in both: %s and: %s categories" % (cat_part.id, cat.name, part_to_category_dict[TRANSLATION_PREFIXES[cat_part.naming_scheme] + cat_part.id]))
            exit()

        # if(cat_part in all_priority_parts):
        #     print("Warn: Duplicate part in multiple categories with different priorities.")
        #     print("Part: %s in both: %s and: %s categories" % (cat_part.id, cat.name, part_to_category_dict[TRANSLATION_PREFIXES[cat_part.naming_scheme] + cat_part.id]))

        part_to_category_dict[TRANSLATION_PREFIXES[cat_part.naming_scheme] + str(cat_part.id)] = cat.name
        same_priority_parts.append(cat_part)

# print(part_to_category_dict)

    
    
