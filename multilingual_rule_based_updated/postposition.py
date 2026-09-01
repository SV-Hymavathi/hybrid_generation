from generated_conditions import get_ppost



import requests
import csv
import os
from io import StringIO

def fetch_sheet_data(path_or_url):
    """
    Loads CSV data from a local file path or a Google Sheets export URL.
    Returns it as a list of rows (excluding header).
    """
    if os.path.exists(path_or_url):  # Local file
        with open(path_or_url, newline='', encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)  # skip header
            return list(reader)

    else:  # Assume it's a URL
        response = requests.get(path_or_url)
        response.raise_for_status()
        csv_content = response.text
        reader = csv.reader(StringIO(csv_content))
        header = next(reader)  # skip header
        return list(reader)

def get_matching_word_from_sheet(term, number, gender, person, anim, spkview_data, relation, sheet_url):
    if not anim or str(anim).strip() in ("", "-"):
        anim = "null"
    number  = str(number).strip()  if number  else ""
    gender  = str(gender).strip()  if gender  else ""
    person  = str(person).strip()  if person  else ""
    anim    = str(anim).strip()
    spkview = str(spkview_data).strip() if spkview_data else ""
    relation= str(relation).strip() if relation else ""
    null_equiv = {"null", "", "-", "0"}
    data_rows = fetch_sheet_data(sheet_url)
    for strict in (True, False):
        for row in data_rows:
            if len(row) < 8:
                continue
            r_word,r_term,r_number,r_gender,r_person,r_anim,r_spkview,r_relation = [c.strip() for c in row[:8]]
            if r_term != term:
                continue
            if r_relation and relation:
                r_rel = r_relation.replace(" ","")
                if r_rel.startswith("!"):
                    if relation in set(r_rel[1:].split("/")):
                        continue
                else:
                    if relation not in set(r_rel.split("/")):
                        continue
            if r_spkview and r_spkview != "0" and spkview:
                if spkview not in set(r_spkview.replace(" ","").split("/")):
                    continue
            if r_number and r_number != "0" and number:
                norm = r_number.replace("sg","s").replace("pl","p")
                if number not in set(norm.replace(" ","").split("/")):
                    continue
            if r_person and r_person != "0" and person:
                if r_person != person:
                    continue
            if r_anim:
                r_anim_list = set(r_anim.replace(" ","").split("/"))
                input_null = anim in null_equiv
                row_null   = bool(r_anim_list & null_equiv)
                if strict:
                    if input_null and not row_null:
                        continue
                    if not input_null and anim not in r_anim_list:
                        continue
                else:
                    if not input_null and r_anim not in null_equiv and anim not in r_anim_list:
                        continue
            if r_gender and r_gender != "0":
                allowed_g = set(r_gender.replace(" ","").split("/"))
                input_null_g = gender in null_equiv
                row_null_g   = bool(allowed_g & null_equiv)
                if input_null_g:
                    if strict and not row_null_g:
                        continue
                else:
                    if gender not in allowed_g:
                        continue
            return r_word
    return term


def preprocess_postposition_new(concept_type, np_data, words_info, verb_data, index_data):
    '''Calculates postposition to words wherever applicable according to rules.'''
    cp_verb_list = ['prayApreprsa+kara', 'sahAyawA+kara']
    
    # Initialize variables to default values.
    data_case = ''
    data_index = None
    data_head = None
    ppost = ''
    new_case = 'o'

    if len(verb_data) > 0:
        verb_term = verb_data[1]
        if len(verb_term) > 0:
            root_main = verb_term.strip().split('-')[0].split('_')[0]

    # Check that np_data is not empty and has the expected elements.
    if np_data != () and len(np_data) > 4 and np_data[4] != '':
        try:
            parts = np_data[4].strip().split(':')
            if len(parts) >= 2:
                data_head = parts[0]
                data_case = parts[1]
            else:
                data_case = ''
        except Exception as e:
            print(f"Error processing np_data[4]: {e}")
            data_case = ''

        data_index = np_data[0]
        data_seman = np_data[2]

        # Call generated function with all possible context
        ppost = get_ppost(
            data_case,
            data_seman=data_seman,
            root_main=root_main if 'root_main' in locals() else None,
            concept_type=concept_type
        )

    return new_case, ppost