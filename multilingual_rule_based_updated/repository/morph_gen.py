import os
import subprocess
from repository.constant import *
from repository.common_v4 import log
from repository.eng_morph import count_syllables
from language_rules.en import days, months, indeclinables_dict

def hi_generate_morph(processed_words):
    """Run Morph generator"""
    morph_input = generate_input_for_morph_generator(processed_words)
    MORPH_INPUT = write_data(morph_input)
    OUTPUT_FILE1 = run_morph_generator(MORPH_INPUT)
    log(f"Output of Morph Generator : {OUTPUT_FILE1}")

    # Build morph_mapping so analyse_output_data can reassemble word tuples.
    surface_words = OUTPUT_FILE1.strip().split()
    morph_mapping = {}
    index_counts = {}
    for item, morph_str, word in zip(processed_words, morph_input, surface_words):
        idx = str(item[0])
        if idx not in index_counts:
            index_counts[idx] = 0
            morph_mapping[idx] = (morph_str, word)
        else:
            index_counts[idx] += 1
            sub_idx = f"{idx}.{index_counts[idx]}"
            morph_mapping[sub_idx] = (morph_str, word)

    # Return as 9-tuple matching en_generate_morph signature
    return (OUTPUT_FILE1, {}, {}, {}, {}, {}, {}, morph_mapping, {})

def en_generate_morph(processed_words, tam_term, depend_data, sentence_type, index_data):
    interrogative_dict = {}
    foreign_words_dict = {}
    calendar_dict = {}
    indec_dict = {}
    rad_dict = {}
    remove_indices = []
    POSSESSIVE_FORMS = {'its', 'his', 'her', 'their', 'my', 'our', 'your', 'whose', 'own'}

    for i, item in enumerate(depend_data):
        if item.split(":")[-1] == "rad":
            rad_index = i
            rad_key = index_data[rad_index] - 1
            rad_value = "oh"
            rad_dict = {rad_key: (rad_key, rad_value, 'interj', '', '', '', 'none', 'none')}
            break

    # Identify items to remove and build dictionaries
    for data in processed_words:
        word_index, word_value = data[0], data[1]
        word_indec = data[2]

        if word_value in [
            "Who", "What", "Whom", "with_what", "to_whom", "from_where",
            "Whose", "Where", "When", "Why", "Which", "How"
        ]:
            interrogative_dict[word_index] = data
            remove_indices.append(word_index)

        elif word_value.startswith('^'):
            word_value = word_value.split('_')[0]
            foreign_words_dict[word_index] = data
            remove_indices.append(word_index)

        elif word_value in days or word_value in months:
            calendar_dict[word_index] = data
            remove_indices.append(word_index)

        elif word_indec == 'indec':
            indec_dict[word_index] = data
            remove_indices.append(word_index)

        elif word_value.lower() in POSSESSIVE_FORMS and word_indec == 'p':
            indec_dict[word_index] = data
            remove_indices.append(word_index)

    # Remove matching indices
    processed_words = [item for item in processed_words if item[0] not in remove_indices]

    for idx in sorted(remove_indices, reverse=True):
        if idx in index_data:
            index = index_data.index(idx)
            index_data.pop(index)
            depend_data.pop(index)

    # Continue processing
    morph_input = generate_input_for_en_morph_generator(
        processed_words, tam_term, depend_data, sentence_type, index_data
    )

    final_morph_input = format_morph_input(morph_input)
    MORPH_INPUT = write_data(final_morph_input)
    OUTPUT_FILE1 = run_en_morph_generator(MORPH_INPUT)

    words = OUTPUT_FILE1.strip().split()

    # ── Fallback English pluralization ───────────────────────────────────────
    # Apertium returns '#lemma' for nouns absent from its monolingual dictionary
    # (e.g. transliterated proper-ish nouns like 'Hindu'). When the morph request
    # asked for a plural noun, apply regular English plural rules so the number
    # feature from the USR is not silently lost.
    def _en_pluralize(lemma):
        irregular = {
            'child': 'children', 'man': 'men', 'woman': 'women', 'tooth': 'teeth',
            'foot': 'feet', 'mouse': 'mice', 'person': 'people', 'goose': 'geese',
        }
        low = lemma.lower()
        if low in irregular:
            out = irregular[low]
            return out.capitalize() if lemma[:1].isupper() else out
        if re.search(r'(s|x|z|ch|sh)$', low):
            return lemma + 'es'
        if re.search(r'[^aeiou]y$', low):
            return lemma[:-1] + 'ies'
        if low.endswith('f'):
            return lemma[:-1] + 'ves'
        if low.endswith('fe'):
            return lemma[:-2] + 'ves'
        return lemma + 's'

    # ── Multiword-aware alignment ────────────────────────────────────────────
    # Apertium multiword tokens (lemma + "# particle", e.g. "use<vblex><past># to")
    # expand to TWO surface words ("used to"). A plain zip(tokens, words) would
    # then mis-align every following token and drop a trailing word (e.g. the main
    # verb in "used to go"). So we consume the right number of words per token:
    # a "# " token takes 2 words, every other token takes 1.
    def _aligned_words_per_token(morph_strs, surface_words):
        out, wi = [], 0
        for mstr in morph_strs:
            if '# ' in mstr and wi + 1 < len(surface_words):
                out.append(' '.join(surface_words[wi:wi + 2]))   # e.g. "used to"
                wi += 2
            else:
                out.append(surface_words[wi] if wi < len(surface_words) else '')
                wi += 1
        # keep any leftover words attached to the last token (defensive)
        if wi < len(surface_words):
            out[-1] = (out[-1] + ' ' + ' '.join(surface_words[wi:])).strip()
        return out

    grouped = _aligned_words_per_token(final_morph_input, words)

    from repository.common_v4 import spkview_dict as _spkview_dict
    def _is_respect(idx):
        for _k in (idx, str(idx)):
            for _t in _spkview_dict.get(_k, []):
                if (isinstance(_t, (tuple, list)) and 'respect' in _t) or _t == 'respect':
                    return True
        return False

    fixed_words = []
    for item, mstr, w in zip(morph_input, final_morph_input, grouped):
        if w.startswith('#') and ('<n>' in mstr or '<np>' in mstr) and '<pl>' in mstr:
            lemma = mstr[1:].split('<', 1)[0]
            if '<np>' in mstr:
                # Honorific/respect plural on a name (e.g. 'śiva_(respect)') is NOT a
                # real count plural — don't add an English 's' to it.
                if _is_respect(item[0]):
                    fixed_words.append(w)
                    continue
                # proper noun apertium could not generate: transliterate WX->Roman
                # then add the English plural so the 'pl' feature is not lost
                # ('sapwapuri' -> 'saptapuri' -> 'saptapuris').
                from repository.common_v4 import wx_to_english
                fixed_words.append(_en_pluralize(wx_to_english(lemma)))
            else:
                # Also apply WX->Roman transliteration for common nouns that
                # are WX-encoded (e.g. 'sapwapuri' -> 'saptapuri' -> 'saptapuris')
                from repository.common_v4 import wx_to_english
                roman_lemma = wx_to_english(lemma)
                fixed_words.append(_en_pluralize(roman_lemma))
        else:
            fixed_words.append(w)
    words = fixed_words
    OUTPUT_FILE1 = ' '.join(words)
    morph_mapping = {}
    index_counts = {}

    for (item, morph_str, word) in zip(morph_input, final_morph_input, words):
        idx = str(item[0])
        if idx not in index_counts:
            index_counts[idx] = 0
            morph_mapping[idx] = (morph_str, word)
        else:
            index_counts[idx] += 1
            sub_idx = f"{idx}.{index_counts[idx]}"
            morph_mapping[sub_idx] = (morph_str, word)

    print(morph_mapping)

    nonfinite_dict = {}
    return OUTPUT_FILE1, interrogative_dict, foreign_words_dict, calendar_dict, indec_dict, nonfinite_dict, morph_mapping, rad_dict


def generate_input_for_morph_generator(input_data):
    """Process the input and generate the input for morph generator"""
    morph_input_data = []
    for data in input_data:
        if data[2] == 'p':
            if data[8] != None and isinstance(data[8], str):
                morph_data = f'^{data[1]}<cat:{data[2]}><parsarg:{data[7]}><fnum:{data[8]}><case:{data[3]}><gen:{data[4]}><num:{data[5]}><per:{data[6]}>$'
            else:
                morph_data = f'^{data[1]}<cat:{data[2]}><case:{data[3]}><parsarg:{data[7]}><gen:{data[4]}><num:{data[5]}><per:{data[6]}>$'
        elif data[2] == 'n' and data[7] in ('proper', 'digit'):
            morph_data = f'{data[1]}'
        elif data[2] == 'vn':
            morph_data = f'^{data[1]}<cat:{data[2]}><case:{data[3]}>$'
        elif data[2] == 'n' and data[7] != 'proper':
            morph_data = f'^{data[1]}<cat:{data[2]}><case:{data[3]}><gen:{data[4]}><num:{data[5]}>$'
        elif data[2] == 'v' and data[8] in ('main', 'auxiliary'):
            morph_data = f'^{data[1]}<cat:{data[2]}><gen:{data[3]}><num:{data[4]}><per:{data[5]}><tam:{data[6]}>$'
        elif data[2] == 'v' and data[6] == 'kara' and data[8] in ('nonfinite', 'adverb'):
            morph_data = f'^{data[1]}<cat:{data[2]}><gen:{data[3]}><num:{data[4]}><per:{data[5]}><tam:{data[6]}>$'
        elif data[2] == 'v' and data[6] != 'kara' and data[8] == 'nonfinite':
            morph_data = f'^{data[1]}<cat:{data[2]}><gen:{data[3]}><num:{data[4]}><case:{data[7]}><tam:{data[6]}>$'
        elif data[2] == 'adj':
            morph_data = f'^{data[1]}<cat:{data[2]}><case:{data[3]}><gen:{data[4]}><num:{data[5]}>$'
        elif data[2] == 'vj':
            morph_data = f'^{data[1]}<cat:{data[2]}><case:{data[3]}><gen:{data[4]}><num:{data[5]}><tam:{data[6]}>$'
        elif data[2] == 'indec':
            morph_data = f'{data[1]}'
        elif data[2] == 'other':
            morph_data = f'{data[1]}'
        else:
            morph_data = f'^{data[1]}$'
        morph_input_data.append(morph_data)
    print(morph_input_data)
    return morph_input_data

import re

word = ''

def generate_input_for_en_morph_generator(input_data, tam_term, depend_data, sentence_type, index_data):
    global word
    person_mapping = {'a': 'p3', 'm': 'p2', 'u': 'p1'}

    input_data = [
        tuple(
            'have' if any(d.endswith(ending) for ending in (':rsma', ':rsm', ':rhh') for d in depend_data) and item == 'statecopula'
            else 'be' if item == 'statecopula'
            else item
            for item in tup
        )
        for tup in input_data
    ]

    morph_input_final_tup = []
    depend_dict = {
        key: (item.split(':')[1] if ':' in item and len(item.split(':')) > 1 else '')
        for key, item in zip(index_data, depend_data)
    }

    for i, data in enumerate(input_data):
        morph_input_tuple = None
        data = list(data)

        # Handle special list structure in data[6]
        if len(data) > 6 and isinstance(data[6], list):
            joined = ' '.join(data[6])
            matches = re.findall(r"\(([^)]+)\)", joined)

            new_list = []
            for token in matches:
                items = token.split(',') if ',' in token else token.split()
                temp = []
                skip_next = False
                for i, t in enumerate(items):
                    if skip_next:
                        skip_next = False
                        continue

                    t = t.strip().replace("'", "")
                    if not t:
                        continue

                    if t == '#' and i + 1 < len(items):
                        next_t = items[i + 1].strip().replace("'", "")
                        temp.append(f"{t} {next_t}")
                        skip_next = True
                    elif t == 'per':
                        temp.append(person_mapping.get(data[5], data[5]))
                    elif t == 'num':
                        data[4] = 'sg' if data[4] == 's' else 'pl'
                        temp.append(data[4])
                    else:
                        temp.append(t)
                new_list.append(tuple(temp))

        # Skip specific words
        if data[1] in ["kEsA", "kyA"]:
            continue

        # Pronoun and determiner cases
        if data[2] == 'p':
            person = person_mapping.get(data[6], None)
            number = 'sg' if data[5] == 's' else 'pl'
            gender = data[4]
            parsarg = data[7] if len(data) > 7 else None
            spkview = data[8] if len(data) > 8 else None
            relation = depend_dict.get(data[0], '')

            # ── $speaker → I/me (1st person) ──
            # ── $speaker → I/me (1st person) ──
            if data[1] in ['speaker', '$speaker', 'I', 'we']:
                case_val = data[3] if len(data) > 3 else 'o'
                if case_val == 'subj':
                    # Subject form: I / we
                    morph_input_tuple = ('prpers', 'prn', 'subj', 'p1', 'mf', number)
                else:
                    # Object form: me / us
                    morph_input_tuple = ('prpers', 'prn', 'obj', 'p1', 'mf', number)

            # ── $addressee → you (2nd person) ──
            elif data[1] in ['addressee', '$addressee']:
                case_val = data[3] if len(data) > 3 else 'o'
                if case_val in ('o', 'd'):
                    morph_input_tuple = ('prpers', 'prn', 'obj', 'p2', 'mf', number)
                else:
                    morph_input_tuple = ('prpers', 'prn', 'subj', 'p2', 'mf', number)

            # ── already-resolved English pronoun words ──
            elif data[1] == 'I' or data[1] == 'we':
                morph_input_tuple = ('prpers', 'prn', 'subj', 'p1', 'mf', number)
            elif data[1] in ['me', 'us', 'my', 'our', 'myself']:
                morph_input_tuple = ('prpers', 'prn', 'obj', 'p1', 'mf', number)
            elif data[1] in ['you', 'your', 'yourself']:
                morph_input_tuple = ('prpers', 'prn', 'subj', 'p2', 'mf', number)
            elif data[1] in ['he']:
                morph_input_tuple = ('prpers', 'prn', 'subj', 'p3', 'm', number)
            elif data[1] in ['him', 'his']:
                morph_input_tuple = ('prpers', 'prn', 'obj', 'p3', 'm', number)
            elif data[1] in ['she']:
                morph_input_tuple = ('prpers', 'prn', 'subj', 'p3', 'f', number)
            elif data[1] in ['her']:
                morph_input_tuple = ('prpers', 'prn', 'obj', 'p3', 'f', number)
            elif data[1] in ['they']:
                morph_input_tuple = ('prpers', 'prn', 'subj', 'p3', 'mf', 'pl')
            elif data[1] in ['them', 'their']:
                morph_input_tuple = ('prpers', 'prn', 'obj', 'p3', 'mf', 'pl')
            elif data[1] in ['it', 'its']:
                morph_input_tuple = ('prpers', 'prn', 'obj', 'p3', 'nt', number)
            elif data[1] in ['this']:
                morph_input_tuple = ('this', 'det', 'dem', 'sg')
            elif data[1] in ['that']:
                morph_input_tuple = ('that', 'det', 'dem', 'sg')
            elif data[1] in ['these']:
                morph_input_tuple = ('these', 'det', 'dem', 'pl')
            elif data[1] in ['those']:
                morph_input_tuple = ('those', 'det', 'dem', 'pl')
            elif data[1] in ['here']:
                morph_input_tuple = ('here', 'adv')
            elif data[1] in ['there']:
                morph_input_tuple = ('there', 'adv')
            elif data[1] in ['prpers', 'of']:
                morph_input_tuple = ('prpers', 'prn', 'obj', person or 'p3', gender or 'mf', number)

            # ── universal quantifier pronouns: all/everyone/everybody/both ──
            elif data[1] in ['all', 'everyone', 'everybody', 'both', 'each', 'many', 'several']:
                morph_input_tuple = (data[1], 'prn', 'subj', 'p3', 'mf', 'pl')

            # ── wyax/it handling ──
            elif data[1] in ['it'] and relation in ['k1', 'k2', 'k7', 'k7p']:
                morph_input_tuple = ('this', 'det', 'dem', 'sg') if number == 'sg' else ('these', 'det', 'dem', 'pl')
                print(f"[DEBUG pronoun tuple] index={data[0]} spkview={spkview} relation={relation} → {morph_input_tuple}")

            # ✅ FIXED: wyax with gender-aware possessive
            elif data[1] in ['wyax', '$wyax']:
                # CHECK IF IT'S POSSESSIVE (r6 relation)
                if relation == 'r6':
                    # Get gender from seman field (index 2) or gnp
                    seman = data[2] if len(data) > 2 else ''
                    if 'male' in str(seman) or gender == 'm':
                        morph_input_tuple = ('his', 'det', 'pos')
                    elif 'female' in str(seman) or gender == 'f':
                        morph_input_tuple = ('her', 'det', 'pos')
                    else:
                        morph_input_tuple = ('its', 'det', 'pos')
                
                # NOT possessive - continue with demonstrative/pronoun logic
                else:
                    animacy = data[7] if len(data) > 7 else None
                    seman = data[2] if len(data) > 2 else '-'

                    # Check relation first — dem/k7p/k7 → demonstrative
                    if relation in ['dem', 'k7p', 'k7', 'k5']:
                        if spkview == 'proximal':
                            morph_input_tuple = ('here', 'adv') if relation in ['k7p', 'k7', 'k5'] else ('this', 'det', 'dem', number)
                        else:
                            morph_input_tuple = ('there', 'adv') if relation in ['k7p', 'k7', 'k5'] else ('that', 'det', 'dem', number)

                    # NULL seman → inanimate → this/that/it
                    elif seman in ['-', '', None, 'null'] or animacy in ['inanim', 'null', None, '-']:
                        if number == 'pl':
                            if spkview == 'proximal':
                                morph_input_tuple = ('these', 'det', 'dem', 'pl')
                            else:
                                morph_input_tuple = ('those', 'det', 'dem', 'pl')
                        else:
                            if spkview == 'proximal':
                                morph_input_tuple = ('this', 'det', 'dem', 'sg')
                            elif spkview == 'distal':
                                morph_input_tuple = ('that', 'det', 'dem', 'sg')
                            else:
                                morph_input_tuple = ('it', 'prn', 'subj', person, 'nt', number)

                    # ANIMATE → he/she/they
                    elif animacy in ['anim', 'per']:
                        if number == 'pl':
                            morph_input_tuple = ('they', 'prpers', 'prn', 'subj', person, 'mf', 'pl')
                        else:
                            if gender == 'f':
                                morph_input_tuple = ('she', 'prpers', 'prn', 'subj', person, 'f', 'sg')
                            elif gender == 'm':
                                morph_input_tuple = ('he', 'prpers', 'prn', 'subj', person, 'm', 'sg')
                            else:
                                morph_input_tuple = ('they', 'prpers', 'prn', 'subj', person, 'mf', number)

                    # Fallback
                    else:
                        morph_input_tuple = ('it', 'prn', 'subj', person, 'nt', number)

        elif data[2] == 'n':
            person = person_mapping.get(data[6], None)
            number = 'sg' if data[5] == 's' else 'pl'
            gender = data[4]
            if data[1] in ['not', 'after', 'before', 'near', 'far']:
                morph_input_tuple = (data[1], 'adv')

            elif data[7] == 'digit':
                word = data[1].lower()

                if re.search(r'(st|nd|rd|th)$', word):
                    number_only = re.sub(r'(st|nd|rd|th)$', '', word)
                    morph_input_tuple = (number_only, 'adj', 'ord')

                elif "o'clock" in word:
                    number_only = word.replace("o'clock", "").strip()
                    morph_input_tuple = [(number_only, 'num'), ("o'clock", 'adv')]

                else:
                    morph_input_tuple = (data[1], 'num')

            elif len(data) > 7 and data[7] == 'proper':
                morph_input_tuple = (data[1], 'np', 'ant', gender, number)
            else:
                morph_input_tuple = (data[1], 'n', number)

        elif data[2] == 'adj':
            syllable_count = count_syllables(data[1])
            morph_input_tuple = (data[1], 'adj', 'sint') if syllable_count == 1 else (data[1], 'adj')

        elif data[2] == 'adv':
            morph_input_tuple = (data[1], 'adv')

        elif data[2] == 'v':
            person = person_mapping.get(data[5], None)
            number = 'sg' if data[4] == 's' else 'pl'
            gender = data[3]

            if isinstance(data[6], list):
                morph_input_final_tup.extend(new_list)

            elif 'es' in data or 'pres' in data:
                if data[4] == "s" and data[5] == "a":
                    morph_input_tuple = (data[1], 'vblex', 'pres', person, number)
                else:
                    morph_input_tuple = (data[1], 'vblex', 'pres')
            elif 'en' in data or (
                    len(data) > 6 and isinstance(data[6], str)
                    and data[6].startswith('en_')
                    and not data[6].startswith('en_got')):
                morph_input_tuple = (data[1], 'vblex', 'pp')
            elif len(data) > 6 and isinstance(data[6], str) and data[6].startswith('en_got'):
                # completive-past form (yA_gayA → en_got): use simple past
                morph_input_tuple = (data[1], 'vblex', 'past')
            elif data[6] == "past" or data[6] == "was":
                # 'was' is the TAM marker for passive past (was_en): main verb → past form
                if data[1] == 'be' and data[4] == "s" and data[5] == "a":
                    morph_input_tuple = (data[1], 'vblex', 'past', person, number)
                else:
                    morph_input_tuple = (data[1], 'vblex', 'past')
            elif 'ed' in data:
                morph_input_tuple = (data[1], 'vblex', 'past')
            elif 'ing' in data:
                morph_input_tuple = (data[1], 'vblex', 'pprs')
            elif data[6] == "had_to":
                morph_input_tuple = (data[1], 'vblex', 'pres')
            elif data[6] == "0":
                morph_input_tuple = (data[1], 'vblex', 'imp')
            else:
                morph_input_tuple = (data[1], 'vblex', 'inf')

        elif sentence_type[1:] in ['negative', 'interrogative'] and tam_term == 'wA_hE_1':
            morph_input_tuple = ('do', 'vaux', 'pres')

        if morph_input_tuple:
            if isinstance(morph_input_tuple, list):
                morph_input_final_tup.extend(morph_input_tuple)
            else:
                morph_input_final_tup.append(morph_input_tuple)

    morph_input_final_tuple = []

    # Build lookup
    word_to_indices = {}
    for data in input_data:
        word = data[1].lower()
        word_to_indices.setdefault(word, []).append(data[0])

    used_indices = set()
    same_length = len(morph_input_final_tup) == len(input_data)

    for i, tup in enumerate(morph_input_final_tup):
        word = tup[0].lower()
        index = None

        if word in word_to_indices:
            for idx in word_to_indices[word]:
                if idx not in used_indices:
                    index = idx
                    used_indices.add(idx)
                    break

        if index is None and same_length:
            index = input_data[i][0]
            used_indices.add(index)

        if index is None:
            index = -1

        morph_input_final_tuple.append((index,) + tup)

    return morph_input_final_tuple


def format_morph_input(morph_input_final_tuple):
    """Formats the morph input data into the required structure with support for +word."""
    morph_input_format = []

    for item in morph_input_final_tuple:
        if isinstance(item, tuple) and len(item) > 1:
            output = '^'
            tags_started = False

            for i, elem in enumerate(item[1:], start=1):
                if isinstance(elem, str) and elem.startswith('#'):
                    marker = elem
                    break
            else:
                marker = ''

            for tag in item[1:]:
                if tag == marker:
                    continue
                if isinstance(tag, str) and tag.startswith('+'):
                    output += tag
                    tags_started = True
                elif not tags_started:
                    output += tag
                    tags_started = True
                else:
                    output += f'<{tag}>'

            output += marker + '$'
            morph_input_format.append(output)

    return morph_input_format


def write_data(writedata):
    """Return the Morph Input Data as a string instead of writing to a file."""
    final_input = " ".join(writedata)
    return final_input

import subprocess

def run_morph_generator(data):
    """Pass the morph generator through the provided data and return the output for Hindi."""
    command = [
        "lt-proc",
        "-g",
        "-c",
        "repository/hi.gen_LC.bin",
    ]

    result = subprocess.run(
        command,
        input=data,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Error in Hindi morph generator: {result.stderr}")

    return result.stdout

def run_en_morph_generator(data):
    print('morph_input', data)
    """Pass the morph generator through the provided data and return the output for English."""
    _tool_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    command = [
        "lt-proc",
        "-g",
        "-c",
        os.path.join(_tool_root, "apertium_eng", "eng.autogen.bin"),
    ]

    result = subprocess.run(
        command,
        input=data,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Error in English morph generator: {result.stderr}")

    return result.stdout
