import os
import sys
import re
import subprocess
import repository.constant
import tempfile
import importlib
from mapping_paradigm import *
# from googletrans import Translator
# from indic_transliteration import sanscript
from repository.coref_discourse import *
from repository.verb import Verb
from repository.concept import Concept
from wxconv import WXC
import json
import tempfile
# from googletrans import Translator
# from generate_input_modularize_new import additional_words_dict,spkview_dict
# from Table import store_data
from repository.verb import Verb
from repository.concept import Concept
from operator import itemgetter
from some_convertions_files.json_to_txt import process_and_write_json
# from nltk.chunk import RegexpParser
additional_words_dict = {}
processed_postpositions_dict = {}
construction_dict = {}
spkview_dict = {}
MORPHO_SEMANTIC_DICT = {}
data_case_for_k4=[]
construction_dict_to_leave={}
# Global dictionary to store words prefixed with '*' along with their category
global_starred_words = {}

#pre processing

def read_file(file_path):
    """
    Read and return the content of a file.
    """
    with open(file_path, 'r') as file:
        return file.read()

# def read_file(file_path):
#     """
#     Functionality: To read the file from mentioned file_path.
#     Exception: If file_path is incorrect raise an exception - "No such File found." and exit the program.
#     Parameters:
#         file_path - path of file to be read.
#     Returns:
#         Returns array of lines for data given in file.
#     """
#     log(f'File ~ {file_path}')
#     try:
#         with open(file_path, 'r') as file:
#             lines = file.readlines()
#             if len(lines) > 10 and lines[10].strip() == '':
#                 lines = lines[:10]
#         log('File data read.')
#     except FileNotFoundError:
#         log('No such File found.', 'ERROR')
#         sys.exit()
#     return lines

def log(mssg, logtype='OK'):
    '''Generates log message in predefined format.'''

    # Format for log message
    print(f'log : [{logtype}]:{mssg}')
    if logtype == 'ERROR':
        try:
            path = sys.argv[1]
            write_hindi_test(' ', 'Error', mssg, 'test.csv', path)
        except (IndexError, Exception):
            pass  # No file path argument available


def write_hindi_test(hindi_output, POST_PROCESS_OUTPUT, src_sentence, OUTPUT_FILE, path):
    """Append the hindi text into the file"""
    OUTPUT_FILE = 'TestResults.csv'# temporary for presenting
    str = path.strip('lion_story/')
    if str == '1':
        with open(OUTPUT_FILE, 'w') as file:
            file.write("")

    with open(OUTPUT_FILE, 'a') as file:
        file.write(path.strip('../hindi_gen/lion_story') + '\t')
        file.write(src_sentence.strip('"').strip('\n').strip('#') + '\t')
        file.write(POST_PROCESS_OUTPUT + '\t')
        file.write(hindi_output + '\t')
        file.write('\n')
        # log('Output data write successfully')
    return "Output data write successfully"


# def masked_postposition(processed_words, words_info, processed_verbs):
#     '''Calculates masked postposition to words wherever applicable according to rules.'''
#     masked_PPdata = {}

#     for data in processed_words:
#         if data[2] not in ('p', 'n', 'other'):
#             continue
#         data_info = getDataByIndex(data[0], words_info)
#         try:
#             data_case = False if data_info == False else data_info[4].split(':')[1].strip()
#         except IndexError:
#             data_case = False
#         ppost = ''
#         ppost_value = '<>'
#         # if data_case in ('k1', 'pk1'):
#         #     if findValue('yA', processed_verbs, index=6)[0]:  # has TAM "yA"
#         #         if findValue('k2', words_info, index=4)[0]: # or findExactMatch('k2p', words_info, index=4)[0]:
#         #             ppost = ppost_value
#         # if data_case in ('r6', 'k3', 'k5', 'k5prk', 'k4', 'k4a', 'k7t', 'jk1','k7', 'k7p','k2g', 'k2','rsk', 'ru' ):
#         #     ppost = ppost_value
#         if data_case in ('k7','k7t','k7p','k2p'):
#             ppost = ppost_value
#         elif data_case == 'krvn' and data_info[2] == 'abs':  #abstract noun as adverb
#             ppost = ppost_value
#         elif data_case in ('k2g', 'k2') and data_info[2] in ("anim", "per"):
#             ppost = ppost_value #'ko'
#         elif data_case in ('rsm', 'rsma','k7a'):
#             ppost = ppost_value+ ' ' + ppost_value #ke pAsa
#         elif data_case == 'rt':
#             # ppost = ppost_value+ ' ' + ppost_value #'ke lie'
#             ppost = ppost_value
#         elif 'rask' in data_case:
#             # ppost = ppost_value+ ' ' + ppost_value #ke sath
#             ppost = ppost_value
#         elif data_case == 'rv':
#             ppost = ppost_value+ ' ' + ppost_value + ' ' + ppost_value#'kI tulanA meM'
#         elif data_case == 'r6':
#             ppost = ppost_value # 'kI' if data[4] == 'f' else 'kA'
#             nn_data = nextNounData(data[0], words_info)
#             if nn_data != False:
#                 if nn_data[4].split(':')[1] in ('k3', 'k4', 'k5', 'k7', 'k7p', 'k7t', 'mk1', 'jk1', 'rt'):
#                     ppost = ppost_value
#                 elif nn_data[3][1] != 'f' and nn_data[3][3] == 'p':
#                     ppost = ppost_value#'ke'
#                 else:
#                     pass
#         else:
#             pass
#         if data[2] == 'p':
#             temp = list(data)
#             temp[7] = ppost if ppost != '' else 0
#             data = tuple(temp)
#         if data[2] == 'n' or data[2] == 'other':
#             temp = list(data)
#             temp[8] = ppost if ppost != '' else None
#             data = tuple(temp)
#             masked_PPdata[data[0]] = ppost
#     # ##print(masked_PPdata,'mppp')
#     return masked_PPdata
import re

def is_abbreviation(word):
    """
    Returns True if word is an abbreviation marked with @ prefix.
    Example: @ke.ke. @U.P. @B.B.C.
    """
    return word.startswith('@')

def clean_abbreviation(word):
    """
    Convert WX abbreviation to display form.
    @ke.ke. → K.K.
    @U.P.   → U.P.
    Rules:
    - Remove @ prefix
    - Each letter before dot is uppercased
    - Dots are preserved
    """
    # Remove @ prefix
    word = word.lstrip('@')
    
    # Split by dot, uppercase each part, rejoin with dot
    parts = word.split('.')
    result = []
    for part in parts:
        if part:  # skip empty strings from trailing dot
            # Convert WX to Roman first, then uppercase
            roman = wx_to_english(part)
            result.append(roman.upper())
    
    return '.'.join(result) + '.'  # add trailing dot back

def clean(word, inplace=''):
    """
    Clean concept words by removing numbers and special characters.
    Keeps + as a space.
    """
    # Replace specific patterns
    word = word.replace('dZ', 'd').replace('jZ', 'j').replace('DZ', 'D')
    
    # Replace + with space
    word = word.replace('+', ' ')
    
    # Remove numbers and other special characters (but keep spaces)
    return re.sub(r'[^a-zA-Z ]+', inplace, word)

def cleans(word, inplace=''):
    """
    Clean concept words by removing numbers and special characters.
    Keeps + as a space.
    """
    # Replace specific patterns
    word = word.replace('dZ', 'd').replace('jZ', 'j').replace('DZ', 'D')
    
    # Replace + with space
    word = word.replace('+', '-')
    
    # Remove numbers and other special characters (but keep spaces)
    return re.sub(r'[^a-zA-Z ]+', inplace, word)

def process_sentence(filtered_data, sentences):
    # Check if filtered_data is not empty
    if filtered_data:
        for segment_id, text_list in filtered_data.items():
            for text in text_list:
                sentences.append({
                    "segment_id": segment_id,
                    "text": text
                })
        # Prepare output in the required format
        output = {
            "bulk": sentences
        }
    else:
        output = {
            "sentence_id": list(filtered_data.keys()),
            "text": list(filtered_data.values())
        }
    
    # Convert the dictionary to a JSON string
    json_output = json.dumps(output, ensure_ascii=False)
    
    # Process and write the JSON output to a file
    process_and_write_json(json_output, output_file="./formatted_output.txt")
    log(f'process_sentence : {json_output}')
    return json_output

def check_main_verb(depend_data):
    for dep in depend_data:
        if dep:  # Check if dep is not empty
            dep_type = dep.strip().split(':')[1]  # Extract the type after splitting
            if dep_type in ('main', 'rcelab', 'rcdelim'):  # Check for main verb types
                return True  # Return immediately if a main verb is found

    # Log the error if no main verb was identified
    log('USR error. Main verb not identified. Check the USR.')
    
    return False

def identify_tam_terms(term):
    # Extract the TAM term from the input
    if '-' in term:
        tam = term.split("-")[1]
        file_path = "repository/tam_morph_tuple.tsv"
        # Open and read the TSV file line by line
        with open(file_path, "r", encoding="utf-8") as file:
            # Read the header line to find the correct column indices
            headers = file.readline().strip().split("\t")
            
            # Identify column indices
            try:
                hindi_tam_index = headers.index("Hindi_TAM")
                english_tam_index = headers.index("English_Tam")
            except ValueError:
                return "Column names not found in the file."

            # Iterate through the file to find the matching TAM
            for line in file:
                columns = line.strip().split("\t")
                if columns[hindi_tam_index] == tam:
                    return columns[english_tam_index]  # Return corresponding English TAM

        return "TAM not found"




def generate_rulesinfo(file_data):
    global src_sentence, root_words, index_data, seman_data, gnp_data
    global depend_data, discourse_data, spkview_data, scope_data, construction_data, sentence_type
    '''
    Functionality: Extract all rows of USR, remove spaces from Running and end and break the entire row on the basis of comma and convert into list of strings.
    Exception: If length of file_data array is less than 10 raise an exception - Invalid USR. USR does not contain 10 lines.' and exit the program.
    Parameters:
        file_data - This is an array of lines read from input file.
    Returns:
        Return list of rows of USR as list of lists.
    '''

    if len(file_data) < 9:
        log('Invalid USR. USR does not contain enough lines.', 'ERROR')
        sys.exit()

    src_sentence = file_data[0]
    root_words = file_data[1].strip().split(',')
    index_data = file_data[2].strip().split(',')
    seman_data = file_data[3].strip().split(',')
    gnp_data = file_data[4].strip().split(',')
    depend_data = file_data[5].strip().split(',')
    discourse_data = file_data[6].strip().split(',')
    spkview_data = file_data[7].strip().split(',')
    scope_data = file_data[8].strip().split(',')
    construction_data = file_data[9].strip().split(',') if len(file_data) > 9 else ['-']
    sentence_type = file_data[10].strip() if len(file_data) > 10 else '%affirmative'
    # construction_data = ''
    # if len(file_data) > 10:
    #     construction_data = file_data[10].strip()

    log('Rules Info extracted succesfully fom USR.')
    # ##print('generate_rulesinfo : ',[src_sentence, root_words, index_data, seman_data, gnp_data, depend_data, discourse_data, spkview_data,
            # scope_data, sentence_type, construction_data])
    return [src_sentence, root_words, index_data, seman_data, gnp_data, depend_data, discourse_data, spkview_data,
            scope_data, construction_data,sentence_type]

# def populate_spkview_dict(
#     spkview_info, discourse_data, index_data,
#     lang, gnp_data=None, construction_data=None,
#     nouns_data=None, depend_data=None
# ):
#     from repository.constant import spkview_list_b, spkview_list_a, construction_list

#     populate_spk_dict = False
#     a, b = 'after', 'before'

#     # Load language-specific config
#     config = lang_config.get(lang, lang_config['hi'])  # default to Hindi if unknown

#     # Preprocess noun data if applicable
#     noun_indices = []
#     noun_terms = []
#     if lang == 'en' and nouns_data:
#         noun_indices = [item[0] for item in nouns_data if isinstance(item[-1], str)]
#         noun_terms = [item[1] for item in nouns_data if isinstance(item[-1], str)]

#     for i, info in enumerate(spkview_info):
#         clean_spk_info = info.rstrip('_1234567890')
#         if '/' in clean_spk_info:
#             clean_spk_info = clean_spk_info.split('/')[1]

#         # Rule: Check against spkview lists
#         if clean_spk_info in spkview_list_b or clean_spk_info in spkview_list_a or clean_spk_info == 'result':
#             populate_spk_dict = True
#             if clean_spk_info in spkview_list_a:
#                 if not discourse_data[i]:
#                     temp = (a, clean_spk_info)
#                     spkview_dict[index_data[i]] = [temp]
#             else:
#                 temp = (b, clean_spk_info)
#                 spkview_dict[index_data[i]] = [temp]

#         # Rule: Language-specific article addition (English only)
#         elif lang == 'en' and (
#             'def' not in clean_spk_info and
#             ('pl' not in gnp_data[i]) and
#             (':begin' not in construction_data[i]) and
#             (':inside' not in construction_data[i]) and
#             (':quant' not in depend_data[i])
#         ):
#             if index_data[i] in noun_indices:
#                 noun = noun_terms[noun_indices.index(index_data[i])]
#                 if noun.lower() not in construction_list:
#                     populate_spk_dict = True
#                     word = noun_terms[noun_indices.index(index_data[i])]
#                     article = 'a'
#                     if word and word[0].lower() in 'aeiou':
#                         article = 'an'
#                     temp = (b, article)
#                     spkview_dict[index_data[i]] = [temp]

#     return populate_spk_dict

# def populate_spkview_dict(spkview_info,discourse_data,index_data):
#     populate_spk_dict = False
#     a = 'after'
#     b = 'before'
#     for i, info in enumerate(spkview_info):
#         clean_spk_info = info.rstrip('_1234567890')
#         # print(discourse_data)
#         if '/' in clean_spk_info :
#             clean_spk_info = clean_spk_info.split('/')[1]
#         if clean_spk_info in repository.constant.spkview_list_b or clean_spk_info in repository.constant.spkview_list_a or clean_spk_info == 'result':
#             populate_spk_dict = True
#             if clean_spk_info in repository.constant.spkview_list_a:
#                 if not discourse_data[i]:
#                     temp = (a, clean_spk_info)
#                     spkview_dict[index_data[i]] = [temp]
#             else:
#                 temp = (b, clean_spk_info)
#                 spkview_dict[index_data[i]] = [temp]
#     return populate_spk_dict


# import importlib

# from repository.constant import spkview_list_a, spkview_list_b

# # Assume this is defined somewhere
# spkview_dict = {}

# def populate_spkview_dict(spkview_info, discourse_data, index_data, lang):
#     """
#     Populates spkview_dict with either internal tags or mapped English words,
#     based on language setting. Also loads sphere_a and speakers_b from language rules.
#     """
#     try:
#         lang_module = importlib.import_module(f'language_rules.{lang}')
#     except ImportError:
#         # Fallback to Hindi if language not found
#         lang_module = importlib.import_module('language_rules.hi')

#     # Load mappings and lists dynamically
#     spkview_to_word_map = getattr(lang_module, 'SPKVIEW_TO_WORD_MAP', {})
#     spkview_list_a = getattr(lang_module, 'speakers_a', [])
#     spkview_list_b = getattr(lang_module, 'speakers_b', [])

#     populate_spk_dict = False
#     a = 'after'
#     b = 'before'
 

#     for i, raw_tag in enumerate(spkview_info):
#         # Clean the tag
#         if '/' in raw_tag:
#             raw_tag = raw_tag.split('/')[1]

#         if lang == 'hi':
#             clean_spk_info = raw_tag.rstrip('_0123456789')  # strip number suffix
#         else:
#             clean_spk_info = raw_tag

     

#         display_value = spkview_to_word_map.get(clean_spk_info, clean_spk_info)

#         if (clean_spk_info in spkview_list_b or
#             clean_spk_info in spkview_list_a or
#             clean_spk_info == 'result'):

#             populate_spk_dict = True

#             # Use sphere_a and speakers_b in logic if needed
#             if clean_spk_info in spkview_list_a:
#                 if not discourse_data[i]:
#                     temp = (a, display_value)
#                     spkview_dict[index_data[i]] = [temp]
#             elif clean_spk_info in spkview_list_b:
#                 temp = (b, display_value)
#                 spkview_dict[index_data[i]] = [temp]

#     return populate_spk_dict
import importlib
import re

spkview_dict = {}
interrogative_dict = ""


import requests
import csv
from io import StringIO

import requests
import csv
from io import StringIO

# def handling_interrogative(processed_words, lang="en"):
#     for data in processed_words:
#         if data[1] in ["Where"]:
#             processed_words.remove(data)

# def handling_interrogative(processed_words, lang="en"):
#     if not processed_words:
#         return processed_words, "kim"  # consistent return type

#     url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBDA4xq199DZQwuwS5g5XHXNUTud_zvZ6O-kGEcPqj7yRe9bpv8k7BRb32f2hcYbB0OFWEhyJCJm9V/pub?gid=0&single=true&output=csv"
#     response = requests.get(url)
#     data_rows = list(csv.DictReader(StringIO(response.text)))

#     for data in processed_words[:]:  # iterate over a copy to safely remove
#         if "kim" in data[1]:
#             # Use split safely
#             relation = data[4].split(':')[1] if ':' in data[4] else data[4]
#             anim = data[2]

#             for row in data_rows:
#                 sheet_relation = row['relation'].strip()
#                 sheet_anim = row['anim'].strip()
#                 value = row['value'].strip()

#                 if sheet_relation != relation:
#                     continue

#                 if sheet_anim == '-':
#                     processed_words.remove(data)
#                     return processed_words, value
#                 elif sheet_anim == 'anim/per' and anim in ['anim', 'per']:
#                     processed_words.remove(data)
#                     return processed_words, value
#                 elif sheet_anim == '!anim/per' and anim not in ['anim', 'per']:
#                     processed_words.remove(data)
#                     return processed_words, value

#     return processed_words, "kim"


def populate_spkview_dict(
    rootwords,spkview_info, discourse_data, index_data, lang,
    gnp_data=None, construction_data=None, words_info=None,
    adjectives_data=None, nouns_data=None, depend_data=None,
    eka_head_index=None
):
    """
    Populates spkview_dict based on language-specific rules:
    - For Hindi: uses internal tags and predefined speaker lists.
    - For English (or others): maps to articles like 'a', 'an', 'the' based on grammar logic.
    """
    try:
        lang_module = importlib.import_module(f'language_rules.{lang}')
    except ImportError:
        lang = 'hi'
        lang_module = importlib.import_module('language_rules.hi')

    spkview_to_word_map = getattr(lang_module, 'SPKVIEW_TO_WORD_MAP', {})
    spkview_list_a = getattr(lang_module, 'speakers_a', [])
    spkview_list_b = getattr(lang_module, 'speakers_b', [])

    populate_spk_dict = False
    a = 'after'
    b = 'before'

    for i, raw_tag in enumerate(spkview_info):
        if '/' in raw_tag:
            raw_tag = raw_tag.split('/')[1]

        clean_spk_info = raw_tag.rstrip('_0123456789')
        display_key = clean_spk_info if lang == 'hi' else raw_tag
        display_value = spkview_to_word_map.get(display_key, display_key)

        index = index_data[i]
        if index in spkview_dict:
            continue  # Skip if already populated

        if lang == "hi" and (clean_spk_info in spkview_list_a or clean_spk_info in spkview_list_b or clean_spk_info == 'result'):
            populate_spk_dict = True
            if clean_spk_info in spkview_list_a and not discourse_data[i]:
                spkview_dict[index] = [(a, display_value)]
            elif clean_spk_info in spkview_list_b:
                spkview_dict[index] = [(b, display_value)]

        elif lang == "en" and clean_spk_info == 'respect':
            populate_spk_dict = True
            spkview_dict[index] = [('respect', 'respect')]

        elif lang == "en" and rootwords[i].split('_')[0] not in ["only", "indeed", "a few", "right from", "not only...but also", "only", "the", "yes", "exactly", "amount", "appproximately", "additional", "also", "even", "any", "yet", "still", "only", "nearly", "almost/approximate", "only", "modifier/intensifier", "so"]:
            if clean_spk_info in spkview_list_a or clean_spk_info in spkview_list_b or clean_spk_info == 'result':
                populate_spk_dict = True
                if clean_spk_info in spkview_list_a or clean_spk_info in spkview_list_b:
                    spkview_dict[index] = [(b, display_value)]


        if lang == 'hi':
            return populate_spk_dict

        vowels = ['a', 'e', 'i', 'o', 'u']
        skip_next = False  # define this outside the loop

        if words_info:
            for word_tuple in words_info:
                word_id = int(word_tuple[0])

                if skip_next:
                    skip_next = False
                    continue  # skip this iteration

                if word_id in spkview_dict:
                    continue  # already populated

                word = word_tuple[1]
                tags_2 = word_tuple[2]
                gnp = word_tuple[3]
                role_tags = word_tuple[4]
                # Safety check - some tuples may have fewer elements
                if len(word_tuple) <= 6:
                    continue
                definiteness = word_tuple[6]
                phrase_tags = tags_2  # corrected redundant assignment

                if 'def' in definiteness:
                    spkview_dict[word_id] = [(b, 'the')]
                    populate_spk_dict = True
                    continue

                # # Corrected syntax: .startswith() instead of `startswith`
                # if 'pl' not  in gnp and word[0].lower() in vowels:
                #     spkview_dict[word_id] = [(b, 'an')]
                #     populate_spk_dict = True
                #     continue


                    

                if eka_head_index == "" and 'pl' not in gnp and (':' in role_tags and role_tags.split(':')[1] not in ['k7t','quant','main']) and ':' in role_tags and role_tags.split(':')[1] in ['mod']:
                    if word[0].lower() in vowels:
                        article = 'an' 
                        spkview_dict[word_id] = [(b, article)]
                        populate_spk_dict = True
                        continue


#             if "card" in role_tags:
#                 skip_next = True  # <-- this skips the next iteration
#                 continue

#             if adjectives_data and word_tuple in adjectives_data:
#                 if (
                  
#                     not any(tag in gnp for tag in ['pl', 'comparmore','comparless','superl'])  and 
#                     not any(tag in role_tags for tag in ['quantless', 'quantmore'])  and 
#                     'mod' in role_tags and
#                     'def' not in definiteness and
#                     not any(tag in tags_2 for tag in ['dom', 'yoc', 'moy', 'numex']) and
#                     'per' not in phrase_tags and 'ne' not in phrase_tags and

#                     not any(tag in role_tags for tag in ['quant', 'rt','card']) and
#                     not re.match(r'^\[ne_\d+\]$', word)
#                 ):
#                     article = 'an' if word[0].lower() in vowels else 'a'
#                     spkview_dict[word_id] = [(b, article)]
#                     populate_spk_dict = True
#                     continue

#             if nouns_data and word_tuple in nouns_data:
#                 if (
#                      not any(tag in gnp for tag in ['pl', 'comparmore','comparless','superl'])  and 
#                     'def' not in definiteness and
#                     not any(tag in role_tags for tag in ['quantless', 'quantmore', 'mod']) and
#                     not any(tag in tags_2 for tag in ['dom', 'yoc', 'moy', 'numex', 'season']) and
#                     'per' not in phrase_tags and 'ne' not in phrase_tags
#  and
#                     not any(tag in role_tags for tag in ['quant', 'rt','card']) and
#                     not re.match(r'^\[ne_\d+\]$', word)
#                 ):
#                     article = 'an' if word[0].lower() in vowels else 'a'
#                     spkview_dict[word_id] = [(b, article)]
#                     populate_spk_dict = True

    return populate_spk_dict



# import importlib
# import re

# import importlib
# import re

# def populate_spkview_dict(spkview_info, discourse_data, index_data, gnp_data, construction_data,
#                           words_info, categorized_words_list, nouns_data, depend_data,
#                           eka_head_index, lang):
#     """
#     Populates spkview_dict with either internal tags or mapped English words,
#     based on language setting. Also loads speakers_a and speakers_b from language rules.
#     """

#     try:
#         lang_module = importlib.import_module(f'language_rules.{lang}')
#     except ImportError:
#         # Fallback to Hindi if language not found
#         lang_module = importlib.import_module('language_rules.hi')

#     # Load mappings and lists dynamically
#     spkview_to_word_map = getattr(lang_module, 'SPKVIEW_TO_WORD_MAP', {})
#     spkview_list_a = getattr(lang_module, 'speakers_a', [])
#     spkview_list_b = getattr(lang_module, 'speakers_b', [])

    
#     populate_spk_dict = False
#     a = 'after'
#     b = 'before'
#     vowels = ['a', 'e', 'i', 'o', 'u']
#     for data in words_info:
#     # Step 1: Handle 'def' cases and EKA logic
    
#         if 'def' in data[6]:
#             spkview_dict[data[1]] = [(b, 'the')]
#             print('=========>', spkview_dict)
#             populate_spk_dict = True
#             continue

#         # Handle EKA head case (e.g., indefinite 'a')
#         if eka_head_index and data[1] == int(eka_head_index[1]):
#             if 'pl' not in data[3] and eka_head_index[0]:
#                     if str(data[0]) == str(eka_head_index[0]):
#                         spkview_dict[int(eka_head_index[0])] = [(b, 'a')]
#                         print('=========>', spkview_dict)
#                         populate_spk_dict = True
#                         break

#     # If article already set via 'def' or eka, skip the rest
#     if populate_spk_dict:
#         return populate_spk_dict

#     # Step 2: Check categorized_words_list and nouns_data (only first match)
#     combined_list = categorized_words_list + nouns_data

#     for word_tuple in combined_list:
#         word = word_tuple[1]
#         if not word:
#             continue

#         word_starts_with_vowel = word[0].lower() in vowels
#         article = 'an' if word_starts_with_vowel else 'a'

#         # Check if this is a categorized word
#         if word_tuple in categorized_words_list:
#             is_not_plural = 'pl' not in word_tuple[3]
#             is_modifier = 'mod' in word_tuple[4]

#             if is_not_plural and is_modifier:
#                 spkview_dict[int(word_tuple[0])] = [(b, article)]
#                 print('=========>', spkview_dict)
#                 populate_spk_dict = True
#                 break

#         # Check if this is a valid noun
#         if word_tuple in nouns_data:
#             if ('pl' not in word_tuple[3]
#                 and 'dom' not in word_tuple[2]
#                 and 'yoc' not in word_tuple[2]
#                 and 'moy' not in word_tuple[2]
#                 and 'numex' not in word_tuple[2]
#                 and ':begin' not in word_tuple[8]
#                 and 'quant' not in word_tuple[4]
#                 and 'rt' not in word_tuple[4]
#                 and not re.match(r'^\[ne_\d+\]$', word)):
#                 spkview_dict[int(word_tuple[0])] = [(b, article)]
#                 print('=========>', spkview_dict)
#                 populate_spk_dict = True
#                 break

#     return populate_spk_dict





def is_kriyAmUla_head(data_list, dep_head):
    # '''<segment_id=Geo_nios_2ch_0019b>
    #     #और आप उपयुक्त उदाहरणों द्वारा उसके प्रकारों का वर्णन कर सकेंगे।
    #     $addressee	4	anim	pl	9:k1	-	respect	-	-
    #     upayukwa_2	5	-	-	6:mod	-	-	-	-
    #     uxAharaNa_1	6	-	-	9:k3	-	-	-	-
    #     $wyax	7	-	-	8:r6	Geo_nios_2ch_0019a.5:coref	proximal	-	-
    #     prakAra_7	8	-	pl	9:k2	-	-	-	-
    #     varNana_1	10	-	-	-	-	-	-	9:kriyAmUla
    #     kara_1-0_sakegA_1	11	-	-	-	-	-	-	9:verbalizer
    #     [cp_1]	9	-	-	0:main	Geo_nios_2ch_0019a.7:samuccaya	-	-	-
    #     %affirmative
    #     </segment_id>
    # '''
    if data_list is None:
        return False
    for i,item in enumerate(data_list):
        if "kriyAmUla" in item and clean(root_words[i]) in repository.constant.kriyAmUla:
            head = item.split(":")[0]  # Extract the number before ':'
            return True and head == dep_head  # Check if it matches dep_head
    return False  # Return False if kriyAmUla is not found


# # Global dictionary assumed to be defined elsewhere
processed_postpositions_dict = {}
data_case_for_k4 = []  # Assuming this is used in other parts of code


# Import generated rule-based postposition function
from generated_conditions import get_ppost


def preprocess_postposition_new(concept_type, np_data, words_info, verb_data, index_data, lang):
    '''Calculates postposition to words wherever applicable according to rules.'''

    # Initialize common variables
    data_index = None
    data_head = None
    data_case = ''
    root_main = None
    data_seman = None
    ppost = ''
    new_case = 'o'

    # Only extract verb info if verb_data is available
    if len(verb_data) > 0:
        verb_term = verb_data[1]
        if len(verb_term) > 0:
            root_main = verb_term.strip().split('-')[0].split('_')[0]
    if  '[' not in np_data[1] and ']' not in np_data[1]:


        # Extract case information from np_data
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

             
        
            

            # Optional: collect case for k4 (depends on outer scope)
            data_case_for_k4.append(np_data[4])

    # Language-specific logic
    if lang == 'hi':
        return _hindi_preprocess_postposition(
            concept_type, np_data, words_info, verb_data, index_data,
            data_case, data_head, data_seman, data_index, root_main
        )
    elif lang == 'en':
        ppost = get_ppost(
            data_case,
            data_head,
            data_seman=data_seman,
            root_main=root_main,
            concept_type=concept_type
        )
        SELF_PREPOSITION_WORDS = {
        'after', 'before', 'since', 'until', 'during', 'from',
        'bAxa', 'pahale', 'Age', 'pICe', 'xUra'
        }
        concept_root = np_data[1].split('_')[0].lower() if np_data[1] else ''
        if concept_root in SELF_PREPOSITION_WORDS:
            ppost = ''
            print(f"[DEBUG] Cleared ppost for self-preposition word: {concept_root}")
        # ← ADD THIS - location pronouns need no preposition
        LOCATION_PRONOUNS = {'here', 'there', 'where', 'somewhere', 'everywhere'}
        if (concept_type == 'pronoun' and 
            data_case in ('k7p', 'k7', 'k5') and
            np_data[1] in LOCATION_PRONOUNS):  # check original word
            ppost = None
            if data_index is not None:
                processed_postpositions_dict[data_index] = None
            return new_case, None
    # ← END ADD
        # rkl relation: preposition is embedded in the concept word itself (bAxa=after, pahale=before)
        # So do not add any additional preposition
        if data_case == 'rkl':
            ppost = ''
            
        # if len(np_data) > 8 and np_data[8] and "component" in np_data[8]:
        #     if np_data[2] == "dom":   
        #         ppost = "on"   
        #     elif np_data[2] == "moy":  
        #         ppost = "in"    
        #     elif np_data[2] == "yoc":
        #           ppost = "in"  
        #     elif "clocktime" in np_data[2]:  
        #         ppost= "at"     
        #     elif  np_data[2] == "dow":
        #         ppost = "on"
        #     elif np_data[2] == "season":
        #         ppost = "in"
                

        if concept_type == 'noun' and np_data[1].strip('[]').split('_')[0] not in repository.constant.construction_list:
            ppost = None if ppost == '' else ppost
        elif concept_type == 'pronoun':
            ppost = 0 if ppost == '' else ppost
        else:
            ppost=None
#if r6 with verb
        if data_index is not None:
            if int(data_head) == verb_data[0] and data_case == "rt":
                ppost = 'to'
            
            if  data_case == "r6":
                ppost = ppost

            processed_postpositions_dict[data_index] = ppost

        return new_case, ppost

    else:
        # Default fallback: no postposition
        return new_case, None


# ———————— HINDI-SPECIFIC LOGIC BELOW ————————
def _hindi_preprocess_postposition(
    concept_type, np_data, words_info, verb_data, index_data,
    data_case, data_head, data_seman, data_index, root_main
):
    """Internal function containing the original Hindi-specific logic."""
    cp_verb_list = ['prayApreprsa+kara', 'sahAyawA+kara']
    ppost = ''
    new_case = 'o'

    # Your full Hindi logic goes here, adapted slightly for clarity
    if data_case in ('k1', 'pk1'):
        if is_tam_ya(verb_data, data_head):  # has TAM "yA" or "yA_hE" or "yA_WA"
            k2exists, k2_index = find_match_with_same_head(data_head, 'k2', words_info, index=4)
            if k2exists:
                ppost = 'ne'
            else:
                ppost = ''
                print('Karma k2 not found. Output may be incorrect')
        elif identify_complete_tam_for_verb(verb_data[1]) in repository.constant.nA_list:
            ppost = 'ko'
        else:
            print('inside tam ya else')

    elif data_case == 'mod' and data_seman == 'season':
        ppost = 'kA'
        nn_data = nextNounData(data_head, words_info)
        if nn_data != False:
            if nn_data[4].split(':')[1] in ('k3', 'k4', 'k5', 'k7', 'k7p', 'k7t', 'r6', 'mk1', 'jk1', 'rt'):
                ppost = 'ke'
                if nn_data[3] == 's':  # agreement with gnp
                    ppost = 'kI' if nn_data[3] == 'f' else 'kA'
        # ... rest of Hindi cases go here ...

    elif data_case == 'k2g':
        ppost = process_dep_k2g(data_case, verb_data)
    elif data_case == 'k2':
        if data_seman and data_seman.split()[0] in ("anim", "per"):
            check_k4 = data_head + ':k4'
            if root_main in repository.constant.reciprocal_verbs:
                ppost = 'se'
            elif check_k4 not in data_case_for_k4:
                ppost = 'ko'
        elif is_kriyAmUla_head(None, data_head):
            ppost = 'kA'
        else:
            new_case = 'd'

    elif data_case == 'k7t' and np_data[1] not in ['kala', 'subaha', 'Aja', 'aBI', 'pahale']:
        ppost = 'ko'
    elif data_case == 'k7t' and np_data[2] == 'timex':
        ppost = 'para'
    elif data_case in ('k2p','k7','k7p','k7t'):
        ppost = '<>'
    elif data_case in ('k3', 'k5', 'k5prk'):
        ppost = 'se'
    elif data_case in ('k4', 'k4a', 'jk1'):
        ppost = 'ko'
    elif data_case == 'k7':
        ppost = 'meM'
    elif data_case == 'k7p':
        ppost = 'para'
    elif data_case == 'k7a':
        ppost = 'ke anusAra'
    elif data_case == 'krvn' and data_seman == 'abs':
        ppost = 'se'
    elif data_case == 'rt':
        ppost = 'ke liye'
    elif data_case == 'rblak':
        ppost = 'ke bAxa'
    elif data_case == 'rblsk':
        ppost = 'we samaya'
    elif data_case == 'rblpk':
        ppost = 'se pahale'
    elif data_case in ('rsm', 'rsma'):
        ppost = 'ke pAsa'
    elif data_case == 'rhh':
        ppost = 'ke'
    elif data_case == 'rsk':
        ppost = 'hue'
    elif data_case == 'rn':
        ppost = 'meM_se'
    elif data_case == 'rib':
        ppost = 'se'
    elif data_case == 'rasneg':
        ppost = 'ke binA'
    elif data_case == 'ru':
        ppost = 'jEsI'
    elif data_case == 'rkl':
        ind_in_index_data = index_data.index(data_index) if data_index in index_data else -1
        next_word = fetchNextWord(ind_in_index_data + 1, index_data, words_info)
        if next_word == 'bAxa':
            ppost = 'ke'
        elif next_word == 'pahale':
            ppost = 'se'
    elif data_case == 'rdl':
        ind_in_index_data = index_data.index(data_index) if data_index in index_data else -1
        next_word = fetchNextWord(ind_in_index_data + 1, index_data, words_info)
        if next_word in ('anxara', 'bAhar', 'Age', 'sAmane', 'pICe', 'Upara', 'nIce', 'xAyeM',
                         'bIca', 'pAsa', 'uparI'):
            ppost = 'ke'
        elif next_word == 'xUra':
            ppost = 'se'
    elif data_case == 'rv':
        ppost = 'se'
    elif data_case == 'mk1':
        ppost = 'se'
    elif data_case == 'rh':
        ppost = 'ke_kAraNa'
    elif data_case == 'rd':
        ppost = 'kI ora'
    elif data_case == 'rp':
        ppost = 'se hokara'
    elif data_case in ('rask1','rask2','rask3','rask4','rask5','k1as','k2as','k3as','k4as','k5as','k7as'):
        ppost = 'ke sAWa'
    elif data_case == 'r6':
        ppost = 'kA'
    elif data_case == 'quantless':
        ppost = 'se kama'
    elif data_case == 'quantmore':
        ppost = 'se aXika'
    else:
        pass

    if ppost == '':
        new_case = 'd'

    if concept_type == 'noun':
        ppost = None if ppost == '' else ppost
    elif concept_type == 'pronoun':
        ppost = 0 if ppost == '' else ppost

    if data_index is not None:
        processed_postpositions_dict[data_index] = ppost

    return new_case, ppost

def generate_wordinfo(root_words, index_data, seman_data, gnp_data, depend_data, discourse_data, spkview_data,
                      scope_data,construction_data):
    '''
    Functionality:
        1. To check USR format
        2. Combine each concept with its corresponding information at the same index in all rows in tuples. Group all these tuples as word_info list.

    Parameters:
        1. root_words - second row of USR. Contains all concepts/ root words
        2. index_data - third row of USR. Contains indexing of concepts from 1, 2, 3 and onwards
        3. seman_data - fourth row of USR. Contains semantic information about all concepts
        4. gnp_data - fifth row of USR. Contains number information of the concept
        5. depend_data - sixth row of USR. Contains dependency information of the concept
        6. discourse_data - seventh row of USR. Contains discourse information of the concept
        7. spkview_data - eighth row of USR. Contains speaker's view information of the concept
        8. scope_data - ninth row of USR. Contains scope information of the concept

    Returns:
        Generates an array of tuples containing word and its USR info i.e USR info word wise.
        '''
    result = list(
        zip(index_data, root_words, seman_data, gnp_data, depend_data, discourse_data, spkview_data, scope_data, construction_data))
    # Ensure all tuples have exactly 9 elements
    padded = []
    for t in result:
        if len(t) < 9:
            t = t + ('-',) * (9 - len(t))
        padded.append(t)
    return padded
    # return check_USR_format(root_words, index_data, seman_data, gnp_data, depend_data, discourse_data, spkview_data, scope_data)

def check_USR_format(root_words, index_data, seman_data, gnp_data, depend_data, discourse_data, spkview_data,
                      scope_data):
    '''
    Functionality:
    1. To check if root words and their indices are in order
    2. To ensure that all the tuples of the USR have same number of enteries

    Returns:
        Corrected USR as an array of tuples containing word and its USR info (corresponding value on same index in each row) i.e USR info word wise.
    '''
    data = [root_words, index_data, seman_data, gnp_data, depend_data, discourse_data, spkview_data, scope_data]
    len_root = len(root_words)
    len_index = len(index_data)

    if len_root > len_index:
        diff = len_root - len_index
        while diff:
            index_data.append(0)
            diff = diff - 1
            log(f'{repository.constant.USR_row_info[1]} has lesser enteries as compared to {repository.constant.USR_row_info[0]}')

    elif len_root < len_index:
        diff = len_index - len_root
        while diff:
            index_data.pop()
            diff = diff - 1
            log(f'{repository.constant.USR_row_info[1]} has more enteries as compared to {repository.constant.USR_row_info[0]}')

    #once the lengths of root_words and index_data are equal check value of each index
    len_root = len(root_words)
    len_index = len(index_data)
    if len_root == len_index:
        for i in range(1, len_root + 1):
            if index_data[i - 1] == i:
                continue
            else:
                index_data[i - 1] = i
                log(f'{repository.constant.USR_row_info[1]} has wrong entry at position {i}')

    #Checking all tuples have same number of enteries
    max_col = max(index_data)
    i = 0
    for ele in data:
        length = len(ele)
        if length < max_col:
            diff = max_col - length
            while diff:
                ele.append('')
                log(f'Added one entry at the end of {repository.constant.USR_row_info[i]}')
                diff = diff - 1
        elif length > max_col:
            diff = length - max_col
            while diff:
                ele.pop()
                log(f'Removed one entry from the end of {repository.constant.USR_row_info[i]}')
                diff = diff - 1
        i = i + 1

    #Removing spaces if any,before/ after each ele for all rows in USR
    for row in data:
        for i in range(0, len(row)):
            if type(row[i]) != int and row[i] != '':
                temp = row[i].strip()
                row[i] = temp

    return list(
        zip(index_data, root_words, seman_data, gnp_data, depend_data, discourse_data, spkview_data, scope_data))

            

# def translate_to_hindi(text):
#     translator = Translator()
#     translated = translator.translate(text, src='en', dest='hi')
#     return translated.text

def convert_to_hindi(word):
    # wx = WXC(order='wx2utf', lang='hin')
    wx1 = WXC(order='utf2wx', lang='hin')
    hindi_text_list = wx1.convert(word)
    return hindi_text_list

def new_to_old_convert_construction_conj_dis(index_data, construction_data, conj_concept):
    result = {}

    for i, concept in enumerate(conj_concept):

        if 'conj' in concept or 'disjunct' in concept :  # Check if the concept contains 'conj'
            ind = index_data[i]
            op_indices = []

            for j, text in enumerate(construction_data):
                if text and 'op' in text:
                    txt_index = int(text.split(':')[0])
                    if txt_index == ind:
                        op_indices.append((index_data[j], text.split(':')[1]))  # Store as a tuple (index in construction_data, opX)

            if op_indices:
                result[ind] = op_indices

    return result

# def new_to_old_convert_construction_conj_dis(index_data,construction_data,conj_concept):
#     # op_index=[]
#     op_sub_ind=[]
#     construction_data1=''
#     print(index_data,construction_data,conj_concept,'ll')
#     for i, concept in enumerate(conj_concept):
        
#         if 'conj' in concept :
#             ind=index_data[i]
#             for j, text in enumerate(construction_data):
#                 # if text!='':
#                 txt=text.split(':')[0]
#                 if 'op' in text and ind==int(txt):
#                         op_sub_ind.append(str(index_data[j]))
                        
#             # op_index.append(str(op_sub_ind))

#             # for j,value in enumerate(op_index):
#             #     if j==0:
#             #         construction_data1='*conj:'+ value.replace(' ','')
#             #     else:
#             #         construction_data1=' conj:'+ value.replace(' ','')
#         elif 'disjunct' in concept :
#             ind=index_data[i]
#             for j, text in enumerate(construction_data):
#                 # if text!='':
#                 txt=text.split(':')[0]
#                 if 'op' in text and ind==int(txt):
#                         op_sub_ind.append(str(index_data[j]))
                        
#             # op_index.append(str(op_sub_ind))

#             # for j,value in enumerate(op_index):
#             #     if j==0:
#             #         construction_data1='*disjunct:'+ value.replace(' ','')
#             #     else:
#             #         construction_data1=' disjunct:'+ value.replace(' ','')
#     return op_sub_ind

def process_dep_k2g(data_case, main_verb):
    verb = identify_main_verb(main_verb[1])
    if verb in repository.constant.kisase_k2g_verbs:
        ppost = 'se'
    else:
        ppost = 'ko'
    return ppost

def get_all_form(morph_forms):
    """
    >>> get_first_form("^mAz/mA<cat:n><case:d><gen:f><num:p>/mAz<cat:n><case:d><gen:f><num:s>/mAz<cat:n><case:o><gen:f><num:s>$")
    'mA<cat:n><case:d><gen:f><num:p>/mAz<cat:n><case:d><gen:f><num:s>/mAz<cat:n><case:o><gen:f><num:s>'
    """
    morph=morph_forms.split("$")[1]
    return morph

def get_first_form(morph_forms):
    """
    >>> get_first_form("^mAz/mA<cat:n><case:d><gen:f><num:p>/mAz<cat:n><case:d><gen:f><num:s>/mAz<cat:n><case:o><gen:f><num:s>$")
    'mA<cat:n><case:d><gen:f><num:p>'
    """
    morph=morph_forms.split("/")[1]
    return morph

def get_default_GNP():
    gender, number, person, case = 'n', 's', 'a', 'o'   # neutral instead of masculine
    return gender, number, person, case
# def get_default_GNP():
#     gender,number,person,case = 'm','s','a','o'
    
#     return gender, number, person, case

def get_gnpcase_from_concept(concept):  # computes GNP values

    if concept[2] == 'v':
        gender = concept[3]
        number = concept[4]
        person = concept[5]
        case = concept[7]

    elif concept[2] == 'vn':
        gender = concept[4]
        number = concept[5]
        person = concept[6]
        case = concept[3]

    elif concept[2] == 'p':   # ✅ PRONOUN FIX
        gender = concept[4]
        number = concept[5]
        person = concept[6]
        case = concept[3]

        # 🔥 Force neutral for demonstratives (wyax → it)
        if concept[1] in ['wyax', 'yah', 'vah', 'यह', 'वह']:
            gender = 'n'

    elif concept[2] == 'n':
        gender = concept[4]
        number = concept[5]
        person = concept[6]
        case = concept[3]

    else:
        return get_default_GNP()

    # ✅ Only fix missing values (DO NOT overwrite valid ones)
    if gender in ['-', None, 'null']:
        gender = 'n'

    if number in ['-', None, 'null']:
        number = 's'

    if person in ['-', None, 'null']:
        person = 'a'

    if case in ['-', None, 'null']:
        case = 'o'

    return gender, number, person, case

# def get_TAM(term, tam):
#     """
#     >>> get_TAM('hE', 'pres')
#     'hE'
#     >>> get_TAM('hE', 'past')
#     'WA'
#     >>> get_TAM('asdf', 'gA')
#     'gA'
#     """
#     if term == 'hE' and tam in ('pres', 'past'):
#         alt_tam = {'pres': 'hE', 'past': 'WA'}
#         return alt_tam[tam]
#     else:
#         if term == 'jA':
#             tam = 'yA1'
#             return tam
#     return tam

# def get_main_verb(term):
#     ''' return main verb from a term'''

#     pass

def getDataByIndex(value: int, searchList: list, index=0):
    '''search and return data by index in an array of tuples.
        Index should be first element of tuples.
        Return False when index not found.'''
    try:
        res = False
        for dataele in searchList:
            # dataele=list(dataele)
            # if (dataele[(index)]) == value and dataele[7]=='vn':
            #     dataele[3]='d'
            #     res = tuple(dataele)
            if (dataele[(index)]) == value:
                # res = tuple(dataele)
                res = dataele
                break
        return res
    except IndexError:
        log(f'Index out of range while searching index:{value} in {searchList}', 'WARNING')
        return False
    

# def getComplexPredicateGNP(term):
#     CP_term = clean(term.split('+')[0])
#     gender = 'm'
#     number = 's'
#     person = 'a'

#     tags = find_tags_from_dix(CP_term)  # getting tags from morph analyzer to assign gender and number for agreement
#     if '*' not in tags['form']:
#         gender = tags['gen']
#         number = tags['num']
#     return gender, number, person

def getGNP_using_k2(k2exists, searchList):
    casedata = getDataByIndex(k2exists, searchList)
    if (casedata == False):
        log('Something went wrong. Cannot determine GNP for verb.', 'ERROR')
        sys.exit()
    verb_gender, verb_number, verb_person = casedata[4], casedata[5], casedata[6]
    return verb_gender, verb_number, verb_person[0]
        
def getGNP_using_k1(k1exists, searchList):
    # for k1 in k1exists:
    casedata = getDataByIndex(k1exists, searchList)
    if (casedata == False):
        log('Something went wrong. Cannot determine GNP for verb k1 is missing.', 'ERROR')
        sys.exit()
    verb_gender, verb_number, verb_person = casedata[4], casedata[5], casedata[6]
    return verb_gender, verb_number, verb_person

def getVerbGNP_new(concept_term, full_tam,index, seman_data, depend_data, sentence_type, processed_nouns, processed_pronouns,index_data,k1_not_need):
    '''
    '''
    #for imperative sentences
    if sentence_type in ('Imperative','imperative') or 'o' in full_tam:
        verb_gender = 'm'
        verb_number = 's'
        verb_person = 'm'
        return verb_gender, verb_number, verb_person

    #for non-imperative sentences
    # For non-imperative sentences
    k1exists = False
    k2exists = False
    k1_case = ''
    k2_case = ''
    verb_gender, verb_number, verb_person, case = get_default_GNP()
    # if process_nominal_form:
    #     searchList = processed_nouns + processed_pronouns 
    # else:
    searchList = processed_nouns + processed_pronouns

    for dep in depend_data:
        # head_index=dep.split(':')[0]
        
        if dep == '':
            continue
        else:
            dep_val=dep.split(':')[1]
        # elif (case=='k1' or case=='pk1') and head_index==str(index):
        if (dep_val=='k1' or dep_val=='pk1'):
            k1exists_index = depend_data.index(dep)
            k1exists = index_data[k1exists_index]
            
        # elif dep[-2:]=='k2' and head_index==index:
        elif dep[-2:]=='k2':
            k2exists_index = depend_data.index(dep)
            k2exists = index_data[k2exists_index]

    if k1exists:
        casedata = getDataByIndex(k1exists, searchList)
        if (casedata == False):
            log('Something went wrong. Cannot determine case for k1.', 'ERROR')
        else:
            k1_case = casedata[3]
   
    if k2exists:
        casedata = getDataByIndex(k2exists, searchList)
        if (casedata == False):
            
            log('Something went wrong. Cannot determine case for k2.', 'ERROR')
        else:
            k2_case = casedata[3]
    
#     if is_cp:
#         cp_term = concept_term.split('+')[0]
#         if not k1exists and not k2exists:
#             verb_gender, verb_number, verb_person = getComplexPredicateGNP(cp_term)
#         elif k1exists and k1_case == 'd':
#             verb_gender, verb_number, verb_person = getGNP_using_k1(k1exists, searchList)
#         elif k1exists and k1_case == 'o' and k2exists and k2_case == 'o':
#             verb_gender, verb_number, verb_person = getComplexPredicateGNP(cp_term)
#         return verb_gender, verb_number, verb_person[0]

    if 'yA' in full_tam:
        if k1exists and k1_case == 'd':
            verb_gender, verb_number, verb_person = getGNP_using_k1(k1exists, searchList)
        elif k1exists and k1_case == 'o' and k2exists and k2_case == 'd':
            verb_gender, verb_number, verb_person = getGNP_using_k2(k2exists, searchList)
        return verb_gender, verb_number, verb_person[0]

    if full_tam in repository.constant.nA_list:
        return verb_gender, verb_number, verb_person[0]

    #tam - gA
    elif k1exists:
        verb_gender, verb_number, verb_person = getGNP_using_k1(k1exists, searchList)
        return verb_gender, verb_number, verb_person[0]
    else:
        return verb_gender, verb_number, verb_person[0]

def is_tam_ya(verbs_data,data_head):
    ya_tam = '-yA_'
    if len(verbs_data) > 0 and verbs_data != ():
        if verbs_data[0]==int(data_head):
            term = verbs_data[1]
            if ya_tam in term:
                return True
    return False

def is_kim(term):
    if term == 'kim':
        return True

    return False
def is_yax(term):
    if term == 'yax':
        return True

    return False

# def is_complex_predicate(concept):
#     return "+" in concept

# def is_CP(term):
#     """
#     >>> is_CP('varRA+ho_1-gA_1')
#     True
#     >>> is_CP("kara_1-wA_hE_1")
#     False
#     """
#     if "+" in term:
#         return True
#     else:
#         return False

def is_update_index_NC(i, processed_words):
    for data in processed_words:
        temp = tuple(data)
        if len(temp) > 7 and float(i) == temp[0] and temp[7] == 'NC':
            return True
    return False

def is_nonfinite_verb(concept):
    return concept.type == 'nonfinite'

def has_tam_ya():
    '''Check if USR has verb with TAM "yA".
        It sets the global variable HAS_TAM to true
    '''
    global HAS_TAM
    if HAS_TAM == True:
        return True
    else:
        return False

def has_GNP(gnp_info):
    if len(gnp_info) and ('sg', 'pl') in gnp_info:
        return True
    return False

def has_ques_mark(POST_PROCESS_OUTPUT,sentence_type):
    # interrogative_lst = ["yn_interrogative", "yn_interrogative_negative", "pass-yn_interrogative", "interrogative",
    #                      "Interrogative", "pass-interrogative"]
    if sentence_type in ("yn_interrogative", "yn_interrogative_negative", "pass-yn_interrogative", "interrogative",
                        "Interrogative", "pass-interrogative"):
        return POST_PROCESS_OUTPUT + ' ?'
    elif sentence_type in ('pass_affirmative','affirmative', 'Affirmative', 'negative', 'Negative', 'imperative', 'Imperative',"fragment","term","title","heading"):
        return POST_PROCESS_OUTPUT + ' .'
    else:
        return POST_PROCESS_OUTPUT

# def identify_case(verb, dependency_data, processed_nouns, processed_pronouns,index_data):
#     return getVerbGNP_new(verb.term, verb.tam, dependency_data, processed_nouns, processed_pronouns,index_data)

def identify_main_verb(concept_term):
    """
    >>> identify_main_verb("kara_1-wA_hE_1")
    'kara'
    >>> identify_main_verb("varRA+ho_1-gA_1")
    'ho'
    """
    if ("+" in concept_term):
        
        concept_term = concept_term.split("+")[1]
    con=clean(concept_term.split("-")[0])
    # ##print(con,'main verb')
    return con

def identify_default_tam_for_main_verb(concept_term):
    """
    >>> identify_default_tam_for_main_verb("kara_1-wA_hE_1")
    'wA'
    >>> identify_default_tam_for_main_verb("kara_1-0_rahA_hE_1")
    '0'
    """
    # con=concept_term.split("-")[1].split("_")[0]
    if '-' in concept_term:
        con=concept_term.split("-")[1]
        if '_' in con:
            con=con.split("_")[0]
            return con
        else:
            return con
    else:
        return concept_term
    return con

def identify_complete_tam_for_verb(concept_term):
    """
    >>> identify_complete_tam_for_verb("kara_1-wA_hE_1")
    'wA_hE'
    >>> identify_complete_tam_for_verb("kara_1-0_rahA_hE_1")
    'rahA_hE'
    >>> identify_complete_tam_for_verb("kara_1-nA_howA_hE_1")
    'nA_howA_hE'
    >>> identify_complete_tam_for_verb("kara_o")
    'o'
    """
    if 'cAha_1-e_1' in concept_term:
        return 'cAhiye'
    elif "-" not in concept_term:
        return concept_term.split("_")[1]
    tmp = concept_term.split("-")[1]
    tokens = tmp.split("_")
    non_digits = filter(lambda x: not x.isdigit(), tokens)
    tam_v="_".join(non_digits)

    return tam_v

def identify_auxiliary_verb_terms(term):
    """
    >>> identify_auxiliary_verb_terms("kara_1-wA_hE_1")
    ['hE']
    >>> identify_auxiliary_verb_terms("kara_1-0_rahA_hE_1")
    ['rahA', 'hE']
    """
    # ##print(term,'ee')
    aux_verb_terms = term.split("-")[1].split("_")[1:]
    # ##print(aux_verb_terms,'ee')
    cleaned_terms = map(clean, aux_verb_terms)
    # ##print(cleaned_terms,'clt')
    aux_list=list(filter(lambda x: x != '', cleaned_terms))
    # ##print(el)
    return aux_list            # Remove empty strings after cleaning

def identify_verb_type(verb_concept):
    '''
    >>identify_verb_type([])
    '''
    #dep_rel = verb_concept[4].strip().split(':')[1] #if using with non-OO program
    dependency = verb_concept.dependency
    dep_rel=''
    if dependency!='-':
        dep_rel = dependency.strip().split(':')[1]
    v_type = ''
    if dep_rel == 'main':
        v_type = "main"
    # elif dep_rel in ('rpk', 'rbk', 'rvks', 'rbks', 'rsk', 'rblpk','rblak','rblsk'):
    #     v_type = "nonfinite"
    elif dep_rel in ('rpk', 'rsk','rbk','rblsk','rblak','rblpk','rvks','rbks'):
        v_type = "nonfinite"
    # elif dep_rel in ('rvks'):
    #     v_type = "verbal adjective"
    # elif dep_rel in ('rblpk','rblak','rblsk'):
    #     v_type = "nominal_verb"
    else:
        v_type = "main"
    return v_type

def find_tags_from_dix(word):
    """
    >>> find_tags_from_dix("mAz")
    {'cat': 'n', 'case': 'd', 'gen': 'f', 'num': 'p', 'form': 'mA'}
    """
    dix_command = "echo {} | apertium-destxt | lt-proc -ac repository/hi.morfLC.bin | apertium-retxt".format(word)
    morph_forms = os.popen(dix_command).read()
    # ##print(morph_forms,'dixxxxxxxx')
    p_m=parse_morph_tags(morph_forms)
    return p_m

# def find_tags_from_dix_as_list(word):
#     """
#     >>> find_tags_from_dix("mAz")
#     {'cat': 'n', 'case': 'd', 'gen': 'f', 'num': 'p', 'form': 'mA'}
#     """
#     dix_command = "echo {} | apertium-destxt | lt-proc -ac repository/hi.morfLC.bin | apertium-retxt".format(word)
#     morph_forms = os.popen(dix_command).read()
#     p_m=parse_morph_tags_as_list(morph_forms)
#     # ##print(p_m,'pmmmmmmmmm')
#     return p_m
import os

def find_tags_from_dix_as_list(word, lang='en'):
    """
    Extract morphological tags from the given word using Apertium's lt-proc.

    Args:
        word (str): The word to analyze.
        lang (str): Language code ('hi', 'en', etc.)

    Returns:
        list: A list of morphological tag dictionaries for the word.

    Example:
        >>> find_tags_from_dix_as_list("mAz", lang='hi')
        [{'cat': 'n', 'case': 'd', 'gen': 'f', 'num': 'p', 'form': 'mA'}]
    """
    # Define language-specific binary paths
    dix_binaries = {
        'hi': 'repository/hi.morfLC.bin',
        'en': '/home/lc4eu/multilingual_rule_based_updated/apertium_eng/eng.automorf.bin',
        # Add more languages here as needed
    }

    dix_bin_path = dix_binaries.get(lang)
    if not dix_bin_path:
        log(f"No morphological analyzer binary defined for language: {lang}", 'ERROR')
        return []

    # Construct and run the Apertium pipeline
    dix_command = f"echo {word} | apertium-destxt | lt-proc -ac {dix_bin_path} | apertium-retxt"
    morph_forms = os.popen(dix_command).read()
    
    return parse_morph_tags_as_list(morph_forms)


def find_exact_dep_info_exists(index, dep_rel, words_info):
    for word in words_info:
        dep = word[4]
        dep_head = word[4].strip().split(':')[0]
        dep_val = word[4].strip().split(':')[1]
        if dep_val == dep_rel and int(dep_head) == index:
            return True

    return False

def find_match_with_same_head(data_head, term, words_info, index):
    #  k2exists, k2_index = find_match_with_same_head(data_head, 'k2', words_info, index=4)
     for dataele in words_info:
        dataele_index = dataele[0]
        dep_head = dataele[index].strip().split(':')[0]
        dep_value = dataele[index].strip().split(':')[1]
        if str(data_head) == dep_head and term == dep_value:
            return True, dataele_index
     return False, -1

def parse_morph_tags(morph_form):
    """
    >>> parse_morph_tags("mA<cat:n><case:d><gen:f><num:p>")
    {'cat': 'n', 'case': 'd', 'gen': 'f', 'num': 'p', 'form': 'mA'}
    """
    form = morph_form.split("<")[0]
    matches = re.findall("<(.*?):(.*?)>", morph_form)
    result = {match[0]: match[1] for match in matches}
    result["form"] = form
    return result

# def parse_morph_tags_as_list(morph_form):
#     """
#     >>> parse_morph_tags("mA<cat:n><case:d><gen:f><num:p>")
#     {'cat': 'n', 'case': 'd', 'gen': 'f', 'num': 'p', 'form': 'mA'}
#     """
#     ##print(morph_form,'form')
#     form = morph_form.split("<")[0]
#     ##print(form,'mmmm')
#     matches = re.findall("<(.*?):(.*?)>", morph_form)
#     result = [(match[0], match[1]) for match in matches]
#     result.append(('form',form))
#     ##print(result,'res')
#     return result

# def parse_morph_tags_as_list(morph_form):
#     """
#     Extracts the word and its corresponding morphological tags from the given morph-form string.

#     Example:
#     >>> parse_morph_tags("mA<cat:n><case:d><gen:f><num:p>")
#     [{'form': 'mA', 'cat': 'n', 'case': 'd', 'gen': 'f', 'num': 'p'}]
#     """
#     # Split the morph-form by '/' to get individual word segments
#     word = morph_form.split('/')[0].replace('^','')
#     segments = morph_form.split('/')
    
#     result = []
#     # Iterate over each segment
#     for segment in segments:
#         form = segment.split("<")[0]  # Extract the word (before the first '<')
#         if word==form:
#             matches = re.findall("<(.*?):(.*?)>", segment)  # Find all morphological tags
#             tag_dict = {match[0]: match[1] for match in matches}  # Convert matches to a dictionary
#             tag_dict['form'] = form  # Add the word under the 'form' key
#             result.append(tag_dict)  # Add the dictionary to the result list
#     # ##print(result,'result')
#     return result
import re

def parse_morph_tags_as_list(morph_form, lang='en'):
    """
    Parses morphological analysis output for a given language.

    Args:
        morph_form (str): Morphological string from lt-proc.
        lang (str): Language code ('hi' for Hindi, 'en' for English).

    Returns:
        list of dicts: Each dict contains morphological features for one form.

    Examples:
        Hindi: "mA<cat:n><case:d><gen:f><num:p>"
        English: "slowly<adv>"
    """
    segments = morph_form.split('/')
    word = morph_form.split('/')[0].replace('^', '')

    result = []

    for segment in segments:
        form = segment.split("<")[0]
        if form != word:
            continue
        
        if lang == 'hi':
            matches = re.findall(r"<(.*?):(.*?)>", segment)
            tag_dict = {match[0]: match[1] for match in matches}
        elif lang == 'en':
            matches = re.findall(r"<(.*?)>", segment)
            tag_dict = {'cat': matches[0]} if matches else {}
        else:
            continue  # or raise an error for unsupported lang

        tag_dict['form'] = form
        result.append(tag_dict)

    return result


def if_morph_kqwpft(processed_words, gnp_data):
    # Check if 'kqwpft' is present in gnp_data
    if 'kqwpft' in gnp_data:
        # Find the index of 'kqwpft' in gnp_data
        index = gnp_data.index('kqwpft')
        
        # Ensure the index is valid for processed_words
        if index < len(processed_words):
            # Modify the corresponding element in processed_words
            word_entry = processed_words[index]
            modified_entry = (
                word_entry[0],  # Keep the first element (ID) unchanged
                word_entry[1],  # Keep the second element (word) unchanged
                'vj',           # Change the third element to 'vj'
                *word_entry[3:6],  # Keep the next two elements unchanged
                'adj_yA_huA',   # Change the 6th element
                *word_entry[7:]  # Keep the rest of the elements unchanged
            )
            processed_words[index] = modified_entry
    return processed_words


# def check_words_in_dict(words,processed_words):
#     """
#     Check if each word in the list is present in the file using shell commands.
#     If a word starts with '#', remove '#', check if the word is present in the file, 
#     then replace '#' with '*' if not found, or leave as is if found.
#     This ensures that only whole words are matched, and matching is case-sensitive.
#     """
#     global global_starred_words  # Declare the global variable
#     words = words.split(' ')
    
#     file_path = "repository/hi_expanded_LC"
#     processed_concepts = []
    
#     for word in words:
#         original_word = word
#         if word.startswith('#'):
#             word_to_check = word[1:]  # Remove '#' for checking
#         else:
#             word_to_check = word  # If there's no '#', use the word as is
        
#         # Use the -w flag to match whole words only and make sure it's case-sensitive
#         command = f"grep -qw '{word_to_check}' {file_path}"
        
#         # Run the grep command
#         result = subprocess.run(command, shell=True)
        
#         # If grep returns a non-zero exit status, the word is not found
#         if result.returncode != 0:
#             if original_word.startswith('#'):
#                 starred_word = f"*{word_to_check}"
#                 processed_concepts.append(starred_word)  # Add * in front if not found
#                 global_starred_words.append(starred_word)  # Store in the global list
#             else:
#                 processed_concepts.append(word_to_check)  # Leave the word as is if not found and doesn't have #
#         else:
#             processed_concepts.append(original_word)  # Keep the original word if found
#     #print(processed_concepts, 'Processed concepts')
#     # #print(global_starred_words, 'Global starred words')
#     return processed_concepts


import subprocess

# Global dictionary to store words prefixed with '*' along with their category
global_starred_words = {}

def check_is_digit(num):
    if num.isdigit():
        return True
    else:
        try:
            float_value = float(num)
            return True
        except ValueError:
            return False
    return False

# def check_words_in_dict(words, processed_words):
#     """
#     Check if each word in the list is present in a .txt file.
#     If a word starts with '#', remove '#', check if the word is present in the file, 
#     then replace '#' with '*' if not found, or leave as is if found.
#     Also, store the word along with its descriptive category in the global list.
#     """
#     global global_starred_words  # Declare the global variable
#     words = words.split(' ')

#     file_path = "repository/extracted_words.txt"
#     processed_concepts = []

#     # Create a dictionary for word categories from `processed_words`
#     word_categories = {entry[1]: entry[2] for entry in processed_words if len(entry) > 2}

#     # Load the .txt file into a set for fast lookups
#     with open(file_path, 'r', encoding='utf-8') as file:
#         file_words = set(file.read().splitlines())

#     for word in words:
#         original_word = word
#         if word.startswith('#'):
#             word_to_check = word[1:]  # Remove '#' for checking
#         else:
#             word_to_check = word  # If there's no '#', use the word as is

#         # Check if the word is in the loaded set
#         if word_to_check not in file_words:
#             # Handle starred word case
#             if original_word.startswith('#') and word_to_check not in repository.constant.construction_list:
#                 starred_word = f"*{word_to_check}"
#                 processed_concepts.append(starred_word)  # Add * in front if not found
                
#                 # Map the category to its descriptive form
#                 category = word_categories.get(word_to_check, "unknown")
#                 descriptive_category = repository.constant.category_mapping.get(category, "unknown")
                
#                 # Add to global dictionary
#                 global_starred_words[starred_word.replace('*', '')] = descriptive_category
#             else:
#                 processed_concepts.append(word_to_check)  # Leave the word as is if not found or is excluded
#         else:
#             processed_concepts.append(original_word)  # Keep the original word if found

#     #print(processed_concepts, 'Processed concepts')
#     #print(global_starred_words, 'Global starred words with descriptive categories')
#     return processed_concepts

def read_output_data(output_file):
    """Check the output file data for post processing"""

    with open(output_file, 'r') as file:
        data = file.read()
    return data

# def analyse_output_data(output_data, morph_input):
#     if isinstance(output_data, str):
#         output_data = output_data.strip().split(" ")

#     combine_data = []
#     for i in range(len(output_data)):
#         morph_input_list = list(morph_input[i])
#         morph_input_list[1] = output_data[i]
#         combine_data.append(tuple(morph_input_list))
#     return combine_data

def analyse_output_data(output_data, morph_input, morphmapping):
    if isinstance(output_data, str):
        output_data = output_data.strip().split()

    # Step 1: Join ["4", "o'clock"] → ["4o'clock"]
    i = 0
    while i < len(output_data) - 1:
        if output_data[i].isdigit() and output_data[i + 1].lower() == "o'clock":
            output_data[i] = output_data[i] + output_data[i + 1]
            del output_data[i + 1]
        else:
            i += 1

    # Step 2: Build reverse lookup from morphmapping values to keys (excluding -1)
    word_to_index_map = {}
    for idx, (_, word) in morphmapping.items():
        if idx != '-1':
            word_to_index_map[word] = idx

    # Step 3: Build a dictionary for quick access to morph_input by index
    morph_input_map = {str(entry[0]): list(entry) for entry in morph_input}

    # Step 4: Replace words in morph_input_map based on output_data and morphmapping
    for word in output_data:
        if word in word_to_index_map:
            index_key = word_to_index_map[word]
            if index_key in morph_input_map:
                morph_input_map[index_key][1] = word  # update word

    # Step 5: Build final combined_data based on morphmapping
    combined_data = []
    existing_entries_set = set()
    dummy_counter = -100  # start dummy indexes for unmatched -1s

    for idx, (orig_idx, word) in morphmapping.items():
        if idx == '-1':
            # Try to match the word in morph_input
            matched = None
            for entry in morph_input:
                if entry[1] == word and str(entry[0]) not in existing_entries_set:
                    matched = list(entry)
                    break

            if matched:
                entry_key = str(matched[0])
                combined_data.append(tuple(matched))
                existing_entries_set.add(entry_key)
            else:
                # Create a unique dummy entry
                while str(dummy_counter) in existing_entries_set:
                    dummy_counter -= 1
                combined_data.append((dummy_counter, word, '', '', '', '', '', '', ''))
                existing_entries_set.add(str(dummy_counter))
                dummy_counter -= 1
        else:
            if idx in morph_input_map and idx not in existing_entries_set:
                combined_data.append(tuple(morph_input_map[idx]))
                existing_entries_set.add(idx)
            else:
                combined_data.append((idx, word, '', '', '', '', '', '', ''))

    return combined_data




def handle_compound_nouns(noun, processed_nouns, category, case, gender, number, person, postposition):
    dnouns = noun[1].split('+')
    relation=noun[4].split(':')[1] if noun[4] else ''
    relation_head = noun[4].split(':')[0] if noun[4] else ''
    # ##print(dnouns,'dns')
    for k in range(len(dnouns)):
        index = noun[0] + (k * 0.1)
        noun_type = 'NC'
        clean_dnouns = clean(dnouns[k])
        if k == len(dnouns) - 1:
            noun_type = 'NC_head'
            dict_index = index
            processed_nouns.append(
                (index, clean_dnouns, category, case, gender, number, person, noun_type, postposition,relation_head,relation))
        else:
            processed_nouns.append((index, clean_dnouns, category, case, gender, number, person, noun_type, '',relation_head,relation))

    if noun[0] in processed_postpositions_dict:
        processed_postpositions_dict[dict_index] = processed_postpositions_dict.pop(noun[0])
    # if clean(noun[1]) in ('cp', 'conj', 'disjunct', 'span', 'widthmeas', 'depthmeas', 'distmeas', 'rate', 'timemeas', 'waw', 'calender', 'massmeas', 'heightmeas', 'spatial'):
    #     del processed_postpositions_dict[index]
    return processed_nouns

def handle_unprocessed_all(outputData, processed_nouns):
    """swapping gender info that does not exist in dictionary."""
    output_data = outputData.strip().split(" ")
    has_changes = False
    reprocess_list = []
    dataIndex = 0  # temporary [to know index value of generated word from sentence]
    for data in output_data:
        dataIndex = dataIndex + 1
        if data[0] == '#':
            for i in range(len(processed_nouns)):
                if round(processed_nouns[i][0]) == dataIndex:
                        if processed_nouns[i][7] != 'proper':
                            temp = list(processed_nouns[i])
                            temp[4] = change_gender(processed_nouns[i][4])
                            #temp[4] = 'f' if processed_nouns[i][4] == 'm' else 'm'
                            reprocess_list.append(['n', i, processed_nouns[i][0],temp[4], temp[7]])
                            processed_nouns[i] = tuple(temp)
                            has_changes = True
                            log(f'{temp[1]} reprocessed as noun with new gen:{temp[4]}.')
    return has_changes, reprocess_list, processed_nouns

# def handle_unprocessed(index_data,depend_data,output_data, processed_nouns):
#     """swapping gender info that does not exist in dictionary."""
#     # output_data = outputData.strip().split(" ")
#     has_changes = False
#     # dataIndex = 0  # temporary [to know index value of generated word from sentence]
#     for dataIndex,data in enumerate(output_data):
#         # ##print(data,output_data,'df')
#         if data[0] == '#':
#             for i in range(len(processed_nouns)):
#                 # ##print(processed_nouns[i][0],'dff')
#                 # if dataIndex in index_data:
#                     # ind = index_data.index(dataIndex-1)
#                 ind = index_data[dataIndex]
#                 if round(processed_nouns[i][0]) == ind:
#                     # ##print(processed_nouns[i][2],depend_data[i].split(':')[1],'klm')
#                     if depend_data[i] and processed_nouns[i][2]=='n' and depend_data[i].split(':')[1]=='k1s':
#                         # ##print('klm')
#                         has_changes = True
#                         temp = list(processed_nouns[i])
#                         temp[2] = 'adj'
#                         # temp[4] = 'f' if processed_nouns[i][4] == 'm' else 'm'
#                         processed_nouns[i] = tuple(temp)
#                     if processed_nouns[i][7] not in ('proper','NC','CP_noun', 'abs', 'vn'):
#                     #if not processed_nouns[i][7] == 'proper' and not processed_nouns[i][7] == 'NC' and not processed_nouns[i][7] == 'CP_noun':
#                         has_changes = True
#                         temp = list(processed_nouns[i])
#                         temp[4] = 'f' if processed_nouns[i][4] == 'm' else 'm'
#                         processed_nouns[i] = tuple(temp)
#                         log(f'{temp[1]} reprocessed as noun with gen:{temp[4]}.')
#                     else:
#                         break
#     # ##print(processed_nouns,'nn')
#     return has_changes, processed_nouns

def handle_star(index_data,output_data,processed_nouns):
    """
    Swaps gender info for nouns that do not exist in the dictionary.
    
    Args:
        index_data (list): Maps indices of `output_data` to corresponding indices in `processed_nouns`.
        depend_data (list): Dependency information for each word.
        output_data (list): Processed words from the sentence.
        processed_nouns (list): List of tuples representing processed nouns.
        
    Returns:
        tuple: A tuple containing a boolean indicating if changes were made and the updated `processed_nouns`.
    """
    has_star = False

    # Ensure index_data is a list
    if not isinstance(index_data, list):
        raise ValueError("index_data must be a list mapping indices.")
    
    for dataIndex, data in enumerate(output_data):
        # Check if the current word starts with '#'
        if data.startswith('*'):
            old_tuple = processed_nouns[dataIndex]
            new_tuple = (old_tuple[0], data.replace('*', ''), *old_tuple[2:])
            processed_nouns[dataIndex] = new_tuple
            has_star = True

    return has_star, processed_nouns
def apply_dict_to_filtered_data(filtered_data, insert_dict, PP_fulldata_dict_with_ids, **kwargs):
    updated_data = {}

    # Step 1: Apply insertions and get updated data
    updated_filtered, updated_ppdict = update_ppdict_and_filtered_data(
        filtered_data, insert_dict, PP_fulldata_dict_with_ids
    )

    # Step 2: Rebuild final output
    for sent_id, sentence_list in updated_filtered.items():  # ✅ FIXED: removed [0]
        updated_sentences = []
        for sentence in sentence_list:
            if isinstance(sentence, list):
                sentence = ' '.join(sentence)
            updated_sentences.append(sentence.strip())
        updated_data[sent_id] = updated_sentences

    return updated_data, updated_ppdict



def add_interrogative_dict(filtered_data, interrogative_dict,PP_fulldata_dict_with_ids):
    return apply_dict_to_filtered_data(filtered_data, interrogative_dict,PP_fulldata_dict_with_ids, replace_underscores=True)

def add_foreign_words_dict(filtered_data, foreign_words_dict,PP_fulldata_dict_with_ids):
    return apply_dict_to_filtered_data(filtered_data, foreign_words_dict,PP_fulldata_dict_with_ids, replace_carets=True)

def add_calendar_dict(filtered_data, calendar_dict,PP_fulldata_dict_with_ids):
    return apply_dict_to_filtered_data(filtered_data, calendar_dict,PP_fulldata_dict_with_ids)

def add_indec_dict(filtered_data, indec_dict,PP_fulldata_dict_with_ids):
    return apply_dict_to_filtered_data(filtered_data, indec_dict,PP_fulldata_dict_with_ids)

def add_verb_dict(filtered_data, verb_dict,PP_fulldata_dict_with_ids):
    return apply_dict_to_filtered_data(filtered_data, verb_dict,PP_fulldata_dict_with_ids)
def add_nonfinite_dict(filtered_data, nonfinite_dict,PP_fulldata_dict_with_ids):
    return apply_dict_to_filtered_data(filtered_data, nonfinite_dict,PP_fulldata_dict_with_ids)
def add_rad_dict(filtered_data, rad_dict,PP_fulldata_dict_with_ids):
    return apply_dict_to_filtered_data(filtered_data, rad_dict,PP_fulldata_dict_with_ids)


import math
import re

def strip_tags(word):
    return re.sub(r'[\(\)\d]', '', word).strip('.')


def update_ppdict_and_filtered_data(filtered_data, insert_dict, ppdict_full):
    for sent_id, insert_items in insert_dict.items():
        if sent_id not in filtered_data:
            continue

        # Sentence: assuming only one sentence per key
        sentence = filtered_data[sent_id][0]
        words = sentence.strip().split()

        if sent_id not in ppdict_full:
            ppdict_full[sent_id] = []

        existing_indices = {entry[0] for entry in ppdict_full[sent_id]}

        for idx, tup in insert_items.items():
            if tup[0] not in existing_indices:
                ppdict_full[sent_id].append(tup)

            word = tup[1]
            insert_pos = int(idx)

            if word not in words:
                if insert_pos >= len(words):
                    if words[-1] in ['.', '?', '!']:
                        words.insert(len(words) - 1, word)
                    else:
                        words.append(word)
                else:
                    words.insert(insert_pos, word)

        # Rebuild sentence and update
        filtered_data[sent_id][0] = ' '.join(words)

    return filtered_data, ppdict_full


def add_masking_model(sentences):
    from dotenv import load_dotenv
    import os
    from groq import Groq

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY") or None
    if not api_key:
        raise ValueError("API key not found. Set GROQ_API_KEY in .env.")

    client = Groq(api_key=api_key)

    updated_sentences = []

    for sentence in sentences:
        if "[mask]" not in sentence:
            updated_sentences.append(sentence)
            continue

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": "add right preposition in the place of [mask].if preposition is not neccesary then remove the [mask].maintain syntax.and dont generate extra info just give output."},
                {"role": "user", "content": sentence}
            ],
            temperature=1,
            max_completion_tokens=1024,
            top_p=1,
            stream=False
        )

        response = completion.choices[0].message.content.strip()
        updated_sentences.append(response)

        print(f"Input: {sentence}")
        print(f"Output: {response}\n")

    return updated_sentences

# wx_to_eng = {
#     "a": "a","A": "aa","i": "i","I": "ii","u": "u","U": "uu",
#     "e": "e","E": "ai","o": "o","O": "au","M": "n","H": "h","q": "ri",

#     "k": "k","K": "kh","g": "g","G": "gh","f": "ng",

#     "c": "ch","C": "chh","j": "j","J": "jh","F": "ny","y": "y",

#     "t": "T","T": "Th","d": "D","D": "Dh","N": "N","L": "L",

#     "w": "t","W": "th","x": "d","X": "dh","n": "n",

#     "p": "p","P": "ph","b": "b","B": "bh","m": "m",

#     "r": "r","l": "l","v": "v",

#     "s": "s","S": "sh","R": "Sh","h": "h",

#     "z": "z","Z": "zh"
# }

wx_to_eng = {
    # Vowels
    "a": "a", "A": "ā", "i": "i", "I": "ī",
    "u": "u", "U": "ū", "e": "e", "E": "ai",
    "o": "o", "O": "au",

    # Sonorants
    "q": "ṛ", "Q": "ṝ", "L": "ḷ",

    # Anusvara & Visarga
    "M": "ṃ", "H": "ḥ",

    # Anunasika & Avagraha
    "z": "̃", "Z": "'",

    # Velar
    "k": "k", "K": "kh", "g": "g", "G": "gh", "f": "ṅ",

    # Palatal
    "c": "c", "C": "ch", "j": "j", "J": "jh", "F": "ñ",

    # Retroflex
    "t": "ṭ", "T": "ṭh", "d": "ḍ", "D": "ḍh", "N": "ṇ",

    # Dental
    "w": "t", "W": "th", "x": "d", "X": "dh", "n": "n",

    # Labial
    "p": "p", "P": "ph", "b": "b", "B": "bh", "m": "m",

    # Semivowels
    "y": "y", "r": "r", "l": "l", "v": "v",

    # Fricatives
    "S": "ś", "R": "ṣ", "s": "s", "h": "h",
}

PREPOSITION_LIST = {"of", "for", "to", "with", "by", "on", "at", "in", "from", "about", "as", "into", "like", "after"}

def wx_to_english(word):
    word = word.split('_')[0]  # remove suffix like _1
    result = []
    
    for ch in word:
        result.append(wx_to_eng.get(ch, ch))
        
    return "".join(result)
def reorder_chunk_to_left_preposition(chunk, sentence_order):
    if not chunk.startswith('['):
        return chunk
    words = chunk.strip("[]").replace("_SUBJ", "").split()
    for i, word in enumerate(words):
        if word.lower() in PREPOSITION_LIST and i != 0:
            # move preposition to front
            reordered = [word] + words[:i] + words[i+1:]
            chunk_core = f"[{' '.join(reordered)}]"
            return chunk_core + ("_SUBJ" if chunk.endswith("_SUBJ") else "")
    return chunk
import re
import re
from collections import defaultdict
def get_verb_tag(tokens, sentence_type):
    """Determine semantic tag for verb chunks based on sentence type and voice."""
    if not tokens:
        return ""
    
    # Detect passive voice: look for 'main' token with 'en' TAM or passive aux patterns
    is_passive = False
    is_imperative = False
    is_interrogative = False
    
    sentence_type_lower = (sentence_type or '').lower()
    
    if 'imperative' in sentence_type_lower:
        is_imperative = True
    elif 'interrogative' in sentence_type_lower:
        is_interrogative = True
    
    # Check for passive via TAM in tokens
    for t in tokens:
        if len(t) > 6:
            tam = str(t[6]) if len(t) > 6 else ''
            word = t[1] if len(t) > 1 else ''
            relation = t[-3] if len(t) > 3 else ''
            
            # Passive indicators: 'en' TAM (past participle) + auxiliary like 'got'/'been'/'was'
            if tam in ('en', 'pp') and 'main' in str(relation):
                is_passive = True
                break
            # Also check word patterns like "done declared", "was built" etc
            if any(aux in word.split() for aux in ['got', 'been', 'was', 'were', 'been', 'is', 'are']):
                if tam in ('en', 'pp'):
                    is_passive = True
                    break
    
    if is_passive:
        return '_PASSIVE'
    elif is_imperative:
        return '_IMPERATIVE'
    elif is_interrogative:
        return '_QUESTION'
    return '_ACTIVE'
# def add_spkview(full_data, spkview_dict):
#     transformed_data = []
#     for data in full_data:
#         index = data[0]
#         # normalize: try both int and string key
#         spk_info = spkview_dict.get(index) or spkview_dict.get(str(index)) or spkview_dict.get(int(index) if str(index).isdigit() else index)
#         if spk_info:
#             temp = list(data)
#             for info in spk_info:
#                 tag = info[0]
#                 val = info[1]
#                 if tag == 'respect':
#                     words = temp[1].split()
#                     for i in range(len(words) - 1, -1, -1):
#                         if words[i].lower() not in {'the', 'a', 'an', 'of', 'in', 'on', 'at'}:
#                             words[i] = words[i] + '_(respect)'
#                             break
#                     temp[1] = ' '.join(words)
#                 elif tag == 'before':
#                     temp[1] = val + ' ' + temp[1]
#                 elif tag == 'after':
#                     temp[1] = temp[1] + ' ' + val
#             data = tuple(temp)
#         transformed_data.append(data)
#     return transformed_data
def add_chinking(sentence, PP_fulldata_dict_with_ids, key, sentence_type=None, span_map=None, ne_words=None):
    """
    Performs syntactic and semantic chinking to form meaningful chunks.
    Handles: nf, krya, rpk, main+aux, coordination, and fallback.
    Enhanced to handle modifier chains and nested structures.
    Outputs structured chunks for multilingual generation.
    """
    import re
    from collections import defaultdict
    # Guard: skip if upstream processing produced an error string
    data = PP_fulldata_dict_with_ids.get(key, [])
    if isinstance(data, str) or (
        isinstance(data, list) and len(data) > 0 and isinstance(data[0], str)
    ):
        print(f"[DEBUG] add_chinking skipping {key} — upstream error: {data}")
        return sentence
    
    print(f"{PP_fulldata_dict_with_ids[key]} PP_fulldata_dict_with_ids")

    # --- Step 1: Add missing words as dummy tokens ---
    existing_words = set()
    for t in PP_fulldata_dict_with_ids[key]:
        if t[1]:  # If token has words
            # Split the token words and add all of them to existing_words
            token_words = t[1].split()
            for word in token_words:
                if '+' in word:
                    parts = word.split('+')
                    for part in parts:
                        existing_words.add(part.lower())
                else:
                    existing_words.add(word.lower())
    
    
    sentence_tokens = sentence.strip().split()
    for word in sentence_tokens:
        word_lower = word.lower()
        if word_lower not in existing_words and word != '.' and word != '<>':
            dummy_token = (0.0, word, '', '', '', '', '', '', '', '', '')
            PP_fulldata_dict_with_ids[key].append(dummy_token)
        else:
            pass
    

    # --- Helper Functions ---
    def sort_index(val):
        try:
            return float(val[0])
        except (ValueError, TypeError):
            return float(str(val[0]).replace("'", ""))

    def float_or_none(x):
        try:
            return float(x)
        except:
            return None

    def find_token_by_index(index):
        try:
            idx = float(index)
        except (TypeError, ValueError):
            return None
        for t in tagged_data:
            try:
                if float(t[0]) == idx:
                    return t
            except:
                continue
        print(f"[DEBUG] Token not found for index: {index}")
        return None

    def get_words(token):
        if not token or len(token) <= 2 or not token[1] or token[1] in ['disjunct','#waw','waw','conj','timemeas','span','compound','nc']:
            return []
        words = token[1].split()
        processed_words = []
        for word in words:
            if '+' in word:
                processed_words.extend(word.split('+'))
            else:
                print("DEBUG word before append:", word, type(word), len(word) if isinstance(word, (list, tuple)) else "NA")
                processed_words.append(word)
                # processed_words.append(word)
        return processed_words

    def get_words_from_chunk(chunk):
        stripped = chunk.strip('[]_SUBJ')
        words = stripped.split()
        return [w.lower() for w in words]

    # --- NEW: Disjunction handling function ---
    def handle_disjunction_groups():
        """
        Handle disjunction groups: when 'disjunct' is found, group tokens with matching last two values
        """
        
        # Find all disjunct tokens
        disjunct_tokens = []
        for t in tagged_data:
            if t[1] == 'disjunct':
                disjunct_tokens.append(t)
                print(f"[DEBUG] Found disjunct token: {t}")
        
        for disjunct in disjunct_tokens:
            # Get the last two values from disjunct token
            disjunct_last_two = (disjunct[-2], disjunct[-1])
            print(f"[DEBUG] Disjunct last twovalues: {disjunct_last_two}")
            
            # Find all tokens with matching last two values (excluding the disjunct itself)
            matching_tokens = []
            for t in tagged_data:
                if (t != disjunct and len(t) >= 8 and 
                    (t[-2], t[-1]) == disjunct_last_two and
                    float(t[0]) not in used_data_indices):
                    matching_tokens.append(t)
                    print(f"[DEBUG] Found matching token: {t[1]} with last two: {(t[-2], t[-1])}")
            
            # If we found matching tokens, create a disjunction group
            if matching_tokens:
                # Sort by index to maintain order
                all_tokens = matching_tokens + [disjunct]
                all_tokens_sorted = sorted(all_tokens, key=lambda x: float(x[0]))
                
                print(f"[DEBUG] Creating disjunction group: {[t[1] for t in all_tokens_sorted]}")
                
                # Create the disjunction chunk
                words_list = []
                for t in all_tokens_sorted:
                    if t[1] and t[1] != 'disjunct':  # Skip the word 'disjunct' itself
                        words_list.extend(get_words(t))
                
                if words_list:
                    merged_words = ' '.join(words_list)
                    chunk = f"[{merged_words}]"
                    
                    # Check if any words are already used
                    words_lower = [w.lower() for w in words_list]
                    if not any(w in used_words for w in words_lower):
                        chunks.append(chunk)
                        used_data_indices.update(float(t[0]) for t in all_tokens_sorted)
                        used_words.update(words_lower)
                        print(f"[DEBUG] Added disjunction chunk: {chunk}")
                        return True
                    else:
                        print(f"[DEBUG] Skipping disjunction chunk - words already used")
            else:
                used_data_indices.add(float(disjunct[0]))
                print(f"[DEBUG] Skipping lone disjunct token: {disjunct}")
        
        return False

    # --- NEW: Merge auxiliary + negation + main verb ---
    def merge_aux_neg_main():
        """
        Merge auxiliary, negation, and main verb into a single verbal complex.
        Orders them semantically: aux -> neg -> main for natural English-like structure.
        """
        
        # Find all main verbs
        main_verbs = []
        for t in tagged_data:
            if (len(t) > 8 and 'main' in str(t[-3]) and 
                float(t[0]) not in used_data_indices):
                main_verbs.append(t)
        
        for main_verb in main_verbs:
            main_idx = float(main_verb[0])
            complex_parts = [main_verb]
            
            
            # 1. Find neg tokens that point to this main verb
            neg_tokens = [t for t in tagged_data if 
                          (len(t) >= 8 and t[-1] == 'neg' and 
                           float_or_none(t[-2]) == main_idx and
                           float(t[0]) not in used_data_indices)]
            
            for neg in neg_tokens:
                complex_parts.append(neg)
                print(f"[DEBUG] Added neg: {neg[1]} to complex")
            
            # 2. Find auxiliary verbs for this main verb (same base index)
            aux_tokens = [t for t in tagged_data if 
                          (len(t) > 8 and 'auxiliary' in str(t[-3]) and 
                           str(float(t[0])).startswith(str(int(main_idx))) and
                           float(t[0]) not in used_data_indices)]
            
            for aux in aux_tokens:
                complex_parts.append(aux)
                print(f"[DEBUG] Added aux: {aux[1]} to complex")
            
            # 3. Create the verbal complex if we have more than just the main verb
            if len(complex_parts) > 1:
                # Collect all auxiliaries, negations, and main
                aux_parts = [t for t in complex_parts if 'auxiliary' in str(t[-3])]
                neg_parts = [t for t in complex_parts if t[-1] == 'neg']
                main_part = next((t for t in complex_parts if 'main' in str(t[-3])), None)
                
                # Sort auxiliaries and negations by index
                sorted_aux = sorted(aux_parts, key=lambda t: float(t[0]))
                sorted_neg = sorted(neg_parts, key=lambda t: float(t[0]))
                
                ordered_words = []
                for aux_t in sorted_aux:
                    ordered_words.append(aux_t[1])
                for neg_t in sorted_neg:
                    ordered_words.append(neg_t[1])
                if main_part:
                    ordered_words.append(main_part[1])
                
                merged_words = ' '.join(ordered_words)
                
                # Use main verb as base and update its words
                merged = list(main_verb)
                merged[1] = merged_words
                merged = tuple(merged)
                
                # Replace main verb with merged complex
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == main_idx:
                        tagged_data[i] = merged
                        print(f"[DEBUG] Created aux+neg+main complex: {merged_words}")
                        break
                
                # Remove other parts from tagged_data
                indices_to_remove = [float(t[0]) for t in complex_parts if float(t[0]) != main_idx]
                original_count = len(tagged_data)
                tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                print(f"[DEBUG] Removed {len(indices_to_remove)} tokens. Count: {original_count} -> {len(tagged_data)}")
                
                # Mark indices as used (though removed, for consistency)
                used_data_indices.update(indices_to_remove)

    # --- Enhanced function to build modifier chains ---
    def find_complete_modifier_network():
        """
        Find all interconnected modifier networks and group them together.
        This handles complex cases where multiple modifiers connect to different parts of a chain.
        FIXED: Better handling of r6, dem, mod relationships and conjunction groups
        """
        
        # Build a comprehensive graph of all relationships
        relationships = []  # [(modifier_idx, head_idx, relation_type)]
        
        # First, identify conjunction groups
        conjunction_groups = defaultdict(list)
        
        for t in tagged_data:
            if len(t) >= 4:
                token_idx = float(t[0])
                relation_type = t[-1]
                head_idx = float_or_none(t[-2]) if len(t) >= 4 else None
                
                if head_idx and relation_type in {'k2', 'k1', 'r6'}:
                    key_group = (head_idx, relation_type)
                    if t[1] not in {'conj', 'disjunct'} and not str(t[1]).startswith('['):
                        if key_group not in conjunction_groups:
                            conjunction_groups[key_group] = []
                        conjunction_groups[key_group].append(token_idx)
        
        
        # Collect all modifier relationships - generic approach for ALL relations
        SKIP_RELATIONS = {'main', 'auxiliary', 'k1', 'k2', 'k3', 'k4', 'k5', 
                          'k7p', 'k7t', 'rt', 'r6', 'rpk', 'rbks', 'rsk',
                          'rblpk', 'rblak', 'rblsk', 'rvks', 'rs', 'rsm',
                          'k1s', 'pk1', 'nf', 'krya', 'neg', 'conj', 
                          'disjunct', 'unit', None, ''}

        for t in tagged_data:
            if len(t) >= 8:
                modifier_idx = float(t[0])
                relation_type = t[-1]
                head_idx = float_or_none(t[-2]) if len(t) >= 8 else None

                if not head_idx:
                    continue

                # Generic: build relationship for modifier-type relations
                # These are relations where the token MODIFIES its head
                MODIFIER_RELATIONS = {'mod', 'intf', 'dem', 'vkvn', 
                                      'card', 'rdl', 'rvks', 'krvn'}
                # quant handled separately - only connects to nouns not verbs
                                      # NOTE: 'r6' removed - handled by NC merge attachment

                # quant should only modify nouns, not verbs
                if relation_type == 'quant':
                    head_token = None
                    for td in tagged_data:
                        try:
                            if float(td[0]) == head_idx and len(td) > 2 and td[2] == 'n':
                                head_token = td
                                break
                        except: pass
                    if head_token:
                        relationships.append((modifier_idx, head_idx, relation_type))
                    continue

                if relation_type in MODIFIER_RELATIONS:
                    if relation_type == 'mod':
                        raw_head_idx = head_idx
                        for (group_head, group_rel), group_members in conjunction_groups.items():
                            if raw_head_idx in group_members and len(group_members) > 1:
                                for member_idx in group_members:
                                    relationships.append((modifier_idx, member_idx, relation_type))
                                    print(f"[DEBUG] Found mod relationship to conjunction member: {t[1]} ({relation_type}) -> {member_idx}")
                                break
                        else:
                            relationships.append((modifier_idx, head_idx, relation_type))
                            print(f"[DEBUG] Found mod relationship: {t[1]} ({relation_type}) -> {head_idx}")
                    else:
                        relationships.append((modifier_idx, head_idx, relation_type))
                        print(f"[DEBUG] Found relationship: {t[1]} ({relation_type}) -> head_idx:{head_idx}")
        
        # Add conjunction relationships within groups
        for (group_head, group_rel), group_members in conjunction_groups.items():
            if len(group_members) > 1:
                # Connect all members of the conjunction group to each other
                for i, member1 in enumerate(group_members):
                    for j, member2 in enumerate(group_members):
                        if i != j:
                            relationships.append((member1, member2, 'conj'))
                print(f"[DEBUG] Added internal conjunction relationships for group: {group_members}")
        
        # ENHANCED: Build transitive closure to find complete chains
        # Create adjacency list for undirected graph
        graph = defaultdict(set)
        direct_relations = {}  # Track direct relationships
        
        for mod_idx, head_idx, rel_type in relationships:
            graph[mod_idx].add(head_idx)
            graph[head_idx].add(mod_idx)
            direct_relations[(mod_idx, head_idx)] = rel_type
            direct_relations[(head_idx, mod_idx)] = rel_type
        
        
        # Find connected components using Union-Find with path compression
        parent = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # Union all connected nodes
        for node in graph:
            for neighbor in graph[node]:
                union(node, neighbor)
        
        # Group nodes by their root parent
        components = defaultdict(set)
        for node in graph:
            components[find(node)].add(node)
        
        # Also include isolated nodes that are part of relationships
        all_relationship_nodes = set()
        for mod_idx, head_idx, _ in relationships:
            all_relationship_nodes.add(mod_idx)
            all_relationship_nodes.add(head_idx)
        
        for node in all_relationship_nodes:
            if node not in parent:
                components[node].add(node)
        
        # Filter networks with 2+ nodes and prioritize longer chains
        networks = [component for component in components.values() if len(component) > 1]
        
        # Sort networks by size (largest first) to handle most complete chains first
        networks.sort(key=len, reverse=True)
        
        return networks
    
    def tokens_from_indices(indices):
        """Get token objects from a set of indices"""
        tokens = []
        for t in tagged_data:
            if float(t[0]) in indices:
                tokens.append(t)
        return sorted(tokens, key=lambda x: float(x[0]))

    # --- Merge Helpers ---
    def merge_nf_with_head():
        """Merge nf (e.g., 'after') with its floor value head (verb/noun)."""
        nf_tokens = []
        for t in tagged_data:
            try:
                if str(t[-1]) == 'nf' and '.' in str(t[0]):
                    nf_tokens.append(t)
            except Exception:
                continue

        for nf in nf_tokens:
            base_idx = str(nf[0]).split('.')[0]
            head = find_token_by_index(base_idx)
            if not head:
                print(f"[DEBUG] merge_nf_with_head - head not found for nf token {nf}")
                continue

            try:
                head_pos = head[2] if len(head) > 2 else None
            except Exception:
                head_pos = None

            if head_pos in {'v', 'n', 'rpk', 'k7p', 'k2'}:
                merged_words = f"{nf[1]} {head[1]}"
                merged = list(head)
                merged[1] = merged_words
                merged = tuple(merged)

                replaced = False
                for i, t in enumerate(tagged_data):
                    try:
                        if float(t[0]) == float(base_idx):
                            tagged_data[i] = merged
                            replaced = True
                            break
                    except Exception:
                        continue

                if not replaced:
                    for i, t in enumerate(tagged_data):
                        if str(t[0]) == base_idx:
                            tagged_data[i] = merged
                            replaced = True
                            break

                tagged_data[:] = [t for t in tagged_data if str(t[0]) != str(nf[0])]
                print(f"[DEBUG] Merged nf: {nf[1]} + {head[1]} → {merged_words}")

    def merge_rbks_with_head():
        """Merge rbks (adjectival participle) with noun heads"""
        rbks_tokens = [t for t in tagged_data if len(t) > 10 and t[-1] == 'rbks']
        for rbks in rbks_tokens:
            head_idx = float_or_none(rbks[-2])
            if not head_idx:
                continue
            head = find_token_by_index(head_idx)
            if not head:
                continue
            if len(head) > 2 and head[2] in {'n', 'k7p'}:
                merged_words = f"{rbks[1]} {head[1]}"
                merged = list(head)
                merged[1] = merged_words
                merged = tuple(merged)
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == head_idx:
                        tagged_data[i] = merged
                        break
                tagged_data[:] = [t for t in tagged_data if float(t[0]) != float(rbks[0])]
                print(f"[DEBUG] Merged rbks: {rbks[1]} + {head[1]} → {merged_words}")

    def merge_krya_with_main():
        krya_tokens = [t for t in tagged_data if len(t) >= 8 and t[-1] == 'krya' and '.' in str(t[0])]
        
        original_count = len(tagged_data)
        
        for krya in krya_tokens:
            base_idx = str(krya[0]).split('.')[0]
            main = find_token_by_index(base_idx)
            
            if main:
                if len(main) > 2 and main[2] == 'v':
                    # Strip 'conj' and any bracket constructions from main verb word
                    main_word = main[1]
                    main_word = re.sub(r'\bconj\b', '', main_word).strip()
                    main_word = re.sub(r'\[.*?\]', '', main_word).strip()
                    
                    merged_words = f"{main_word} {krya[1]}" if main_word else krya[1]
                    merged = list(main)
                    merged[1] = merged_words
                    merged = tuple(merged)
                    
                    for i, t in enumerate(tagged_data):
                        if float(t[0]) == float(base_idx):
                            tagged_data[i] = merged
                            break
                    
                    tagged_data[:] = [t for t in tagged_data if str(t[0]) != str(krya[0])]
                    used_data_indices.add(float(krya[0]))
                    
                    print(f"[DEBUG] Removed krya token. Count: {original_count} -> {len(tagged_data)}")
                    print(f"[DEBUG] Merged krya: {main[1]} + {krya[1]} → {merged_words}")
                
                else:
                    print(f"[DEBUG] Main verb {main[1]} is not a verb (pos: {main[2] if len(main) > 2 else 'unknown'})")
            
            else:
                print(f"[DEBUG] No main verb found for base index {base_idx}")
    temp = None
    r6_words = []
    def merge_nc_with_nc_head():
        """Merge NC (noun compound) with NC_head to form compound noun phrases, ensuring a preposition at the left boundary if possible."""
        
        # Common prepositions list
        prepositions = {'to', 'in', 'on', 'at', 'for', 'with', 'by', 'from', 'of', 'about', 'after', 'before', 'during', 'since', 'until', 'over', 'under', 'between', 'among'}
        
        # Find NC tokens
        nc_tokens = []
        for t in tagged_data:
            if len(t) > 7 and t[7] == 'NC':  # NC is at position 7 (0-indexed)
                nc_tokens.append(t)
                print(f"[DEBUG] Found NC token: {t[1]} at index {t[0]}")
        
        # Find NC_head tokens
        nc_head_tokens = []
        for t in tagged_data:
            if len(t) > 7 and t[7] == 'NC_head':  # NC_head is at position 7
                nc_head_tokens.append(t)
                print(f"[DEBUG] Found NC_head token: {t[1]} at index {t[0]}")
                # In merge_nc_with_nc_head, r6 attachment:
        is_pron = False
        if 'r6t' in locals() and r6t:
            if len(r6t) > 2:
                is_pron = (r6t[2] == 'p')
        if is_pron:
            FRONT_PREPS = {'in','on','at','from','to','by','for','with','into','onto'}
            head_words_clean = [w for i,w in enumerate(head_words) 
                                if not (i==0 and w.lower() in FRONT_PREPS)]
            temp[1] = ' '.join(r6_words) + ' ' + ' '.join(head_words_clean)
        else:
            if 'temp' in locals() and temp is not None:
                if 'r6_words' in locals() and r6_words:
                    temp[1] = temp[1] + ' ' + ' '.join(r6_words)
        # Group NC + NC_head pairs by their base index
        from collections import defaultdict
        nc_groups = defaultdict(list)
        
        for nc in nc_tokens:
            base_idx = int(float(nc[0]))  # Get base index (e.g., 10.0 -> 10)
            nc_groups[base_idx].append(nc)
        
        for nc_head in nc_head_tokens:
            base_idx = int(float(nc_head[0]))  # Get base index (e.g., 10.1 -> 10)
            nc_groups[base_idx].append(nc_head)
                
        # Merge NC + NC_head pairs
        for base_idx, group in nc_groups.items():
            if len(group) >= 2:  # Must have at least NC and NC_head
                # Sort by float index to maintain order
                group_sorted = sorted(group, key=lambda t: float(t[0]))
                # Collect ALL NC tokens (not just first one) and the NC_head
                all_nc_modifiers = [t for t in group_sorted if t[7] == 'NC']
                nc_head_token = next((t for t in group_sorted if t[7] == 'NC_head'), None)

                if all_nc_modifiers and nc_head_token:
                    PREPOSITIONS = {
                        'from', 'to', 'of', 'in', 'on', 'at', 'by', 'for',
                        'with', 'about', 'among', 'between', 'through',
                        'into', 'onto', 'upon', 'within', 'without',
                        'across', 'along', 'around', 'behind', 'below',
                        'beside', 'over', 'under', 'after', 'before', '<>'
                    }

                    # Split NC_head words and extract any leading preposition
                    # e.g. "from #steSana" → leading_preps=["from"], remaining=["#steSana"]
                    # e.g. "the kAraxaMga" → leading_preps=["the"], remaining=["kAraxaMga"]
                    # Note: "the" is kept with NC modifiers not extracted as prep
                    nc_head_words = nc_head_token[1].split()
                    leading_preps = []
                    remaining_head_words = []
                    collecting_preps = True
                    # 'of' is genitive - keep with head, don't extract as leading prep
                    nc_relation = nc_head_token[-1] if len(nc_head_token) >= 8 else ''
                    if nc_relation == 'r6':
                        EXTRACT_PREPS = PREPOSITIONS
                    else:
                        EXTRACT_PREPS = {p for p in PREPOSITIONS if p != 'of'}
                    for w in nc_head_words:
                        if collecting_preps and w.lower() in EXTRACT_PREPS and w.lower() != 'the':
                            leading_preps.append(w)
                        else:
                            collecting_preps = False
                            remaining_head_words.append(w)

                    # Collect all NC modifier words
                    nc_mod_words = []
                    for mod_tok in all_nc_modifiers:
                        for w in mod_tok[1].split():
                            nc_mod_words.append(w)

                    # English order: preposition + NC head remainder + NC modifiers
                    # NC_head is the semantic head, NC modifiers describe it
                    # e.g. "to #gaMgA fair" not "to fair #gaMgA"
                    # Detect if this is a Named Entity (NE) or Noun Compound (NC)
                    # NE (begin/inside): modifier words come BEFORE head → kAraxaMga goMpA
                    # NC (compound noun): head word comes BEFORE modifiers → gesata hAusa
                    # NE detection: the head content word starts with '#' (needs WX conversion)
                    # means it's a proper name (inside word of NE)
                    # NC detection: head is a common English word (no '#')
                    is_named_entity = False
                    SKIP_WORDS = {'the', 'a', 'an', 'of', 'from', 'to', 'in',
                                  'on', 'at', 'by', 'with', 'for', 'among', 'between'}
                    ne_word_set = ne_words or set()

                    def word_is_ne(word):
                        """Check if a word is a named entity word."""
                        w = word.lstrip('#').split('_')[0].lower()
                        return any(w == ne.lower() or w == ne.split('_')[0].lower()
                                   for ne in ne_word_set)

                    # Check 1: modifier starts with 'the' → NE
                    for mod_tok in all_nc_modifiers:
                        if mod_tok[1].startswith('the '):
                            is_named_entity = True
                            break

                    # Check 2: head content word starts with '#' → NE
                    if not is_named_entity:
                        if remaining_head_words and remaining_head_words[0].startswith('#'):
                            is_named_entity = True

                    # Check 3: modifier content word is in ne_words → NE begin word
                    if not is_named_entity:
                        mod_flat = []
                        for mod_tok in all_nc_modifiers:
                            mod_flat.extend(mod_tok[1].split())
                        mod_content = [w for w in mod_flat if w.lower() not in SKIP_WORDS]
                        if mod_content and (mod_content[0].startswith('#') or
                                            word_is_ne(mod_content[0])):
                            # Also check head is NE word
                            head_content = [w for w in remaining_head_words
                                           if w.lower() not in SKIP_WORDS]
                            if head_content and (head_content[0].startswith('#') or
                                                 word_is_ne(head_content[0])):
                                is_named_entity = True

                    if is_named_entity:
                        all_words = leading_preps + nc_mod_words + remaining_head_words
                    else:
                        all_words = leading_preps + remaining_head_words + nc_mod_words

                    # Strip trailing conjunction markers added by add_construction
                    while all_words and all_words[-1] in {'and', 'or', ','}:
                        all_words.pop()

                    merged_words = ' '.join(all_words)
                    merged = list(nc_head_token)
                    merged[1] = merged_words
                    merged = tuple(merged)
                    print(f"[DEBUG] Merging NC group: {[t[1] for t in group_sorted]} -> {merged_words}")
                    for i, t in enumerate(tagged_data):
                        if float(t[0]) == float(nc_head_token[0]):
                            tagged_data[i] = merged
                            print(f"[DEBUG] Replaced token at index {i} with merged NC compound")
                            break

                    # Remove ALL NC modifier tokens
                    indices_to_remove = [float(t[0]) for t in all_nc_modifiers]
                    original_count = len(tagged_data)
                    tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                    print(f"[DEBUG] Removed {len(indices_to_remove)} NC tokens. Count: {original_count} -> {len(tagged_data)}")
                    
                    # After NC merge, attach any r6 modifiers pointing to base_idx into the merged token
                    nc_head_float = float(nc_head_token[0])
                    base_idx_float = float(base_idx)
                    r6_tokens = [t for t in tagged_data 
                                 if len(t) >= 8 and t[-1] == 'r6' and 
                                 float_or_none(t[-2]) == base_idx_float and
                                 float(t[0]) not in indices_to_remove]
                    
                    r6_indices_to_remove = []
                    for r6t in r6_tokens:
                        r6_words = r6t[1].split()
                        is_pron = False
                        if 'r6t' in locals() and r6t:
                            if len(r6t) > 2:
                                is_pron = (r6t[2] == 'p')
                        
                        for i, t in enumerate(tagged_data):
                            if float(t[0]) == nc_head_float:
                                temp = list(t)
                                if is_pron:
                                    # Possessive pronoun goes BEFORE the noun phrase
                                    temp[1] = ' '.join(r6_words) + ' ' + temp[1]
                                else:
                                    # Noun genitive goes AFTER: "beauty of the garden"
                                    temp[1] = temp[1] + ' ' + ' '.join(r6_words)
                                tagged_data[i] = tuple(temp)
                                print(f"[DEBUG] Attached r6 '{r6t[1]}' ({'before' if is_pron else 'after'}) to NC head '{t[1]}'")
                                break
                        r6_indices_to_remove.append(float(r6t[0]))
                    
                    # Remove consumed r6 tokens
                    if r6_indices_to_remove:
                        tagged_data[:] = [t for t in tagged_data 
                                         if float(t[0]) not in r6_indices_to_remove]
                 
                # Separate NC and NC_head tokens
                # nc_token = next((t for t in group_sorted if t[7] == 'NC'), None)
                # nc_head_token = next((t for t in group_sorted if t[7] == 'NC_head'), None)
                
                # if nc_token and nc_head_token:
                #     # Check if NC_head starts with a preposition
                #     nc_head_words = nc_head_token[1].split()
                #     has_preposition = nc_head_words and nc_head_words[0].lower() in prepositions
                    
                #     # Initialize merged words
                #     merged_words_list = nc_head_words + nc_token[1].split()
                    
                    # If no preposition in NC_head, try to find a relevant preposition
                #     preposition = ""
                #     if not has_preposition:
                #         # Look for preposition tokens (e.g., k7p, nf) related to the base_idx
                #         for t in tagged_data:
                #             if (len(t) >= 8 and t[-1] in {'k7p', 'nf', 'k7t'} and 
                #                 float_or_none(t[-2]) == float(base_idx) and 
                #                 float(t[0]) not in used_data_indices):
                #                 preposition = t[1]
                #                 used_data_indices.add(float(t[0]))
                #                 print(f"[DEBUG] Found preposition '{preposition}' for base index {base_idx}")
                #                 break
                        
                #         # If no preposition found, use a default preposition (e.g., 'of') if appropriate
                #         if not preposition:
                #             preposition = "of"  # Default preposition, can be adjusted based on context
                #             print(f"[DEBUG] No preposition found; using default 'of' for base index {base_idx}")
                    
                #     # Create merged words: preposition (if any) + NC_head + NC# Split NC token words
                #    # Split head token
                #     # --- Generic NC + NC_head merge ---

                #                         # Split NC_head# Split NC_head
                #     head_parts = nc_head_token[1].split()

                #     preposition = ''
                #     modifier_words = []

                #     # Detect preposition
                #     if head_parts and head_parts[0].lower() in prepositions:
                #         preposition = head_parts[0]
                #         modifier_words = head_parts[1:]
                #     else:
                #         modifier_words = head_parts

                #     # Split NC token
                #     nc_words = nc_token[1].split()

                #     # Separate determiners from noun head
                #     determiners = []
                #     head_words = []

                #     for w in nc_words:
                #         if w.startswith('#'):
                #             head_words.append('#' + w.replace('#',''))
                #         else:
                #             determiners.append(w)

                #     # Convert modifier words to NC markers
                #     modifier_words = ['#' + w.replace('#','') for w in modifier_words]

                #     merged_words_list = []

                #     if preposition:
                #         merged_words_list.append(preposition)

                #     merged_words_list.extend(determiners)
                #     merged_words_list.extend(modifier_words)
                #     merged_words_list.extend(head_words)

                #     merged_words = ' '.join(merged_words_list)

                #     merged = list(nc_head_token)
                #     merged[1] = merged_words
                #     merged = tuple(merged)

                #     print(f"[DEBUG] Merging NC group: ['{nc_head_token[1]}', '{nc_token[1]}'] -> {merged_words}")
                #     for i, t in enumerate(tagged_data):
                #         if float(t[0]) == float(nc_head_token[0]):
                #             tagged_data[i] = merged
                #             print(f"[DEBUG] Replaced token at index {i} with merged NC compound")
                #             break
                    
                #     # Remove the NC token
                #     indices_to_remove = [float(t[0]) for t in group_sorted if t[7] == 'NC']
                #     original_count = len(tagged_data)
                #     tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                #     print(f"[DEBUG] Removed {len(indices_to_remove)} NC tokens. Count: {original_count} -> {len(tagged_data)}")
    def merge_conj_construction(): 
        """
        Find conj-head tokens, collect operands, merge into subject chunk,
        strip 'conj' from verbal token.
        """

        conj_heads = []
        for t in tagged_data:
            if len(t) > 1 and t[1] and (
                'conj' in str(t[1]).lower() or
                (len(t) > 6 and 'conj' in str(t[6]).lower())
            ):
                conj_heads.append(t)

        for conj_head in conj_heads:
            head_idx = float(conj_head[0])
            op_tokens = []

            # ── Method 1: explicit opN in construction field (index 8) ──
            for t in PP_fulldata_dict_with_ids[key]:
                if float(t[0]) in used_data_indices:
                    continue
                matched = False
                if len(t) > 8 and isinstance(t[8], str) and ':' in t[8]:
                    ref_str, ref_rel = t[8].split(':', 1)
                    try:
                        if float(ref_str) == head_idx and re.match(r'op\d+', ref_rel):
                            matched = True
                    except ValueError:
                        pass
                if not matched and len(t) > 10:
                    try:
                        if float(t[9]) == head_idx and re.match(r'op\d+', str(t[10])):
                            matched = True
                    except (ValueError, TypeError):
                        pass
                if matched:
                    t_idx = float(t[0])
                    for td in tagged_data:
                        if (float(td[0]) == t_idx and
                                float(td[0]) not in used_data_indices and
                                td[1] not in {'conj', 'disjunct',}):
                            op_tokens.append(td)
                            print(f"[DEBUG] Found op token (construction field): {td[1]}")
                            break

            # ── Method 2: tokens sharing same head & relation as conj_head ──
            if not op_tokens:
                conj_rel = conj_head[-1] if len(conj_head) >= 8 else ''
                conj_head_of_head = (float_or_none(conj_head[-2])
                                    if len(conj_head) >= 8 else None)
                if conj_rel and conj_head_of_head:
                    for td in tagged_data:
                        if (float(td[0]) != head_idx and
                                float(td[0]) not in used_data_indices and
                                len(td) >= 8 and
                                td[-1] == conj_rel and
                                float_or_none(td[-2]) == conj_head_of_head and
                                td[1] not in {'conj', 'disjunct'} and
                                td[1] not in {'.', '?', '!', ','}):
                            op_tokens.append(td)
                            print(f"[DEBUG] Found op token (same head/rel): {td[1]}")

            # ── Method 3: empty-relation fallback ──
            if not op_tokens:
                for td in tagged_data:
                    if (len(td) >= 2 and td[-1] == '' and
                            float(td[0]) > 0 and
                            td[1] not in {'.', '?', '!', ',', ';', ':',
                                        'conj', 'disjunct'} and
                            float(td[0]) != head_idx and
                            float(td[0]) not in used_data_indices):
                        op_tokens.append(td)
                        print(f"[DEBUG] Found op token (empty-rel fallback): {td[1]}")

            if not op_tokens:
                continue

            op_tokens_sorted = sorted(op_tokens, key=lambda t: float(t[0]))

            # ── Extend with card/dem/quant modifiers of each op token ──
            extended_op_tokens = list(op_tokens_sorted)
            op_base_indices = set()
            for op in op_tokens_sorted:
                # collect both the exact float index and its integer base
                op_base_indices.add(float(op[0]))
                op_base_indices.add(float(int(float(op[0]))))

            for td in tagged_data:
                if (float(td[0]) not in used_data_indices and
                        td not in extended_op_tokens and
                        len(td) >= 8 and
                        td[-1] in {'card', 'dem', 'quant'} and
                        td[1] not in {'conj', 'disjunct'}):
                    td_head = float_or_none(td[-2])
                    # check if this modifier points to any op token
                    # (by exact index OR by integer base index for NC cases)
                    if td_head in op_base_indices:
                        extended_op_tokens.append(td)
                        print(f"[DEBUG] Added modifier {td[1]} ({td[-1]}) "
                            f"to op token group")

            extended_op_tokens_sorted = sorted(extended_op_tokens,
                                            key=lambda t: float(t[0]))

            # ── Build op_words_list stripping <> placeholders ──
            op_words_list = []
            for op in extended_op_tokens_sorted:
                words = [w for w in get_words(op) if w != '<>']
                if words:
                    op_words_list.append(' '.join(words))

            # ── Safe trailing 'and'/',' removal without truncating letters ──
            cleaned = []
            for w in op_words_list:
                words_split = w.split()
                while words_split and words_split[-1] in {'and', ','}:
                    words_split.pop()
                if words_split:
                    cleaned.append(' '.join(words_split))
            op_words_list = cleaned

            if not op_words_list:
                print(f"[DEBUG] No words in op list for conj head {conj_head[1]}")
                continue

            # ── Build merged subject string ──
            if len(op_words_list) == 1:
                merged = op_words_list[0]
            elif len(op_words_list) == 2:
                merged = f"{op_words_list[0]} and {op_words_list[1]}"
            else:
                merged = ', '.join(op_words_list[:-1]) + f" and {op_words_list[-1]}"

            print(f"[DEBUG] Merged conj ops: {merged}")

            # ── Clean 'conj'/brackets from verbal token word ──
            # do NOT mark head_idx as used — let Step 9.7 emit it as verb chunk
            for i, t in enumerate(tagged_data):
                if float(t[0]) == head_idx:
                    temp = list(t)
                    real_verb = re.sub(r'\bconj\b', '', temp[1]).strip()
                    real_verb = re.sub(r'\[.*?\]', '', real_verb).strip()
                    temp[1] = real_verb if real_verb else temp[1]
                    tagged_data[i] = tuple(temp)
                    print(f"[DEBUG] Cleaned conj verb to: {temp[1]}")
                    break

            # ── Add subject chunk directly to chunks ──
            subject_chunk = f"[{merged}]_SUBJ"
            if subject_chunk not in chunks:
                chunks.append(subject_chunk)
                print(f"[DEBUG] Added subject chunk: {subject_chunk}")

            # ── Mark ALL extended op tokens as used ──
            # NOTE: do NOT mark head_idx (the verb) as used
            op_indices = {float(t[0]) for t in extended_op_tokens_sorted}
            for t in extended_op_tokens_sorted:
                used_data_indices.add(float(t[0]))
                used_words.update(w.lower() for w in get_words(t) if w != '<>')

            # ── Remove op tokens from tagged_data ──
            before = len(tagged_data)
            tagged_data[:] = [t for t in tagged_data
                            if float(t[0]) not in op_indices]
            print(f"[DEBUG] Removed {len(op_indices)} op tokens. "
                f"Count: {before} -> {len(tagged_data)}")
        
    def merge_adj_with_noun_head():
        """
        Merge adjective modifiers with their noun heads ONLY when the noun head
        has an empty relation (operand context). Do NOT merge when the noun head
        has a grammatical relation like k5, k1, mod etc — those are handled by
        the modifier network in Step 0.
        """
        adj_tokens = [t for t in tagged_data
                    if len(t) >= 8 and t[-1] == 'mod' and
                    len(t) > 2 and t[2] == 'adj' and
                    float(t[0]) not in used_data_indices]

        for adj in adj_tokens:
            head_idx = float_or_none(adj[-2]) if len(adj) >= 8 else None
            if not head_idx:
                continue
            head = find_token_by_index(head_idx)
            if not head or float(head[0]) in used_data_indices:
                continue
            # CRITICAL: only merge when head has empty relation
            # If head has a grammatical relation (k1, k5, mod, etc.) skip it
            # — it will be handled by the modifier network
            head_rel = head[-1] if len(head) >= 8 else ''
            if head_rel != '':
                continue
            if len(head) > 2 and head[2] in ('n', 'NC_head', 'NC'):
                merged_words = f"{adj[1]} {head[1]}"
                merged = list(head)
                merged[1] = merged_words
                merged = tuple(merged)
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == head_idx:
                        tagged_data[i] = merged
                        break
                tagged_data[:] = [t for t in tagged_data
                                if float(t[0]) != float(adj[0])]
                used_data_indices.add(float(adj[0]))
                print(f"[DEBUG] Merged adj+noun: {adj[1]} + {head[1]} → {merged_words}")
    def merge_calendar_construction():
        calendar_keywords = {'calendar', 'calender'}

        cal_tokens = []
        for t in tagged_data:
            if len(t) > 1 and t[1] and any(
                kw in str(t[1]).lower() for kw in calendar_keywords
            ):
                cal_tokens.append(t)
                print(f"[DEBUG] Found calendar token: {t[1]} at index {t[0]}")

        for cal_token in cal_tokens:
            cal_idx = float(cal_token[0])
            component_tokens = []

            # Find component tokens from PP_fulldata_dict_with_ids[key]
            for t in PP_fulldata_dict_with_ids[key]:
                if len(t) <= 8:
                    continue
                construction_field = t[8]
                if isinstance(construction_field, str) and ':' in construction_field:
                    const_parts = construction_field.split(':')
                    try:
                        const_head = float(const_parts[0])
                        const_rel = const_parts[1]
                        if const_head == cal_idx and 'component' in const_rel:
                            t_idx = float(t[0])
                            for td in tagged_data:
                                if float(td[0]) == t_idx:
                                    component_tokens.append(td)
                                    print(f"[DEBUG] Found calendar component: {td[1]}")
                                    break
                    except (ValueError, TypeError):
                        pass

            # Also pick up any tokens with empty head that are adjacent
            # (date digits and month names with '' head)
            if not component_tokens:
                for t in tagged_data:
                    if (len(t) >= 10 and
                            str(t[9]) == '' and str(t[10]) == '' and
                            float(t[0]) not in used_data_indices and
                            t[2] in ('n', 'adj') and
                            t[0] != cal_token[0]):
                        component_tokens.append(t)
                        print(f"[DEBUG] Found adjacent calendar component: {t[1]}")

            if component_tokens:
                component_sorted = sorted(component_tokens, key=lambda t: float(t[0]))
                merged_parts = []
                for ct in component_sorted:
                    merged_parts.extend(get_words(ct))

                if merged_parts:
                    merged_word = ' '.join(merged_parts)
                    print(f"[DEBUG] Merged calendar: {merged_word}")

                    merged_token = list(cal_token)
                    merged_token[1] = merged_word
                    merged_token = tuple(merged_token)

                    for i, t in enumerate(tagged_data):
                        if float(t[0]) == cal_idx:
                            tagged_data[i] = merged_token
                            break

                    indices_to_remove = {float(t[0]) for t in component_tokens}
                    original_count = len(tagged_data)
                    tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                    print(f"[DEBUG] Removed {len(indices_to_remove)} calendar tokens. Count: {original_count} -> {len(tagged_data)}")

    def merge_meas_construction():
        meas_keywords = {
            'distmeas', 'timemeas', 'massmeas', 'heightmeas',
            'widthmeas', 'depthmeas', 'lengthmeas', 'tempmeas',
            'weightmeas', 'span', 'dist_meas'
        }

        meas_tokens = [t for t in tagged_data
                    if len(t) > 1 and t[1] and
                    any(kw in str(t[1]).lower() for kw in meas_keywords)]

        for meas_token in meas_tokens:
            meas_idx = float(meas_token[0])
            meas_head_idx = float_or_none(meas_token[-2]) if len(meas_token) >= 8 else None
            meas_rel = meas_token[-1] if len(meas_token) >= 2 else ''

            count_token = None
            unit_tokens = []
            location_tokens = []

            # ── Step 1: find count via construction field "<meas_idx>:count" ──
            for t in PP_fulldata_dict_with_ids[key]:
                t_idx_f = float(t[0])
                if t_idx_f in used_data_indices:
                    continue
                if len(t) > 8 and isinstance(t[8], str) and ':' in t[8]:
                    ref_str, ref_rel = t[8].split(':', 1)
                    try:
                        ref_head = float(ref_str)
                    except ValueError:
                        continue
                    if ref_head == meas_idx and ref_rel == 'count':
                        for td in tagged_data:
                            if float(td[0]) == t_idx_f and float(td[0]) not in used_data_indices:
                                count_token = td
                                print(f"[DEBUG] Found count token (construction→meas): {td[1]}")
                                break

            # ── Step 2: find count via construction field "<verb_head>:count" ──
            if not count_token and meas_head_idx:
                for t in PP_fulldata_dict_with_ids[key]:
                    t_idx_f = float(t[0])
                    if t_idx_f in used_data_indices:
                        continue
                    if len(t) > 8 and isinstance(t[8], str) and ':' in t[8]:
                        ref_str, ref_rel = t[8].split(':', 1)
                        try:
                            ref_head = float(ref_str)
                        except ValueError:
                            continue
                        if ref_head == meas_head_idx and ref_rel == 'count':
                            for td in tagged_data:
                                if float(td[0]) == t_idx_f and float(td[0]) not in used_data_indices:
                                    count_token = td
                                    print(f"[DEBUG] Found count token (construction→verb head): {td[1]}")
                                    break

            # ── Step 3: find count by following rmeas chain ──
            # Tourism_072: 5→rmeas→9(north)→k7p→10(verb)
            # distmeas→rmeas→9(north). So count points to same head as distmeas
            # OR count points to anything in the rmeas chain
            if not count_token:
                rmeas_chain = {meas_idx}
                if meas_head_idx:
                    rmeas_chain.add(meas_head_idx)
                for td in tagged_data:
                    if (len(td) >= 8 and
                            td[-1] in ('rmeas', 'count', 'k7p', 'k7t') and
                            float(td[0]) not in used_data_indices and
                            float(td[0]) != meas_idx):
                        td_head = float_or_none(td[-2])
                        if td_head in rmeas_chain:
                            word = td[1] if len(td) > 1 else ''
                            pos = td[2] if len(td) > 2 else ''
                            noun_type = td[7] if len(td) > 7 else ''
                            # Must be numeric AND not a unit/indec token
                            is_numeric = (
                                word.replace('.','').isdigit() or
                                noun_type in ('digit', 'numex', 'meas') or
                                pos == 'numex'
                            )
                            is_unit = (pos == 'indec' or noun_type == 'unit')
                            if is_numeric and not is_unit:
                                count_token = td
                                print(f"[DEBUG] Found count token (rmeas chain): {td[1]}")
                                break

            # ── Step 4: find unit - indec tokens ──
            for t in PP_fulldata_dict_with_ids[key]:
                t_idx_f = float(t[0])
                if t_idx_f in used_data_indices:
                    continue
                if len(t) == 6 and t[2] == 'indec' and str(t[3]) == 'unit':
                    for td in tagged_data:
                        if float(td[0]) == t_idx_f and float(td[0]) not in used_data_indices:
                            if td not in unit_tokens:
                                unit_tokens.append(td)
                                print(f"[DEBUG] Found unit token (indec 6-tuple): {td[1]}")
                            break
                elif len(t) >= 4 and t[2] == 'indec':
                    for td in tagged_data:
                        if float(td[0]) == t_idx_f and float(td[0]) not in used_data_indices:
                            if td not in unit_tokens:
                                unit_tokens.append(td)
                                print(f"[DEBUG] Found unit token (indec): {td[1]}")
                            break
            # ── Step 4b: find start/end tokens using span_map ──
            start_token = None
            end_token = None

            span_index_str = str(int(meas_idx))  # e.g. '10'

            if span_map and span_index_str in span_map:
                span_entry = span_map[span_index_str]

                for tidx in span_entry.get('start', []):
                    for td in tagged_data:
                        if str(int(float(td[0]))) == tidx and float(td[0]) not in used_data_indices:
                            start_token = td
                            print(f"[DEBUG] Found start token via span_map: {td[1]}")
                            break

                for tidx in span_entry.get('end', []):
                    for td in tagged_data:
                        if str(int(float(td[0]))) == tidx and float(td[0]) not in used_data_indices:
                            end_token = td
                            print(f"[DEBUG] Found end token via span_map: {td[1]}")
                            break

                for tidx in span_entry.get('unit', []):
                    for td in tagged_data:
                        if (str(int(float(td[0]))) == tidx and
                                float(td[0]) not in used_data_indices and
                                td not in unit_tokens):
                            unit_tokens.append(td)
                            print(f"[DEBUG] Found unit token via span_map: {td[1]}")
                            break

            # ── Step 5: find location ──
            # location = token with k7p pointing to meas_head (verb)
            # OR pointing to an intermediate node in rmeas chain
            # But NOT the count or unit tokens
            count_idx = float(count_token[0]) if count_token else None
            unit_idxs = {float(ut[0]) for ut in unit_tokens}
            exclude = {meas_idx, count_idx} | unit_idxs
            exclude.discard(None)

            # also collect all rmeas-chain intermediate nodes
            rmeas_intermediates = set()
            for td in tagged_data:
                if (len(td) >= 8 and td[-1] == 'rmeas' and
                        float(td[0]) not in exclude):
                    td_head = float_or_none(td[-2])
                    if td_head == meas_idx or td_head == meas_head_idx:
                        rmeas_intermediates.add(float(td[0]))
            # Hello
            # Step 5: find location
            # Case A: token with k7p/k7t pointing to meas_head (verb)
            # Case B: meas_head itself is a spatial token (rmeas points TO it)
            #         e.g. distmeas→rmeas→north(k7p)→verb
            #         In this case meas_head IS the location token
            count_idx = float(count_token[0]) if count_token else None
            unit_idxs = {float(ut[0]) for ut in unit_tokens}
            exclude = {meas_idx, count_idx} | unit_idxs
            exclude.discard(None)

            rmeas_intermediates = set()
            for td in tagged_data:
                if (len(td) >= 8 and td[-1] == 'rmeas' and
                        float(td[0]) not in exclude):
                    td_head = float_or_none(td[-2])
                    if td_head == meas_idx or td_head == meas_head_idx:
                        rmeas_intermediates.add(float(td[0]))

            # Check if meas_head is itself a spatial/directional token
            meas_head_token = None
            if meas_head_idx:
                for td in tagged_data:
                    if float(td[0]) == meas_head_idx and float(td[0]) not in exclude:
                        meas_head_token = td
                        break

            if meas_head_token and meas_head_token[-1] in ('k7p', 'k7t', 'k7', 'rmeas'):
                # The meas_head IS the location (e.g. north)
                location_tokens.append(meas_head_token)
                print(f"[DEBUG] Found location token (meas_head is spatial): {meas_head_token[1]}")
            else:
                # Normal: find tokens pointing TO meas_head or verb
                for td in tagged_data:
                    td_f = float(td[0])
                    if td_f in used_data_indices or td_f in exclude:
                        continue
                    if len(td) < 8:
                        continue
                    td_head = float_or_none(td[-2])
                    td_rel = td[-1]
                    # Skip purely numeric tokens — they are count, not location
                    td_word = td[1] if len(td) > 1 else ''
                    if td_word.replace('.','').isdigit():
                        continue
                    if td_rel in ('k7p', 'k7t', 'k7'):
                        if (td_head == meas_head_idx or
                                td_head == meas_idx or
                                td_head in rmeas_intermediates):
                            location_tokens.append(td)
                            print(f"[DEBUG] Found location token: {td[1]}")

            # ── Step 6: build merged — correct order: count unit location ──
            # ── Step 6: build merged — correct order: start end unit location ──
            # ── Step 6: build merged — correct order: start end count unit location ──
            merged_parts = []
            # For span: output as "from START to END" not "from START to END mixed"
            # start_token already has 'from' prefix, end_token has 'to' prefix
            # We want: start_words + end_words in natural order
            if start_token and end_token:
                start_words = [w for w in get_words(start_token) if w != '<>']
                end_words = [w for w in get_words(end_token) if w != '<>']
                # Natural order: from X to Y
                # start_words = ['from', 'patanA'], end_words = ['to', 'barElA']  
                merged_parts.extend(start_words)
                merged_parts.extend(end_words)
            elif start_token:
                start_words = [w for w in get_words(start_token) if w != '<>']
                merged_parts.extend(start_words)
            elif end_token:
                end_words = [w for w in get_words(end_token) if w != '<>']
                merged_parts.extend(end_words)
            if count_token:
                count_words = [w for w in get_words(count_token) if w != '<>']
                merged_parts.extend(count_words)
            for ut in sorted(unit_tokens, key=lambda x: float(x[0])):
                unit_words = [w for w in get_words(ut) if w != '<>']
                merged_parts.extend(unit_words)
            for lt in sorted(location_tokens, key=lambda x: float(x[0])):
                loc_words = [w for w in get_words(lt) if w != '<>']
                merged_parts.extend(loc_words)

            if not merged_parts:
                print(f"[DEBUG] No parts for meas {meas_token[1]}, skipping")
                continue

            merged_word = ' '.join(merged_parts)
            print(f"[DEBUG] Merged measurement: {merged_word}")

            # Replace meas token
            merged_tok = list(meas_token)
            merged_tok[1] = merged_word
            merged_tok = tuple(merged_tok)
            for i, t in enumerate(tagged_data):
                if float(t[0]) == meas_idx:
                    tagged_data[i] = merged_tok
                    break

            # Remove consumed tokens
            remove_idx = set()
            if start_token:
                remove_idx.add(float(start_token[0]))
            if end_token:
                remove_idx.add(float(end_token[0]))
            if count_token:
                remove_idx.add(float(count_token[0]))
            for ut in unit_tokens:
                remove_idx.add(float(ut[0]))
            for lt in location_tokens:
                remove_idx.add(float(lt[0]))

            before = len(tagged_data)
            tagged_data[:] = [t for t in tagged_data
                            if float(t[0]) not in remove_idx]
            print(f"[DEBUG] Removed {len(remove_idx)} meas tokens. "
                f"Count: {before} -> {len(tagged_data)}")

    def merge_complete_verbal_complexes():
        """
        Merge complete verbal complexes: nf + rpk + main + krya/aux
        This handles cases like "after placing do hot" as a single unit
        """
        
        # Find all main verbs first
        main_verbs = []
        for t in tagged_data:
            if (len(t) > 8 and 'main' in str(t[-3]) and 
                float(t[0]) not in used_data_indices):
                main_verbs.append(t)
        
        for main_verb in main_verbs:
            main_idx = float(main_verb[0])
            complex_parts = [main_verb]
            
            
            # 1. Find krya for this main verb
            krya_tokens = [t for t in tagged_data if 
                           (len(t) > 8 and t[-1] == 'krya' and 
                            str(t[0]).startswith(str(int(main_idx))) and
                            float(t[0]) not in used_data_indices)]
            
            for krya in krya_tokens:
                complex_parts.append(krya)
                print(f"[DEBUG] Added krya: {krya[1]} to complex")
            
            # 2. Find rpk tokens that point to this main verb
            rpk_tokens = [t for t in tagged_data if 
                          (len(t) > 10 and t[-1] == 'rpk' and 
                           float_or_none(t[-2]) == main_idx and
                           float(t[0]) not in used_data_indices)]
            
            for rpk in rpk_tokens:
                rpk_idx = float(rpk[0])
                complex_parts.append(rpk)
                print(f"[DEBUG] Added rpk: {rpk[1]} to complex")
                
                # 3. Find nf tokens for this rpk
                nf_tokens = [t for t in tagged_data if 
                             (len(t) > 8 and t[-1] == 'nf' and 
                              str(t[0]).startswith(str(int(rpk_idx))) and
                              float(t[0]) not in used_data_indices)]
                
                for nf in nf_tokens:
                    complex_parts.append(nf)
                    print(f"[DEBUG] Added nf: {nf[1]} to complex")
            
            print(f"[DEBUG] Skipping auxiliary verbs - will be handled in Step 9.7")
            
            # 5. Create the complete verbal complex if we have more than just the main verb
            if len(complex_parts) > 1:
                # Sort by index to get proper order
                complex_parts_sorted = sorted(complex_parts, key=lambda t: float(t[0]))
                
                # Create merged verbal complex
                merged_words = ' '.join([t[1] for t in complex_parts_sorted])
                
                # Use main verb as base and update its words
                merged = list(main_verb)
                merged[1] = merged_words
                merged = tuple(merged)
                
                # Replace main verb with merged complex
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == main_idx:
                        tagged_data[i] = merged
                        print(f"[DEBUG] Created complete verbal complex: {merged_words}")
                        break
                
                # Remove other parts from tagged_data
                indices_to_remove = [float(t[0]) for t in complex_parts if float(t[0]) != main_idx]
                original_count = len(tagged_data)
                tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                print(f"[DEBUG] Removed {len(indices_to_remove)} tokens. Count: {original_count} -> {len(tagged_data)}")
                
                # Mark indices as used
                used_data_indices.update(indices_to_remove)

    def add_chunk(tokens, tag="", step="", preserve_order=False):
        if not tokens:
            return False
        sorted_tokens = tokens if preserve_order else sorted(tokens, key=lambda t: float(t[0]))
        words = sum((get_words(t) for t in sorted_tokens), [])
        # Move articles (the/a/an) to the front of the chunk for English word order
        # FIND this entire block in add_chunk:
        ARTICLES = {'the', 'a', 'an', 'also'}
        FRONT_PREPOSITIONS = {'from', 'to', 'in', 'on', 'at', 'by', 'for',
                            'with', 'about', 'among', 'between', 'through',
                            'into', 'onto', 'upon', 'within', 'without',
                            'across', 'along', 'around', 'behind', 'below',
                            'beside', 'over', 'under', 'after', 'before',
                            'during', 'since', 'until'}
        prep_words = [w for w in words if w.lower() in FRONT_PREPOSITIONS]
        article_words = [w for w in words if w.lower() in ARTICLES]
        content_words = [w for w in words if w.lower() not in FRONT_PREPOSITIONS and w.lower() not in ARTICLES]
        if prep_words or article_words:
            content_lower = [w.lower() for w in content_words]
            unique_articles = [w for w in article_words if w.lower() not in content_lower]
            seen = set()
            deduped_content = []
            for w in content_words:
                wl = w.lower()
                if wl in {'the', 'a', 'an'} and wl in seen:
                    continue
                seen.add(wl)
                deduped_content.append(w)
            words = prep_words + unique_articles + deduped_content

        # REPLACE WITH:
        FOCUS_MARKERS = {'also', 'only', 'even', 'just', 'still', 'yet', 'already'}
        ARTICLES = {'the', 'a', 'an'}
        FRONT_PREPOSITIONS = {'from', 'to', 'in', 'on', 'at', 'by', 'for',
                            'with', 'about', 'among', 'between', 'through',
                            'into', 'onto', 'upon', 'within', 'without',
                            'across', 'along', 'around', 'behind', 'below',
                            'beside', 'over', 'under', 'after', 'before',
                            'during', 'since', 'until'}

        focus_words  = [w for w in words if w.lower() in FOCUS_MARKERS]
        prep_words   = [w for w in words if w.lower() in FRONT_PREPOSITIONS]
        article_words= [w for w in words if w.lower() in ARTICLES]
        content_words= [w for w in words if w.lower() not in FOCUS_MARKERS
                                        and w.lower() not in FRONT_PREPOSITIONS
                                        and w.lower() not in ARTICLES]

        if focus_words or prep_words or article_words:
            content_lower = [w.lower() for w in content_words]
            unique_articles = [w for w in article_words if w.lower() not in content_lower]
            seen = set()
            deduped_content = []
            for w in content_words:
                wl = w.lower()
                if wl in {'the', 'a', 'an'} and wl in seen:
                    continue
                seen.add(wl)
                deduped_content.append(w)
            # Order: focus markers first, then prepositions, then articles, then content
            words = focus_words + prep_words + unique_articles + deduped_content
        words_lower = [w.lower() for w in words]
        chunk = f"[{ ' '.join(words) }]{tag}"

        if not words:
            print(f"[DEBUG] {step} - Skipped (no words): {chunk}")
            return False
        
            # ADD THIS — exclude punctuation-only chunks
        if all(w in {'.', '?', '!', ',', ';', ':'} for w in words):
            print(f"[DEBUG] {step} - Skipped (punctuation only): {chunk}")
            return False
        
        if chunk in chunks:
            print(f"[DEBUG] {step} - Skipped (duplicate): {chunk}")
            return False

        # Check if tokens are already used
        if any(float(t[0]) in used_data_indices for t in tokens):
            print(f"[DEBUG] {step} - Skipped (indices used): {chunk}")
            return False

        # Verify words exist in sentence
        sentence_words_lower = [w.lower() for w in sentence_tokens]
        
        # Check if this chunk has ANY words that could be valid
        has_article_or_ne = any(
            w.startswith('#') or w in {'the', 'a', 'an', 'of', 'from', 'also'} 
            for w in words_lower
        )
        in_sentence = any(
            w in sentence_words_lower or any(w in sw for sw in sentence_words_lower)
            for w in words_lower
            if w not in {'<>'}
        )
        # NC-merged tokens won't appear in sentence — allow them through
        is_nc_chunk = any(
            len(t) > 7 and str(t[7]) in ('NC', 'NC_head')
            for t in tokens
        )

        if not in_sentence and not has_article_or_ne and not is_nc_chunk:
            print(f"[DEBUG] {step} - Skipped (no valid words in sentence): {chunk}")
            return False

        # Remove duplicate consecutive prepositions at word boundaries
        chunk = f"[{ ' '.join(words) }]{tag}"

        chunks.append(chunk)
        used_data_indices.update(float(t[0]) for t in tokens)
        used_words.update(words_lower)
        print(f"[DEBUG] {step} - Added: {chunk}")
        return True

    # --- Initialize ---
    tagged_data = sorted(PP_fulldata_dict_with_ids[key], key=sort_index)
    original_order = sentence.strip().split()
    has_rsm = any(len(t) > 10 and t[-1] == 'rsm' for t in tagged_data)


    def find_cond(cond):
        return [t for t in tagged_data if cond(t) and float(t[0]) not in used_data_indices and len(t) > 1]

    chunks = []
    used_data_indices = set()
    used_words = set()

        # --- Step -0.1: Merge rbks, nf, krya ---
   # --- Step -0.1 ---
    merge_calendar_construction()
    merge_meas_construction()
    merge_rbks_with_head()
    merge_nf_with_head()
    merge_nc_with_nc_head()
    merge_adj_with_noun_head()        # NEW: adj+noun before conj
    merge_complete_verbal_complexes()  # verb+krya (no longer marks main used)
    merge_conj_construction()          # conj after all noun merges
    merge_krya_with_main()
    merge_aux_neg_main()
    

    # --- Step 0: FIXED Enhanced modifier chain handling (BEFORE conjunction handling) ---
    
    # Find all interconnected modifier networks
    networks = find_complete_modifier_network()
    
    # Special handling: Build complete noun phrases including modifiers and conjunctions
    for network_indices in networks:
        # Skip if any token in the network is already used
        if any(idx in used_data_indices for idx in network_indices):
            continue
            
        # Get tokens for this network
        network_tokens = tokens_from_indices(network_indices)
        
        # ENHANCED: For each token in the network, check if it has conjunctions
        extended_tokens = list(network_tokens)
        
        # Check for conjunction relationships
        for token in network_tokens:
            token_idx = float(token[0])
            
            # Look for tokens that have conjunction relationships with this token
            for t in tagged_data:
                if (float(t[0]) not in used_data_indices and 
                    t not in extended_tokens):
                    
                    # Check if this token is part of a conjunction with our network token
                    if (len(t) >= 8 and len(token) >= 8 and 
                        t[-2] == token[-2] and t[-1] == token[-1] and  # Same head and relation
                        t[-1] in {'k2', 'k1', 'r6','k4'}):  # Common conjunction relations
                        extended_tokens.append(t)
                    
                    # Also check for 'conj' tokens that connect to this head
                    if (t[1] == 'conj' and len(t) >= 8 and len(token) >= 8 and
                        t[-2] == token[-2] and t[-1] == token[-1]):
                        extended_tokens.append(t)
        
        # Also look for modifiers of tokens in the extended network
        for token in list(extended_tokens):
            token_idx = float(token[0])
            
            # Find modifiers that point to this token
            for t in tagged_data:
                if (len(t) >= 8 and float(t[0]) not in used_data_indices and
                    t not in extended_tokens and
                    float_or_none(t[-2]) == token_idx and
                    t[-1] in {'mod', 'dem', 'quant', 'vkvn', 'intf', 'card', 'rdl', 'krvn'}):
                    extended_tokens.append(t)
        
        
        if len(extended_tokens) > 1:
            # Sort by index to maintain order
            def english_order_key(t):
                base = float(t[0])
                rel = t[-1] if len(t) >= 2 else ''
                head_val = t[-2] if len(t) >= 8 else None

                if rel == 'r6':
                    # Genitive: place AFTER its head noun
                    try:
                        head = float(head_val) if head_val else base
                        return head + 0.1
                    except (ValueError, TypeError):
                        pass
                elif rel == 'mod':
                    # Adjective modifier: place BEFORE its head noun
                    try:
                        head = float(head_val) if head_val else base
                        return head - 0.1
                    except (ValueError, TypeError):
                        pass
                return base

            extended_tokens_sorted = sorted(extended_tokens, key=english_order_key)
            
            # Determine if this should be tagged as _SUBJ
            has_subject = any(len(t) >= 8 and t[-1] in {'k1', 'rsm', 'pk1'} for t in extended_tokens_sorted)
            tag = '_SUBJ' if has_subject else ''
            
            
            if add_chunk(extended_tokens_sorted, tag, "Step 0 (complete extended network)", preserve_order=True):
                continue  # Move to next network
            else:
                pass
    
    # Handle individual modifiers that weren't part of networks
    for t in tagged_data:
        if (t[-1] in {'dem', 'quant', 'vkvn', 'mod', 'intf', 'card', 'rdl', 'rvks', 'krvn'} and 
            float(t[0]) not in used_data_indices):
            
            head_idx = float_or_none(t[-2]) if len(t) >= 4 else None
            head = find_token_by_index(head_idx) if head_idx else None
            
            if head and float(head[0]) not in used_data_indices:
                tag = '_SUBJ' if len(head) >= 8 and head[-1] in {'k1', 'rsm', 'pk1'} else ''
                add_chunk([t, head], tag, f"Step 0 ({t[-1]}+head)")
            else:
                add_chunk([t], "", f"Step 0 ({t[-1]} alone)")

    # Handle r6 tokens separately: attach AFTER their head noun (genitive order)
    # Handle r6 tokens separately
    for t in tagged_data:
        if t[-1] == 'r6' and float(t[0]) not in used_data_indices:
            head_idx = float_or_none(t[-2]) if len(t) >= 4 else None
            head = find_token_by_index(head_idx) if head_idx else None
            is_pron = (t[2] == 'p') if len(t) > 2 else False   # ← define once here
            
            if head and float(head[0]) not in used_data_indices:
                tag = '_SUBJ' if len(head) >= 8 and head[-1] in {'k1', 'rsm', 'pk1'} else ''
                head_words = get_words(head)
                r6_words = get_words(t)
                if is_pron:
                    merged_words = r6_words + head_words   # possessive BEFORE noun
                else:
                    merged_words = head_words + r6_words   # genitive AFTER noun
                merged_str = ' '.join(merged_words)
                chunk = f"[{merged_str}]{tag}"
                if chunk not in chunks:
                    chunks.append(chunk)
                    used_data_indices.add(float(t[0]))
                    used_data_indices.add(float(head[0]))
                    used_words.update(w.lower() for w in merged_words)
                    print(f"[DEBUG] Step 0 (r6+head) - Added: {chunk}")
            else:
                r6_words = get_words(t)
                r6_head_idx = float_or_none(t[-2]) if len(t) >= 4 else None
                appended = False
                if r6_words and chunks and r6_head_idx:
                    for ci in range(len(chunks)-1, -1, -1):
                        chunk_inner = chunks[ci].replace(']_SUBJ','').replace(']_ACTIVE','').replace(']_PASSIVE','').replace(']_IMPERATIVE','').strip('[]')
                        head_tok = None
                        for td in tagged_data:
                            try:
                                if float(td[0]) == r6_head_idx:
                                    head_tok = td
                                    break
                            except: pass
                        if head_tok:
                            head_words = get_words(head_tok)
                            if any(w.lower() in chunk_inner.lower() for w in head_words if w not in {'the','a','an','of'}):
                                suffix = ''
                                for s in ['_SUBJ','_ACTIVE','_PASSIVE','_IMPERATIVE']:
                                    if chunks[ci].endswith(s):
                                        suffix = s
                                        break
                                inner = chunks[ci][1:chunks[ci].rfind(']')]
                                if is_pron:
                                    chunks[ci] = '[' + ' '.join(r6_words) + ' ' + inner + ']' + suffix
                                else:
                                    chunks[ci] = '[' + inner + ' ' + ' '.join(r6_words) + ']' + suffix
                                used_data_indices.add(float(t[0]))
                                used_words.update(w.lower() for w in r6_words)
                                print(f"[DEBUG] Step 0 (r6 appended to chunk): {chunks[ci]}")
                                appended = True
                                break
                if not appended and r6_words:
                    for ci in range(len(chunks)-1, -1, -1):
                        if '_SUBJ' in chunks[ci]:
                            inner = chunks[ci][1:chunks[ci].rfind(']')]
                            if is_pron:
                                chunks[ci] = '[' + ' '.join(r6_words) + ' ' + inner + ']_SUBJ'
                            else:
                                chunks[ci] = '[' + inner + ' ' + ' '.join(r6_words) + ']_SUBJ'
                            used_data_indices.add(float(t[0]))
                            used_words.update(w.lower() for w in r6_words)
                            print(f"[DEBUG] Step 0 (r6 appended to SUBJ fallback): {chunks[ci]}")
                            break
    # --- Step -1: Handle remaining disjunction groups ---
    handle_disjunction_groups()

    # --- Step -0.5: Coordinated groups (rs) ---
    from collections import defaultdict
    rs_groups = defaultdict(list)
    for t in tagged_data:
        if t[-1] == 'rs' and t[-2]:
            rs_groups[float_or_none(t[-2])].append(t)
    for group in rs_groups.values():
        if len(group) >= 2:
            add_chunk(sorted(group, key=lambda t: float(t[0])), "", "Step -0.5 (rs)", preserve_order=True)

    # --- Step -0.3: Duration/range ---
    dur_groups = defaultdict(list)
    for t in tagged_data:
        if t[-1] in {'dur', 'k7t'} and t[-2]:
            dur_groups[float_or_none(t[-2])].append(t)
    for group in dur_groups.values():
        if group:
            add_chunk(sorted(group, key=lambda t: float(t[0])), "", "Step -0.3 (dur)", preserve_order=True)

    # --- Step 5: Subjects (for tokens not already in chains) ---
    for subj in find_cond(lambda t: t[-1] in {'k1', 'pk1'}):
        add_chunk([subj], '_SUBJ', "Step 5 (subject)")
    # rsm = "near/proximity" - treated as location, not subject
    for subj in find_cond(lambda t: t[-1] == 'rsm'):
        add_chunk([subj], '_SUBJ', "Step 5 (rsm subject)")

    # --- Step 6.5: Handle 'rh' (reason) ---
    for rh in find_cond(lambda t: t[-1] == 'rh'):
        head_idx = float_or_none(rh[-2]) if len(rh) >= 8 else None
        h = find_token_by_index(head_idx) if head_idx else None
        if h and float(h[0]) not in used_data_indices:
            add_chunk([rh, h], "", "Step 6.5 (rh+head)")
        else:
            add_chunk([rh], "", "Step 6.5 (rh alone)")

    # --- Step 8: intf/mod + adj ---
    for i in range(len(tagged_data) - 1):
        t = tagged_data[i]
        nxt = tagged_data[i+1]
        if (len(t) > 2 and len(nxt) > 2 and t[2] == 'adj' and 
            len(t) >= 8 and t[-1] in {'intf', 'mod'} and nxt[2] == 'adj'):
            if float(t[0]) not in used_data_indices and float(nxt[0]) not in used_data_indices:
                add_chunk([t, nxt], "", "Step 8 (adj+adj)")

    # --- Step 9.5: Spatio-temporal sequences ---
    PREPOSITION_RELATIONS = {
        'k7t', 'k3', 'k5', 'k5prk', 'k7', 'k7p', 'k7a', 'k2p',
        'rblak', 'rt', 'rblpk', 'rn', 'rd', 'rp', 'r6',
        'rask1', 'rask2', 'rask3', 'rask4', 'rask5', 'rask7',
        'k1as', 'k2as', 'k3as', 'k4as', 'k5as', 'k7as',
        'quantless', 'quantmore', 'rkl', 'rh', 'rasneg', 'rv',
        'k4', 'k4a', 'ru', 'k2s', 'rbks', 'nf'
    }
    candidates = [t for t in tagged_data if len(t) >= 8 and t[-1] in PREPOSITION_RELATIONS
                  and float(t[0]) not in used_data_indices
                  and not (len(t) > 2 and t[2] == 'v')]  # exclude verbal rbks
    for t in sorted(candidates, key=lambda t: float(t[0])):
        if float(t[0]) not in used_data_indices:
            add_chunk([t], "", "Step 9.5 (preposition-bearing single)", preserve_order=True)

    # --- Step 9.7: Auxiliary + Main Verb Complexes ---
    
    # Find auxiliary verbs
    aux_verbs = []
    for t in tagged_data:
        if (len(t) > 8 and 'auxiliary' in str(t[-3]) and 
            float(t[0]) not in used_data_indices):
            aux_verbs.append(t)
    
    # Find main verbs
    main_verbs = []
    for t in tagged_data:
        if (len(t) > 8 and 'main' in str(t[-3]) and 
            float(t[0]) not in used_data_indices):
            main_verbs.append(t)
    
    # Try to pair auxiliary verbs with main verbs
    for aux in aux_verbs[:]:  # Use slice to avoid modification during iteration
        aux_idx = float(aux[0])
        
        # Find main verb with same base index or closest following main verb
        matching_main = None
        
        # First, look for exact base index match (e.g., 12.1 aux matches with 12 main)
        base_aux_idx = int(aux_idx) if aux_idx != int(aux_idx) else aux_idx
        for main in main_verbs:
            main_idx = float(main[0])
            if main_idx == base_aux_idx:
                matching_main = main
                break
        
        # If no exact match, find the closest following main verb
        if not matching_main:
            for main in main_verbs:
                main_idx = float(main[0])
                if main_idx > aux_idx:
                    matching_main = main
                    break
        
        # Create the auxiliary + main verb chunk
        if matching_main:
            # Order them properly (auxiliary first, then main)
            verb_complex = [aux, matching_main] 
            
            verb_tag = get_verb_tag(verb_complex, sentence_type)
            if add_chunk(verb_complex, verb_tag, "Step 9.7 (aux+main)", preserve_order=True):
            # if add_chunk(verb_complex, "", "Step 9.7 (aux+main)", preserve_order=True):
                # Remove from lists to avoid reprocessing
                if aux in aux_verbs:
                    aux_verbs.remove(aux)
                if matching_main in main_verbs:
                    main_verbs.remove(matching_main)
                print(f"[DEBUG] Created aux+main complex: {aux[1]} + {matching_main[1]}")
            else:
                print(f"[DEBUG] Failed to create aux+main complex: {aux[1]} + {matching_main[1]}")
        else:
            pass
    
    # Handle remaining auxiliary verbs alone
    for aux in aux_verbs:
        if float(aux[0]) not in used_data_indices:
            add_chunk([aux], "", "Step 9.7 (aux alone)")
    
    # Handle remaining main verbs alone  
    for main in main_verbs:
        if float(main[0]) not in used_data_indices:
            verb_tag = get_verb_tag([main], sentence_type)
            add_chunk([main], verb_tag, "Step 9.7 (main alone)")

    # --- Step 10: Remaining Verb Complexes ---
    
    main_verbs = []
    for t in tagged_data:
        # Skip if already processed
        if float(t[0]) in used_data_indices:
            continue
            
        if (len(t) > 2 and t[2] == 'v' and float(t[0]).is_integer()):
            if len(t) > 8 and ('main' in str(t[-3]) or 'inf' in str(t[-3])):
                main_verbs.append(t)
            elif len(t) > 8 and len(t) > 10 and t[-1] != 'rpk':
                main_verbs.append(t)

    # Also include compound verbs (verbs with spaces)
    for t in find_cond(lambda x: len(x) > 1 and x[1] and ' ' in x[1] and len(x) > 2 and 'v' in str(x[2])):
        if t not in main_verbs:
            main_verbs.append(t)

    for main in main_verbs:
        # Skip if already processed
        if float(main[0]) in used_data_indices:
            continue
            
        parts = [main]
        main_idx = float(main[0])

        # Handle main + rpk, krya etc.
        rpk_token = next(
            (t for t in find_cond(
                lambda x: len(x) > 10 and x[-1] == 'rpk' and float_or_none(x[-2]) == main_idx
            )),
            None
        )
        if rpk_token:
            parts = [rpk_token, main]

        parts = sorted(parts, key=lambda t: float(t[0]))
        # add_chunk(parts, "", "Step 10 (verb complex)", preserve_order=True)
        verb_tag = get_verb_tag(parts, sentence_type)
        add_chunk(parts, verb_tag, "Step 10 (verb complex)", preserve_order=True)

    # --- Step 11: Fallback for remaining tokens ---
    remaining = [t for t in tagged_data if float(t[0]) not in used_data_indices]
    remaining.sort(key=lambda t: (0 if len(t) > 2 and t[2] in {'n','v','adj','adv'} else 1, float(t[0])))
    
    for t in remaining:
        words = get_words(t)
        if words:
            words_lower = [w.lower() for w in words]
            if any(w not in used_words for w in words_lower):
                add_chunk([t], "", "Step 11 (fallback)")

    # --- Step 12: Handle unused sentence tokens ---
    for word in sentence_tokens:
        word_lower = word.lower()
        if word_lower not in used_words and word != '.' and word != '<>':
            dummy_token = next((t for t in tagged_data if t[1] == word), None)
            if not dummy_token:
                dummy_token = (0.0, word, '', '', '', '', '', '', '', '', '')
            add_chunk([dummy_token], "", "Step 12 (unused word)")

    # --- Final Reordering ---
    def first_index(chunk):
        words = get_words_from_chunk(chunk)
        valid = [original_order.index(w) for w in words if w in original_order]
        return min(valid) if valid else len(original_order)

    unique_chunks = list(dict.fromkeys(chunks))
    subj = [c for c in unique_chunks if c.endswith('_SUBJ')]
    reg = [c for c in unique_chunks if c not in subj]

    subj.sort(key=first_index)
    reg.sort(key=first_index)

    result = " ".join(subj + reg)
    print(f"[DEBUG] Final Output: {result}")
    
    # Final check for missing words
    final_words = set()
    for chunk in unique_chunks:
        inner = re.sub(r'\]_\w+', '', chunk).strip('[]')
        for w in inner.split():
            final_words.add(w.lower())
    
    missing_words = [w for w in sentence_tokens 
                     if w.lower() not in final_words 
                     and w != '.' 
                     and w != '<>']
    if missing_words:
        print(f"[WARNING] Missing words detected: {missing_words}")
        for word in missing_words:
            result += f" [{word}]"
    
    return result  # ← make sure this line exists and is not inside an if block
#     nlp = spacy.load("en_core_web_sm")

#     # Replace special characters and apply # rule after lowering
#     def transform_word(word):
#         word = word.lower()  # convert to lowercase first
#         if "#" in word:
#             word = word.replace("#", "")
#             word = word.replace("w", "t").replace("x", "d")
#         return word.replace("*", "")

#     # Apply transformation to each word
#     words = text.split()
#     transformed_words = [transform_word(word) for word in words]
#     cleaned_text = " ".join(transformed_words)

#     doc = nlp(cleaned_text)

#     segments = []
#     i = 0
#     interrogatives = {"where", "what", "when", "who", "whom", "whose", "why", "how", "which"}
#     quantifier_pos = {"NUM", "DET"}

#     while i < len(doc):
#         token = doc[i]
#         lower_text = token.text.lower()

#         if token.dep_ == "prep" or token.tag_ == "IN":
#             phrase = [token.text]
#             i += 1
#             while i < len(doc) and doc[i].pos_ in {"DET", "ADJ", "NOUN", "PROPN", "PRON"}:
#                 phrase.append(doc[i].text)
#                 i += 1
#             segments.append("[" + " ".join(phrase) + "]")
#             continue

#         if token.tag_ == "VBG":
#             phrase = [token.text]
#             i += 1
#             while i < len(doc) and doc[i].pos_ in {"ADP", "DET", "NOUN", "PROPN", "ADV"}:
#                 phrase.append(doc[i].text)
#                 i += 1
#             segments.append("[" + " ".join(phrase) + "]")
#             continue

#         if lower_text in interrogatives:
#             segments.append("[" + token.text + "]")
#             i += 1
#             continue

#         if token.pos_ in quantifier_pos and i + 1 < len(doc) and doc[i + 1].pos_ in {"ADJ", "NOUN", "PROPN"}:
#             phrase = [token.text]
#             i += 1
#             while i < len(doc) and doc[i].pos_ in {"NUM", "DET", "ADJ", "NOUN", "PROPN"}:
#                 phrase.append(doc[i].text)
#                 i += 1
#             segments.append("[" + " ".join(phrase) + "]")
#             continue

#         if token.text.lower() in {"while", "because", "although", "though", "if", "unless", "until"}:
#             segments.append("[" + token.text + "]")
#             i += 1
#             continue

#         if token.pos_ in {"AUX", "VERB"}:
#             phrase = [token.text]
#             i += 1
#             while i < len(doc) and doc[i].pos_ in {"AUX", "VERB"}:
#                 phrase.append(doc[i].text)
#                 i += 1
#             while i < len(doc) and doc[i].pos_ in {"ADV", "ADP", "DET", "NOUN", "PROPN", "PRON"}:
#                 phrase.append(doc[i].text)
#                 i += 1
#             if i < len(doc) and doc[i].pos_ == "PUNCT":
#                 phrase.append(doc[i].text)
#                 i += 1
#             segments.append("[" + " ".join(phrase) + "]")
#             continue

#         if token.pos_ in {"NOUN", "PROPN", "PRON"}:
#             segments.append("[" + token.text + "]")
#             i += 1
#             continue

#         if token.pos_ == "PUNCT":
#             if segments and segments[-1].endswith("]"):
#                 segments[-1] = segments[-1][:-1] + " " + token.text + "]"
#             else:
#                 segments.append("[" + token.text + "]")
#             i += 1
#             continue

#         segments.append(token.text)
#         i += 1

#     return " ".join(segments)



# def add_verb_dict(filtered_data, verb_dict, morph_mapping):
#     def add_verb_dict(output_words, verb_dict, morph_mapping):
#         words = output_words[:]  # make a copy

#         for index, verb in sorted(verb_dict.items(), reverse=True):
#             key = str(index)
#             if key in morph_mapping:
#                 _, word = morph_mapping[key]
#                 if word in words:
#                     insert_index = words.index(word) + 1
#                     words.insert(insert_index, verb)
#         return words

#     updated_data = {}

#     for sent_id, sentence_set in filtered_data.items():
#         new_sentences = set()

#         for sentence in sentence_set:
#             words = sentence.strip().split()
#             modified_words = add_verb_dict(words, verb_dict, morph_mapping)
#             new_sentence = ' '.join(modified_words)
#             new_sentences.add(new_sentence)

#         updated_data[sent_id] = new_sentences

#     return updated_data










def handle_unprocessed(index_data, depend_data, output_data, processed_nouns, construction_data):
    """
    Swaps gender info for nouns that do not exist in the dictionary.
    
    Args:
        index_data (list): Maps indices of `output_data` to corresponding indices in `processed_nouns`.
        depend_data (list): Dependency information for each word.
        output_data (list): Processed words from the sentence.
        processed_nouns (list): List of tuples representing processed nouns.
        
    Returns:
        tuple: A tuple containing a boolean indicating if changes were made and the updated `processed_nouns`.
    """
    has_changes = False

    # Ensure index_data is a list
    if not isinstance(index_data, list):
        raise ValueError("index_data must be a list mapping indices.")

    for dataIndex, data in enumerate(output_data):
        # Check if the current word starts with '#'
        if data.startswith('#'):
            # Get the corresponding index in processed_nouns
            if dataIndex >= len(index_data):
                continue  # Skip if index_data does not have a mapping for this dataIndex
            noun_index = index_data[dataIndex]

            # Find the matching noun in processed_nouns
            for i, noun in enumerate(processed_nouns):
                if round(noun[0]) == noun_index and len(noun) > 2 and noun[2] == 'n':
                    print(construction_data[i].split(':')[1] if ':' in construction_data[i] else "No ':' found")
                    
                    # Check if depend_data[i] exists and contains ':'
                    depend_check = depend_data[i] and isinstance(depend_data[i], str) and ':' in depend_data[i]
                    construction_check = construction_data[i] and isinstance(construction_data[i], str) and ':' in construction_data[i]

                    # Get dependency tags safely
                    depend_tag = depend_data[i].split(':')[1] if depend_check else ""
                    construction_tag = construction_data[i].split(':')[1] if construction_check else ""

                    # If either condition matches, update noun POS tag
                    if depend_tag == 'k1s' or construction_tag == 'kriyAmUla':
                        temp = list(noun)
                        temp[2] = 'adj'
                        processed_nouns[i] = tuple(temp)
                        has_changes = True
                        break  # Exit loop after first match

                    # Swap gender if the noun is not a proper noun or special type
                    if noun[7] not in ('proper', 'NC', 'CP_noun', 'abs', 'vn'):
                        temp = list(noun)
                        temp[4] = 'f' if noun[4] == 'm' else 'm'
                        processed_nouns[i] = tuple(temp)
                        has_changes = True
                        log(f'{temp[1]} reprocessed as noun with gen:{temp[4]}.')
                    break  # Stop searching once the noun is found
        elif data.startswith('*'):
            has_changes = True
    log(f'processed_nouns after handling # :{processed_nouns}')
    return has_changes, processed_nouns

def nextNounData_fromFullData(fromIndex, PP_FullData):
    index = fromIndex
    # ##print(index,'ind',PP_FullData)
    for data in PP_FullData:
        if data[0]==index and data[2] == 'n':
            return data
    return ()

def is_next_word_noun(index,processed_nouns):
    for data in processed_nouns:
        if data[0]==index and data[2]=='n':
            return data
            # return data
    else:
        return False

def nextNounData(fromIndex, word_info):
    #for NC go till NC_head and return that tuple
    # index = fromIndex
    # for i in range(len(word_info)):
    #     for data in word_info:
    #         if index == data[0]:
    #             if data[3] != '' and index != fromIndex:
    #                 return data
    index = fromIndex
    # ##print(index,'indx')
    for data in word_info:
        # if index == data[0] and data[3] != '':
        data=list(data)
        if index == str(data[0]):
            if 'female' in data[2]:
                data[2]='f'
            elif 'male' in data[2]:
                data[2]='m'
            if 'pl' in data[3]:
                data[3]='p'
            elif data[3]!='':
                data[3]='s'
            data=tuple(data)
            return data
                # if ':' in data[4]:
                #     index = int(data[4][0])
    return False

def fetchNextWord(index,index_data, words_info):
    next_word = ''
    idx = index_data[index]
    for data in words_info:
        if idx == data[0]:
            next_word = clean(data[1])
            break
    return next_word

def change_gender(current_gender):
    """
    >>> change_gender('m')
    'f'
    >>> change_gender('f')
    'm'
    """
    return 'f' if current_gender == 'm' else 'm'

def set_gender_make_plural(processed_words, g, num):
    process_data = []
    # for all k1s and main verb change gender to female and number to plural
    for i in range(len(processed_words)):
        word_list = list(processed_words[i])
        if word_list[2] == 'adj':
            # 4th index - gender, 5th index - number
            word_list[4] = g
            word_list[5] = num
        elif word_list[2] == 'v':
            # 3rd index - gender, 4th index - number
            word_list[3] = g
            word_list[4] = num
        process_data.append(tuple(word_list))
    return process_data

def set_main_verb_tam_zero(verb: Verb):
    verb.tam = 0
    return verb

def get_additional_word(relation, index):
    value_mapping = {'rpk': 'after','rsk':'while','rblpk':'before','rblak':"after",'rblsk':'while','rvks':'','rbks':'after'}
   
    mapped_value = value_mapping.get(relation, relation)  # fallback if not found
    nonfinite_dict = {index: mapped_value}
    return nonfinite_dict


def set_tam_for_nonfinite(dependency):
    '''
    Sets the TAM (Tense-Aspect-Mood) for non-finite verb forms based on the given dependency code.

    Parameters:
        dependency (str): The dependency code indicating the type of non-finite form.

    Returns:
        str: The TAM code for the given non-finite form.

    Examples:
        >>> set_tam_for_nonfinite('rvks')
        'adj_wA_huA'
        >>> set_tam_for_nonfinite('rbks')
        'yA_huA'
        >>> set_tam_for_nonfinite('rsk')
        'wA_huA'
        >>> set_tam_for_nonfinite('rpk')
        'kara'
    '''
    tam = {
        # 'rvks': 'adj_wA_huA',
        'rpk': 'ing',
        'rsk': 'ing',
        'rblpk':'ing',
        'rvks':'ing',
        'rblak':'ing',
        'rblsk':'ing',
        'rbks':'en'
        
        
        # 'rbks': 'adj_yA_huA',
        # 'rblpk': 'nA',
        # 'rbk': 'yA_gayA',
    }.get(dependency, '')
    return tam

def update_ppost_dict(data_index, param):
    # whether entry exists or not, param is updated in ppost_dict
    processed_postpositions_dict[data_index] = param

import importlib
import os
import sys

def extract_tamdict(lang):
    """
    Extract TAM entries by reading the language-specific TAM_DICT_FILES
    defined in language rule files (e.g., hi.py, en.py), then read the .dat file.
    
    Args:
        lang (str): ISO 2-letter language code (e.g., 'hi', 'en')
    
    Returns:
        list: List of TAM strings read from the file
    """
    tam_list = []

    try:
        # Import the language-specific module
        lang_module = importlib.import_module(f'language_rules.{lang}')
        
        # Get TAM_DICT_FILES from the module
        tam_dict_files = getattr(lang_module, 'TAM_DICT_FILES', None)

        if not tam_dict_files or not isinstance(tam_dict_files, dict):
            print(f"Invalid or missing TAM_DICT_FILES in '{lang}' module.")
            return []

        # Get the file path using the language code as key
        tam_file_path = tam_dict_files.get(lang)

        if not tam_file_path:
            print(f"No TAM dictionary configured for language code: {lang}")
            return []

        # Read TAM entries from the file
        with open(tam_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    tam_list.append(line)
        return tam_list

    except ImportError:
        print(f"Language module not found: language_rules.{lang}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error loading TAM dictionary for '{lang}': {e}", file=sys.stderr)
        return []




def extract_gnp_noun(noun_data):
    gender = 'm'
    number = 's'
    person = 'a'

    if len(noun_data):
        noun_term = noun_data[1]
        if check_is_digit(noun_term):
            noun_term = noun_term
        elif '+' in noun_term:
            cn_terms = noun_term.strip().split('+')
            for i in range(len(cn_terms)):
                if i == len(cn_terms) - 1:
                    noun_term = clean(cn_terms[i])
        else:
            noun_term = clean(noun_term)

        #Setting gender
        seman_data = noun_data[2].strip()
        #seman_info_lst = seman_data.split()
        if len(seman_data) > 0:
            if 'female' in seman_data:
                gender = 'f'
            elif 'male' in seman_data:
                gender = 'm'
        # else:
            # tags = find_tags_from_dix(noun_term)
            # # ##print(tags,'tags2')
            # if '*' not in tags['form']:
            #     gender = tags['gen']

        #Setting number
        if len(noun_data[3]):
            # number = noun_data[3].strip()[0]
            if noun_data[3] =='':
                number = 's'
            elif 'pl' in noun_data[3]:
                number = 'p'
            # number = noun_data[3].strip()[3]

        #Setting person
        if noun_term == 'speaker':
            person = 'u'
        elif noun_term == 'addressee':
            person = 'm'
        else:
            person = 'a'
    return gender, number, person

def extract_gnp(data):
    gender = 'm'
    number = 's'
    person = 'a'

    if len(data):
        term = clean(data[1])

        # Setting gender
        seman_data = data[2].strip()
        # seman_info_lst = seman_data.split()
        if len(seman_data) > 0:
            if 'female' in seman_data:
                gender = 'f'
            elif 'male' in seman_data:
                gender = 'm'

        # Setting number
        if len(data[3]):
            if data[3]=='pl':
                number = 'p'
            else:
                number = 's'

        # Setting person
        if term == 'speaker':
            person = 'u'
        elif term == 'addressee':
            person = 'm'
        else:
            person = 'a'
    # ##print(number,'gl')
    return gender, number, person

def add_postposition(transformed_fulldata, index_data, depend_data, processed_postpositions):
    PPFulldata = []
    
    # Special location words that already imply direction
    LOCATION_WORDS = {'here', 'there', 'somewhere', 'everywhere', 'nowhere',
                      'where', 'anywhere', 'herein', 'therein'}

    for i, ele in enumerate(depend_data):
        if 'rs' in ele:
            ind0, ind1 = index_data[i-1], index_data[i]
            if ind0 in processed_postpositions_dict:
                processed_postpositions_dict[ind1] = processed_postpositions_dict.pop(ind0)

    last_store_index = None
    last_r6post = None

    for data in transformed_fulldata:
        index = data[0]
        temp = list(data)
        ppost = processed_postpositions.get(index)

        if isinstance(ppost, str) and ":" in ppost:
            last_store_index, last_r6post = ppost.split(':', 1)
            temp[8] = None
            ppost = None

        if str(temp[0]) == last_store_index:
            ppost = last_r6post
            temp[8] = ppost

        POSSESSIVE_FORMS = {'its', 'his', 'her', 'their', 'my', 'our', 
                            'your', 'whose', 'own'}

        # ← ADD THIS BLOCK - Step 4 fix
        # If word is a location pronoun (here/there), remove postposition
        # because "in here" / "in there" is wrong English
        if (temp[2] == 'p' and 
            temp[1].lower().strip() in LOCATION_WORDS and
            ppost in ('in', 'at', 'on', 'to', 'from')):
            ppost = None
            processed_postpositions_dict[index] = None
            print(f"[DEBUG] Removed postposition '{ppost}' from location word '{temp[1]}'")
        # ← END ADD

        if ppost is not None and temp[2] in ('n', 'vn', 'p'):
            if str(ppost) != '<>':  # skip mask placeholder
                DISCOURSE_MARKERS = {
                    'only', 'really', 'a few', 'as soon as', 'even',
                    'also', 'any', 'even a single', 'may', 'even while',
                    'so', 'more', 'quite', 'nearly', 'almost', 'yes',
                    'exactly', 'amount', 'about', 'just', 'too', 'indeed'
                }
                words = temp[1].split()
                # Find how many leading words are discourse markers
                insert_pos = 0
                for w in words:
                    if w.lower() in DISCOURSE_MARKERS:
                        insert_pos += 1
                    else:
                        break
                # Insert preposition after discourse markers
                words.insert(insert_pos, str(ppost))
                temp[1] = ' '.join(words)
        elif ppost is not None and temp[2] == 'p':
            if temp[1].lower() not in POSSESSIVE_FORMS:
                temp[1] = str(ppost) + ' ' + temp[1]

        PPFulldata.append(tuple(temp))

    return PPFulldata




def add_adj_to_noun_attribute(key, value):
    if key is not None:
        if key in repository.constant.noun_attribute:
            repository.constant.noun_attribute[key][0].append(value)
        else:
            repository.constant.noun_attribute[key] = [[],[]]

def add_verb_to_noun_attribute(key, value):
    if key is not None:
        if key in repository.constant.noun_attribute:
            repository.constant.noun_attribute[key][1].append(value)
        else:
            repository.constant.noun_attribute[key] = [[], []]

def add_spkview(full_data, spkview_dict):
    PREPOSITIONS = {
        'in', 'on', 'at', 'of', 'from', 'to', 'by', 'with', 'for',
        'about', 'among', 'between', 'through', 'into', 'onto', 'upon',
        'within', 'without', 'across', 'along', 'around', 'behind',
        'below', 'beside', 'over', 'under', 'after', 'before',
        'according', 'less', 'more', 'via', 'than', 'like', 'because',
        'the', 'a', 'an', '<>'
    }
    # Discourse markers that must go at the very beginning
    # before any preposition or article
    DISCOURSE_MARKERS = {
        'only', 'really', 'a few', 'as soon as', 'even', 'also',
        'any', 'even a single', 'may', 'even while', 'so', 'more',
        'quite', 'nearly', 'almost', 'yes', 'exactly', 'amount',
        'about', 'also', 'only', 'even', 'just', 'too', 'indeed'
    }
    # Articles that go AFTER preposition but BEFORE the noun
    ARTICLES = {'the', 'a', 'an'}

    transformed_data = []
    for data in full_data:
        index = data[0]
        spk_info = (spkview_dict.get(index) or
                    spkview_dict.get(str(index)) or
                    spkview_dict.get(int(index) if str(index).isdigit() else index))
        if spk_info:
            temp = list(data)
            for info in spk_info:
                tag = info[0]
                val = info[1]
                if tag == 'respect':
                    words = temp[1].split()
                    for i in range(len(words) - 1, -1, -1):
                        if words[i].lower() not in {'the', 'a', 'an', 'of', 'in', 'on', 'at'}:
                            words[i] = words[i] + '_(respect)'
                            break
                    temp[1] = ' '.join(words)
                elif tag == 'before':
                    if val in DISCOURSE_MARKERS:
                        # Discourse marker goes at the very beginning
                        # before preposition and article
                        # e.g. "in the haswinApura" → "only in the haswinApura"
                        # e.g. "a XAma" → "also a XAma"
                        temp[1] = val + ' ' + temp[1]
                    elif val in ARTICLES:
                        # Article goes after preposition but before noun
                        # e.g. "in haswinApura" → "in the haswinApura"
                        # e.g. "from steSana" → "from the steSana"
                        words = temp[1].split()
                        insert_pos = 0
                        for i, w in enumerate(words):
                            if w.lower() in PREPOSITIONS - ARTICLES:
                                insert_pos = i + 1
                            else:
                                break
                        words.insert(insert_pos, val)
                        temp[1] = ' '.join(words)
                    else:
                        # Default: prepend at beginning
                        temp[1] = val + ' ' + temp[1]
                elif tag == 'after':
                    temp[1] = temp[1] + ' ' + val
            data = tuple(temp)
        transformed_data.append(data)
    return transformed_data
def add_MORPHO_SEMANTIC(full_data, MORPHO_SEMANTIC_DICT):
    transformed_data = []
    for data in full_data:
        index = data[0]
        if index in MORPHO_SEMANTIC_DICT:
            temp = list(data)
            term = MORPHO_SEMANTIC_DICT[index]
            for t in term:
                tag = t[0]
                val = t[1]
                if tag == 'before':
                    temp[1] = val + ' ' + temp[1]
                else:
                    temp[1] = temp[1] + ' ' + val
            data = tuple(temp)
        transformed_data.append(data)
    return transformed_data

def add_construction(transformed_data, construction_dict):
    Constructdata = []
    dependency_check = ['k7p', 'k7t']
    add_words_list = ['meM', 'ko', 'ke', 'kI', 'kA']
    depend_data1 = ''
    
    for data in transformed_data:
        index = data[0]
        if len(data) == 9:
            depend_data1 = data[8]

        if index in construction_dict:
            temp = list(data)
            # Remove duplicate (tag, val) pairs
            unique_terms = list(dict.fromkeys(construction_dict[index]))  # preserves order

            for tag, val in unique_terms:
                if tag == 'before':
                    temp[1] = val + ' ' + temp[1]
                else:
                    if val in [',', '-']:
                        temp[1] = temp[1] + val
                    else:
                        if depend_data1 and depend_data1 in add_words_list and depend_data1 in temp[1]:
                            temp[1] = temp[1].split()[0] + ' ' + val
                        else:
                            temp[1] = temp[1] + ' ' + val

            data = tuple(temp)

        Constructdata.append(data)
        
    return Constructdata


def add_additional_words(additional_words_dict, processed_data):
    additionalData = []
    for data in processed_data:
        index = data[0]
        if index in additional_words_dict:
            temp = list(data)
            term = additional_words_dict[index]
            for t in term:
                tag = t[0]
                val = t[1]
                if tag == 'before':
                    temp[1] = val + ' ' + temp[1]
                else:
                    temp1=temp[1].split()
                    if len(temp1)>=2 and temp1[1]=='ko':
                        temp1[1] = val
                        temp[1] = ' '.join(temp1)
                    else:
                        temp[1] = temp[1] + ' ' + val
            data = tuple(temp)
        additionalData.append(data)
    return additionalData

# post_process_utils.py

def add_coreferences(segment_id, index_data, words_info, json_output, discourse_data, coref_list):
    """
    Process coreferences and return the updated coref list.
    """
    # sub_coref_list=[]
    # if 'coref' in discourse_data[i]:  # No '.' in discourse_head, simpler case
    #     sub_coref_list.append(index_data[i])
    #     indx=int(discourse_data[i].split(':')[0])
    #     for processed_word in processed_words:
    #         if processed_word[0]==indx:  # Check if indx is composed entirely of digits
    #             coref_word = processed_word[1]
    #             # morpho_sem = processed_word[3]
    #             sub_coref_list.append(coref_word)

    #             break

    # if sub_coref_list:  # Append to coref_list if there's any coreference info
    #     coref_list.append(sub_coref_list)
    return process_coref(segment_id, index_data, words_info, json_output, discourse_data, coref_list)

def clean_post_process_output(post_process_output, processed_foreign_words):
    """
    Clean and update the post-process output with foreign words.
    """
    for i in range(len(processed_foreign_words)):
        n = processed_foreign_words[i][0]
        post_process_output[n - 1] = processed_foreign_words[i][1].replace('+', ' ')
    return ' '.join(post_process_output)

def add_discourse_elements_to_output(discourse_data,discourse, spkview_data, sp_data, post_process_output):
    """
    Add discourse elements to the output based on given data.
    """
    if not discourse_data:  # Check if discourse_data is None or empty
        return post_process_output
    relation = ['AvaSyakawApariNAma', 'vyaBicAra']
    if discourse and discourse in relation:
        return add_discourse_elements(discourse, spkview_data, sp_data, post_process_output)
    for i in discourse_data:
        if i and i.split(':')[1] not in relation and 'coref' not in i:
            post_process_output = add_discourse_elements(discourse_data, spkview_data, sp_data, post_process_output)
    return post_process_output

def check_special_conditions(discourse_data, spkview_data, post_process_output):
    """
    Modify the post-process output based on specific conditions.
    """
    for i in discourse_data:
        if 'AvaSyakawApariNAma' in i and 'nahIM' not in spkview_data:
            return 'if' + post_process_output
        elif 'vyaBicAra' in i:
            return 'although' + post_process_output
    return post_process_output


def fetch_NC_head(i, processed_words):
    for data in processed_words:
        temp = tuple(data)
        if int(temp[0]) == int(i) and temp[7] == 'NC_head':
            return temp[0]
        


def auxmap(aux_verb, lang):
    """
    Finds all non-overlapping auxiliary chunks in longest-first priority.
    Returns list of (matched_chunk, root, TAMs).
    """
    import importlib
    import sys

    lang_module = importlib.import_module(f'language_rules.{lang}')
    aux_map_files = getattr(lang_module, 'AUX_MAP_FILE', None)
    aux_file_path = aux_map_files.get(lang)

    if not aux_file_path:
        log(f'No mapping file defined for language: {lang}', 'ERROR')
        return []

    # Load auxiliary mapping into dictionary
    aux_dict = {}
    try:
        with open(aux_file_path, 'r') as tamfile:
            for line in tamfile:
                parts = line.strip().split(',')
                key = parts[0]
                if lang == 'hi':
                    aux_dict[key] = (parts[1], parts[2])
                else:
                    aux_dict[key] = (parts[1], parts[2:])
    except FileNotFoundError:
        log(f'Auxiliary mapping file not found: {aux_file_path}', 'ERROR')
        sys.exit()

    parts = aux_verb.split('_')
    n = len(parts)
    matched_results = []
    covered_indices = set()

    for k in range(n, 0, -1):  # Try lengths 4→1
        for i in range(n - k + 1):
            # Skip if any of these indices already matched
            if any(j in covered_indices for j in range(i, i + k)):
                continue
            candidate = '_'.join(parts[i:i + k])
            if candidate in aux_dict:
                root, tam = aux_dict[candidate]
                log(f'Found match: "{candidate}" from "{aux_verb}"', 'INFO')
                matched_results.append((candidate, root, tam))
                # Mark these indices as covered
                covered_indices.update(range(i, i + k))

    # Warn for unmatched words
    for idx, word in enumerate(parts):
        if idx not in covered_indices:
            log(f'"{word}" not found in auxiliary mapping.', 'WARNING')

    return matched_results



# def auxmap_hin(aux_verb,lang):
#     """
#     Finds auxiliary verb in auxiliary mapping file. Returns its root and tam.
#     >>> auxmap_hin('sakawA')
#     ('saka', 'wA')
#     """
#     # ##print(aux_verb)
#     # try:
 

#     with open(AUX_MAP_FILE, 'r') as tamfile:
#         for line in tamfile.readlines():
#             # ##print(line,'lll')
#             aux_mapping = line.strip().split(',')
#             if aux_mapping[0] == aux_verb:
#                 return aux_mapping[1], aux_mapping[2]
#     log(f'"{aux_verb}" not found in auxiliary mapping.', 'WARNING')
#     #     return None, None       # TODO Figure out the fallback
#     # except FileNotFoundError:
#     #     log('auxiliary Mapping File not found.', 'ERROR')
#     #     sys.exit()

# def auxmap_en(aux_verb):
#     """
#     Finds auxiliary verb in auxiliary mapping file. Returns its root and tam.
#     >>> auxmap_hin('sakawA')
#     ('saka', 'wA')
#     """
#     # ##print(aux_verb)
#     # try:
#     with open(AUX_MAP_FILE, 'r') as tamfile:
#         for line in tamfile.readlines():
#             # ##print(line,'lll')
#             aux_mapping = line.strip().split(',')
#             if aux_mapping[0] == aux_verb:
#                 return aux_mapping[1], aux_mapping[2:]
#     log(f'"{aux_verb}" not found in auxiliary mapping.', 'WARNING')
#     #     return None, None       # TODO Figure out the fallback
#     # except FileNotFoundError:
#     #     log('auxiliary Mapping File not found.', 'ERROR')
#     #     sys.exit()

def update_additional_words_dict(index, tag, add_word):
    value = (tag, add_word)
    value_found = False
    if index in additional_words_dict:
        value_list = additional_words_dict[index]
        for data in value_list:
            if data[0] == tag and data[1] == add_word:
                value_found = True
        if not value_found:
            additional_words_dict[index].append(value)
    else:
        additional_words_dict[index] = [value]

def to_tuple(verb: Verb):
    return (verb.index, verb.term, verb.category, verb.gender, verb.number, verb.person, verb.tam, verb.case, verb.type , verb.relation_head,verb.relation)

def postposition_finalization(processed_nouns, processed_pronouns,processed_foreign_words, words_info,lang):
    if lang != 'hi':
        return
    for data in words_info:
        data_index = data[0]
        dep = data[4]
        # head = data[4].strip().split(':')[0]

        if 'r6' in dep:
            dep = data[4].strip().split(':')[1]
            head = data[4].strip().split(':')[0]
            for noun in processed_nouns:
                index = noun[0]
                case = noun[3]
                if head == str(index) and case == 'o':
                    update_ppost_dict(data_index, 'ke')

            for pronoun in processed_pronouns:
                index = pronoun[0]
                case = pronoun[3]
                if head == str(index) and case == 'o':
                    update_ppost_dict(data_index, 'ke')

            # for nominal_v in process_nominal_form:
            #     index = nominal_v[0]
            #     case = nominal_v[3]
            #     if head == str(index) and case == 'o':
            #         update_ppost_dict(data_index, 'ke')
            # for f_word in processed_foreign_words:
            #     index = f_word[0]
            #     case = f_word[3]
            #     if head == str(index) and case == 'o':
            #         update_ppost_dict(data_index, 'ke')

def collect_processed_data(index_data, processed_foreign_words, processed_pronouns, processed_nouns, processed_adjectives,
                           processed_verbs, processed_auxverbs, processed_indeclinables, processed_others):
    """Collect, sort, and return processed data. Items not found in index_data are added at the end."""
    
    # Combine all lists
    combined_data = (
        processed_foreign_words + processed_pronouns + processed_nouns +
        processed_adjectives + processed_verbs +
        processed_auxverbs + processed_indeclinables + processed_others
    )

    # Sort safely by index (first element of each tuple), treating None or invalid as high value
    def safe_sort_key(item):
        index = item[0]
        try:
            return float(index) if index is not None else float('inf')
        except (ValueError, TypeError):
            return float('inf')

    sorted_data = sorted(combined_data, key=safe_sort_key)

    # Build final output
    result = []
    used_indices = set(str(idx) for idx in index_data)
    matched_items = []
    unmatched_items = []

    # Separate matched vs unmatched indices
    for item in sorted_data:
        item_idx = str(item[0])
        if item_idx in used_indices:
            matched_items.append(item)
        else:
            unmatched_items.append(item)

    # Sort matched items according to index_data order
    for idx in index_data:
        for item in matched_items:
            if str(item[0]) == str(idx):
                result.append(item)

    # Append all unmatched items at the end
    result.extend(unmatched_items)

    return result

def join_compounds(transformed_data, construction_data):
    '''joins compound words without spaces'''
    resultant_data = []
    prevword = ''
    previndex = -1

    for data in transformed_data:
        if (data[0]) == previndex and data[2] == 'n':
            temp = list(data)
            temp[1] = prevword + ' ' + temp[1]
            data = tuple(temp)
            resultant_data.pop()
        resultant_data.append(data)
        previndex = data[0]
        prevword = data[1]
    return resultant_data

# Main file (e.g., morpho_processor.py)








def populate_morpho_semantic_dict(index_data, gnp_info, PPfull_data, words_info, lang):
    """
    Populates the MORPHO_SEMANTIC_DICT based on morpho-semantic rules per language.
    
    Args:
        index_data (list): Index positions.
        gnp_info (list): Grammatical features like 'superl', 'compermore', etc.
        PPfull_data (list): Tuples containing word info.
        words_info (list): Additional word metadata.
        lang (str): Language code (e.g., 'en' for English, 'hi' for Hindi).

    Returns:
        tuple: (bool indicating if dict was populated, updated PPfull_data)
    """
    populate_morpho_semantic_dict_flag = False
    a = 'after'
    b = 'before'

    try:
        lang_module = importlib.import_module(f'language_rules.{lang}')
        lang_rules = getattr(lang_module, 'morpho_seman', {})
    except ImportError:
        lang_rules = {}
    
    for i, term in enumerate(gnp_info):
        input_string = gnp_info[i]

        if term in repository.constant.morpho_seman:
            populate_morpho_semantic_dict_flag = True

           

            if term == 'superl' and not any(re.match(r'^more_\d+$', word[1]) for word in words_info):
                temp = lang_rules.get('superl', (b, 'sabase'))


            elif term in ('comparmore'):
                temp = lang_rules.get('comparmore', (b, 'aXika'))

            elif term in ('comparless'):
                temp = lang_rules.get('comparless', (b, 'kama'))

            elif term == 'superl':
                dup_word = clean(words_info[i][1])
                if dup_word in PPfull_data[i][1]:  # Check membership in tuple
                    if 'para' in PPfull_data[i][1]:
                        dup_word1 = dup_word + '-' + dup_word + ' para'
                        PPfull_data[i] = PPfull_data[i][:1] + (dup_word1,) + PPfull_data[i][2:]
                        temp = (a, '')
                    if 'more' in PPfull_data[i][1]:
                        dup_word1 = 'most'
                        PPfull_data[i] = PPfull_data[i][:1] + (dup_word1,) + PPfull_data[i][2:]
                        temp = (a, '')
                    else:
                        dup_word = '-' + dup_word
                        temp = (a, dup_word)

                else:
                    temp = (a, '')  # Default if no match

            else:
                noun_data = nextNounData_fromFullData(index_data[i+1], PPfull_data)
                if noun_data != ():
                    g = noun_data[4]
                    n = noun_data[5]
                    p = noun_data[6]
                    if g == 'f':
                        temp = (a, 'vAlI')
                    elif n == 'p':
                        temp = (a, 'vAle')
                    elif n == 's':
                        temp = (a, 'with')
                    else:
                        temp = (a, '')  # Default fallback
                else:
                    temp = (a, '')  # No noun data

            # Update the global dictionary
            current_index = index_data[i]
            if current_index in MORPHO_SEMANTIC_DICT:
                MORPHO_SEMANTIC_DICT[current_index].append(temp)
            else:
                MORPHO_SEMANTIC_DICT[current_index] = [temp]

    return populate_morpho_semantic_dict_flag, PPfull_data

def join_indeclinables(transformed_data, processed_indeclinables, processed_others):

    """Joins Indeclinable data with transformed data and sort it by index number."""
    return transformed_data + processed_indeclinables + processed_others

# def rearrange_sentence(fulldata,coref_list):
#     '''Function comments'''
#     finalData = fulldata
#     final_words = [x[1].strip() for x in finalData]
#     r_s=" ".join(final_words)
#     return r_s

# def filter_and_concat_data(data, sentence_type_dict):
#     print('data:',data)
#     filtered_data = {}

#     for key, values in data.items():
#         concatenated = []
#         for item in values:
#             word = item[1]
#             # Only add the word if it's not in the construction_list
#             if word not in repository.constant.construction_list:
#                 concatenated.append(word)

#         # Check if the key exists in sentence_type_dict
#         if key in sentence_type_dict:
#             # Call has_ques_mark with concatenated words and sentence type
#             concatenated_data = has_ques_mark(' '.join(concatenated), sentence_type_dict[key])

#         # Store the concatenated result in the filtered data dictionary
#         filtered_data[key] = [concatenated_data]
#     print(filtered_data)
#     return filtered_data



def filter_and_concat_data(data, sentence_type_dict):
    filtered_data = {}

    meas_skip_words = [
        '#waw', 'calender', '#ne',
        'lengthmeas', 'tempmeas', 'weightmeas',
        'widthmeas', 'depthmeas', 'distmeas',
        'rate', 'timemeas', 'massmeas', 'heightmeas',
        'dist_meas', 'span', 'statecopula', 'conj',
        'disjunct', 'waw', 'nc', 'cp', 'ne'
    ]

    CONSTRUCTION_SKIP = {
        'distmeas', 'conj', 'disjunct', 'statecopula',
        'waw', 'span', 'timemeas', 'massmeas', 'heightmeas',
        'widthmeas', 'depthmeas', 'lengthmeas', 'tempmeas',
        'weightmeas', 'dist_meas', 'nc', 'cp'
    }

    for key, values in data.items():
        concatenated = []

        if isinstance(values, list) and all(isinstance(item, tuple) for item in values):
            for item in values:
                word = item[1]
                skip_phrases = ['statecopula']

                if any(phrase in word for phrase in skip_phrases):
                    continue

                # Skip NC modifier tokens
                if len(item) > 7 and item[7] == 'NC':
                    continue
                if len(item) > 7 and item[7] == 'NC_head':
                    continue

                # Skip measurement construction tokens
                if any(meas in word for meas in meas_skip_words):
                    continue

                # Skip <> placeholder
                if word.strip() == '<>':
                    continue

                # Skip construction name words
                if word.lower() in CONSTRUCTION_SKIP:
                    print(f"[DEBUG] Skipping construction name: {word}")
                    continue

                if word not in repository.constant.construction_list:
                    concatenated.append(word)

            if key in sentence_type_dict:
                concatenated_data = has_ques_mark(' '.join(concatenated), sentence_type_dict[key])
            else:
                concatenated_data = ' '.join(concatenated)

            filtered_data[key] = [concatenated_data]

        elif isinstance(values, str):
            filtered_data[key] = ["ERROR: " + values]

        else:
            filtered_data[key] = ["Unexpected data format"]

    return filtered_data

def rearrange_sentence(fulldata, index_data):
    '''Function to rearrange sentence based on coreference list'''
    # Create a dictionary for quick lookup from coref_list
    # coref_dict = {item[0]: item[1] for item in coref_list}
    # coref_dict = {index: value for index, value in coref_list}
    finalData = []
    # Join the words for the final rearranged sentence
    # final_words = [x[1].strip() for x in finalData]
    # r_s = " ".join(final_words)
    final_words = []
    for i in range(len(finalData)):
        word = finalData[i][1].strip()
        
        # If the word ends with a hyphen, join without space
        if i > 0 and final_words[-1].endswith('-'):
            final_words[-1] = final_words[-1] + word
        else:
            final_words.append(word)
    
    r_s = " ".join(final_words)
    ##print(r_s,'rsss')
    return r_s

# def collect_hindi_output(source_text):
#     """Take the output text and find the hindi text from it."""
#     hindi_format = WXC(order="wx2utf", lang="hin")
#     if source_text and '_' in source_text:
#         source_text = source_text.replace('_', ' ')

#     generate_hindi_text = hindi_format.convert(source_text)
#     return generate_hindi_text

def collect_hindi_output(filtered_data):
    """Take the filtered data and convert the Hindi text found in it."""
    # hindi_format = WXC(order="wx2utf", lang="hin")
    
    # Create a dictionary to store the converted text
    converted_data = {}
    generate_hindi_text=""
    
    for key, values in filtered_data.items():
        # Iterate through the list of values for each key
        converted_values = []
        for value in values:
            if value.startswith("ERROR:") or "ERROR:" in value:
                # Append the value as-is without conversion
                converted_values.append(value)
            else:
                pass
            # Replace underscores with spaces if applicable
                words = value.split()
    # Filter and join words
                value = ' '.join(v for v in words if v[1:] not in repository.constant.construction_list)
                value = value.replace('_', ' ')
                # Convert the Hindi text using the WXC converter
                # generate_hindi_text = hindi_format.convert(value)
                #mask tag
                if '<>' in generate_hindi_text:
                    print(generate_hindi_text,'oppp')
                    generate_hindi_text = generate_hindi_text.replace('<>','[MASK]')
                converted_values.append(generate_hindi_text)
            # Store the converted values in the dictionary
        converted_data[key] = converted_values
    
    return converted_data


def parse_segments(input_text):
    """
    Split the input text into segments based on </id>.
    """
    return input_text.strip().split('</id>')

def reset_global_dicts():
    global additional_words_dict, processed_postpositions_dict, construction_dict, spkview_dict, MORPHO_SEMANTIC_DICT
    additional_words_dict.clear()
    processed_postpositions_dict.clear()
    construction_dict.clear()
    spkview_dict.clear()
    MORPHO_SEMANTIC_DICT.clear()
    global_starred_words.clear()

# def convert_sentences_to_json(sentences):
#     """
#     Converts a list of sentences into the required JSON format.
    
#     Args:
#         sentences (list): A list of sentences.
    
#     Returns:
#         str: A JSON string with the sentences in the specified format.
#     """
#     # Prepare the output structure
#     output = {
#         "sentences": sentences
#     }
    
#     # Convert the dictionary to JSON
#     output_json = json.dumps(output, ensure_ascii=False, indent=4)
#     return output_json    


# from repository.common_v4 import *
# def multi_construction():

if __name__ == '__main__':
    import doctest
    doctest.run_docstring_examples(identify_complete_tam_for_verb, globals())

# ==============================================
