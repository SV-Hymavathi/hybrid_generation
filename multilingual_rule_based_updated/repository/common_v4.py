# Core utility library for the multilingual rule-based NLG system.
# Provides: USR parsing, postposition rules, spkview/article assignment,
# noun/pronoun/verb helpers, and the main add_chinking() chunking pipeline.
# ============================================================

import os
import sys
import re
import subprocess
import repository.constant
import tempfile
import importlib
from mapping_paradigm import *
from repository.coref_discourse import *
from repository.verb import Verb
from repository.concept import Concept
from wxconv import WXC
import json
from repository.verb import Verb
from repository.concept import Concept
from operator import itemgetter
from some_convertions_files.json_to_txt import process_and_write_json

# ── Global dictionaries shared across the pipeline ──────────────────────────
additional_words_dict = {}        # Extra words to insert before/after tokens
processed_postpositions_dict = {} # Stores computed postpositions keyed by word index
construction_dict = {}            # Construction-specific word additions (conj, waw, etc.)
spkview_dict = {}                 # Speaker-view markers (articles, focus words, respect)
MORPHO_SEMANTIC_DICT = {}         # Morpho-semantic modifiers (comparatives, superlatives)
data_case_for_k4 = []             # Tracks k4 case occurrences (used in postposition logic)
construction_dict_to_leave = {}   # Constructions intentionally skipped
global_starred_words = {}         # Words not found in dictionary, marked with '*'


# ── File I/O ─────────────────────────────────────────────────────────────────

def read_file(file_path):
    """Read and return the full contents of a file as a string."""
    with open(file_path, 'r') as file:
        return file.read()


def log(mssg, logtype='OK'):
    """Print a formatted log message. On ERROR, also writes to CSV results file."""
    print(f'log : [{logtype}]:{mssg}')
    if logtype == 'ERROR':
        try:
            path = sys.argv[1]
            write_hindi_test(' ', 'Error', mssg, 'test.csv', path)
        except (IndexError, Exception):
            pass


def write_hindi_test(hindi_output, POST_PROCESS_OUTPUT, src_sentence, OUTPUT_FILE, path):
    """Append one row of generation results to the CSV test-results file."""
    OUTPUT_FILE = 'TestResults.csv'
    str_path = path.strip('lion_story/')
    if str_path == '1':
        with open(OUTPUT_FILE, 'w') as file:
            file.write("")
    with open(OUTPUT_FILE, 'a') as file:
        file.write(path.strip('../hindi_gen/lion_story') + '\t')
        file.write(src_sentence.strip('"').strip('\n').strip('#') + '\t')
        file.write(POST_PROCESS_OUTPUT + '\t')
        file.write(hindi_output + '\t')
        file.write('\n')
    return "Output data write successfully"


# ── String cleaning helpers ───────────────────────────────────────────────────

import re

def is_abbreviation(word):
    """Return True if word is an @-prefixed abbreviation (e.g. @U.P.)."""
    return word.startswith('@')


def clean_abbreviation(word):
    """
    Convert a WX-encoded abbreviation to display form.
    Example: '@ke.ke.' → 'K.K.'
    Steps: strip '@', split on '.', WX-convert each part, uppercase it, re-join with dots.
    """
    word = word.lstrip('@')
    parts = word.split('.')
    result = []
    for part in parts:
        if part:
            roman = wx_to_english(part)
            result.append(roman.upper())
    return '.'.join(result) + '.'


def clean(word, inplace=''):
    """
    Normalise a WX concept word for lookup/comparison.
    - Replaces dZ→d, jZ→j, DZ→D (WX variant forms)
    - Replaces '+' with space (compound separator)
    - Removes all digits and non-alpha characters
    """
    word = word.replace('dZ', 'd').replace('jZ', 'j').replace('DZ', 'D')
    word = word.replace('+', ' ')
    return re.sub(r'[^a-zA-Z ]+', inplace, word)


def cleans(word, inplace=''):
    """
    Like clean() but replaces '+' with '-' (used for foreign-word display).
    """
    word = word.replace('dZ', 'd').replace('jZ', 'j').replace('DZ', 'D')
    word = word.replace('+', '-')
    return re.sub(r'[^a-zA-Z ]+', inplace, word)


# ── Output sentence collection ────────────────────────────────────────────────

def process_sentence(filtered_data, sentences):
    """
    Collect all generated sentences from filtered_data into a JSON structure
    and write them to formatted_output.txt.
    """
    if filtered_data:
        for segment_id, text_list in filtered_data.items():
            for text in text_list:
                sentences.append({"segment_id": segment_id, "text": text})
        output = {"bulk": sentences}
    else:
        output = {
            "sentence_id": list(filtered_data.keys()),
            "text": list(filtered_data.values())
        }
    json_output = json.dumps(output, ensure_ascii=False)
    process_and_write_json(json_output, output_file="./formatted_output.txt")
    log(f'process_sentence : {json_output}')
    return json_output


# ── USR validation ────────────────────────────────────────────────────────────

def check_main_verb(depend_data):
    """
    Verify that the USR contains at least one main-verb dependency ('main', 'rcelab', or 'rcdelim').
    Logs a warning if none is found (generation may still proceed but output could be wrong).
    """
    for dep in depend_data:
        if dep:
            dep_type = dep.strip().split(':')[1]
            if dep_type in ('main', 'rcelab', 'rcdelim'):
                return True
    log('USR error. Main verb not identified. Check the USR.')
    return False


# ── TAM lookup ───────────────────────────────────────────────────────────────

def identify_tam_terms(term):
    """
    Map a Hindi TAM string (e.g. 'wA_hE') to its English equivalent
    by reading repository/tam_morph_tuple.tsv.
    Returns the English TAM string, or an error message if not found.
    """
    if '-' in term:
        tam = term.split("-")[-1]
        file_path = "repository/tam_morph_tuple.tsv"
        with open(file_path, "r", encoding="utf-8") as file:
            headers = file.readline().strip().split("\t")
            try:
                hindi_tam_index = headers.index("Hindi_TAM")
                english_tam_index = headers.index("English_Tam")
            except ValueError:
                log("TAM tuple file: column names not found", 'ERROR')
                return None
            for line in file:
                columns = line.strip().split("\t")
                if columns[hindi_tam_index] == tam:
                    return columns[english_tam_index]
        # TAM not in the table: return None (NOT a space-containing string, which
        # would corrupt the columnar USR parse). The sentence is flagged TAM-broken
        # downstream and degrades to partial output.
        log(f'TAM not found in tuple table: {tam}', 'WARNING')
        return None


# ── USR row extraction ────────────────────────────────────────────────────────

def generate_rulesinfo(file_data):
    """
    Parse one USR block (already split into lines) into labelled lists.
    The 11 rows of a USR are:
      0 - source sentence (Hindi)
      1 - root concepts (comma-separated)
      2 - index numbers
      3 - semantic tags (anim, per, female, dom, moy…)
      4 - GNP (gender/number/person)
      5 - dependency (e.g. '3:k1', '0:main')
      6 - discourse (coref, samuccaya…)
      7 - speaker-view (def, BI_1, respect…)
      8 - scope
      9 - construction (begin/inside/op1/component…)
     10 - sentence type (%affirmative, %imperative…)
    Returns a list of all 11 items.
    """
    global src_sentence, root_words, index_data, seman_data, gnp_data
    global depend_data, discourse_data, spkview_data, scope_data, construction_data, sentence_type

    if len(file_data) < 9:
        log('Invalid USR. USR does not contain enough lines.', 'ERROR')
        raise ValueError('invalid USR: not enough lines')

    src_sentence     = file_data[0]
    root_words       = file_data[1].strip().split(',')
    index_data       = file_data[2].strip().split(',')
    seman_data       = file_data[3].strip().split(',')
    gnp_data         = file_data[4].strip().split(',')
    depend_data      = file_data[5].strip().split(',')
    discourse_data   = file_data[6].strip().split(',')
    spkview_data     = file_data[7].strip().split(',')
    scope_data       = file_data[8].strip().split(',')
    construction_data = file_data[9].strip().split(',') if len(file_data) > 9 else ['-']
    sentence_type    = file_data[10].strip() if len(file_data) > 10 else '%affirmative'

    log('Rules Info extracted succesfully fom USR.')
    return [src_sentence, root_words, index_data, seman_data, gnp_data, depend_data,
            discourse_data, spkview_data, scope_data, construction_data, sentence_type]


import importlib
import re

spkview_dict = {}
interrogative_dict = ""

import requests
import csv
from io import StringIO


# ── Speaker-view / article assignment ────────────────────────────────────────

def populate_spkview_dict(
    rootwords, spkview_info, discourse_data, index_data, lang,
    gnp_data=None, construction_data=None, words_info=None,
    adjectives_data=None, nouns_data=None, depend_data=None,
    eka_head_index=None
):
    """
    Fill spkview_dict with display markers for each USR token index.

    For HINDI:
      - 'BI_1' → 'also' placed before the word
      - 'hI_1' → 'only' placed after the word
      - 'def'  → 'the' placed before the noun (English only)
      - 'respect' → '_(respect)' suffix on the content word

    For ENGLISH:
      - 'def' marker in words_info triggers 'the' before the noun
      - 'respect' in spkview_info triggers the '_(respect)' suffix
      - Mapped values come from language_rules/en.py → SPKVIEW_TO_WORD_MAP

    The dict is keyed by USR index (int) and values are lists of (position, value) tuples
    where position is 'before', 'after', or 'respect'.
    """
    try:
        lang_module = importlib.import_module(f'language_rules.{lang}')
    except ImportError:
        lang = 'hi'
        lang_module = importlib.import_module('language_rules.hi')

    spkview_to_word_map = getattr(lang_module, 'SPKVIEW_TO_WORD_MAP', {})
    spkview_list_a = getattr(lang_module, 'speakers_a', [])   # words that go AFTER
    spkview_list_b = getattr(lang_module, 'speakers_b', [])   # words that go BEFORE

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
            continue  # Already populated — skip

        if lang == "hi" and (clean_spk_info in spkview_list_a or
                              clean_spk_info in spkview_list_b or
                              clean_spk_info == 'result'):
            populate_spk_dict = True
            if clean_spk_info in spkview_list_a and not discourse_data[i]:
                spkview_dict[index] = [(a, display_value)]
            elif clean_spk_info in spkview_list_b:
                spkview_dict[index] = [(b, display_value)]

        elif lang == "en" and clean_spk_info == 'respect':
            # Mark this token to receive the '_(respect)' suffix
            populate_spk_dict = True
            spkview_dict[index] = [('respect', 'respect')]

        elif lang == "en" and rootwords[i].split('_')[0] not in [
            "only", "indeed", "a few", "right from", "not only...but also",
            "the", "yes", "exactly", "amount", "appproximately", "additional",
            "also", "even", "any", "yet", "still", "nearly", "almost/approximate",
            "modifier/intensifier", "so"
        ]:
            if clean_spk_info in spkview_list_a or clean_spk_info in spkview_list_b or clean_spk_info == 'result':
                populate_spk_dict = True
                if clean_spk_info in spkview_list_a or clean_spk_info in spkview_list_b:
                    spkview_dict[index] = [(b, display_value)]

        if lang == 'hi':
            return populate_spk_dict  # Hindi is simple — one pass is enough

        # ── English: assign articles ('the', 'a', 'an') from words_info ──
        vowels = ['a', 'e', 'i', 'o', 'u']
        skip_next = False

        if words_info:
            for word_tuple in words_info:
                word_id = int(word_tuple[0])

                if skip_next:
                    skip_next = False
                    continue

                if word_id in spkview_dict:
                    continue  # Already has an article/marker

                word         = word_tuple[1]
                tags_2       = word_tuple[2]
                gnp          = word_tuple[3]
                role_tags    = word_tuple[4]
                if len(word_tuple) <= 6:
                    continue
                definiteness = word_tuple[6]

                if 'def' in definiteness:
                    # 'def' marker in GNP → definite article 'the'
                    spkview_dict[word_id] = [(b, 'the')]
                    populate_spk_dict = True
                    continue

                # Assign 'an' before vowel-initial adjective modifiers
                if (eka_head_index == "" and
                        'pl' not in gnp and
                        ':' in role_tags and
                        role_tags.split(':')[1] not in ['k7t', 'quant', 'main'] and
                        role_tags.split(':')[1] in ['mod']):
                    if word[0].lower() in vowels:
                        spkview_dict[word_id] = [(b, 'an')]
                        populate_spk_dict = True
                        continue

    return populate_spk_dict


# ── kriyAmUla check ───────────────────────────────────────────────────────────

def is_kriyAmUla_head(data_list, dep_head):
    """
    Return True if any entry in data_list has 'kriyAmUla' and its head index
    equals dep_head. Used to decide whether to add the genitive postposition 'kA'.
    """
    if data_list is None:
        return False
    for i, item in enumerate(data_list):
        if "kriyAmUla" in item and clean(root_words[i]) in repository.constant.kriyAmUla:
            head = item.split(":")[0]
            return True and head == dep_head
    return False


# ── Postposition computation ──────────────────────────────────────────────────

processed_postpositions_dict = {}
data_case_for_k4 = []

from generated_conditions import get_ppost


def preprocess_postposition_new(concept_type, np_data, words_info, verb_data, index_data, lang):
    """
    Compute the postposition (preposition for English) for one noun/pronoun token.

    Parameters:
        concept_type (str) : 'noun' or 'pronoun'
        np_data      (tuple): The processed word tuple for this token
        words_info   (list) : All USR word tuples (for context)
        verb_data    (tuple): The main verb tuple (for agreement/TAM checks)
        index_data   (list) : USR index list
        lang         (str)  : 'hi' or 'en'

    For English: calls get_ppost() from generated_conditions.py,
    then removes the postposition for self-preposition words (after, before, etc.)
    and for location pronouns (here, there, …).

    For Hindi: delegates to _hindi_preprocess_postposition().

    Stores the result in processed_postpositions_dict[data_index].
    Returns (new_case, ppost).
    """
    data_index = None
    data_head  = None
    data_case  = ''
    root_main  = None
    data_seman = None
    ppost      = ''
    new_case   = 'o'

    if len(verb_data) > 0:
        verb_term = verb_data[1]
        if len(verb_term) > 0:
            root_main = verb_term.strip().split('-')[0].split('_')[0]

    if '[' not in np_data[1] and ']' not in np_data[1]:
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
            data_case_for_k4.append(np_data[4])

    if lang == 'hi':
        return _hindi_preprocess_postposition(
            concept_type, np_data, words_info, verb_data, index_data,
            data_case, data_head, data_seman, data_index, root_main
        )

    elif lang == 'en':
        # Look up the preposition from the rule table
        ppost = get_ppost(
            data_case,
            data_head,
            data_seman=data_seman,
            root_main=root_main,
            concept_type=concept_type
        )

        # Override k7p 'in' -> 'on' for surface/route/road/line concepts.
        # English uses 'on' not 'in' for physical surfaces, roads, routes, lines.
        # e.g. "on the railway line", "on the road", "on the route"
        if ppost == 'in' and data_case == 'k7p':
            _surface_concepts = {
                'line', 'road', 'route', 'path', 'track', 'rail', 'railway',
                'highway', 'street', 'avenue', 'lane', 'bridge', 'border',
                'coast', 'shore', 'bank', 'surface', 'floor', 'ground',
                'way', 'runway', 'platform', 'course', 'belt',
            }
            concept_word = np_data[1].lower().split('_')[0].split('+')[-1] if np_data[1] else ''
            if any(sw in concept_word for sw in _surface_concepts):
                ppost = 'on'
                print("[DEBUG] k7p postposition override: 'in' -> 'on' for concept '%s'" % concept_word)

        # Words that already contain their own preposition semantically
        # (e.g. 'before', 'after') — don't add another preposition on top
        SELF_PREPOSITION_WORDS = {
            'after', 'before', 'since', 'until', 'during', 'from',
            'ahead', 'behind', 'away', 'apart', 'beyond', 'above', 'below',
            'bAxa', 'bxa', 'pahale', 'phle', 'Age', 'age', 'pICe', 'pice', 'xUra', 'xura',
        }
        concept_root = np_data[1].split('_')[0].lower() if np_data[1] else ''
        if concept_root in SELF_PREPOSITION_WORDS:
            ppost = ''
            print(f"[DEBUG] Cleared ppost for self-preposition word: {concept_root}")

        # Location pronouns (here, there) don't need a spatial preposition
        LOCATION_PRONOUNS = {'here', 'there', 'where', 'somewhere', 'everywhere'}
        if (concept_type == 'pronoun' and
                data_case in ('k7p', 'k7', 'k5') and
                np_data[1] in LOCATION_PRONOUNS):
            ppost = None
            if data_index is not None:
                processed_postpositions_dict[data_index] = None
            return new_case, None

        # 'rkl' relation: the word itself encodes the preposition — skip
        if data_case == 'rkl':
            ppost = ''

        if concept_type == 'noun' and np_data[1].strip('[]').split('_')[0] not in repository.constant.construction_list:
            ppost = None if ppost == '' else ppost
        elif concept_type == 'pronoun':
            ppost = 0 if ppost == '' else ppost
        else:
            ppost = None

        if data_index is not None:
            if verb_data and str(data_head).lstrip('-').isdigit() and int(data_head) == verb_data[0] and data_case == "rt":
                ppost = 'to'
            processed_postpositions_dict[data_index] = ppost

        return new_case, ppost

    else:
        return new_case, None


# ── Hindi postposition logic (internal) ──────────────────────────────────────

def _hindi_preprocess_postposition(
    concept_type, np_data, words_info, verb_data, index_data,
    data_case, data_head, data_seman, data_index, root_main
):
    """
    Hindi-specific postposition rules.
    Maps each USR dependency case (k1, k2, k7, r6, …) to its Hindi postposition
    (ne, ko, meM, kA, …).
    Called only when lang == 'hi'.
    """
    ppost    = ''
    new_case = 'o'

    if data_case in ('k1', 'pk1'):
        if is_tam_ya(verb_data, data_head):
            k2exists, k2_index = find_match_with_same_head(data_head, 'k2', words_info, index=4)
            if k2exists:
                ppost = 'ne'
            else:
                ppost = ''
                print('Karma k2 not found. Output may be incorrect')
        elif identify_complete_tam_for_verb(verb_data[1]) in repository.constant.nA_list:
            ppost = 'ko'

    elif data_case == 'mod' and data_seman == 'season':
        ppost = 'kA'
        nn_data = nextNounData(data_head, words_info)
        if nn_data:
            if nn_data[4].split(':')[1] in ('k3', 'k4', 'k5', 'k7', 'k7p', 'k7t', 'r6', 'mk1', 'jk1', 'rt'):
                ppost = 'ke'
                if nn_data[3] == 's':
                    ppost = 'kI' if nn_data[3] == 'f' else 'kA'

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
    elif data_case in ('k2p', 'k7', 'k7p', 'k7t'):
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
    elif data_case in ('rask1', 'rask2', 'rask3', 'rask4', 'rask5',
                       'k1as', 'k2as', 'k3as', 'k4as', 'k5as', 'k7as'):
        ppost = 'ke sAWa'
    elif data_case == 'r6':
        ppost = 'kA'
    elif data_case == 'quantless':
        ppost = 'se kama'
    elif data_case == 'quantmore':
        ppost = 'se aXika'

    if ppost == '':
        new_case = 'd'

    if concept_type == 'noun':
        ppost = None if ppost == '' else ppost
    elif concept_type == 'pronoun':
        ppost = 0 if ppost == '' else ppost

    if data_index is not None:
        processed_postpositions_dict[data_index] = ppost

    return new_case, ppost


# ── USR word-info packaging ───────────────────────────────────────────────────

def generate_wordinfo(root_words, index_data, seman_data, gnp_data, depend_data,
                      discourse_data, spkview_data, scope_data, construction_data):
    """
    Zip all nine USR rows into a list of per-word tuples:
      (index, root_word, seman, gnp, depend, discourse, spkview, scope, construction)
    Pads any short tuples to exactly 9 elements with '-'.
    """
    result = list(zip(index_data, root_words, seman_data, gnp_data, depend_data,
                      discourse_data, spkview_data, scope_data, construction_data))
    padded = []
    for t in result:
        if len(t) < 9:
            t = t + ('-',) * (9 - len(t))
        padded.append(t)
    return padded


def check_USR_format(root_words, index_data, seman_data, gnp_data, depend_data,
                     discourse_data, spkview_data, scope_data):
    """
    Validate and repair a USR's row lengths.
    - Makes root_words and index_data the same length
    - Ensures all eight rows have the same number of entries
    - Strips whitespace from every cell
    Returns zipped tuples of corrected USR data.
    """
    data = [root_words, index_data, seman_data, gnp_data, depend_data,
            discourse_data, spkview_data, scope_data]
    len_root = len(root_words)
    len_index = len(index_data)

    if len_root > len_index:
        diff = len_root - len_index
        while diff:
            index_data.append(0)
            diff -= 1
            log(f'{repository.constant.USR_row_info[1]} has lesser entries than {repository.constant.USR_row_info[0]}')
    elif len_root < len_index:
        diff = len_index - len_root
        while diff:
            index_data.pop()
            diff -= 1
            log(f'{repository.constant.USR_row_info[1]} has more entries than {repository.constant.USR_row_info[0]}')

    len_root = len(root_words)
    for i in range(1, len_root + 1):
        if index_data[i - 1] != i:
            index_data[i - 1] = i
            log(f'{repository.constant.USR_row_info[1]} has wrong entry at position {i}')

    max_col = max(index_data)
    i = 0
    for ele in data:
        length = len(ele)
        if length < max_col:
            diff = max_col - length
            while diff:
                ele.append('')
                log(f'Added one entry at the end of {repository.constant.USR_row_info[i]}')
                diff -= 1
        elif length > max_col:
            diff = length - max_col
            while diff:
                ele.pop()
                log(f'Removed one entry from the end of {repository.constant.USR_row_info[i]}')
                diff -= 1
        i += 1

    for row in data:
        for i in range(len(row)):
            if type(row[i]) != int and row[i] != '':
                row[i] = row[i].strip()

    return list(zip(index_data, root_words, seman_data, gnp_data, depend_data,
                    discourse_data, spkview_data, scope_data))


# ── Hindi WX converter (UTF-8 → WX direction) ────────────────────────────────

def convert_to_hindi(word):
    """Convert a UTF-8 Hindi string to WX encoding using the WXC library."""
    wx1 = WXC(order='utf2wx', lang='hin')
    return wx1.convert(word)


# ── Construction helpers ──────────────────────────────────────────────────────

def new_to_old_convert_construction_conj_dis(index_data, construction_data, conj_concept):
    """
    Extract conjunction/disjunction operand mappings from construction_data.
    Returns a dict: {conj_index: [(op_index, 'op1'), (op_index, 'op2'), …]}
    Used to wire up coordinated noun phrases.
    """
    result = {}
    for i, concept in enumerate(conj_concept):
        if 'conj' in concept or 'disjunct' in concept or 'xvanxva' in concept:
            ind = index_data[i]
            op_indices = []
            for j, text in enumerate(construction_data):
                if text and 'op' in text:
                    txt_index = int(text.split(':')[0])
                    if txt_index == ind:
                        op_indices.append((index_data[j], text.split(':')[1]))
            if op_indices:
                result[ind] = op_indices
    return result


def process_dep_k2g(data_case, main_verb):
    """
    Decide postposition for k2g relation:
    - 'se' if the main verb is in the kisase_k2g_verbs list
    - 'ko' otherwise
    """
    verb = identify_main_verb(main_verb[1])
    if verb in repository.constant.kisase_k2g_verbs:
        return 'se'
    return 'ko'


# ── Morphological form helpers ────────────────────────────────────────────────

def get_all_form(morph_forms):
    """Return the full morphological analysis string (after the '$' prefix)."""
    return morph_forms.split("$")[1]


def get_first_form(morph_forms):
    """Return only the first morphological form from an Apertium output string."""
    return morph_forms.split("/")[1]


def get_default_GNP():
    """Return safe defaults: gender=neutral, number=singular, person=any, case=oblique."""
    return 'n', 's', 'a', 'o'


def get_gnpcase_from_concept(concept):
    """
    Extract (gender, number, person, case) from a processed word tuple.
    Handles verbs, verbal nouns, pronouns, and nouns.
    Falls back to defaults if any value is missing ('-', None, 'null').
    """
    if concept[2] == 'v':
        gender, number, person, case = concept[3], concept[4], concept[5], concept[7]
    elif concept[2] == 'vn':
        gender, number, person, case = concept[4], concept[5], concept[6], concept[3]
    elif concept[2] == 'p':
        gender, number, person, case = concept[4], concept[5], concept[6], concept[3]
        if concept[1] in ['wyax', 'yah', 'vah', 'यह', 'वह']:
            gender = 'n'  # demonstratives are neutral
    elif concept[2] == 'n':
        gender, number, person, case = concept[4], concept[5], concept[6], concept[3]
    else:
        return get_default_GNP()

    if gender in ['-', None, 'null']:  gender = 'n'
    if number in ['-', None, 'null']:  number = 's'
    if person in ['-', None, 'null']:  person = 'a'
    if case   in ['-', None, 'null']:  case   = 'o'

    return gender, number, person, case


# ── Data lookup helpers ───────────────────────────────────────────────────────

def getDataByIndex(value, searchList, index=0):
    """
    Search a list of tuples for the first entry where tuple[index] == value.
    Returns the matching tuple, or False if not found.
    """
    try:
        for dataele in searchList:
            if (dataele[index]) == value:
                return dataele
        return False
    except IndexError:
        log(f'Index out of range while searching index:{value} in {searchList}', 'WARNING')
        return False


def getGNP_using_k2(k2exists, searchList):
    """Return the GNP of the k2 (object) argument from processed nouns/pronouns."""
    casedata = getDataByIndex(k2exists, searchList)
    if casedata is False:
        log('Something went wrong. Cannot determine GNP for verb.', 'ERROR')
        raise ValueError('cannot determine GNP for verb (k2 object not found)')
    return casedata[4], casedata[5], casedata[6][0]


def getGNP_using_k1(k1exists, searchList):
    """Return the GNP of the k1 (subject) argument from processed nouns/pronouns."""
    casedata = getDataByIndex(k1exists, searchList)
    if casedata is False:
        log('Something went wrong. Cannot determine GNP for verb k1 is missing.', 'ERROR')
        raise ValueError('cannot determine GNP for verb (k1 subject not found)')
    return casedata[4], casedata[5], casedata[6]


def getVerbGNP_new(concept_term, full_tam, index, seman_data, depend_data, sentence_type,
                   processed_nouns, processed_pronouns, index_data, k1_not_need):
    """
    Determine the gender/number/person that the main verb should agree with.
    - Imperative: always masculine singular
    - TAM 'yA': agree with k1 (direct case) or k2 (direct case) depending on transitivity
    - Otherwise: agree with k1 subject
    Returns (gender, number, person).
    """
    if sentence_type in ('Imperative', 'imperative') or 'o' in full_tam:
        return 'm', 's', 'm'

    k1exists = k2exists = False
    verb_gender, verb_number, verb_person, case = get_default_GNP()
    searchList = processed_nouns + processed_pronouns

    for dep in depend_data:
        if dep == '':
            continue
        dep_val = dep.split(':')[1]
        if dep_val in ('k1', 'pk1'):
            k1exists = index_data[depend_data.index(dep)]
        elif dep_val[-2:] == 'k2':
            k2exists = index_data[depend_data.index(dep)]

    k1_case = k2_case = ''
    if k1exists:
        casedata = getDataByIndex(k1exists, searchList)
        if casedata:
            k1_case = casedata[3]
    if k2exists:
        casedata = getDataByIndex(k2exists, searchList)
        if casedata:
            k2_case = casedata[3]

    if 'yA' in full_tam:
        if k1exists and k1_case == 'd':
            verb_gender, verb_number, verb_person = getGNP_using_k1(k1exists, searchList)
        elif k1exists and k1_case == 'o' and k2exists and k2_case == 'd':
            verb_gender, verb_number, verb_person = getGNP_using_k2(k2exists, searchList)
        return verb_gender, verb_number, verb_person[0]

    if full_tam in repository.constant.nA_list:
        return verb_gender, verb_number, verb_person[0]

    if k1exists:
        verb_gender, verb_number, verb_person = getGNP_using_k1(k1exists, searchList)
        # English verb agreement override: when the k1 subject noun is modified
        # by a universal quantifier (every, each, हर) the verb is always singular
        # in English, regardless of the noun's number feature in the USR.
        # e.g. "हर तीर्थ बड़ा है" → "every pilgrimage is" (not "are")
        # Words that force singular verb agreement in English regardless of noun number
        # 'all' here is the English concept mapped from Hindi 'हर' (hara)
        UNIVERSAL_QUANT = {'every', 'each', 'hara', 'all', 'every one', 'each one'}
        k1_data = getDataByIndex(k1exists, searchList)
        if k1_data and verb_number == 'p':
            # Check if any modifier of k1 is a universal quantifier
            k1_idx = float(k1exists)
            for entry in searchList:
                if (len(entry) > 10 and entry[2] in ('p', 'adj') and
                        entry[1].lower() in UNIVERSAL_QUANT):
                    # This is a pronoun/adj with universal quant meaning
                    verb_number = 's'
                    break
    return verb_gender, verb_number, verb_person[0]


# ── TAM / verb identification helpers ────────────────────────────────────────

def is_tam_ya(verbs_data, data_head):
    """Return True if the main verb tuple has the '-yA_' TAM marker."""
    if len(verbs_data) > 0 and verbs_data != ():
        if verbs_data[0] == int(data_head):
            if '-yA_' in verbs_data[1]:
                return True
    return False


def is_kim(term):
    """Return True if the term is the interrogative pronoun 'kim' (who/what)."""
    return term == 'kim'


def is_yax(term):
    """Return True if the term is the relative pronoun 'yax' (who/which)."""
    return term == 'yax'


def is_update_index_NC(i, processed_words):
    """Return True if a processed word at index i is tagged as an NC (noun compound modifier)."""
    for data in processed_words:
        temp = tuple(data)
        if len(temp) > 7 and float(i) == temp[0] and temp[7] == 'NC':
            return True
    return False


def is_nonfinite_verb(concept):
    """Return True if the Concept object represents a non-finite verb."""
    return concept.type == 'nonfinite'


def has_tam_ya():
    """Check whether the global HAS_TAM flag is True (set during verb processing)."""
    global HAS_TAM
    return HAS_TAM is True


def has_GNP(gnp_info):
    """Return True if gnp_info contains a number marker ('sg' or 'pl')."""
    return bool(len(gnp_info) and ('sg', 'pl') in gnp_info)


def has_ques_mark(POST_PROCESS_OUTPUT, sentence_type):
    """
    Append the appropriate sentence-final punctuation based on sentence type:
    - interrogative → ' ?'
    - affirmative / imperative / fragment → ' .'
    - other → no change
    """
    if sentence_type in ("yn_interrogative", "yn_interrogative_negative",
                         "pass-yn_interrogative", "pass_yn_interrogative",
                         "interrogative", "Interrogative",
                         "pass-interrogative", "pass_interrogative"):
        return POST_PROCESS_OUTPUT + ' ?'
    elif sentence_type in ('pass_affirmative', 'pass-affirmative',
                           'pass_negative', 'pass-negative',
                           'affirmative', 'Affirmative',
                           'negative', 'Negative', 'imperative', 'Imperative',
                           "fragment", "term", "title", "heading"):
        return POST_PROCESS_OUTPUT + ' .'
    return POST_PROCESS_OUTPUT


def identify_main_verb(concept_term):
    """
    Extract the root of the main verb from a full concept term.
    Examples:
      'kara_1-wA_hE_1' → 'kara'
      'varRA+ho_1-gA_1' → 'ho'
    """
    if "+" in concept_term:
        concept_term = concept_term.split("+")[1]
    return clean(concept_term.split("-")[0])


def identify_default_tam_for_main_verb(concept_term):
    """
    Extract just the immediate TAM token (the part right after the '-').
    Examples:
      'kara_1-wA_hE_1' → 'wA'
      'kara_1-0_rahA_hE_1' → '0'
    """
    if '-' in concept_term:
        con = concept_term.split("-")[1]
        return con.split("_")[0] if '_' in con else con
    return concept_term


def identify_complete_tam_for_verb(concept_term):
    """
    Extract the full TAM string from a concept term (everything after '-', digits removed).
    Examples:
      'kara_1-wA_hE_1'    → 'wA_hE'
      'kara_1-0_rahA_hE_1' → 'rahA_hE'
      'kara_o'             → 'o'
    """
    if 'cAha_1-e_1' in concept_term:
        return 'cAhiye'
    elif "-" not in concept_term:
        return concept_term.split("_")[1]
    tmp = concept_term.split("-")[1]
    tokens = tmp.split("_")
    non_digits = filter(lambda x: not x.isdigit(), tokens)
    return "_".join(non_digits)


def identify_auxiliary_verb_terms(term):
    """
    Extract the list of auxiliary verb roots from a full concept term.
    Example: 'kara_1-0_rahA_hE_1' → ['rahA', 'hE']
    """
    aux_verb_terms = term.split("-")[1].split("_")[1:]
    cleaned_terms = map(clean, aux_verb_terms)
    return list(filter(lambda x: x != '', cleaned_terms))


def identify_verb_type(verb_concept):
    """
    Classify a verb Concept as 'main' or 'nonfinite' based on its dependency relation.
    Non-finite relations: rpk, rsk, rbk, rblsk, rblak, rblpk, rvks, rbks.
    """
    dependency = verb_concept.dependency
    dep_rel = ''
    if dependency != '-':
        dep_rel = dependency.strip().split(':')[1]
    if dep_rel == 'main':
        return "main"
    elif dep_rel in ('rpk', 'rsk', 'rbk', 'rblsk', 'rblak', 'rblpk', 'rvks', 'rbks'):
        return "nonfinite"
    return "main"


# ── Morphological analysis (Apertium) ────────────────────────────────────────

def find_tags_from_dix(word):
    """
    Run Apertium morph-analyser on a word (Hindi) and return a dict of its tags.
    Uses hi.morfLC.bin.
    """
    dix_command = "echo {} | apertium-destxt | lt-proc -ac repository/hi.morfLC.bin | apertium-retxt".format(word)
    morph_forms = os.popen(dix_command).read()
    return parse_morph_tags(morph_forms)


import os

def find_tags_from_dix_as_list(word, lang='en'):
    """
    Run Apertium morph-analyser on a word for the given language and return
    a list of tag dicts (one per analysis).

    Args:
        word (str): The word to analyse.
        lang (str): 'hi' (Hindi) or 'en' (English).

    Returns:
        list of dicts, e.g. [{'cat': 'n', 'case': 'd', 'gen': 'f', 'num': 'p', 'form': 'mA'}]
    """
    _tool_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dix_binaries = {
        'hi': os.path.join(_tool_root, 'repository', 'hi.morfLC.bin'),
        'en': os.path.join(_tool_root, 'apertium_eng', 'eng.automorf.bin'),
    }
    dix_bin_path = dix_binaries.get(lang)
    if not dix_bin_path:
        log(f"No morphological analyzer binary defined for language: {lang}", 'ERROR')
        return []
    dix_command = f"echo {word} | apertium-destxt | lt-proc -ac {dix_bin_path} | apertium-retxt"
    morph_forms = os.popen(dix_command).read()
    return parse_morph_tags_as_list(morph_forms)


def find_exact_dep_info_exists(index, dep_rel, words_info):
    """Return True if words_info contains a token with head == index and relation == dep_rel."""
    for word in words_info:
        dep_head = word[4].strip().split(':')[0]
        dep_val  = word[4].strip().split(':')[1]
        if dep_val == dep_rel and int(dep_head) == index:
            return True
    return False


def find_match_with_same_head(data_head, term, words_info, index):
    """
    Search words_info for a token whose dependency head == data_head and
    whose relation == term. Returns (True, token_index) or (False, -1).
    """
    for dataele in words_info:
        dep_head  = dataele[index].strip().split(':')[0]
        dep_value = dataele[index].strip().split(':')[1]
        if str(data_head) == dep_head and term == dep_value:
            return True, dataele[0]
    return False, -1


def parse_morph_tags(morph_form):
    """
    Parse a single Apertium morph-analysis string into a tag dict.
    Example: 'mA<cat:n><case:d><gen:f><num:p>' → {'cat': 'n', 'case': 'd', …, 'form': 'mA'}
    """
    form    = morph_form.split("<")[0]
    matches = re.findall("<(.*?):(.*?)>", morph_form)
    result  = {match[0]: match[1] for match in matches}
    result["form"] = form
    return result


import re

def parse_morph_tags_as_list(morph_form, lang='en'):
    """
    Parse Apertium output for a word into a list of tag dicts (one per analysis).
    Hindi uses '<tag:value>' pairs; English uses bare '<tag>' items.
    """
    segments = morph_form.split('/')
    word     = morph_form.split('/')[0].replace('^', '')
    result   = []
    for segment in segments:
        form = segment.split("<")[0]
        if form != word:
            continue
        if lang == 'hi':
            matches  = re.findall(r"<(.*?):(.*?)>", segment)
            tag_dict = {match[0]: match[1] for match in matches}
        elif lang == 'en':
            matches  = re.findall(r"<(.*?)>", segment)
            tag_dict = {'cat': matches[0]} if matches else {}
        else:
            continue
        tag_dict['form'] = form
        result.append(tag_dict)
    return result


# ── Misc helpers ──────────────────────────────────────────────────────────────

def if_morph_kqwpft(processed_words, gnp_data):
    """
    If 'kqwpft' is found in gnp_data, change the corresponding processed word's
    POS to 'vj' (verbal adjective) with TAM 'adj_yA_huA'.
    """
    if 'kqwpft' in gnp_data:
        index = gnp_data.index('kqwpft')
        if index < len(processed_words):
            word_entry = processed_words[index]
            modified_entry = (
                word_entry[0], word_entry[1], 'vj',
                *word_entry[3:6], 'adj_yA_huA',
                *word_entry[7:]
            )
            processed_words[index] = modified_entry
    return processed_words


def read_output_data(output_file):
    """Read and return the contents of an output file for post-processing checks."""
    with open(output_file, 'r') as file:
        return file.read()


def analyse_output_data(output_data, morph_input, morphmapping):
    """
    Merge Apertium-generated word forms back into the processed word tuple list.

    Steps:
      1. Join digit + "o'clock" pairs (e.g. ['4', "o'clock"] → ['4o\'clock'])
      2. Build a reverse map from morph output words to their USR indices
      3. Replace words in morph_input_map with the generated forms
      4. Assemble combined_data in the morphmapping order, creating dummy tuples
         for any '-1' entries (words not in the USR, e.g. auxiliaries)
    """
    if isinstance(output_data, str):
        output_data = output_data.strip().split()

    # Step 1: join clock-time tokens
    i = 0
    while i < len(output_data) - 1:
        if output_data[i].isdigit() and output_data[i + 1].lower() == "o'clock":
            output_data[i] = output_data[i] + output_data[i + 1]
            del output_data[i + 1]
        else:
            i += 1

    # Step 2: reverse-lookup from generated word → USR index
    word_to_index_map = {}
    for idx, (_, word) in morphmapping.items():
        if idx != '-1':
            word_to_index_map[word] = idx

    # Step 3: update morph_input_map with generated forms
    morph_input_map = {str(entry[0]): list(entry) for entry in morph_input}
    for word in output_data:
        if word in word_to_index_map:
            index_key = word_to_index_map[word]
            if index_key in morph_input_map:
                morph_input_map[index_key][1] = word

    # Step 4: build final combined_data
    combined_data       = []
    existing_entries_set = set()
    dummy_counter       = -100

    for idx, (orig_idx, word) in morphmapping.items():
        if idx == '-1':
            matched = None
            for entry in morph_input:
                if entry[1] == word and str(entry[0]) not in existing_entries_set:
                    matched = list(entry)
                    break
            if matched:
                combined_data.append(tuple(matched))
                existing_entries_set.add(str(matched[0]))
            else:
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


# ── Compound noun handling ────────────────────────────────────────────────────

def handle_compound_nouns(noun, processed_nouns, category, case, gender, number,
                          person, postposition):
    """
    Split a compound noun (joined by '+') into NC/NC_head sub-tokens.
    The last sub-token gets the NC_head tag; others get NC.
    Also migrates any postposition dict entry from the compound index to the head index.
    """
    dnouns         = noun[1].split('+')
    relation       = noun[4].split(':')[1] if noun[4] else ''
    relation_head  = noun[4].split(':')[0] if noun[4] else ''

    for k in range(len(dnouns)):
        index         = noun[0] + (k * 0.1)
        noun_type     = 'NC'
        if '-' in dnouns[k]:
            # A hyphenated concept (e.g. 'muMbaI-BopAla-xillI') is a multi-part
            # proper noun; clean() would strip the hyphens and fuse the parts
            # ('muṃbaībhopāladillī'), damaging the meaning. Clean each hyphen-part
            # separately and rejoin with hyphens so they survive to the output.
            _parts = []
            for _p in dnouns[k].split('-'):
                _cp = clean(_p)
                if not _cp.strip():
                    _cp = re.sub(r'_\d+$', '', _p).strip()
                if _cp.strip():
                    _parts.append(_cp.strip())
            clean_dnouns = '-'.join(_parts)
        else:
            clean_dnouns  = clean(dnouns[k])
        if not clean_dnouns.strip():
            # clean() removes all digits, which would wipe numeral components of a
            # named entity (e.g. 'sector 23'). Preserve the literal token (minus any
            # sense suffix like '_1') so the number surfaces as-is.
            clean_dnouns = re.sub(r'_\d+$', '', dnouns[k]).strip()
        # The relation postposition goes on the FIRST sub-token so it precedes the
        # whole entity ('known as śiva ballabhapura') instead of landing on the head
        # ('śiva known as ballabhapura'), which would split a multi-word postposition
        # and break the named entity. Only the last sub-token is tagged NC_head.
        is_first = (k == 0)
        is_last  = (k == len(dnouns) - 1)
        # Assign the relation postposition to the FIRST sub-token so it leads the
        # whole entity (e.g. 'known as śiva ballabhapura'). Guard: if the postposition
        # starts with the same word as this sub-token's own cleaned word (e.g.
        # postposition='along with' and word='along'), don't prefix — it would
        # produce 'along with along' instead of just 'along with'.
        if is_first and postposition:
            first_post_word = postposition.split()[0].lower()
            first_tok_word  = clean_dnouns.split()[0].lower() if clean_dnouns else ''
            sub_post = '' if first_post_word == first_tok_word else postposition
        else:
            sub_post = ''
        sub_num  = number if is_last else 's'
        if is_last:
            noun_type = 'NC_head'
        if is_first:
            dict_index = index
        processed_nouns.append(
            (index, clean_dnouns, category, case, gender, sub_num, person,
             noun_type, sub_post, relation_head, relation))

    if noun[0] in processed_postpositions_dict:
        processed_postpositions_dict[dict_index] = processed_postpositions_dict.pop(noun[0])
    return processed_nouns


# ── Post-generation gender-swap ───────────────────────────────────────────────

def handle_unprocessed_all(outputData, processed_nouns):
    """
    Swap the gender of nouns that received a '#'-prefixed output word
    (meaning Apertium did not recognise the word, so try the other gender).
    """
    output_data  = outputData.strip().split(" ")
    has_changes  = False
    reprocess_list = []
    dataIndex    = 0

    for data in output_data:
        dataIndex += 1
        if data[0] == '#':
            for i in range(len(processed_nouns)):
                if round(processed_nouns[i][0]) == dataIndex:
                    if processed_nouns[i][7] != 'proper':
                        temp        = list(processed_nouns[i])
                        temp[4]     = change_gender(processed_nouns[i][4])
                        reprocess_list.append(['n', i, processed_nouns[i][0], temp[4], temp[7]])
                        processed_nouns[i] = tuple(temp)
                        has_changes = True
                        log(f'{temp[1]} reprocessed as noun with new gen:{temp[4]}.')
    return has_changes, reprocess_list, processed_nouns


def handle_star(index_data, output_data, processed_nouns):
    """
    Strip the '*' prefix from starred words (words not in dictionary)
    and flag that reprocessing is needed.
    """
    has_star = False
    if not isinstance(index_data, list):
        raise ValueError("index_data must be a list mapping indices.")
    for dataIndex, data in enumerate(output_data):
        if data.startswith('*'):
            old_tuple = processed_nouns[dataIndex]
            new_tuple = (old_tuple[0], data.replace('*', ''), *old_tuple[2:])
            processed_nouns[dataIndex] = new_tuple
            has_star = True
    return has_star, processed_nouns


# ── Dict-enrichment helpers ───────────────────────────────────────────────────

def apply_dict_to_filtered_data(filtered_data, insert_dict, PP_fulldata_dict_with_ids, **kwargs):
    """
    Generic helper: insert words from a generation sub-dict (verb, calendar, etc.)
    into the filtered sentence strings and into PP_fulldata_dict_with_ids.
    Returns (updated_filtered_data, updated_PP_fulldata_dict_with_ids).
    """
    updated_data = {}
    updated_filtered, updated_ppdict = update_ppdict_and_filtered_data(
        filtered_data, insert_dict, PP_fulldata_dict_with_ids
    )
    for sent_id, sentence_list in updated_filtered.items():
        updated_sentences = []
        for sentence in sentence_list:
            if isinstance(sentence, list):
                sentence = ' '.join(sentence)
            updated_sentences.append(sentence.strip())
        updated_data[sent_id] = updated_sentences
    return updated_data, updated_ppdict


def add_interrogative_dict(filtered_data, interrogative_dict, PP_fulldata_dict_with_ids):
    """Insert interrogative words (who/what/where…) into the generated sentence."""
    return apply_dict_to_filtered_data(filtered_data, interrogative_dict, PP_fulldata_dict_with_ids, replace_underscores=True)

def add_foreign_words_dict(filtered_data, foreign_words_dict, PP_fulldata_dict_with_ids):
    """Insert foreign/transliterated words into the generated sentence."""
    return apply_dict_to_filtered_data(filtered_data, foreign_words_dict, PP_fulldata_dict_with_ids, replace_carets=True)

def add_calendar_dict(filtered_data, calendar_dict, PP_fulldata_dict_with_ids):
    """Insert calendar (date/month) words into the generated sentence."""
    return apply_dict_to_filtered_data(filtered_data, calendar_dict, PP_fulldata_dict_with_ids)

def add_indec_dict(filtered_data, indec_dict, PP_fulldata_dict_with_ids):
    """Insert indeclinable words into the generated sentence."""
    return apply_dict_to_filtered_data(filtered_data, indec_dict, PP_fulldata_dict_with_ids)

def add_verb_dict(filtered_data, verb_dict, PP_fulldata_dict_with_ids):
    """Insert generated verb forms into the generated sentence."""
    return apply_dict_to_filtered_data(filtered_data, verb_dict, PP_fulldata_dict_with_ids)

def add_nonfinite_dict(filtered_data, nonfinite_dict, PP_fulldata_dict_with_ids):
    """Insert non-finite verb forms (gerund, infinitive, participle) into the sentence."""
    return apply_dict_to_filtered_data(filtered_data, nonfinite_dict, PP_fulldata_dict_with_ids)

def add_rad_dict(filtered_data, rad_dict, PP_fulldata_dict_with_ids):
    """Insert RAD (radical/base form) words into the generated sentence."""
    return apply_dict_to_filtered_data(filtered_data, rad_dict, PP_fulldata_dict_with_ids)


import math
import re

def strip_tags(word):
    """Remove brackets, digits, and trailing dots from a word (utility for display)."""
    return re.sub(r'[\(\)\d]', '', word).strip('.')


def update_ppdict_and_filtered_data(filtered_data, insert_dict, ppdict_full):
    """
    Insert words from insert_dict into the right positions in filtered_data sentences,
    and add corresponding tuples to ppdict_full.
    Handles end-of-sentence punctuation gracefully.
    """
    for sent_id, insert_items in insert_dict.items():
        if sent_id not in filtered_data:
            continue
        sentence = filtered_data[sent_id][0]
        words    = sentence.strip().split()
        if sent_id not in ppdict_full:
            ppdict_full[sent_id] = []
        existing_indices = {entry[0] for entry in ppdict_full[sent_id]}
        for idx, tup in insert_items.items():
            if tup[0] not in existing_indices:
                ppdict_full[sent_id].append(tup)
            word        = tup[1]
            insert_pos  = int(idx)
            if word not in words:
                if insert_pos >= len(words):
                    if words[-1] in ['.', '?', '!']:
                        words.insert(len(words) - 1, word)
                    else:
                        words.append(word)
                else:
                    words.insert(insert_pos, word)
        filtered_data[sent_id][0] = ' '.join(words)
    return filtered_data, ppdict_full


# ── LLM mask filler (optional, requires Groq API) ───────────────────────────

def add_masking_model(sentences):
    """
    Replace '[mask]' placeholders in sentences using a Groq LLM call.
    The model inserts the most appropriate preposition (or removes the placeholder).
    Falls back gracefully if the API key is missing.
    """
    from dotenv import load_dotenv
    from groq import Groq
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
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
            temperature=1, max_completion_tokens=1024, top_p=1, stream=False
        )
        response = completion.choices[0].message.content.strip()
        updated_sentences.append(response)
        print(f"Input: {sentence}\nOutput: {response}\n")
    return updated_sentences


# ── WX → Roman transliteration table ─────────────────────────────────────────
# Maps each WX character to its Unicode/Roman equivalent.
# WX is a standard ASCII encoding of Devanagari used in NLP tools.

wx_to_eng = {
    "a": "a",  "A": "ā",  "i": "i",  "I": "ī",
    "u": "u",  "U": "ū",  "e": "e",  "E": "ai",
    "o": "o",  "O": "au",
    "q": "ṛ",  "Q": "ṝ",  "L": "ḷ",
    "M": "ṃ",  "H": "ḥ",
    "z": "̃",  "Z": "'",  "Y": "",
    "k": "k",  "K": "kh", "g": "g",  "G": "gh", "f": "ṅ",
    "c": "c",  "C": "ch", "j": "j",  "J": "jh", "F": "ñ",
    "t": "ṭ",  "T": "ṭh", "d": "ḍ",  "D": "ḍh", "N": "ṇ",
    "w": "t",  "W": "th", "x": "d",  "X": "dh", "n": "n",
    "p": "p",  "P": "ph", "b": "b",  "B": "bh", "m": "m",
    "y": "y",  "r": "r",  "l": "l",  "v": "v",
    "S": "ś",  "R": "ṣ",  "s": "s",  "h": "h",
}

PREPOSITION_LIST = {"of", "for", "to", "with", "by", "on", "at", "in", "from",
                    "about", "as", "into", "like", "after"}


# def wx_to_english(word):
#     """
#     Transliterate a WX-encoded word to Unicode Roman script using wx_to_eng table.
#     Strips any trailing sense-number suffix (e.g. '_1') before converting.
#     Example: 'gaMgA' → 'gaṃgā'
#     """
#     word = word.split('_')[0]  # Remove sense-number suffix like _1
#     return "".join(wx_to_eng.get(ch, ch) for ch in word)
def wx_to_english(word):
    """
    Transliterate a WX-encoded word to Unicode Roman script using wx_to_eng table.
    Strips any trailing sense-number suffix (e.g. '_1') before converting.
    Handles two-character WX sequences (dZ, jZ, DZ) before single characters.
    Example: 'gaMgA' → 'gaṃgā', 'KadZe' → 'khaḍe'
    """
    word = word.split('_')[0]  # Remove sense-number suffix like _1
    # Two-character WX sequences must be checked before single-char lookup
    TWO_CHAR_WX = {
        'dZ': 'ḍ',
        'jZ': 'j',
        'DZ': 'ḍh',
    }
    result = ''
    i = 0
    while i < len(word):
        two = word[i:i+2]
        if two in TWO_CHAR_WX:
            result += TWO_CHAR_WX[two]
            i += 2
        else:
            result += wx_to_eng.get(word[i], word[i])
            i += 1
    return result


def reorder_chunk_to_left_preposition(chunk, sentence_order):
    """
    If a preposition appears somewhere inside a chunk (not at position 0),
    move it to the front of the chunk.
    Example: '[river the from]' → '[from the river]'
    """
    if not chunk.startswith('['):
        return chunk
    words = chunk.strip("[]").replace("_SUBJ", "").split()
    for i, word in enumerate(words):
        if word.lower() in PREPOSITION_LIST and i != 0:
            reordered  = [word] + words[:i] + words[i+1:]
            chunk_core = f"[{' '.join(reordered)}]"
            return chunk_core + ("_SUBJ" if chunk.endswith("_SUBJ") else "")
    return chunk


import re
from collections import defaultdict


def get_verb_tag(tokens, sentence_type):
    """
    Determine the semantic tag for a verb chunk: _ACTIVE, _PASSIVE, _IMPERATIVE, or _QUESTION.

    Detection rules:
    - _IMPERATIVE: sentence_type contains 'imperative'
    - _QUESTION:   sentence_type contains 'interrogative'
    - _PASSIVE:    detected by _rule_passive in postprocessing (jA/jAwA TAM pattern)
    - _ACTIVE:     default

    Note: passive is NOT detected here from the TAM — a present-perfect active sentence
    (yA_hE_1 = 'has gone') also has 'en' TAM but is NOT passive.  Passive detection is
    handled exclusively by _rule_passive() in gold_postprocess.py which inspects the
    actual Hindi passive morpheme (jA/jAwA) in the main verb string.
    """
    if not tokens:
        return ""
    sentence_type_lower = (sentence_type or '').lower()
    if 'imperative' in sentence_type_lower:
        return '_IMPERATIVE'
    elif 'interrogative' in sentence_type_lower:
        return '_QUESTION'
    return '_ACTIVE'


# ══════════════════════════════════════════════════════════════════════════════
# add_chinking()  — The main chunking / phrase-grouping pipeline
# ══════════════════════════════════════════════════════════════════════════════

def add_chinking(sentence, PP_fulldata_dict_with_ids, key,
                 sentence_type=None, span_map=None, ne_words=None, lang='en'):
    """
    Convert a flat list of processed word tuples (PP_fulldata) into a
    structured string of labelled chunks, e.g.:

      [Ganga Mukteshvara]_SUBJ [sacred pilgrimage of the Hindus] [is]_ACTIVE

    The function works in a fixed sequence of merge and chunk steps:

    Pre-merge steps (order matters):
      1.  merge_calendar_construction  — join date+month into one calendar token
      2.  merge_meas_construction      — join count+unit+location into one meas token
      3.  merge_rbks_with_head         — attach adjectival participle to its noun
      4.  merge_nf_with_head           — attach 'nf' (non-finite preposition word) to its verb
      5.  merge_nc_with_nc_head        — join NC modifier + NC_head into one compound token
      6.  merge_adj_with_noun_head     — attach adj to noun ONLY when noun has no own relation
      7.  merge_complete_verbal_complexes — merge rpk/krya/nf chains into verb
      8.  merge_conj_construction      — build coordinated subject chunks from conj operands
      9.  merge_krya_with_main         — attach krya (complex predicate nominal) to verb
      10. merge_aux_neg_main           — merge negation + auxiliaries into a single verbal token

    Chunk-building steps:
      Step 0   : Build complete modifier networks (adj–noun, r6 genitive, intf–adj, etc.)
      Step -1  : Disjunction groups
      Step -0.5: Coordinated groups (rs relation)
      Step -0.3: Duration/range groups (dur, k7t)
      Step 5   : Bare subject tokens (k1, pk1, rsm)
      Step 6.5 : Reason phrase (rh)
      Step 8   : Adjacent adjective pairs (intf+adj)
      Step 9.5 : Preposition-bearing single tokens (k7t, k3, k5, k2p, …)
      Step 9.7 : Auxiliary + main verb complexes
      Step 10  : Any remaining verb complexes
      Step 11  : Fallback — remaining unprocessed tokens
      Step 12  : Unused original sentence words (safety net)

    Final reordering: subject chunks first, then rest in original word order.

    Parameters:
        sentence                  (str)  : The filtered flat sentence string
        PP_fulldata_dict_with_ids (dict) : {sent_id: [word_tuples]}
        key                       (str)  : The sentence ID
        sentence_type             (str)  : Sentence type (%affirmative, %imperative, …)
        span_map                  (dict) : Start/end/unit info from USR for span constructions
        ne_words                  (set/dict): Named-entity words for proper name detection

    Returns:
        str: The chunked sentence string with labelled brackets.
    """
    import re
    from collections import defaultdict

    # Guard: skip error strings from upstream
    data = PP_fulldata_dict_with_ids.get(key, [])
    if isinstance(data, str) or (isinstance(data, list) and len(data) > 0 and isinstance(data[0], str)):
        return sentence


    # ── Step 1: Add dummy tokens for any sentence word not yet in PP_fulldata ──
    # This ensures no word is silently dropped from the output.
    existing_words = set()
    for t in PP_fulldata_dict_with_ids[key]:
        if t[1]:
            for word in t[1].split():
                if '+' in word:
                    for part in word.split('+'):
                        existing_words.add(part.lower())
                else:
                    existing_words.add(word.lower())

    sentence_tokens = sentence.strip().split()
    for word in sentence_tokens:
        word_lower = word.lower()
        if word_lower not in existing_words and word != '.' and word != '<>':
            dummy_token = (0.0, word, '', '', '', '', '', '', '', '', '')
            PP_fulldata_dict_with_ids[key].append(dummy_token)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def sort_index(val):
        """Sort key that converts tuple index to float."""
        try:
            return float(val[0])
        except (ValueError, TypeError):
            return float(str(val[0]).replace("'", ""))

    def float_or_none(x):
        """Safely convert x to float, returning None on failure."""
        try:
            return float(x)
        except:
            return None

    def find_token_by_index(index):
        """Find a token in tagged_data by its float index value."""
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
        """
        Extract the list of display words from a token tuple.
        Splits compound '+'-joined words. Skips structural markers
        (conj, waw, timemeas, etc.) that should never appear in output.
        """
        if not token or len(token) <= 2 or not token[1] or token[1] in [
            'disjunct', '#waw', 'waw', 'conj', 'timemeas', 'span', 'compound', 'nc'
        ]:
            return []
        words = token[1].split()
        processed_words = []
        for word in words:
            if '+' in word:
                processed_words.extend(word.split('+'))
            else:
                print("DEBUG word before append:", word, type(word),
                      len(word) if isinstance(word, (list, tuple)) else "NA")
                processed_words.append(word)
        return processed_words

    def get_words_from_chunk(chunk):
        """Extract lowercase word list from a bracketed chunk string."""
        stripped = chunk.strip('[]_SUBJ')
        return [w.lower() for w in stripped.split()]

    # ── Disjunction group handler ────────────────────────────────────────────

    def handle_disjunction_groups():
        """
        When a 'disjunct' token is found, collect all tokens sharing the same
        last two fields (head, relation) and join them with ' or '.
        Adds the result as a plain chunk (no subject/verb tag).
        """
        disjunct_tokens = [t for t in tagged_data if t[1] == 'disjunct']
        for disjunct in disjunct_tokens:
            disjunct_last_two = (disjunct[-2], disjunct[-1])
            matching_tokens = [
                t for t in tagged_data
                if t != disjunct and len(t) >= 8 and
                (t[-2], t[-1]) == disjunct_last_two and
                float(t[0]) not in used_data_indices
            ]
            if matching_tokens:
                all_tokens = sorted(matching_tokens + [disjunct], key=lambda x: float(x[0]))
                words_list = []
                for t in all_tokens:
                    if t[1] and t[1] != 'disjunct':
                        words_list.extend(get_words(t))
                if words_list:
                    merged_words = ' '.join(words_list)
                    chunk        = f"[{merged_words}]"
                    words_lower  = [w.lower() for w in words_list]
                    if not any(w in used_words for w in words_lower):
                        chunks.append(chunk)
                        used_data_indices.update(float(t[0]) for t in all_tokens)
                        used_words.update(words_lower)
                        print(f"[DEBUG] Added disjunction chunk: {chunk}")
                        return True
            else:
                used_data_indices.add(float(disjunct[0]))
        return False

    # ── Auxiliary + negation + main verb merger ───────────────────────────────

    def merge_aux_neg_main():
        """
        Find each main verb and collect its negation tokens (neg relation)
        and auxiliary tokens (same base index with '.X' float suffix).
        Merge them into a single verbal token ordered: aux → neg → main.
        Example: 'can' + 'not' + 'reached' → 'can not reached'
        """
        main_verbs = [
            t for t in tagged_data
            if len(t) > 8 and 'main' in str(t[-3]) and float(t[0]) not in used_data_indices
        ]
        for main_verb in main_verbs:
            main_idx      = float(main_verb[0])
            complex_parts = [main_verb]

            # Collect negation tokens pointing to this main verb
            neg_tokens = [
                t for t in tagged_data
                if len(t) >= 8 and t[-1] == 'neg' and
                float_or_none(t[-2]) == main_idx and
                float(t[0]) not in used_data_indices
            ]
            complex_parts.extend(neg_tokens)

            # Collect auxiliary tokens with the same base integer index
            aux_tokens = [
                t for t in tagged_data
                if len(t) > 8 and 'auxiliary' in str(t[-3]) and
                str(float(t[0])).startswith(str(int(main_idx))) and
                float(t[0]) not in used_data_indices
            ]
            complex_parts.extend(aux_tokens)

            if len(complex_parts) > 1:
                aux_parts  = [t for t in complex_parts if 'auxiliary' in str(t[-3])]
                neg_parts  = [t for t in complex_parts if t[-1] == 'neg']
                main_part  = next((t for t in complex_parts if 'main' in str(t[-3])), None)

                sorted_aux = sorted(aux_parts, key=lambda t: float(t[0]))
                sorted_neg = sorted(neg_parts, key=lambda t: float(t[0]))

                if lang == 'hi':
                    # Hindi: main verb first, then auxiliaries
                    ordered_words = (([main_part[1]] if main_part else []) +
                                     [n[1] for n in sorted_neg] +
                                     [a[1] for a in sorted_aux])
                else:
                    # English: auxiliaries first, then main verb
                    ordered_words = ([a[1] for a in sorted_aux] +
                                     [n[1] for n in sorted_neg] +
                                     ([main_part[1]] if main_part else []))
                merged_words  = ' '.join(ordered_words)

                merged = list(main_verb)
                merged[1] = merged_words
                merged = tuple(merged)

                for i, t in enumerate(tagged_data):
                    if float(t[0]) == main_idx:
                        tagged_data[i] = merged
                        print(f"[DEBUG] Created aux+neg+main complex: {merged_words}")
                        break

                indices_to_remove = [float(t[0]) for t in complex_parts if float(t[0]) != main_idx]
                original_count    = len(tagged_data)
                tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                print(f"[DEBUG] Removed {len(indices_to_remove)} tokens. Count: {original_count} -> {len(tagged_data)}")
                used_data_indices.update(indices_to_remove)

    # ── Modifier network discovery ────────────────────────────────────────────

    def find_complete_modifier_network():
        """
        Find all groups of tokens that are connected through modifier relations
        (mod, intf, dem, card, rdl, rvks, krvn, quant).

        Strategy:
          1. Collect all (modifier_idx, head_idx, relation) triples.
          2. Build an undirected graph from these triples.
          3. Find connected components (Union-Find).
          4. Return groups of 2+ nodes so they can be chunked together.

        Special cases:
          - 'quant' only connects to noun heads (not verbs)
          - 'mod' propagates to all members of a conjunction group
          - Conjunction groups (k1/k2/r6 with same head) are also connected
        """
        relationships      = []
        conjunction_groups = defaultdict(list)

        # Identify conjunction groups: tokens sharing the same head+relation
        for t in tagged_data:
            if len(t) >= 4:
                token_idx     = float(t[0])
                relation_type = t[-1]
                head_idx      = float_or_none(t[-2]) if len(t) >= 4 else None
                if head_idx and relation_type in {'k2', 'k1', 'r6'}:
                    key_group = (head_idx, relation_type)
                    if t[1] not in {'conj', 'disjunct', 'xvanxva'} and not str(t[1]).startswith('['):
                        conjunction_groups[key_group].append(token_idx)

        MODIFIER_RELATIONS = {'mod', 'intf', 'dem', 'vkvn', 'card', 'rdl', 'rvks', 'krvn'}

        for t in tagged_data:
            if len(t) >= 8:
                modifier_idx  = float(t[0])
                relation_type = t[-1]
                head_idx      = float_or_none(t[-2]) if len(t) >= 8 else None
                if not head_idx:
                    continue

                # quant should only connect to nouns
                if relation_type == 'quant':
                    head_token = None
                    for td in tagged_data:
                        try:
                            if float(td[0]) == head_idx and len(td) > 2 and td[2] == 'n':
                                head_token = td
                                break
                        except:
                            pass
                    if head_token:
                        relationships.append((modifier_idx, head_idx, relation_type))
                    continue

                if relation_type in MODIFIER_RELATIONS:
                    if relation_type == 'mod':
                        # If head is part of a conjunction group, connect modifier to ALL members
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

        # Add internal conjunction-group edges
        for (group_head, group_rel), group_members in conjunction_groups.items():
            if len(group_members) > 1:
                for i, m1 in enumerate(group_members):
                    for j, m2 in enumerate(group_members):
                        if i != j:
                            relationships.append((m1, m2, 'conj'))
                print(f"[DEBUG] Added internal conjunction relationships for group: {group_members}")

        # Build undirected graph
        graph = defaultdict(set)
        for mod_idx, head_idx, rel_type in relationships:
            graph[mod_idx].add(head_idx)
            graph[head_idx].add(mod_idx)

        # Union-Find to discover connected components
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

        for node in graph:
            for neighbor in graph[node]:
                union(node, neighbor)

        components = defaultdict(set)
        for node in graph:
            components[find(node)].add(node)

        all_relationship_nodes = set()
        for mod_idx, head_idx, _ in relationships:
            all_relationship_nodes.add(mod_idx)
            all_relationship_nodes.add(head_idx)
        for node in all_relationship_nodes:
            if node not in parent:
                components[node].add(node)

        networks = [c for c in components.values() if len(c) > 1]
        networks.sort(key=len, reverse=True)  # Largest networks first
        return networks

    def tokens_from_indices(indices):
        """Return sorted token tuples whose float indices are in the given set."""
        return sorted(
            [t for t in tagged_data if float(t[0]) in indices],
            key=lambda x: float(x[0])
        )

    # ── Pre-merge functions ───────────────────────────────────────────────────

    def merge_nf_with_head():
        """
        Merge a non-finite preposition word (nf, float index like 3.2) with its
        integer-index head verb/noun.
        Example: nf='after' at index 8.2, head verb at 8 → 'after goes'
        """
        nf_tokens = [t for t in tagged_data
                     if str(t[-1]) == 'nf' and '.' in str(t[0])]
        for nf in nf_tokens:
            base_idx = str(nf[0]).split('.')[0]
            head     = find_token_by_index(base_idx)
            if not head:
                continue
            head_pos = head[2] if len(head) > 2 else None
            if head_pos in {'v', 'n', 'rpk', 'k7p', 'k2'}:
                merged_words = f"{nf[1]} {head[1]}"
                merged       = tuple(list(head)[:1] + [merged_words] + list(head)[2:])
                for i, t in enumerate(tagged_data):
                    try:
                        if float(t[0]) == float(base_idx):
                            tagged_data[i] = merged
                            break
                    except:
                        continue
                tagged_data[:] = [t for t in tagged_data if str(t[0]) != str(nf[0])]
                print(f"[DEBUG] Merged nf: {nf[1]} + {head[1]} → {merged_words}")

    def merge_rbks_with_head():
        """
        Merge an adjectival participle (rbks relation, float index) with its noun head.
        Example: 'running' at 5.1 modifying 'water' at 5 → 'running water'
        """
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
                merged       = list(head)
                merged[1]    = merged_words
                merged       = tuple(merged)
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == head_idx:
                        tagged_data[i] = merged
                        break
                tagged_data[:] = [t for t in tagged_data if float(t[0]) != float(rbks[0])]
                print(f"[DEBUG] Merged rbks: {rbks[1]} + {head[1]} → {merged_words}")

    def merge_krya_with_main():
        """
        Merge a krya (complex-predicate nominal, float index) with its main verb.
        The nominal is stripped of any 'conj' or bracket constructions first,
        then appended to the verb word.
        Example: main='does' + krya='work' → 'does work'
        """
        krya_tokens = [t for t in tagged_data
                       if len(t) >= 8 and t[-1] == 'krya' and '.' in str(t[0])]
        original_count = len(tagged_data)
        for krya in krya_tokens:
            base_idx = str(krya[0]).split('.')[0]
            main     = find_token_by_index(base_idx)
            if main and len(main) > 2 and main[2] == 'v':
                main_word = re.sub(r'\bconj\b', '', main[1]).strip()
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
                if main:
                    print(f"[DEBUG] Main verb {main[1]} is not a verb (pos: {main[2] if len(main) > 2 else 'unknown'})")
                else:
                    print(f"[DEBUG] No main verb found for base index {base_idx}")

    temp     = None
    r6_words = []
    def merge_re_examples():
        """
        Find all tokens with relation 're' (elaboration/example) that share
        the same head, and merge them into a single token prefixed with 'such as'.
        Example: mountain, river, animals → 'such as mountain, river and animals'
        """
        re_tokens = [t for t in tagged_data if len(t) >= 8 and t[-1] == 're'
                     and float(t[0]) not in used_data_indices]
        if not re_tokens:
            return

        # Group by head index
        from collections import defaultdict
        re_groups = defaultdict(list)
        for t in re_tokens:
            head = t[-2] if len(t) >= 8 else None
            if head:
                re_groups[str(head)].append(t)

        for head_idx, group in re_groups.items():
            if len(group) == 0:
                continue
            group_sorted = sorted(group, key=lambda t: float(t[0]))
            words_list = []
            for t in group_sorted:
                w = get_words(t)
                if w:
                    words_list.append(' '.join(w))

            if not words_list:
                continue

            # Build "such as X, Y and Z"
            if len(words_list) == 1:
                merged_str = 'such as ' + words_list[0]
            elif len(words_list) == 2:
                merged_str = 'such as ' + words_list[0] + ' and ' + words_list[1]
            else:
                merged_str = 'such as ' + ', '.join(words_list[:-1]) + ' and ' + words_list[-1]

            # Replace the first re-token with the merged string, remove the rest
            first = group_sorted[0]
            merged = list(first)
            merged[1] = merged_str
            # Change relation so it goes through as a simple adverb chunk
            if len(merged) >= 8:
                merged[-1] = 're_merged'
            merged = tuple(merged)

            for i, t in enumerate(tagged_data):
                if float(t[0]) == float(first[0]):
                    tagged_data[i] = merged
                    break

            # Remove remaining re-tokens
            remove_idx = {float(t[0]) for t in group_sorted[1:]}
            tagged_data[:] = [t for t in tagged_data if float(t[0]) not in remove_idx]
            print(f"[DEBUG] Merged re-examples: {merged_str}")

    def merge_rvks_with_location():
        """
        When a nonfinite verb (rvks relation) modifies a location noun (k7p/k7/k7t),
        collect the rvks verb and ALL its own arguments (k5 source, k2/k2p destination,
        conj destination group) and merge them into the location noun token.

        Generic pattern:
          jA_1 (rvks → line_27) + k5=mughal_sarai(24) + k2=conj_23(amritsar+dehradun)
          → line_27 word becomes: "main railway line going from mughal sarai to amritsar and dehradun"

        This handles any case where a participial modifier (going/coming/passing etc.)
        of a location noun carries its own source/destination arguments.
        """
        # Find all rvks nonfinite verbs
        rvks_tokens = [
            t for t in tagged_data
            if len(t) > 10 and t[-1] == 'rvks' and t[2] == 'v'
            and float(t[0]) not in used_data_indices
        ]
        for rvks_tok in rvks_tokens:
            rvks_idx = float(rvks_tok[0])
            head_idx = float_or_none(rvks_tok[-2])
            if not head_idx:
                continue
            # Find the head location noun
            # The head may be an NC compound (27 -> 27.0/27.1/27.2),
            # so also search by integer base index
            head_tok = find_token_by_index(head_idx)
            if not head_tok:
                # Try finding by integer base index (NC compounds)
                base_int = int(head_idx)
                candidates = sorted(
                    [t for t in tagged_data
                     if int(float(t[0])) == base_int
                     and float(t[0]) not in used_data_indices],
                    key=lambda t: float(t[0])
                )
                # Use the NC_head token (last one) for relation check
                head_tok = candidates[-1] if candidates else None
            if not head_tok or float(head_tok[0]) in used_data_indices:
                continue
            # Only merge when head is a location noun (k7p/k7/k7t)
            if head_tok[-1] not in ('k7p', 'k7', 'k7t', 'NC_head', 'NC'):
                continue
            # Get the actual location relation from any of the compound sub-tokens
            head_rel = head_tok[-1]
            if head_rel in ('NC', 'NC_head'):
                base_int = int(float(head_tok[0]))
                for t in tagged_data:
                    if int(float(t[0])) == base_int and t[-1] in ('k7p', 'k7', 'k7t'):
                        head_rel = t[-1]
                        break
            if head_rel not in ('k7p', 'k7', 'k7t', 'NC', 'NC_head'):
                continue

            # Collect arguments of the rvks verb by base integer index
            # (handles NC compound nouns split into float sub-indices like 24.0, 24.1)
            source_base_indices = []   # base int indices for k5 sources
            dest_base_indices = []     # base int indices for k2/k2p destinations
            pending_k2_bases = []      # (base, word) for direct k2 dests before conj sort
            conj_tokens = []           # conj/disjunct tokens (already have merged names)
            all_arg_base_indices = set()

            for t in tagged_data:
                if float(t[0]) in used_data_indices or float(t[0]) == rvks_idx:
                    continue
                if len(t) < 8:
                    continue
                t_head = float_or_none(t[-2])
                t_rel = t[-1]
                if t_head != rvks_idx:
                    continue
                base = int(float(t[0]))
                if t_rel in ('k5', 'k5prk'):
                    if base not in source_base_indices:
                        source_base_indices.append(base)
                    all_arg_base_indices.add(base)
                elif t_rel in ('k2', 'k2p'):
                    if t[1] in ('conj', 'disjunct'):
                        conj_tokens.append(t)
                        all_arg_base_indices.add(base)
                    else:
                        # Direct k2 non-conj destinations: collect separately first,
                        # will be sorted and added to dest_base_indices after conj processing
                        pending_k2_bases.append((base, t[1]))
                        all_arg_base_indices.add(base)
                elif t_rel == 'k2s':
                    if base not in dest_base_indices:
                        dest_base_indices.append(base)
                    all_arg_base_indices.add(base)

            # Add direct k2 destinations (non-conj) now, but mark them for resorting
            # if they turn out to be conj operands (handled in sibling loop below)
            for base, word in pending_k2_bases:
                if base not in dest_base_indices:
                    dest_base_indices.append(base)

            # For conj tokens: find their sibling operands in tagged_data.
            # Operands share the same (head, rel) as the conj token itself.
            # Sort: tokens WITHOUT trailing 'and'/'or' come first (op1),
            # tokens WITH connector come after (op2+). This preserves USR order.
            conj_operand_base_indices = set()
            for conj_tok in list(conj_tokens):
                conj_head = float_or_none(conj_tok[-2])
                conj_rel = conj_tok[-1]
                siblings = []
                for t in tagged_data:
                    if float(t[0]) in used_data_indices:
                        continue
                    if float(t[0]) == float(conj_tok[0]) or float(t[0]) == rvks_idx:
                        continue
                    if len(t) < 8:
                        continue
                    if float_or_none(t[-2]) == conj_head and t[-1] == conj_rel:
                        if t[1] not in ('conj', 'disjunct'):
                            siblings.append(t)
                # Sort: no trailing connector = op1 (0), trailing 'and'/'or' = op2 (1)
                siblings.sort(key=lambda tok: (
                    1 if tok[1].lower().rstrip().endswith((' and', ' or', ' ,')) else 0
                ))
                # Remove siblings from dest_base_indices (added in wrong order)
                # then re-add in correct op1-first order
                for sib in siblings:
                    base = int(float(sib[0]))
                    if base in dest_base_indices:
                        dest_base_indices.remove(base)
                # Now add in sorted order (op1 first)
                for sib in siblings:
                    base = int(float(sib[0]))
                    dest_base_indices.append(base)
                    all_arg_base_indices.add(base)
                    conj_operand_base_indices.add(base)

            conj_base_indices = {int(float(t[0])) for t in conj_tokens} | conj_operand_base_indices

            if not source_base_indices and not dest_base_indices and not conj_tokens:
                continue  # rvks verb has no arguments to merge

            # Collect NC sub-tokens for compound head nouns
            base_int = int(float(head_tok[0]))
            nc_sub_toks = sorted(
                [t for t in tagged_data
                 if int(float(t[0])) == base_int
                 and float(t[0]) not in used_data_indices],
                key=lambda t: float(t[0])
            )
            head_words = []
            for nt in nc_sub_toks:
                head_words.extend([w for w in get_words(nt) if w not in ('<>', 'in', 'on', 'at')])
            if not head_words:
                head_words = get_words(head_tok)

            rvks_words = get_words(rvks_tok)

            # Build: head + going + from source + to dest1 and dest2
            merged_parts = head_words + rvks_words

            # Add sources (single 'from')
            for src_base in sorted(source_base_indices):
                sub_toks = sorted(
                    [t for t in tagged_data if int(float(t[0])) == src_base
                     and float(t[0]) not in used_data_indices],
                    key=lambda t: float(t[0])
                )
                src_words = []
                for st in sub_toks:
                    src_words.extend([w for w in get_words(st) if w not in ('<>', 'from', 'to')])
                if src_words:
                    merged_parts.append('from')
                    merged_parts.extend(src_words)

            # Add destinations (single 'to', 'and' between multiple)
            # Use dest_base_indices as-is (already sorted op1-first by sibling loop)
            all_dest_words = []
            for dest_base in dest_base_indices:
                sub_toks = sorted(
                    [t for t in tagged_data if int(float(t[0])) == dest_base
                     and float(t[0]) not in used_data_indices],
                    key=lambda t: float(t[0])
                )
                dest_words = []
                for st in sub_toks:
                    # Strip trailing 'and'/'or' from word — we add our own connector
                    words = get_words(st)
                    clean = [w for w in words if w not in ('<>', 'from', 'to', 'and', 'or')]
                    dest_words.extend(clean)
                if dest_words:
                    if all_dest_words:
                        all_dest_words.append('and')
                    all_dest_words.extend(dest_words)

            # conj operands were already added to rvks_arg_base_indices above
            # (via conj_operand_base_indices). No separate loop needed.
            pass

            if all_dest_words:
                merged_parts.append('to')
                merged_parts.extend(all_dest_words)

            merged_word = ' '.join(w for w in merged_parts if w)
            print("[DEBUG] merge_rvks_with_location: %s" % merged_word)

            # Mark rvks verb, its argument tokens, and NC sub-tokens as used/removed
            indices_to_remove = {rvks_idx}
            # Remove all float sub-tokens of source and dest base indices
            for base in all_arg_base_indices | conj_base_indices:
                for t in tagged_data:
                    if int(float(t[0])) == base:
                        indices_to_remove.add(float(t[0]))
            # Remove NC sub-tokens of head (they're merged into the new token)
            for nt in nc_sub_toks:
                indices_to_remove.add(float(nt[0]))
            # Build updated head token at the base integer index
            # Use 'on' as postposition for route/line/road/surface location nouns
            _surface_concepts = {
                'line', 'road', 'route', 'path', 'track', 'rail', 'railway',
                'highway', 'street', 'avenue', 'lane', 'bridge', 'way',
                'runway', 'platform', 'course', 'belt', 'surface',
            }
            # Check if the head noun is a surface concept
            head_concept = (nc_sub_toks[-1][1] if nc_sub_toks else head_tok[1]).lower().split('_')[0]
            # Also check ALL NC parts for surface keywords
            all_nc_words = ' '.join(st[1].lower() for st in nc_sub_toks) if nc_sub_toks else head_concept
            is_surface = any(sw in all_nc_words for sw in _surface_concepts)
            loc_ppost = 'on' if is_surface else head_tok[-1] if head_tok[-1] in ('k7', 'k7p', 'k7t') else 'in'

            # Prepend the location preposition directly to the merged word
            # so add_chunk's Step 1 finds it at the front (not as stranded preposition)
            merged_word_with_prep = loc_ppost + ' ' + merged_word
            # Update processed_postpositions_dict so add_postposition doesn't re-add
            if base_int in processed_postpositions_dict:
                del processed_postpositions_dict[base_int]
            for sub_float_idx in [float(nt[0]) for nt in nc_sub_toks]:
                if sub_float_idx in processed_postpositions_dict:
                    del processed_postpositions_dict[sub_float_idx]

            base_head = list(nc_sub_toks[-1] if nc_sub_toks else head_tok)
            base_head[1] = merged_word_with_prep
            base_head[0] = base_int
            if len(base_head) > 8:
                base_head[8] = None  # postposition already embedded in word
            merged_head = tuple(base_head)
            # Remove old tokens then add merged head
            tagged_data[:] = [t for t in tagged_data
                               if float(t[0]) not in indices_to_remove]
            tagged_data.append(merged_head)


    def merge_nc_with_nc_head():
        """
        Merge NC (noun compound modifier) + NC_head tokens into a single compound noun phrase.

        NC tokens appear as float indices like 3.0, 3.1 from handle_compound_nouns().
        The merger:
          1. Groups NC and NC_head tokens by their integer base index
          2. Extracts any leading preposition from the NC_head word string
          3. Detects whether the compound is a Named Entity (NE) or a common compound:
             - NE: modifier words come BEFORE head (e.g. 'Ganga fair')
             - Common compound: head comes BEFORE modifiers (e.g. 'guest house')
          4. Builds the merged word string in correct order
          5. Also attaches any r6 (genitive) modifiers pointing at the base index

        NE detection uses three checks:
          Check 1: NC modifier starts with 'the' → NE
          Check 2: NC_head's first content word starts with '#' → NE (proper name)
          Check 3: NC modifier's first content word is in ne_words set → NE
        """
        prepositions = {'to', 'in', 'on', 'at', 'for', 'with', 'by', 'from', 'of',
                        'about', 'after', 'before', 'during', 'since', 'until',
                        'over', 'under', 'between', 'among'}

        # Collect NC and NC_head tokens
        nc_tokens      = [t for t in tagged_data if len(t) > 7 and t[7] == 'NC']
        nc_head_tokens = [t for t in tagged_data if len(t) > 7 and t[7] == 'NC_head']

        # Group by integer base index
        nc_groups = defaultdict(list)
        for nc in nc_tokens:
            nc_groups[int(float(nc[0]))].append(nc)
        for nc_head in nc_head_tokens:
            nc_groups[int(float(nc_head[0]))].append(nc_head)

        for base_idx, group in nc_groups.items():
            if len(group) < 2:
                continue
            group_sorted    = sorted(group, key=lambda t: float(t[0]))
            all_nc_modifiers = [t for t in group_sorted if t[7] == 'NC']
            nc_head_token    = next((t for t in group_sorted if t[7] == 'NC_head'), None)
            if not all_nc_modifiers or not nc_head_token:
                continue

            PREPOSITIONS = {
                'from', 'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
                'about', 'among', 'between', 'through', 'into', 'onto', 'upon',
                'within', 'without', 'across', 'along', 'around', 'behind',
                'below', 'beside', 'over', 'under', 'after', 'before', '<>'
            }

            # Extract any leading preposition from NC_head
            nc_head_words   = nc_head_token[1].split()
            leading_preps   = []
            remaining_head_words = []
            collecting_preps = True
            nc_relation     = nc_head_token[-1] if len(nc_head_token) >= 8 else ''
            EXTRACT_PREPS   = PREPOSITIONS if nc_relation == 'r6' else {p for p in PREPOSITIONS if p != 'of'}

            for w in nc_head_words:
                if collecting_preps and w.lower() in EXTRACT_PREPS and w.lower() != 'the':
                    leading_preps.append(w)
                else:
                    collecting_preps = False
                    remaining_head_words.append(w)

            # Collect modifier words
            nc_mod_words = []
            for mod_tok in all_nc_modifiers:
                nc_mod_words.extend(mod_tok[1].split())

            # ── Detect Named Entity vs common compound ──
            is_named_entity = False
            SKIP_WORDS = {'the', 'a', 'an', 'of', 'from', 'to', 'in', 'on', 'at', 'by', 'with', 'for', 'among', 'between'}
            ne_word_set = ne_words or set()

            def word_is_ne(word):
                """Check if a word's root form matches any NE in ne_word_set."""
                w = word.lstrip('#').split('_')[0].lower()
                return any(w == ne.lower() or w == ne.split('_')[0].lower() for ne in ne_word_set)

            # Check 1: modifier starts with 'the' → NE
            for mod_tok in all_nc_modifiers:
                if mod_tok[1].startswith('the '):
                    is_named_entity = True
                    break

            # Check 2: head content word starts with '#' → NE (proper name)
            if not is_named_entity:
                if remaining_head_words and remaining_head_words[0].startswith('#'):
                    is_named_entity = True

            # Check 3: both modifier and head are NE words
            if not is_named_entity:
                mod_flat    = []
                for mod_tok in all_nc_modifiers:
                    mod_flat.extend(mod_tok[1].split())
                mod_content = [w for w in mod_flat if w.lower() not in SKIP_WORDS]
                if mod_content and (mod_content[0].startswith('#') or word_is_ne(mod_content[0])):
                    head_content = [w for w in remaining_head_words if w.lower() not in SKIP_WORDS]
                    if head_content and (head_content[0].startswith('#') or word_is_ne(head_content[0])):
                        is_named_entity = True

            # English noun compounds are MODIFIER + HEAD ("aśoka pillar",
            # "bus station", "Ganga fair"). Measured to improve word-order
            # similarity vs gold over the previous head-first realisation.
            all_words = leading_preps + nc_mod_words + remaining_head_words

            # Strip trailing conjunctions
            while all_words and all_words[-1] in {'and', 'or', ','}:
                all_words.pop()

            merged_words = ' '.join(all_words)
            merged       = list(nc_head_token)
            merged[1]    = merged_words
            merged       = tuple(merged)

            for i, t in enumerate(tagged_data):
                if float(t[0]) == float(nc_head_token[0]):
                    tagged_data[i] = merged
                    break

            # Remove all NC modifier tokens
            indices_to_remove = [float(t[0]) for t in all_nc_modifiers]
            tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]

            # Attach any r6 (genitive) modifiers pointing at this compound's base index
            nc_head_float = float(nc_head_token[0])
            base_idx_float = float(base_idx)
            r6_tokens = [
                t for t in tagged_data
                if len(t) >= 8 and t[-1] == 'r6' and
                float_or_none(t[-2]) == base_idx_float and
                float(t[0]) not in indices_to_remove
            ]
            r6_indices_to_remove = []
            for r6t in r6_tokens:
                r6_words_local = r6t[1].split()
                is_pron        = (r6t[2] == 'p') if len(r6t) > 2 else False
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == nc_head_float:
                        temp_t = list(t)
                        if is_pron:
                            # Possessive pronoun goes BEFORE the compound
                            temp_t[1] = ' '.join(r6_words_local) + ' ' + temp_t[1]
                        else:
                            # Noun genitive goes AFTER: 'beauty of the garden'
                            temp_t[1] = temp_t[1] + ' ' + ' '.join(r6_words_local)
                        tagged_data[i] = tuple(temp_t)
                        break
                r6_indices_to_remove.append(float(r6t[0]))
            if r6_indices_to_remove:
                tagged_data[:] = [t for t in tagged_data if float(t[0]) not in r6_indices_to_remove]

    def merge_conj_construction():
        """
        Build coordinated subject chunks from conjunction tokens.

        Finds each token that contains 'conj' in its word or POS field, then
        collects its operands via three methods (in priority order):
          Method 1: tokens with explicit opN reference in the construction field
          Method 2: tokens sharing the same (head, relation) as the conj token
          Method 3: tokens with an empty relation (fallback)

        Also extends operands with any card/dem/quant modifiers pointing to them.
        Joins all operand words with 'and' or ', … and' and adds as a _SUBJ chunk.
        Cleans 'conj' from the verbal token so the verb can be emitted normally.
        """
        conj_heads = [
            t for t in tagged_data
            if len(t) > 1 and t[1] and (
                'conj' in str(t[1]).lower() or
                (len(t) > 6 and 'conj' in str(t[6]).lower())
            )
        ]
        for conj_head in conj_heads:
            head_idx  = float(conj_head[0])
            op_tokens = []

            # Method 1: explicit opN in construction field (index 8)
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
                                td[1] not in {'conj', 'disjunct', 'xvanxva'}):
                            op_tokens.append(td)
                            print(f"[DEBUG] Found op token (construction field): {td[1]}")
                            break

            # Method 2: tokens sharing same head & relation as conj_head
            if not op_tokens:
                conj_rel         = conj_head[-1] if len(conj_head) >= 8 else ''
                conj_head_of_head = float_or_none(conj_head[-2]) if len(conj_head) >= 8 else None
                if conj_rel and conj_head_of_head:
                    for td in tagged_data:
                        if (float(td[0]) != head_idx and
                                float(td[0]) not in used_data_indices and
                                len(td) >= 8 and
                                td[-1] == conj_rel and
                                float_or_none(td[-2]) == conj_head_of_head and
                                td[1] not in {'conj', 'disjunct', 'xvanxva'} and
                                td[1] not in {'.', '?', '!', ','}):
                            op_tokens.append(td)
                            print(f"[DEBUG] Found op token (same head/rel): {td[1]}")

            # Method 3: empty-relation fallback
            if not op_tokens:
                for td in tagged_data:
                    if (len(td) >= 2 and td[-1] == '' and
                            float(td[0]) > 0 and
                            td[1] not in {'.', '?', '!', ',', ';', ':', 'conj', 'disjunct', 'xvanxva'} and
                            float(td[0]) != head_idx and
                            float(td[0]) not in used_data_indices):
                        op_tokens.append(td)
                        print(f"[DEBUG] Found op token (empty-rel fallback): {td[1]}")

            if not op_tokens:
                continue

            op_tokens_sorted = sorted(op_tokens, key=lambda t: float(t[0]))

            # Extend with card/dem/quant modifiers of each op token
            extended_op_tokens = list(op_tokens_sorted)
            op_base_indices    = set()
            for op in op_tokens_sorted:
                op_base_indices.add(float(op[0]))
                op_base_indices.add(float(int(float(op[0]))))
            for td in tagged_data:
                if (float(td[0]) not in used_data_indices and
                        td not in extended_op_tokens and
                        len(td) >= 8 and
                        td[-1] in {'card', 'dem', 'quant'} and
                        td[1] not in {'conj', 'disjunct', 'xvanxva'}):
                    td_head = float_or_none(td[-2])
                    if td_head in op_base_indices:
                        extended_op_tokens.append(td)

            extended_op_tokens_sorted = sorted(extended_op_tokens, key=lambda t: float(t[0]))

            # Build op word list, stripping '<>' placeholders and trailing 'and'
            op_words_list = []
            for op in extended_op_tokens_sorted:
                words = [w for w in get_words(op) if w != '<>']
                if words:
                    op_words_list.append(' '.join(words))
            cleaned = []
            for w in op_words_list:
                ws = w.split()
                while ws and ws[-1] in {'and', ','}:
                    ws.pop()
                if ws:
                    cleaned.append(' '.join(ws))
            op_words_list = cleaned

            if not op_words_list:
                continue

            # Join operands with 'and'
            if len(op_words_list) == 1:
                merged_str = op_words_list[0]
            elif len(op_words_list) == 2:
                merged_str = f"{op_words_list[0]} and {op_words_list[1]}"
            else:
                merged_str = ', '.join(op_words_list[:-1]) + f" and {op_words_list[-1]}"

            print(f"[DEBUG] Merged conj ops: {merged_str}")

            # Clean 'conj' from the verbal token
            for i, t in enumerate(tagged_data):
                if float(t[0]) == head_idx:
                    temp_t = list(t)
                    real_verb = re.sub(r'\bconj\b', '', temp_t[1]).strip()
                    real_verb = re.sub(r'\[.*?\]', '', real_verb).strip()
                    temp_t[1] = real_verb if real_verb else temp_t[1]
                    tagged_data[i] = tuple(temp_t)
                    print(f"[DEBUG] Cleaned conj verb to: {temp_t[1]}")
                    break

            conj_rel = conj_head[-1] if len(conj_head) >= 8 else ''
            is_subj_conj = conj_rel in ('k1', 'k1s', 'pk1', 'k2', 'k2s', '')
            chunk_tag = '_SUBJ' if is_subj_conj else ''
            subject_chunk = f"[{merged_str}]{chunk_tag}"
            if subject_chunk not in chunks:
                chunks.append(subject_chunk)
                print(f"[DEBUG] Added {'subject' if is_subj_conj else 'conj'} chunk: {subject_chunk}")

            op_indices = {float(t[0]) for t in extended_op_tokens_sorted}
            for t in extended_op_tokens_sorted:
                used_data_indices.add(float(t[0]))
                used_words.update(w.lower() for w in get_words(t) if w != '<>')

            before = len(tagged_data)
            tagged_data[:] = [t for t in tagged_data if float(t[0]) not in op_indices]
            print(f"[DEBUG] Removed {len(op_indices)} op tokens. Count: {before} -> {len(tagged_data)}")

    def merge_adj_with_noun_head():
        """
        Merge adjective (mod relation) into its noun head ONLY when the noun has
        an empty dependency relation (meaning it's an operand, not a grammatical argument).
        Grammatical arguments (k1, k5, etc.) are handled later in the modifier network.
        Example: adj 'big' + noun 'tree' (empty relation) → 'big tree'
        """
        adj_tokens = [
            t for t in tagged_data
            if len(t) >= 8 and t[-1] == 'mod' and
            len(t) > 2 and t[2] == 'adj' and
            float(t[0]) not in used_data_indices
        ]
        for adj in adj_tokens:
            head_idx = float_or_none(adj[-2]) if len(adj) >= 8 else None
            if not head_idx:
                continue
            head     = find_token_by_index(head_idx)
            if not head or float(head[0]) in used_data_indices:
                continue
            head_rel = head[-1] if len(head) >= 8 else ''
            if head_rel != '':
                # Head has its own grammatical relation — skip, handled by modifier network
                continue
            if len(head) > 2 and head[2] in ('n', 'NC_head', 'NC'):
                merged_words = f"{adj[1]} {head[1]}"
                merged       = list(head)
                merged[1]    = merged_words
                merged       = tuple(merged)
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == head_idx:
                        tagged_data[i] = merged
                        break
                tagged_data[:] = [t for t in tagged_data if float(t[0]) != float(adj[0])]
                used_data_indices.add(float(adj[0]))
                print(f"[DEBUG] Merged adj+noun: {adj[1]} + {head[1]} → {merged_words}")

    def merge_calendar_construction():
        """
        Find 'calendar'/'calender' tokens and merge all their component tokens
        (date digit + month name) into a single date string.
        Components are identified via the construction field (component relation)
        or by adjacent tokens with empty head/relation.
        Example: '13' + 'November' → merged into the calendar token as '13 November'
        """
        calendar_keywords = {'calendar', 'calender'}
        cal_tokens = [
            t for t in tagged_data
            if len(t) > 1 and t[1] and any(kw in str(t[1]).lower() for kw in calendar_keywords)
        ]
        for cal_token in cal_tokens:
            cal_idx          = float(cal_token[0])
            component_tokens = []
            print(f"[DEBUG] Found calendar token: {cal_token[1]} at index {cal_token[0]}")

            # Find components via construction field
            for t in PP_fulldata_dict_with_ids[key]:
                if len(t) <= 8:
                    continue
                construction_field = t[8]
                if isinstance(construction_field, str) and ':' in construction_field:
                    const_parts = construction_field.split(':')
                    try:
                        const_head = float(const_parts[0])
                        const_rel  = const_parts[1]
                        if const_head == cal_idx and 'component' in const_rel:
                            t_idx = float(t[0])
                            for td in tagged_data:
                                if float(td[0]) == t_idx:
                                    component_tokens.append(td)
                                    print(f"[DEBUG] Found calendar component: {td[1]}")
                                    break
                    except (ValueError, TypeError):
                        pass

            # Fallback: adjacent tokens with empty head
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
                merged_parts     = []
                for ct in component_sorted:
                    merged_parts.extend(get_words(ct))
                if merged_parts:
                    merged_word  = ' '.join(merged_parts)
                    print(f"[DEBUG] Merged calendar: {merged_word}")
                    merged_token    = list(cal_token)
                    merged_token[1] = merged_word
                    merged_token    = tuple(merged_token)
                    for i, t in enumerate(tagged_data):
                        if float(t[0]) == cal_idx:
                            tagged_data[i] = merged_token
                            break
                    indices_to_remove = {float(t[0]) for t in component_tokens}
                    original_count    = len(tagged_data)
                    tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                    print(f"[DEBUG] Removed {len(indices_to_remove)} calendar tokens. Count: {original_count} -> {len(tagged_data)}")

    def merge_meas_construction():
        """
        Find measurement tokens (distmeas, timemeas, massmeas, …) and merge their
        count, unit, start, end, and location sub-tokens into one measurement phrase.

        Count is found via (in order):
          1. construction field pointing to the meas token
          2. construction field pointing to the verb head
          3. numeric token in the rmeas chain

        Unit is found via indec tokens.
        Start/end tokens use span_map if available.
        Location is found as a k7p/k7t token pointing to the meas head.

        Final merged order: [start] [end] count unit location
        """
        meas_keywords = {
            'distmeas', 'timemeas', 'massmeas', 'heightmeas', 'widthmeas',
            'depthmeas', 'lengthmeas', 'tempmeas', 'weightmeas', 'span', 'dist_meas'
        }
        meas_tokens = [
            t for t in tagged_data
            if len(t) > 1 and t[1] and any(kw in str(t[1]).lower() for kw in meas_keywords)
        ]
        for meas_token in meas_tokens:
            meas_idx      = float(meas_token[0])
            meas_head_idx = float_or_none(meas_token[-2]) if len(meas_token) >= 8 else None
            count_token   = None
            unit_tokens   = []
            location_tokens = []

            # Step 1: count via construction field → meas token
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

            # Step 2: count via construction field → verb head
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

            # Step 3: count via rmeas chain (numeric token)
            if not count_token:
                rmeas_chain = {meas_idx}
                if meas_head_idx:
                    rmeas_chain.add(meas_head_idx)
                for td in tagged_data:
                    if (len(td) >= 8 and
                            td[-1] in ('rmeas', 'count', 'k7p', 'k7t') and
                            float(td[0]) not in used_data_indices and
                            float(td[0]) != meas_idx):
                        td_head    = float_or_none(td[-2])
                        word       = td[1] if len(td) > 1 else ''
                        pos        = td[2] if len(td) > 2 else ''
                        noun_type  = td[7] if len(td) > 7 else ''
                        is_numeric = (
                            word.replace('.', '').isdigit() or
                            noun_type in ('digit', 'numex', 'meas') or
                            pos == 'numex'
                        )
                        is_unit    = (pos == 'indec' or noun_type == 'unit')
                        if td_head in rmeas_chain and is_numeric and not is_unit:
                            count_token = td
                            print(f"[DEBUG] Found count token (rmeas chain): {td[1]}")
                            break

            # Step 4: find unit tokens (indec type)
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

            # Step 4b: start/end tokens via span_map.
            # An NE start/end can be a noun compound (e.g. 'prayAga station') that
            # handle_compound_nouns split into NC sub-tokens at float indices like
            # 20.0/20.1. Collect ALL sub-tokens sharing the integer base index so the
            # inside word(s) stay inside the span ('from prayAga station to ...').
            start_tokens = []
            end_tokens = []
            span_index_str = str(int(meas_idx))
            if span_map and span_index_str in span_map:
                span_entry = span_map[span_index_str]
                for tidx in span_entry.get('start', []):
                    for td in tagged_data:
                        if str(int(float(td[0]))) == tidx and float(td[0]) not in used_data_indices:
                            start_tokens.append(td)
                            print(f"[DEBUG] Found start token via span_map: {td[1]}")
                for tidx in span_entry.get('end', []):
                    for td in tagged_data:
                        if str(int(float(td[0]))) == tidx and float(td[0]) not in used_data_indices:
                            end_tokens.append(td)
                            print(f"[DEBUG] Found end token via span_map: {td[1]}")
                for tidx in span_entry.get('unit', []):
                    for td in tagged_data:
                        if (str(int(float(td[0]))) == tidx and
                                float(td[0]) not in used_data_indices and
                                td not in unit_tokens):
                            unit_tokens.append(td)
                            print(f"[DEBUG] Found unit token via span_map: {td[1]}")
                            break
            start_tokens.sort(key=lambda t: float(t[0]))
            end_tokens.sort(key=lambda t: float(t[0]))
            start_token = start_tokens[0] if start_tokens else None
            end_token = end_tokens[0] if end_tokens else None

            # Step 5: find location token (k7p/k7t pointing to meas_head or verb)
            count_idx  = float(count_token[0]) if count_token else None
            unit_idxs  = {float(ut[0]) for ut in unit_tokens}
            exclude    = {meas_idx, count_idx} | unit_idxs
            exclude.discard(None)
            rmeas_intermediates = set()
            for td in tagged_data:
                if (len(td) >= 8 and td[-1] == 'rmeas' and float(td[0]) not in exclude):
                    td_head = float_or_none(td[-2])
                    if td_head == meas_idx or td_head == meas_head_idx:
                        rmeas_intermediates.add(float(td[0]))

            meas_head_token = None
            if meas_head_idx:
                for td in tagged_data:
                    if float(td[0]) == meas_head_idx and float(td[0]) not in exclude:
                        meas_head_token = td
                        break

            if meas_head_token and meas_head_token[-1] in ('k7p', 'k7t', 'k7', 'rmeas'):
                location_tokens.append(meas_head_token)
                print(f"[DEBUG] Found location token (meas_head is spatial): {meas_head_token[1]}")
            else:
                for td in tagged_data:
                    td_f    = float(td[0])
                    if td_f in used_data_indices or td_f in exclude:
                        continue
                    if len(td) < 8:
                        continue
                    td_head = float_or_none(td[-2])
                    td_rel  = td[-1]
                    td_word = td[1] if len(td) > 1 else ''
                    if td_word.replace('.', '').isdigit():
                        continue
                    if td_rel in ('k7p', 'k7t', 'k7'):
                        if (td_head == meas_head_idx or
                                td_head == meas_idx or
                                td_head in rmeas_intermediates):
                            location_tokens.append(td)
                            print(f"[DEBUG] Found location token: {td[1]}")

            # Step 5b: find k5 (source) compound noun sharing same head as meas token
            # e.g. [dist_meas_1] k7p->verb AND [ne_4] k5->verb
            # Collect NC sub-tokens by base integer index so compound names like
            # "mugala sarAya station" (28.0, 28.1, 28.2) merge into ONE source.
            source_tokens = []  # each entry = list of NC sub-tokens for one source NE
            if meas_head_idx:
                # Find all k5 tokens (and their NC sub-tokens) pointing to meas head
                k5_base_indices = set()
                for td in tagged_data:
                    td_f = float(td[0])
                    if td_f in used_data_indices or td_f in exclude:
                        continue
                    if len(td) < 8:
                        continue
                    td_head = float_or_none(td[-2])
                    td_rel = td[-1]
                    if td_head == meas_head_idx and td_rel in ('k5', 'k5prk'):
                        k5_base_indices.add(int(td_f))
                        print("[DEBUG] Found k5 base for dist_meas: %s (base %d)" % (td[1], int(td_f)))
                # For each k5 base index, collect ALL float sub-tokens in order
                for base_idx in sorted(k5_base_indices):
                    sub_toks = sorted(
                        [td for td in tagged_data
                         if int(float(td[0])) == base_idx
                         and float(td[0]) not in used_data_indices
                         and float(td[0]) not in exclude],
                        key=lambda t: float(t[0])
                    )
                    if sub_toks:
                        source_tokens.append(sub_toks)
                        print("[DEBUG] Found source compound for dist_meas: %s" % [t[1] for t in sub_toks])

            # For dist_meas: filter location_tokens to ONLY include tokens that
            # directly point to the meas token (not siblings that share the same
            # verb head) — sibling k7p tokens like railway line should NOT be
            # included as location of the measurement.
            is_dist_meas = any('dist' in str(meas_token[1]).lower() for _ in [1])
            if is_dist_meas and source_tokens:
                # Remove sibling k7p tokens from location_tokens
                # Only keep tokens whose head is the meas itself, not the verb
                location_tokens = [
                    lt for lt in location_tokens
                    if float_or_none(lt[-2]) == meas_idx
                ]

            # Step 6: build merged measurement phrase — order: start end count unit source location
            merged_parts = []
            # Add 'at' prefix for distance measurements to produce "at 7 miles from..."
            if is_dist_meas and (count_token or unit_tokens):
                merged_parts.append('at')
            if start_tokens and end_tokens:
                for st in start_tokens:
                    merged_parts.extend([w for w in get_words(st) if w != '<>'])
                for et in end_tokens:
                    merged_parts.extend([w for w in get_words(et) if w != '<>'])
            elif start_tokens:
                for st in start_tokens:
                    merged_parts.extend([w for w in get_words(st) if w != '<>'])
            elif end_tokens:
                for et in end_tokens:
                    merged_parts.extend([w for w in get_words(et) if w != '<>'])
            if count_token:
                merged_parts.extend([w for w in get_words(count_token) if w != '<>'])
            for ut in sorted(unit_tokens, key=lambda x: float(x[0])):
                merged_parts.extend([w for w in get_words(ut) if w != '<>'])
            for lt in sorted(location_tokens, key=lambda x: float(x[0])):
                merged_parts.extend([w for w in get_words(lt) if w != '<>'])
            for sub_toks in source_tokens:
                src_words = []
                for st in sub_toks:
                    src_words.extend([w for w in get_words(st) if w != '<>'])
                if src_words:
                    # Add 'from' if not already in first word
                    if src_words[0].lower() not in ('from', 'to', 'via'):
                        merged_parts.append('from')
                    merged_parts.extend(src_words)

            # Mark source sub-tokens as used so they don't appear as standalone chunks
            if source_tokens:
                for sub_toks in source_tokens:
                    for st in sub_toks:
                        used_data_indices.add(float(st[0]))
                        print("[DEBUG] Marked dist_meas source token as used: %s" % st[1])

            if not merged_parts:
                print("[DEBUG] No parts for meas %s, skipping" % meas_token[1])
                continue

            merged_word = ' '.join(merged_parts)
            print("[DEBUG] Merged measurement: %s" % merged_word)

            merged_tok    = list(meas_token)
            merged_tok[1] = merged_word
            merged_tok    = tuple(merged_tok)
            for i, t in enumerate(tagged_data):
                if float(t[0]) == meas_idx:
                    tagged_data[i] = merged_tok
                    break

            # Remove consumed sub-tokens
            remove_idx = set()
            for tok in start_tokens + end_tokens + [count_token]:
                if tok:
                    remove_idx.add(float(tok[0]))
            for ut in unit_tokens:
                remove_idx.add(float(ut[0]))
            for lt in location_tokens:
                remove_idx.add(float(lt[0]))
            before = len(tagged_data)
            tagged_data[:] = [t for t in tagged_data if float(t[0]) not in remove_idx]
            print(f"[DEBUG] Removed {len(remove_idx)} meas tokens. Count: {before} -> {len(tagged_data)}")

    def merge_complete_verbal_complexes():
        """
        Merge non-finite verb chains (rpk → nf) and krya tokens with the main verb
        into a single verbal token BEFORE the auxiliary merging step.
        Example: nf='after placing' + rpk='placing' + main='do' → 'after placing do'
        Auxiliary verbs are intentionally left for step merge_aux_neg_main().
        """
        main_verbs = [
            t for t in tagged_data
            if len(t) > 8 and 'main' in str(t[-3]) and float(t[0]) not in used_data_indices
        ]
        for main_verb in main_verbs:
            main_idx      = float(main_verb[0])
            complex_parts = [main_verb]

            # Collect krya tokens with same base integer index
            krya_tokens = [
                t for t in tagged_data
                if len(t) > 8 and t[-1] == 'krya' and
                str(t[0]).startswith(str(int(main_idx))) and
                float(t[0]) not in used_data_indices
            ]
            complex_parts.extend(krya_tokens)

            # Collect rpk tokens pointing to this main verb
            rpk_tokens = [
                t for t in tagged_data
                if len(t) > 10 and t[-1] == 'rpk' and
                float_or_none(t[-2]) == main_idx and
                float(t[0]) not in used_data_indices
            ]
            for rpk in rpk_tokens:
                complex_parts.append(rpk)
                rpk_idx = float(rpk[0])
                # Also collect nf tokens belonging to this rpk
                nf_tokens = [
                    t for t in tagged_data
                    if len(t) > 8 and t[-1] == 'nf' and
                    str(t[0]).startswith(str(int(rpk_idx))) and
                    float(t[0]) not in used_data_indices
                ]
                complex_parts.extend(nf_tokens)

            print(f"[DEBUG] Skipping auxiliary verbs - will be handled in Step 9.7")

            if len(complex_parts) > 1:
                complex_parts_sorted = sorted(complex_parts, key=lambda t: float(t[0]))
                merged_words = ' '.join([t[1] for t in complex_parts_sorted])
                merged       = list(main_verb)
                merged[1]    = merged_words
                merged       = tuple(merged)
                for i, t in enumerate(tagged_data):
                    if float(t[0]) == main_idx:
                        tagged_data[i] = merged
                        print(f"[DEBUG] Created complete verbal complex: {merged_words}")
                        break
                indices_to_remove = [float(t[0]) for t in complex_parts if float(t[0]) != main_idx]
                original_count    = len(tagged_data)
                tagged_data[:] = [t for t in tagged_data if float(t[0]) not in indices_to_remove]
                print(f"[DEBUG] Removed {len(indices_to_remove)} tokens. Count: {original_count} -> {len(tagged_data)}")
                used_data_indices.update(indices_to_remove)

    # ── add_chunk() — the core chunk builder ─────────────────────────────────

    def add_chunk(tokens, tag="", step="", preserve_order=False):
        """
        Build one chunk from a list of tokens and append it to the chunks list.

        Word ordering inside the chunk:
          - Focus markers (also, only, even, …) come first
          - Prepositions (from, to, in, …) come second
          - Articles (the, a, an) come third
          - Content words come last
          - Duplicate articles within content are removed

        Validation checks (skips the chunk if any fail):
          - Token indices must not already be in used_data_indices
          - At least one word must appear in sentence_tokens (or be a #-marked NE,
            article, or NC compound token which won't appear verbatim)
          - Must not be a punctuation-only chunk
          - Must not be a duplicate of an existing chunk

        Parameters:
            tokens        (list)  : List of word tuples
            tag           (str)   : '_SUBJ', '_ACTIVE', '_PASSIVE', '_IMPERATIVE', or ''
            step          (str)   : Debug label (e.g. 'Step 0 (complete extended network)')
            preserve_order (bool) : If True, use tokens in the order given rather than by index
        """
        if not tokens:
            return False

        sorted_tokens = tokens if preserve_order else sorted(tokens, key=lambda t: float(t[0]))
        words = sum((get_words(t) for t in sorted_tokens), [])

        # Classify words into focus markers, prepositions, articles, and content
        FOCUS_MARKERS     = {'also', 'only', 'even', 'just', 'still', 'yet', 'already'}
        ARTICLES          = {'the', 'a', 'an'}
        FRONT_PREPOSITIONS = {
            'from', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'about',
            'among', 'between', 'through', 'into', 'onto', 'upon', 'within',
            'without', 'across', 'along', 'around', 'behind', 'below', 'beside',
            'over', 'under', 'after', 'before', 'during', 'since', 'until',
            'of',
        }
        # English cardinal and ordinal number words. Used to distinguish a
        # leading r6-postposition 'of' (e.g. 'of the seven places', where 'seven'
        # is a numeral modifier) from an internal genitive 'of' that must stay in
        # place (e.g. 'son of guṃḍamahādevī', where 'son' is a common noun). The
        # assembler's Step 2 only moves 'of' to the front when the word immediately
        # before it in content_words is a cardinal/ordinal — never when it is a
        # common noun like 'son', 'name', 'importance', etc.
        _CARDINALS = {
            'two','three','four','five','six','seven','eight','nine','ten',
            'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen',
            'eighteen','nineteen','twenty','thirty','forty','fifty','sixty',
            'seventy','eighty','ninety','hundred','thousand','million','billion',
            'first','second','third','fourth','fifth','sixth','seventh','eighth',
            'ninth','tenth',
        }
        # Compound prepositions where an inner word like "to" must NOT be split out
        COMPOUND_PREPOSITIONS = {
            'opposite to', 'next to', 'according to', 'due to', 'prior to',
            'contrary to', 'close to', 'similar to', 'compared to',
            'in addition to', 'with regard to', 'as opposed to',
        }
        # If the entire word string starts with a known compound preposition, treat
        # it as one unit — skip the per-word classification that would break it.
        phrase_str = ' '.join(w.lower() for w in words)
        _skip_reorder = any(phrase_str.startswith(cp) for cp in COMPOUND_PREPOSITIONS)

        # Distance/direction words — must stay at END of phrase, never pulled to front
        POSTPOSITION_WORDS = {'away', 'ahead', 'apart',
                              'above', 'below', 'beyond', 'outside', 'inside'}

        # Possessives — must come right after preposition, before adjectives and noun
        POSSESSIVES = {'its', 'his', 'her', 'their', 'my', 'our', 'your', 'whose', 'own'}

        if _skip_reorder:
            # Compound preposition is already at the front — keep words as-is
            focus_words   = []
            prep_words    = []
            article_words = []
            poss_words    = []
            post_words    = []
            content_words = words
        else:
            focus_words   = [w for w in words if w.lower() in FOCUS_MARKERS]
            article_words = [w for w in words if w.lower() in ARTICLES]
            poss_words    = [w for w in words if w.lower() in POSSESSIVES]
            post_words    = [w for w in words if w.lower() in POSTPOSITION_WORDS]

            # Step 1: Check if the first non-focus word is already a preposition
            first_non_focus = next(
                (w for w in words if w.lower() not in FOCUS_MARKERS), None
            )
            prep_words = (
                [first_non_focus]
                if first_non_focus and first_non_focus.lower() in FRONT_PREPOSITIONS
                else []
            )

            # Build set of already-classified words.
            # IMPORTANT: prep_words uses index-based exclusion, not string-based,
            # so a phrase like 'of śekha of salīma' keeps its second 'of' in
            # content_words (only the first is pulled out as the leading preposition).
            prep_indices = set()
            if prep_words:
                for pi, pw in enumerate(words):
                    if pw.lower() == prep_words[0].lower():
                        prep_indices.add(pi)
                        break  # only remove the first occurrence
            already_taken = (
                set(w.lower() for w in focus_words)  |
                set(w.lower() for w in article_words)|
                set(w.lower() for w in poss_words)   |
                set(w.lower() for w in post_words)
            )
            # Build content_words, skipping the one extracted prep by index
            content_words = []
            for ci_w, w in enumerate(words):
                if w.lower() in already_taken:
                    continue
                if ci_w in prep_indices:
                    continue
                content_words.append(w)

            # Step 2: If no preposition found at front, search inside content_words
            # for a stranded preposition (e.g. "Hindu in religion", "charming in beauty")
            # and pull it to the front.
            # Special guard for 'of': only pull it to front when the word immediately
            # before it is a cardinal/ordinal number or adjective (e.g. 'seven of
            # places' -> 'of the seven places'). When the word before 'of' is a common
            # noun (e.g. 'son of guṃḍamahādevī'), 'of' is an internal genitive and
            # must stay in place.
            if not prep_words:
                for i, w in enumerate(content_words):
                    if w.lower() in FRONT_PREPOSITIONS:
                        if w.lower() == 'of':
                            prev_word = content_words[i - 1].lower() if i > 0 else ''
                            next_word = content_words[i + 1] if i + 1 < len(content_words) else ''
                            # Pull 'of' to front if:
                            # (a) prev word is a cardinal/ordinal number, OR
                            # (b) next word is a #-marked NE (proper name) AND prev word
                            #     is a title/modifier (not a common noun head like 'son',
                            #     'name', 'importance'). This handles: 'lord of #SaMkara'
                            #     → 'of lord #SaMkara' (NE with title modifier).
                            if prev_word and prev_word not in _CARDINALS:
                                if not (next_word and next_word.startswith('#')):
                                    continue  # genitive 'of' — leave in place
                        prep_words = [content_words.pop(i)]
                        break

        if focus_words or prep_words or article_words or poss_words:
            content_lower   = [w.lower() for w in content_words]
            unique_articles = [w for w in article_words if w.lower() not in content_lower]
            seen            = set()
            deduped_content = []
            for w in content_words:
                wl = w.lower()
                if wl in {'the', 'a', 'an'} and wl in seen:
                    continue
                seen.add(wl)
                deduped_content.append(w)
            # Final order:
            # focus-marker → preposition → possessive → article → content → direction-word
            # Examples:
            #   "in Hindu religion"          ✓  (was: "Hindu in religion")
            #   "in its charming beauty"     ✓  (was: "charming its in beauty")
            #   "10 kilometre away"          ✓  (was: "10 in away kilometre") — 'in' not pulled
            #   "in the fair ground"         ✓  (was: "fair to the ground" / "to the fair ground")
            words = focus_words + prep_words + poss_words + unique_articles + deduped_content + post_words

        words_lower = [w.lower() for w in words]
        chunk = f"[{ ' '.join(words) }]{tag}"

        # Validation gates
        if not words:
            print(f"[DEBUG] {step} - Skipped (no words): {chunk}")
            return False

        if all(w in {'.', '?', '!', ',', ';', ':'} for w in words):
            print(f"[DEBUG] {step} - Skipped (punctuation only): {chunk}")
            return False

        if chunk in chunks:
            print(f"[DEBUG] {step} - Skipped (duplicate): {chunk}")
            return False

        if any(float(t[0]) in used_data_indices for t in tokens):
            print(f"[DEBUG] {step} - Skipped (indices used): {chunk}")
            return False

        sentence_words_lower = [w.lower() for w in sentence_tokens]
        has_article_or_ne = any(
            w.startswith('#') or w in {'the', 'a', 'an', 'of', 'from', 'also'}
            for w in words_lower
        )
        in_sentence = any(
            w in sentence_words_lower or any(w in sw for sw in sentence_words_lower)
            for w in words_lower
            if w not in {'<>'}
        )
        is_nc_chunk = any(
            len(t) > 7 and str(t[7]) in ('NC', 'NC_head')
            for t in tokens
        )
        # Also accept words that appear in PP_fulldata (morphologically generated forms
        # differ from the raw WX source tokens so they won't be in sentence_tokens).
        pp_words_lower = set()
        for t in PP_fulldata_dict_with_ids.get(key, []):
            if t[1]:
                for w in str(t[1]).split():
                    pp_words_lower.add(w.lower())
        in_ppdata = any(w in pp_words_lower for w in words_lower if w not in {'<>'})

        if not in_sentence and not has_article_or_ne and not is_nc_chunk and not in_ppdata:
            print(f"[DEBUG] {step} - Skipped (no valid words in sentence): {chunk}")
            return False

        chunks.append(chunk)
        used_data_indices.update(float(t[0]) for t in tokens)
        used_words.update(words_lower)
        print(f"[DEBUG] {step} - Added: {chunk}")
        return True

    # ── Initialise state ──────────────────────────────────────────────────────
    tagged_data     = sorted(PP_fulldata_dict_with_ids[key], key=sort_index)
    original_order  = sentence.strip().split()
    has_rsm         = any(len(t) > 10 and t[-1] == 'rsm' for t in tagged_data)

    def find_cond(cond):
        """Return all tokens in tagged_data that satisfy cond and are not yet used."""
        return [t for t in tagged_data if cond(t) and float(t[0]) not in used_data_indices and len(t) > 1]

    chunks            = []
    used_data_indices = set()
    used_words        = set()

    # ── Execute all pre-merge steps (order is important) ────────────────────
    merge_calendar_construction()       # Date + month → single calendar token
    merge_meas_construction()           # Count + unit + location → measurement token
    merge_rbks_with_head()              # Adjectival participle → noun
    merge_rvks_with_location()          # rvks verb + its args → location noun
    merge_nf_with_head()                # Non-finite preposition word → verb
    merge_nc_with_nc_head()             # NC modifier + NC_head → compound noun phrase
    merge_adj_with_noun_head()          # Adjective + noun (operand only)
    merge_complete_verbal_complexes()   # rpk/nf/krya chains → verb
    merge_conj_construction()           # Conjunction operands → coordinated subject
    merge_krya_with_main()
    merge_re_examples()              # Complex-predicate nominal → verb
    merge_aux_neg_main()                # aux + neg + main → single verbal token

    # ── Step 0: Modifier networks ────────────────────────────────────────────
    # Find all interconnected modifier chains and build complete noun phrases.
    networks = find_complete_modifier_network()
    for network_indices in networks:
        if any(idx in used_data_indices for idx in network_indices):
            continue
        network_tokens  = tokens_from_indices(network_indices)
        extended_tokens = list(network_tokens)

        # Expand network with conjunction siblings and their modifiers
        for token in network_tokens:
            token_idx = float(token[0])
            for t in tagged_data:
                if (float(t[0]) not in used_data_indices and t not in extended_tokens):
                    if (len(t) >= 8 and len(token) >= 8 and
                            t[-2] == token[-2] and t[-1] == token[-1] and
                            t[-1] in {'k2', 'k1', 'r6', 'k4'}):
                        extended_tokens.append(t)
                    if (t[1] == 'conj' and len(t) >= 8 and len(token) >= 8 and
                            t[-2] == token[-2] and t[-1] == token[-1]):
                        extended_tokens.append(t)
        for token in list(extended_tokens):
            token_idx = float(token[0])
            for t in tagged_data:
                if (len(t) >= 8 and float(t[0]) not in used_data_indices and
                        t not in extended_tokens and
                        float_or_none(t[-2]) == token_idx and
                        t[-1] in {'mod', 'dem', 'quant', 'vkvn', 'intf', 'card', 'rdl', 'krvn'}):
                    extended_tokens.append(t)

        if len(extended_tokens) > 1:
            def english_order_key(t):
                """
                Sort key for English word order inside a noun phrase:
                - r6 (genitive) goes AFTER its head noun (head_index + 0.1)
                - mod/card/quant (adjective/numeral) goes BEFORE its head noun (head_index - 0.1)
                - mod whose head is itself an r6 node (e.g. 'lord' modifying NE [ne_2]
                  which is r6 of 'abode') goes just BEFORE that r6 node's output position
                  (r6_head + 0.1 - 0.01), so 'lord śaṃkara' not 'śaṃkara lord'
                - Others keep their natural USR index position
                """
                base = float(t[0])
                rel  = t[-1] if len(t) >= 2 else ''
                head_val = t[-2] if len(t) >= 8 else None
                if rel == 'r6':
                    try:
                        head = float(head_val) if head_val else base
                        return head + 0.1
                    except (ValueError, TypeError):
                        pass
                elif rel in ('mod', 'card', 'quant'):
                    try:
                        head = float(head_val) if head_val else base
                        # Check if this mod's head is itself an r6 token in the network.
                        # If so, position this modifier just before the r6 node's output slot
                        # (r6_output = r6_head_of_r6 + 0.1), giving: modifier BEFORE NE.
                        head_token = None
                        for td in extended_tokens:
                            try:
                                if float(td[0]) == head and len(td) >= 8 and td[-1] == 'r6':
                                    head_token = td
                                    break
                            except (ValueError, TypeError):
                                pass
                        if head_token is not None:
                            r6_head_val = head_token[-2]
                            try:
                                r6_head = float(r6_head_val)
                                # Place just before the r6 node's output position
                                return r6_head + 0.1 - 0.01
                            except (ValueError, TypeError):
                                pass
                        return head - 0.1
                    except (ValueError, TypeError):
                        pass
                return base

            extended_tokens_sorted = sorted(extended_tokens, key=english_order_key)
            has_subject = any(len(t) >= 8 and t[-1] in {'k1', 'rsm', 'pk1'}
                              for t in extended_tokens_sorted)
            tag = '_SUBJ' if has_subject else ''
            if add_chunk(extended_tokens_sorted, tag,
                         "Step 0 (complete extended network)", preserve_order=True):
                continue

    # Handle individual modifiers not covered by any network
    for t in tagged_data:
        if (t[-1] in {'dem', 'quant', 'vkvn', 'mod', 'intf', 'card', 'rdl', 'rvks', 'krvn'} and
                float(t[0]) not in used_data_indices):
            head_idx = float_or_none(t[-2]) if len(t) >= 4 else None
            head     = find_token_by_index(head_idx) if head_idx else None
            if head and float(head[0]) not in used_data_indices:
                tag = '_SUBJ' if len(head) >= 8 and head[-1] in {'k1', 'rsm', 'pk1'} else ''
                add_chunk([t, head], tag, f"Step 0 ({t[-1]}+head)")
            else:
                add_chunk([t], "", f"Step 0 ({t[-1]} alone)")

    # Handle r6 (genitive) tokens: genitive comes AFTER its head noun in English
    for t in tagged_data:
        if t[-1] == 'r6' and float(t[0]) not in used_data_indices:
            head_idx = float_or_none(t[-2]) if len(t) >= 4 else None
            head     = find_token_by_index(head_idx) if head_idx else None
            is_pron  = (t[2] == 'p') if len(t) > 2 else False

            if head and float(head[0]) not in used_data_indices:
                tag         = '_SUBJ' if len(head) >= 8 and head[-1] in {'k1', 'rsm', 'pk1'} else ''
                head_words  = get_words(head)
                r6_words_l  = get_words(t)
                if is_pron:
                    merged_words = r6_words_l + head_words   # possessive BEFORE noun
                else:
                    merged_words = head_words + r6_words_l   # genitive AFTER noun: 'beauty of the garden'
                merged_str = ' '.join(merged_words)
                chunk = f"[{merged_str}]{tag}"
                if chunk not in chunks:
                    chunks.append(chunk)
                    used_data_indices.add(float(t[0]))
                    used_data_indices.add(float(head[0]))
                    used_words.update(w.lower() for w in merged_words)
                    print(f"[DEBUG] Step 0 (r6+head) - Added: {chunk}")
            else:
                # Head already used — try to append r6 words to an existing chunk
                r6_words_l   = get_words(t)
                r6_head_idx  = float_or_none(t[-2]) if len(t) >= 4 else None
                appended     = False
                if r6_words_l and chunks and r6_head_idx:
                    for ci in range(len(chunks) - 1, -1, -1):
                        chunk_inner = chunks[ci].replace(']_SUBJ', '').replace(']_ACTIVE', '').replace(']_PASSIVE', '').replace(']_IMPERATIVE', '').strip('[]')
                        head_tok    = None
                        for td in tagged_data:
                            try:
                                if float(td[0]) == r6_head_idx:
                                    head_tok = td
                                    break
                            except:
                                pass
                        if head_tok:
                            head_words = get_words(head_tok)
                            if any(w.lower() in chunk_inner.lower() for w in head_words if w not in {'the', 'a', 'an', 'of'}):
                                suffix = ''
                                for s in ['_SUBJ', '_ACTIVE', '_PASSIVE', '_IMPERATIVE']:
                                    if chunks[ci].endswith(s):
                                        suffix = s
                                        break
                                inner = chunks[ci][1:chunks[ci].rfind(']')]
                                if is_pron:
                                    chunks[ci] = '[' + ' '.join(r6_words_l) + ' ' + inner + ']' + suffix
                                else:
                                    chunks[ci] = '[' + inner + ' ' + ' '.join(r6_words_l) + ']' + suffix
                                used_data_indices.add(float(t[0]))
                                used_words.update(w.lower() for w in r6_words_l)
                                print(f"[DEBUG] Step 0 (r6 appended to chunk): {chunks[ci]}")
                                appended = True
                                break
                if not appended and r6_words_l:
                    # Last resort: append to the existing _SUBJ chunk
                    for ci in range(len(chunks) - 1, -1, -1):
                        if '_SUBJ' in chunks[ci]:
                            inner = chunks[ci][1:chunks[ci].rfind(']')]
                            if is_pron:
                                chunks[ci] = '[' + ' '.join(r6_words_l) + ' ' + inner + ']_SUBJ'
                            else:
                                chunks[ci] = '[' + inner + ' ' + ' '.join(r6_words_l) + ']_SUBJ'
                            used_data_indices.add(float(t[0]))
                            used_words.update(w.lower() for w in r6_words_l)
                            print(f"[DEBUG] Step 0 (r6 appended to SUBJ fallback): {chunks[ci]}")
                            break

    # ── Step -1: Remaining disjunction groups ────────────────────────────────
    handle_disjunction_groups()

    # ── Step -0.5: Coordinated groups (rs relation) ──────────────────────────
    # 'rs' = same-referent (co-reference coordination)
    rs_groups = defaultdict(list)
    for t in tagged_data:
        if t[-1] == 'rs' and t[-2]:
            rs_groups[float_or_none(t[-2])].append(t)
    for group in rs_groups.values():
        if len(group) >= 2:
            add_chunk(sorted(group, key=lambda t: float(t[0])), "", "Step -0.5 (rs)", preserve_order=True)

    # ── Step -0.3: Duration / range groups (dur, k7t) ─────────────────────────
    # Groups two tokens sharing the same temporal head (e.g. 'from Monday to Friday')
    dur_groups = defaultdict(list)
    for t in tagged_data:
        if t[-1] in {'dur', 'k7t'} and t[-2]:
            dur_groups[float_or_none(t[-2])].append(t)
    for group in dur_groups.values():
        if group:
            add_chunk(sorted(group, key=lambda t: float(t[0])), "", "Step -0.3 (dur)", preserve_order=True)

    # ── Step 5: Bare subject tokens ───────────────────────────────────────────
    # k1 = subject, pk1 = passive subject, rsm = proximity subject
    for subj in find_cond(lambda t: t[-1] in {'k1', 'pk1'}):
        add_chunk([subj], '_SUBJ', "Step 5 (subject)")
    for subj in find_cond(lambda t: t[-1] == 'rsm'):
        add_chunk([subj], '_SUBJ', "Step 5 (rsm subject)")

    # ── Step 6.5: Reason phrase (rh) ─────────────────────────────────────────
    # 'rh' = reason; try to include its head for context
    for rh in find_cond(lambda t: t[-1] == 'rh'):
        head_idx = float_or_none(rh[-2]) if len(rh) >= 8 else None
        h = find_token_by_index(head_idx) if head_idx else None
        if h and float(h[0]) not in used_data_indices:
            add_chunk([rh, h], "", "Step 6.5 (rh+head)")
        else:
            add_chunk([rh], "", "Step 6.5 (rh alone)")

    # ── Step 8: Adjacent adjective pairs (intensifier + adjective) ───────────
    # Handles cases like 'very beautiful' where intf→adj
    for i in range(len(tagged_data) - 1):
        t   = tagged_data[i]
        nxt = tagged_data[i + 1]
        if (len(t) > 2 and len(nxt) > 2 and t[2] == 'adj' and
                len(t) >= 8 and t[-1] in {'intf', 'mod'} and nxt[2] == 'adj'):
            if float(t[0]) not in used_data_indices and float(nxt[0]) not in used_data_indices:
                add_chunk([t, nxt], "", "Step 8 (adj+adj)")

    # ── Step 9.5: Preposition-bearing single tokens ───────────────────────────
    # Any grammatical relation that carries a preposition becomes its own chunk.
    # Verbal tokens are excluded (they belong in verb chunks).
    PREPOSITION_RELATIONS = {
        'k7t', 'k3', 'k5', 'k5prk', 'k7', 'k7p', 'k7a', 'k2p',
        'rblak', 'rt', 'rblpk', 'rn', 'rd', 'rp', 'r6',
        'rask1', 'rask2', 'rask3', 'rask4', 'rask5', 'rask7',
        'k1as', 'k2as', 'k3as', 'k4as', 'k5as', 'k7as',
        'quantless', 'quantmore', 'rkl', 'rh', 'rasneg', 'rv',
        'k4', 'k4a', 'ru', 'k2s', 'rbks', 'nf', 'rkrl', 'krvnneg', 'rviroXIk1', 'rprop', 'rask6', 'rad', 're', 'rs',
    }
    candidates = [
        t for t in tagged_data
        if len(t) >= 8 and t[-1] in PREPOSITION_RELATIONS and
        float(t[0]) not in used_data_indices and
        not (len(t) > 2 and t[2] == 'v')
    ]
    for t in sorted(candidates, key=lambda t: float(t[0])):
        if float(t[0]) not in used_data_indices:
            add_chunk([t], "", "Step 9.5 (preposition-bearing single)", preserve_order=True)

    # ── Step 9.7: Auxiliary + Main Verb Complexes ────────────────────────────
    # Pair each auxiliary verb with its main verb (by base index, or nearest following).
    # Remaining unpaired auxiliaries or main verbs are emitted alone.
    aux_verbs = [
        t for t in tagged_data
        if len(t) > 8 and 'auxiliary' in str(t[-3]) and float(t[0]) not in used_data_indices
    ]
    main_verbs = [
        t for t in tagged_data
        if len(t) > 8 and 'main' in str(t[-3]) and float(t[0]) not in used_data_indices
    ]
    for aux in list(aux_verbs):
        aux_idx      = float(aux[0])
        matching_main = None
        base_aux_idx  = int(aux_idx) if aux_idx != int(aux_idx) else aux_idx
        for main in main_verbs:
            if float(main[0]) == base_aux_idx:
                matching_main = main
                break
        if not matching_main:
            for main in main_verbs:
                if float(main[0]) > aux_idx:
                    matching_main = main
                    break
        if matching_main:
            verb_complex = [aux, matching_main]
            verb_tag     = get_verb_tag(verb_complex, sentence_type)
            if add_chunk(verb_complex, verb_tag, "Step 9.7 (aux+main)", preserve_order=True):
                if aux in aux_verbs:
                    aux_verbs.remove(aux)
                if matching_main in main_verbs:
                    main_verbs.remove(matching_main)
                print(f"[DEBUG] Created aux+main complex: {aux[1]} + {matching_main[1]}")
    for aux in aux_verbs:
        if float(aux[0]) not in used_data_indices:
            add_chunk([aux], "", "Step 9.7 (aux alone)")
    for main in main_verbs:
        if float(main[0]) not in used_data_indices:
            verb_tag = get_verb_tag([main], sentence_type)
            add_chunk([main], verb_tag, "Step 9.7 (main alone)")

    # ── Step 10: Remaining verb complexes ────────────────────────────────────
    # Any verb still unused (with a 'main' or 'inf' type, or compound verb string)
    # along with any rpk token pointing to it.
    main_verbs = []
    for t in tagged_data:
        if float(t[0]) in used_data_indices:
            continue
        if len(t) > 2 and t[2] == 'v' and float(t[0]).is_integer():
            if len(t) > 8 and ('main' in str(t[-3]) or 'inf' in str(t[-3])):
                main_verbs.append(t)
            elif len(t) > 10 and t[-1] != 'rpk':
                main_verbs.append(t)
    for t in find_cond(lambda x: len(x) > 1 and x[1] and ' ' in x[1] and len(x) > 2 and 'v' in str(x[2])):
        if t not in main_verbs:
            main_verbs.append(t)
    for main in main_verbs:
        if float(main[0]) in used_data_indices:
            continue
        parts    = [main]
        main_idx = float(main[0])
        rpk_token = next(
            (t for t in find_cond(lambda x: len(x) > 10 and x[-1] == 'rpk' and float_or_none(x[-2]) == main_idx)),
            None
        )
        if rpk_token:
            parts = [rpk_token, main]
        parts    = sorted(parts, key=lambda t: float(t[0]))
        verb_tag = get_verb_tag(parts, sentence_type)
        add_chunk(parts, verb_tag, "Step 10 (verb complex)", preserve_order=True)

    # ── Step 11: Fallback for remaining tokens ────────────────────────────────
    # Any token not yet emitted gets its own chunk. Content words (n/v/adj/adv) come first.
    remaining = [t for t in tagged_data if float(t[0]) not in used_data_indices]
    remaining.sort(key=lambda t: (0 if len(t) > 2 and t[2] in {'n', 'v', 'adj', 'adv'} else 1, float(t[0])))
    for t in remaining:
        words = get_words(t)
        if words:
            words_lower = [w.lower() for w in words]
            if any(w not in used_words for w in words_lower):
                add_chunk([t], "", "Step 11 (fallback)")

    # ── Step 12: Safety net for unused sentence words ─────────────────────────
    # If any original sentence word was never placed in a chunk, add it as a bare word chunk.
    for word in sentence_tokens:
        word_lower = word.lower()
        if word_lower not in used_words and word != '.' and word != '<>':
            dummy_token = next((t for t in tagged_data if t[1] == word), None)
            if not dummy_token:
                dummy_token = (0.0, word, '', '', '', '', '', '', '', '', '')
            add_chunk([dummy_token], "", "Step 12 (unused word)")

    # ── Final reordering ──────────────────────────────────────────────────────
    # Subject chunks come first, sorted by their first word's position in the original sentence.
    # Then all other chunks, also sorted by original position.
    def first_index(chunk):
        words = get_words_from_chunk(chunk)
        valid = [original_order.index(w) for w in words if w in original_order]
        return min(valid) if valid else len(original_order)

    unique_chunks = list(dict.fromkeys(chunks))
    subj = [c for c in unique_chunks if c.endswith('_SUBJ')]
    reg  = [c for c in unique_chunks if c not in subj]
    subj.sort(key=first_index)
    reg.sort(key=first_index)
    result = " ".join(subj + reg)
    print(f"[DEBUG] Final Output: {result}")

    # ── Final missing-word check ──────────────────────────────────────────────
    # Append any word that disappeared from all chunks (debugging safety net).
    final_words = set()
    for chunk in unique_chunks:
        inner = re.sub(r'\]_\w+', '', chunk).strip('[]')
        for w in inner.split():
            final_words.add(w.lower())
    missing_words = [
        w for w in sentence_tokens
        if w.lower() not in final_words and w != '.' and w != '<>'
    ]
    if missing_words:
        print(f"[WARNING] Missing words detected: {missing_words}")
        for word in missing_words:
            result += f" [{word}]"

    return result


# ── Post-generation support functions ─────────────────────────────────────────

def handle_unprocessed(index_data, depend_data, output_data, processed_nouns, construction_data):
    """
    After Apertium generation, handle words that returned '#'-prefixed output
    (not found in the dictionary).

    Actions:
    - If the noun has k1s dependency or kriyAmUla construction → change POS to adj
    - Otherwise → swap gender (try the other gender, will re-run morphology)
    - Words starting with '*' indicate starred (unknown) words → set has_changes flag

    Returns (has_changes, updated_processed_nouns).
    """
    has_changes = False
    if not isinstance(index_data, list):
        raise ValueError("index_data must be a list mapping indices.")

    for dataIndex, data in enumerate(output_data):
        if data.startswith('#'):
            if dataIndex >= len(index_data):
                continue
            noun_index = index_data[dataIndex]
            for i, noun in enumerate(processed_nouns):
                if round(noun[0]) == noun_index and len(noun) > 2 and noun[2] == 'n':
                    if i >= len(construction_data) or i >= len(depend_data):
                        break
                    depend_check      = depend_data[i] and isinstance(depend_data[i], str) and ':' in depend_data[i]
                    construction_check = construction_data[i] and isinstance(construction_data[i], str) and ':' in construction_data[i]
                    depend_tag        = depend_data[i].split(':')[1] if depend_check else ""
                    construction_tag  = construction_data[i].split(':')[1] if construction_check else ""
                    if depend_tag == 'k1s' or construction_tag == 'kriyAmUla':
                        temp = list(noun)
                        temp[2] = 'adj'
                        processed_nouns[i] = tuple(temp)
                        has_changes = True
                        break
                    if noun[7] not in ('proper', 'NC', 'CP_noun', 'abs', 'vn'):
                        temp     = list(noun)
                        temp[4]  = 'f' if noun[4] == 'm' else 'm'
                        processed_nouns[i] = tuple(temp)
                        has_changes = True
                        log(f'{temp[1]} reprocessed as noun with gen:{temp[4]}.')
                    break
        elif data.startswith('*'):
            has_changes = True

    log(f'processed_nouns after handling # :{processed_nouns}')
    return has_changes, processed_nouns


# ── Noun lookup helpers ───────────────────────────────────────────────────────

def nextNounData_fromFullData(fromIndex, PP_FullData):
    """Find and return the first noun tuple in PP_FullData whose index equals fromIndex."""
    for data in PP_FullData:
        if data[0] == fromIndex and data[2] == 'n':
            return data
    return ()


def is_next_word_noun(index, processed_nouns):
    """Return the noun tuple for the given index, or False if not found."""
    for data in processed_nouns:
        if data[0] == index and data[2] == 'n':
            return data
    return False


def nextNounData(fromIndex, word_info):
    """
    Find the next noun entry in word_info matching fromIndex.
    Normalises 'female'/'male' seman to 'f'/'m' and 'pl' to 'p'.
    """
    for data in word_info:
        data = list(data)
        if fromIndex == str(data[0]):
            if 'female' in data[2]:
                data[2] = 'f'
            elif 'male' in data[2]:
                data[2] = 'm'
            if 'pl' in data[3]:
                data[3] = 'p'
            elif data[3] != '':
                data[3] = 's'
            return tuple(data)
    return False


def fetchNextWord(index, index_data, words_info):
    """
    Return the cleaned root word at the given index position in index_data.
    Used for rkl/rdl postposition decisions (e.g. 'bAxa'=after, 'pahale'=before).
    """
    next_word = ''
    idx = index_data[index]
    for data in words_info:
        if idx == data[0]:
            next_word = clean(data[1])
            break
    return next_word


def change_gender(current_gender):
    """Return the opposite gender: 'm' → 'f', 'f' → 'm'."""
    return 'f' if current_gender == 'm' else 'm'


def set_gender_make_plural(processed_words, g, num):
    """
    Override gender and number for all adjective (adj) and verb (v) tokens.
    Used when agreement must be forced (e.g. honorific plural).
    """
    process_data = []
    for i in range(len(processed_words)):
        word_list = list(processed_words[i])
        if word_list[2] == 'adj':
            word_list[4] = g
            word_list[5] = num
        elif word_list[2] == 'v':
            word_list[3] = g
            word_list[4] = num
        process_data.append(tuple(word_list))
    return process_data


def set_main_verb_tam_zero(verb):
    """Set a Verb object's TAM to 0 (base form). Used in shade/auxiliary processing."""
    verb.tam = 0
    return verb


def get_additional_word(relation, index):
    """
    Map a non-finite dependency relation to its English preposition word.
    Returns a dict {index: word} used to insert the word before the non-finite verb.
    Mapping: rpk→'after', rsk→'while', rblpk→'before', rblak→'after', rblsk→'while', rbks→'after'
    """
    value_mapping = {
        'rpk': 'after', 'rsk': 'while', 'rblpk': 'before',
        'rblak': 'after', 'rblsk': 'while', 'rbks': 'after', 'rvks': ''
    }
    mapped_value = value_mapping.get(relation, relation)
    return {index: mapped_value}


def set_tam_for_nonfinite(dependency):
    """
    Return the English TAM string for a non-finite verb based on its dependency relation.
    rpk/rsk/rblpk/rvks/rblak/rblsk → 'ing' (gerund/present participle)
    rbks → 'en' (past participle)
    """
    return {
        'rpk': 'ing', 'rsk': 'ing', 'rblpk': 'ing',
        'rvks': 'ing', 'rblak': 'ing', 'rblsk': 'ing',
        'rbks': 'en'
    }.get(dependency, '')


def update_ppost_dict(data_index, param):
    """Directly set or overwrite the postposition for data_index in the global dict."""
    processed_postpositions_dict[data_index] = param


# ── TAM dictionary loader ─────────────────────────────────────────────────────

import importlib
import os
import sys

def extract_tamdict(lang):
    """
    Load the TAM list for the given language by reading the file path defined in
    language_rules/{lang}.py → TAM_DICT_FILES[lang].
    Returns a list of TAM strings (one per line, ignoring # comments).
    """
    tam_list = []
    try:
        lang_module    = importlib.import_module(f'language_rules.{lang}')
        tam_dict_files = getattr(lang_module, 'TAM_DICT_FILES', None)
        if not tam_dict_files or not isinstance(tam_dict_files, dict):
            print(f"Invalid or missing TAM_DICT_FILES in '{lang}' module.")
            return []
        tam_file_path = tam_dict_files.get(lang)
        if not tam_file_path:
            print(f"No TAM dictionary configured for language code: {lang}")
            return []
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


# ── GNP extraction helpers ────────────────────────────────────────────────────

def extract_gnp_noun(noun_data):
    """
    Extract (gender, number, person) from a raw USR noun tuple.
    Uses seman_data field for gender ('female'/'male') and gnp field for number ('pl').
    Special persons: 'speaker' → 'u', 'addressee' → 'm', otherwise 'a'.
    """
    gender = 'm'
    number = 's'
    person = 'a'
    if len(noun_data):
        noun_term = noun_data[1]
        if check_is_digit(noun_term):
            pass  # digit stays as-is
        elif '+' in noun_term:
            cn_terms  = noun_term.strip().split('+')
            noun_term = clean(cn_terms[-1])  # Use last part of compound
        else:
            noun_term = clean(noun_term)

        seman_data = noun_data[2].strip()
        if len(seman_data) > 0:
            if 'female' in seman_data:
                gender = 'f'
            elif 'male' in seman_data:
                gender = 'm'

        if len(noun_data[3]):
            if noun_data[3] == '':
                number = 's'
            elif 'pl' in noun_data[3]:
                number = 'p'

        if noun_term == 'speaker':
            person = 'u'
        elif noun_term == 'addressee':
            person = 'm'
        else:
            person = 'a'
    return gender, number, person


def extract_gnp(data):
    """
    Extract (gender, number, person) from any word tuple using the same logic as extract_gnp_noun.
    """
    gender = 'm'
    number = 's'
    person = 'a'
    if len(data):
        term       = clean(data[1])
        seman_data = data[2].strip()
        if len(seman_data) > 0:
            if 'female' in seman_data:
                gender = 'f'
            elif 'male' in seman_data:
                gender = 'm'
        if len(data[3]):
            if data[3] == 'pl':
                number = 'p'
            else:
                number = 's'
        if term == 'speaker':
            person = 'u'
        elif term == 'addressee':
            person = 'm'
        else:
            person = 'a'
    return gender, number, person


# ── Postposition application to output data ───────────────────────────────────

def add_postposition(transformed_fulldata, index_data, depend_data, processed_postpositions):
    """
    Insert prepositions/postpositions into each token's word string.

    Rules:
    - 'rs' relation: migrate postposition from previous index to current
    - Noun/verbal-noun: insert preposition after any leading discourse markers
      (also, only, even, …) but before the main content word
    - Pronoun: prepend preposition (unless possessive)
    - Location pronouns (here/there/…): remove any spatial preposition
    - Stored ':' postpositions (delayed r6): apply when the correct index is reached
    """
    PPFulldata = []
    LOCATION_WORDS = {'here', 'there', 'somewhere', 'everywhere', 'nowhere',
                      'where', 'anywhere', 'herein', 'therein'}

    # Migrate postposition for 'rs' relation tokens
    for i, ele in enumerate(depend_data):
        if 'rs' in ele:
            ind0, ind1 = index_data[i - 1], index_data[i]
            if ind0 in processed_postpositions_dict:
                processed_postpositions_dict[ind1] = processed_postpositions_dict.pop(ind0)

    last_store_index = None
    last_r6post      = None

    for data in transformed_fulldata:
        index = data[0]
        temp  = list(data)
        ppost = processed_postpositions.get(index)

        # Handle stored ':' postpositions (genitive delayed)
        if isinstance(ppost, str) and ":" in ppost:
            last_store_index, last_r6post = ppost.split(':', 1)
            temp[8] = None
            ppost   = None
        if str(temp[0]) == last_store_index:
            ppost   = last_r6post
            temp[8] = ppost

        POSSESSIVE_FORMS = {'its', 'his', 'her', 'their', 'my', 'our', 'your', 'whose', 'own'}

        # Remove spatial prepositions from location pronouns (here/there)
        if (temp[2] == 'p' and
                temp[1].lower().strip() in LOCATION_WORDS and
                ppost in ('in', 'at', 'on', 'to', 'from')):
            ppost = None
            processed_postpositions_dict[index] = None
            print(f"[DEBUG] Removed postposition '{ppost}' from location word '{temp[1]}'")

        if ppost is not None and temp[2] in ('n', 'vn', 'p'):
            if str(ppost) != '<>':
                # For English: insert preposition at position 0 (very start).
                # add_chunk() will then correctly order:
                #   focus-marker → preposition → article → noun
                # e.g. token "also garden" + ppost "in" → "in also garden"
                # then add_chunk orders to: "also in the garden"  ✓
                words = temp[1].split()
                # Guard: if the token's first word already IS the preposition's
                # first word (e.g. word='along', ppost='along with'), inserting
                # would produce 'along with along'. Skip in that case.
                first_ppost = str(ppost).split()[0].lower()
                if not (words and words[0].lower() == first_ppost):
                    words.insert(0, str(ppost))
                temp[1] = ' '.join(words)
        elif ppost is not None and temp[2] == 'p':
            if temp[1].lower() not in POSSESSIVE_FORMS:
                temp[1] = str(ppost) + ' ' + temp[1]

        PPFulldata.append(tuple(temp))
    return PPFulldata


# ── Noun attribute dictionaries ───────────────────────────────────────────────

def add_adj_to_noun_attribute(key, value):
    """Add an adjective value to the noun_attribute dict for the given noun key."""
    if key is not None:
        if key in repository.constant.noun_attribute:
            repository.constant.noun_attribute[key][0].append(value)
        else:
            repository.constant.noun_attribute[key] = [[], []]


def add_verb_to_noun_attribute(key, value):
    """Add a verb value to the noun_attribute dict for the given noun key."""
    if key is not None:
        if key in repository.constant.noun_attribute:
            repository.constant.noun_attribute[key][1].append(value)
        else:
            repository.constant.noun_attribute[key] = [[], []]


# ── Speaker-view application ──────────────────────────────────────────────────

def add_spkview(full_data, spkview_dict):
    """
    Apply speaker-view markers from spkview_dict to each token's word string.

    Three types of marker:
    'respect' → append '_(respect)' to the last non-article content word
    'before'  →
        - Discourse marker (also/only/…): prepend before everything
        - Article (the/a/an): insert after any leading preposition, before noun
        - Other: prepend at the start
    'after'   → append at the end of the word string
    """
    PREPOSITIONS = {
        'in', 'on', 'at', 'of', 'from', 'to', 'by', 'with', 'for', 'about',
        'among', 'between', 'through', 'into', 'onto', 'upon', 'within',
        'without', 'across', 'along', 'around', 'behind', 'below', 'beside',
        'over', 'under', 'after', 'before', 'according', 'less', 'more',
        'via', 'than', 'like', 'because', 'the', 'a', 'an', '<>'
    }
    DISCOURSE_MARKERS = {
        'only', 'really', 'a few', 'as soon as', 'even', 'also', 'any',
        'even a single', 'may', 'even while', 'so', 'more', 'quite', 'nearly',
        'almost', 'yes', 'exactly', 'amount', 'about', 'just', 'too', 'indeed'
    }
    ARTICLES = {'the', 'a', 'an'}

    transformed_data = []
    for data in full_data:
        index   = data[0]
        spk_info = (spkview_dict.get(index) or
                    spkview_dict.get(str(index)) or
                    spkview_dict.get(int(index) if str(index).isdigit() else index))
        if spk_info:
            temp = list(data)
            for info in spk_info:
                tag = info[0]
                val = info[1]
                if tag == 'respect':
                    # Append '_(respect)' to last non-article word
                    words = temp[1].split()
                    for i in range(len(words) - 1, -1, -1):
                        if words[i].lower() not in {'the', 'a', 'an', 'of', 'in', 'on', 'at'}:
                            words[i] = words[i] + '_(respect)'
                            break
                    temp[1] = ' '.join(words)
                elif tag == 'before':
                    if val in DISCOURSE_MARKERS:
                        # Discourse marker goes at the very beginning
                        temp[1] = val + ' ' + temp[1]
                    elif val in ARTICLES:
                        # Article goes after any leading preposition but before noun
                        words      = temp[1].split()
                        insert_pos = 0
                        for i, w in enumerate(words):
                            if w.lower() in PREPOSITIONS - ARTICLES:
                                insert_pos = i + 1
                            else:
                                break
                        words.insert(insert_pos, val)
                        temp[1] = ' '.join(words)
                    else:
                        temp[1] = val + ' ' + temp[1]
                elif tag == 'after':
                    temp[1] = temp[1] + ' ' + val
            data = tuple(temp)
        transformed_data.append(data)
    return transformed_data


# ── Morpho-semantic marker application ───────────────────────────────────────

def add_MORPHO_SEMANTIC(full_data, MORPHO_SEMANTIC_DICT):
    """
    Apply morpho-semantic modifiers (superlative, comparative) to token words.
    Each entry is a ('before'/'after', word) pair prepended/appended to the token.
    """
    transformed_data = []
    for data in full_data:
        index = data[0]
        if index in MORPHO_SEMANTIC_DICT:
            temp = list(data)
            for t in MORPHO_SEMANTIC_DICT[index]:
                tag, val = t[0], t[1]
                if tag == 'before':
                    temp[1] = val + ' ' + temp[1]
                else:
                    temp[1] = temp[1] + ' ' + val
            data = tuple(temp)
        transformed_data.append(data)
    return transformed_data


# ── Construction marker application ──────────────────────────────────────────

def add_construction(transformed_data, construction_dict):
    """
    Apply construction-specific word additions (conjunctions, conj markers, etc.)
    to token words. Entries can be 'before' (prepend) or 'after' (append).
    Handles special characters: comma and dash are appended without a space.
    """
    Constructdata  = []
    add_words_list = ['meM', 'ko', 'ke', 'kI', 'kA']
    depend_data1   = ''

    for data in transformed_data:
        index = data[0]
        if len(data) == 9:
            depend_data1 = data[8]
        if index in construction_dict:
            temp         = list(data)
            unique_terms = list(dict.fromkeys(construction_dict[index]))
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


# ── Additional words application ─────────────────────────────────────────────

def add_additional_words(additional_words_dict, processed_data):
    """
    Insert additional words (e.g. non-finite prepositions like 'after', 'while')
    before or after each token based on additional_words_dict entries.
    """
    additionalData = []
    for data in processed_data:
        index = data[0]
        if index in additional_words_dict:
            temp = list(data)
            for t in additional_words_dict[index]:
                tag, val = t[0], t[1]
                if tag == 'before':
                    temp[1] = val + ' ' + temp[1]
                else:
                    temp1 = temp[1].split()
                    if len(temp1) >= 2 and temp1[1] == 'ko':
                        temp1[1] = val
                        temp[1]  = ' '.join(temp1)
                    else:
                        temp[1] = temp[1] + ' ' + val
            data = tuple(temp)
        additionalData.append(data)
    return additionalData


# ── Coreference and discourse utilities ──────────────────────────────────────

def add_coreferences(segment_id, index_data, words_info, json_output, discourse_data, coref_list):
    """Process coreference entries and delegate to process_coref() from coref_discourse module."""
    return process_coref(segment_id, index_data, words_info, json_output, discourse_data, coref_list)


def clean_post_process_output(post_process_output, processed_foreign_words):
    """Replace foreign word positions in the output array with their processed forms, then join."""
    for i in range(len(processed_foreign_words)):
        n = processed_foreign_words[i][0]
        post_process_output[n - 1] = processed_foreign_words[i][1].replace('+', ' ')
    return ' '.join(post_process_output)


def add_discourse_elements_to_output(discourse_data, discourse, spkview_data, sp_data, post_process_output):
    """Add discourse connectives (AvaSyakawApariNAma → 'if', vyaBicAra → 'although') to output."""
    if not discourse_data:
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
    Prepend 'if' or 'although' to the output when discourse data signals
    conditional or concessive sentence types.
    """
    for i in discourse_data:
        if 'AvaSyakawApariNAma' in i and 'nahIM' not in spkview_data:
            return 'if' + post_process_output
        elif 'vyaBicAra' in i:
            return 'although' + post_process_output
    return post_process_output


def fetch_NC_head(i, processed_words):
    """Return the index of the NC_head token at integer index i, or None if not found."""
    for data in processed_words:
        temp = tuple(data)
        if int(temp[0]) == int(i) and temp[7] == 'NC_head':
            return temp[0]


# ── Auxiliary mapping ─────────────────────────────────────────────────────────

def auxmap(aux_verb, lang):
    """
    Find all non-overlapping auxiliary chunks in the auxiliary mapping file
    (longest match first). Returns list of (matched_chunk, root, TAMs).

    The mapping file (language_rules/{lang}.py → AUX_MAP_FILE) maps
    auxiliary verb forms (e.g. 'wA_hE') to (root, TAM) pairs.
    Uses a greedy longest-match strategy: tries length 4 down to 1.
    Warns about any unmatched sub-words.
    """
    import importlib
    import sys

    lang_module    = importlib.import_module(f'language_rules.{lang}')
    aux_map_files  = getattr(lang_module, 'AUX_MAP_FILE', None)
    aux_file_path  = aux_map_files.get(lang)
    if not aux_file_path:
        log(f'No mapping file defined for language: {lang}', 'ERROR')
        return []

    aux_dict = {}
    try:
        with open(aux_file_path, 'r') as tamfile:
            for line in tamfile:
                parts = line.strip().split(',')
                if len(parts) < 3:
                    continue
                key = parts[0]
                if key in ('word', 'Word', ''):
                    continue  # skip header line
                if lang == 'hi':
                    aux_dict[key] = (parts[1], parts[2])
                else:
                    aux_dict[key] = (parts[1], parts[2:])
    except FileNotFoundError:
        log(f'Auxiliary mapping file not found: {aux_file_path}', 'ERROR')
        sys.exit()

    parts            = aux_verb.split('_')
    n                = len(parts)
    matched_results  = []
    covered_indices  = set()

    # Try longest match first (length n down to 1)
    for k in range(n, 0, -1):
        for i in range(n - k + 1):
            if any(j in covered_indices for j in range(i, i + k)):
                continue
            candidate = '_'.join(parts[i:i + k])
            if candidate in aux_dict:
                root, tam = aux_dict[candidate]
                log(f'Found match: "{candidate}" from "{aux_verb}"', 'INFO')
                matched_results.append((candidate, root, tam))
                covered_indices.update(range(i, i + k))

    for idx, word in enumerate(parts):
        if idx not in covered_indices:
            log(f'"{word}" not found in auxiliary mapping.', 'WARNING')

    return matched_results


# ── Additional words dict update ──────────────────────────────────────────────

def update_additional_words_dict(index, tag, add_word):
    """
    Add (tag, add_word) to additional_words_dict[index].
    Avoids duplicate entries with the same (tag, word) combination.
    """
    value       = (tag, add_word)
    value_found = False
    if index in additional_words_dict:
        for data in additional_words_dict[index]:
            if data[0] == tag and data[1] == add_word:
                value_found = True
        if not value_found:
            additional_words_dict[index].append(value)
    else:
        additional_words_dict[index] = [value]


def to_tuple(verb):
    """Convert a Verb object to an 11-element tuple for insertion into processed_words."""
    return (verb.index, verb.term, verb.category, verb.gender, verb.number,
            verb.person, verb.tam, verb.case, verb.type, verb.relation_head, verb.relation)


# ── Postposition finalisation (Hindi only) ───────────────────────────────────

def postposition_finalization(processed_nouns, processed_pronouns, processed_foreign_words, words_info, lang):
    """
    Hindi only: after all nouns/pronouns are processed, correct any 'ke' postpositions
    for r6 relations where the head noun is in oblique case.
    Called at the end of process_all_cat().
    """
    if lang != 'hi':
        return
    for data in words_info:
        data_index = data[0]
        dep        = data[4]
        if 'r6' in dep:
            dep  = data[4].strip().split(':')[1]
            head = data[4].strip().split(':')[0]
            for noun in processed_nouns:
                index = noun[0]
                case  = noun[3]
                if head == str(index) and case == 'o':
                    update_ppost_dict(data_index, 'ke')
            for pronoun in processed_pronouns:
                index = pronoun[0]
                case  = pronoun[3]
                if head == str(index) and case == 'o':
                    update_ppost_dict(data_index, 'ke')


# ── Processed data collector ──────────────────────────────────────────────────

def collect_processed_data(index_data, processed_foreign_words, processed_pronouns,
                           processed_nouns, processed_adjectives, processed_verbs,
                           processed_auxverbs, processed_indeclinables, processed_others):
    """
    Combine all category-specific processed word lists into one sorted list,
    ordered by USR index. Words not in index_data are appended at the end.
    """
    combined_data = (
        processed_foreign_words + processed_pronouns + processed_nouns +
        processed_adjectives + processed_verbs +
        processed_auxverbs + processed_indeclinables + processed_others
    )

    def safe_sort_key(item):
        index = item[0]
        try:
            return float(index) if index is not None else float('inf')
        except (ValueError, TypeError):
            return float('inf')

    sorted_data    = sorted(combined_data, key=safe_sort_key)
    result         = []
    used_indices   = set(str(idx) for idx in index_data)
    matched_items  = []
    unmatched_items = []

    for item in sorted_data:
        item_idx = str(item[0])
        if item_idx in used_indices:
            matched_items.append(item)
        else:
            unmatched_items.append(item)

    for idx in index_data:
        for item in matched_items:
            if str(item[0]) == str(idx):
                result.append(item)

    result.extend(unmatched_items)
    return result


# ── Compound word joiner (Hindi) ─────────────────────────────────────────────

def join_compounds(transformed_data, construction_data):
    """
    Join consecutive tokens at the same index (e.g. NC compound splits) with a space.
    Used in Hindi output to re-join compound words separated during processing.
    """
    resultant_data = []
    prevword       = ''
    previndex      = -1
    for data in transformed_data:
        if (data[0]) == previndex and data[2] == 'n':
            temp     = list(data)
            temp[1]  = prevword + ' ' + temp[1]
            data     = tuple(temp)
            resultant_data.pop()
        resultant_data.append(data)
        previndex = data[0]
        prevword  = data[1]
    return resultant_data


# ── Morpho-semantic dict population ──────────────────────────────────────────

def populate_morpho_semantic_dict(index_data, gnp_info, PPfull_data, words_info, lang):
    """
    Detect morpho-semantic features in GNP data (superl, comparmore, comparless)
    and populate MORPHO_SEMANTIC_DICT with ('before'/'after', word) entries.

    For English (from language_rules/en.py):
      superl → ('before', 'most')
      comparmore → ('before', 'more')
      comparless → ('before', 'less')

    Returns (bool: dict_was_populated, updated PPfull_data).
    """
    populate_morpho_semantic_dict_flag = False
    a = 'after'
    b = 'before'

    try:
        lang_module = importlib.import_module(f'language_rules.{lang}')
        lang_rules  = getattr(lang_module, 'morpho_seman', {})
    except ImportError:
        lang_rules = {}

    for i, term in enumerate(gnp_info):
        if term in repository.constant.morpho_seman:
            populate_morpho_semantic_dict_flag = True
            if term == 'superl' and not any(re.match(r'^more_\d+$', word[1]) for word in words_info):
                temp = lang_rules.get('superl', (b, 'sabase'))
            elif term in ('comparmore',):
                temp = lang_rules.get('comparmore', (b, 'aXika'))
            elif term in ('comparless',):
                temp = lang_rules.get('comparless', (b, 'kama'))
            elif term == 'superl':
                dup_word = clean(words_info[i][1])
                if dup_word in PPfull_data[i][1]:
                    if 'para' in PPfull_data[i][1]:
                        dup_word1 = dup_word + '-' + dup_word + ' para'
                        PPfull_data[i] = PPfull_data[i][:1] + (dup_word1,) + PPfull_data[i][2:]
                        temp = (a, '')
                    elif 'more' in PPfull_data[i][1]:
                        dup_word1 = 'most'
                        PPfull_data[i] = PPfull_data[i][:1] + (dup_word1,) + PPfull_data[i][2:]
                        temp = (a, '')
                    else:
                        dup_word = '-' + dup_word
                        temp = (a, dup_word)
                else:
                    temp = (a, '')
            else:
                noun_data = nextNounData_fromFullData(index_data[i + 1], PPfull_data)
                if noun_data != ():
                    g, n = noun_data[4], noun_data[5]
                    if g == 'f':
                        temp = (a, 'vAlI')
                    elif n == 'p':
                        temp = (a, 'vAle')
                    elif n == 's':
                        temp = (a, 'with')
                    else:
                        temp = (a, '')
                else:
                    temp = (a, '')

            current_index = index_data[i]
            if current_index in MORPHO_SEMANTIC_DICT:
                MORPHO_SEMANTIC_DICT[current_index].append(temp)
            else:
                MORPHO_SEMANTIC_DICT[current_index] = [temp]

    return populate_morpho_semantic_dict_flag, PPfull_data


# ── Misc output helpers ───────────────────────────────────────────────────────

def join_indeclinables(transformed_data, processed_indeclinables, processed_others):
    """Concatenate indeclinables and other words to the main transformed data list."""
    return transformed_data + processed_indeclinables + processed_others


# ── Sentence filter and output builder ───────────────────────────────────────

def filter_and_concat_data(data, sentence_type_dict):
    """
    Convert PP_fulldata (list of word tuples per sentence) into flat sentence strings.
    Skips:
    - NC modifier tokens (type 'NC' or 'NC_head' in field 7)
    - Measurement construction names (distmeas, timemeas, etc.)
    - State-copula markers ('statecopula')
    - <> placeholders
    - Words in the global construction_list (conj, waw, span, etc.)
    Appends sentence-final punctuation based on sentence_type_dict.
    """
    filtered_data = {}
    meas_skip_words = [
        '#waw', 'calender', '#ne', 'lengthmeas', 'tempmeas', 'weightmeas',
        'widthmeas', 'depthmeas', 'distmeas', 'rate', 'timemeas', 'massmeas',
        'heightmeas', 'dist_meas', 'span', 'statecopula', 'conj', 'disjunct',
        'waw', 'nc', 'cp', 'ne'
    ]
    CONSTRUCTION_SKIP = {
        'distmeas', 'conj', 'disjunct', 'statecopula', 'waw', 'span',
        'timemeas', 'massmeas', 'heightmeas', 'widthmeas', 'depthmeas',
        'lengthmeas', 'tempmeas', 'weightmeas', 'dist_meas', 'nc', 'cp'
    }

    for key, values in data.items():
        concatenated = []
        if isinstance(values, list) and all(isinstance(item, tuple) for item in values):
            for item in values:
                word = item[1]
                if any(phrase in word for phrase in ['statecopula']):
                    continue
                if len(item) > 7 and item[7] in ('NC', 'NC_head'):
                    continue
                if any(meas in word for meas in meas_skip_words):
                    continue
                if word.strip() == '<>':
                    continue
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
    """Join word strings from fulldata into a sentence, handling hyphenated words without spaces."""
    finalData  = []
    final_words = []
    for i in range(len(finalData)):
        word = finalData[i][1].strip()
        if i > 0 and final_words[-1].endswith('-'):
            final_words[-1] = final_words[-1] + word
        else:
            final_words.append(word)
    return " ".join(final_words)


# ── Hindi output collector (WX → Devanagari, Hindi only) ─────────────────────

def collect_hindi_output(filtered_data):
    """
    Process filtered_data for Hindi output.
    Removes construction-list words and returns the cleaned strings.
    (WXC conversion is disabled; Hindi strings are handled elsewhere.)
    """
    converted_data    = {}
    generate_hindi_text = ""
    for key, values in filtered_data.items():
        converted_values = []
        for value in values:
            if value.startswith("ERROR:") or "ERROR:" in value:
                converted_values.append(value)
            else:
                words = value.split()
                value = ' '.join(v for v in words if v[1:] not in repository.constant.construction_list)
                value = value.replace('_', ' ')
                if '<>' in generate_hindi_text:
                    print(generate_hindi_text, 'oppp')
                    generate_hindi_text = generate_hindi_text.replace('<>', '[MASK]')
                converted_values.append(generate_hindi_text)
        converted_data[key] = converted_values
    return converted_data


# ── Segment parser ────────────────────────────────────────────────────────────

def parse_segments(input_text):
    """Split raw USR input text into individual segment blocks on '</id>' boundaries."""
    return input_text.strip().split('</id>')


# ── Global state reset ────────────────────────────────────────────────────────

def reset_global_dicts():
    """
    Clear all global dictionaries before processing a new sentence segment.
    This prevents state from one sentence leaking into the next.
    """
    global additional_words_dict, processed_postpositions_dict, construction_dict
    global spkview_dict, MORPHO_SEMANTIC_DICT
    additional_words_dict.clear()
    processed_postpositions_dict.clear()
    construction_dict.clear()
    spkview_dict.clear()
    MORPHO_SEMANTIC_DICT.clear()
    global_starred_words.clear()


# ── Numeric helpers ───────────────────────────────────────────────────────────

def check_is_digit(num):
    """Return True if num can be parsed as an integer or float."""
    if num.isdigit():
        return True
    try:
        float(num)
        return True
    except ValueError:
        return False


# ── Module self-test ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    import doctest
    doctest.run_docstring_examples(identify_complete_tam_for_verb, globals())
