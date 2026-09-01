import sys
from repository.common_v4 import *



import re



import re

def is_cp(input_data):
    print("Input Data:\n", input_data)

    sentences = re.findall(r'(<sent_id=(.*?)>[\s\S]*?</sent_id>)', input_data)
    updated_sentences = []
    store_cp_with_ids = {}  # {cp_index: [(sent_id, word_id), ...]}

    for full_sent, sent_id in sentences:
        lines = full_sent.strip().split('\n')
        line_list = [line.strip().split() for line in lines if line.strip()]

        # Find all CP entries in the sentence
        cp_entries = []
        for parts in line_list:
            if parts and re.fullmatch(r'\[cp_\d+\]', parts[0]) and len(parts) > 1:
                cp_entries.append((parts[0], parts[1]))

        if not cp_entries:
            updated_sentences.append(full_sent)
            continue

        # Store kriyAmUla & verbalizer mappings as lists
        kriyamula_map = {}
        verbalizer_map = {}

        for parts in line_list:
            if len(parts) >= 9:
                for cp_tag, cp_index in cp_entries:
                    if parts[8] == f"{cp_index}:kriyAmUla":
                        kriyamula_map.setdefault(cp_index, []).append(parts[1])
                    elif parts[8] == f"{cp_index}:verbalizer":
                        verbalizer_map.setdefault(cp_index, []).append(parts[1])

        # Build head_mod_map for each cp_index
        head_mod_map = {}
        for cp_tag, cp_index in cp_entries:
            kriya_idxs = kriyamula_map.get(cp_index, [])
            verb_idxs = verbalizer_map.get(cp_index, [])
            head = None
            mod = None

            for parts in line_list:
                if len(parts) >= 2:
                    if parts[1] in kriya_idxs:
                        store_cp_with_ids.setdefault(cp_index, []).append((sent_id, parts[0]))
                        head = parts[0].rsplit("_", 1)[0]
                    if parts[1] in verb_idxs:
                        mod = parts[0]

            if head and mod:
                head_mod_map[cp_index] = f"{head}+{mod}"

        # Update lines by replacing cp_index with head+mod
        updated_lines = []
        for parts in line_list:
            if len(parts) < 2:
                updated_lines.append(' '.join(parts))
                continue

            index = parts[1]

            # Skip kriyAmUla or verbalizer lines
            if any(index in lst for lst in kriyamula_map.values()) or \
               any(index in lst for lst in verbalizer_map.values()):
                continue

            for cp_tag, cp_index in cp_entries:
                if index == cp_index and cp_index in head_mod_map:
                    parts[0] = head_mod_map[cp_index]
                    break

            updated_lines.append(' '.join(parts))

        updated_sentences.append('\n'.join(updated_lines))
        print(store_cp_with_ids)

    return '\n'.join(updated_sentences), store_cp_with_ids

import re

import re

def is_tat(input_data):
    """Tatpurusha compound [N-tat_n]: collapse its modifier members + head into a
    single '+'-joined compound on the construction line (like is_nc but for many
    modifiers), then delete the member lines. Membership may be declared in either
    the dependency column (4) or the construction column (8). A modifier carrying
    the 'wawCIlAxi' morph (gnp col 3) is marked with a '~ing' suffix so it renders
    as a present participle ('jāne vālī' -> 'going') inside the compound."""
    sentences = re.findall(r'(<sent_id=.*?>\n.*?\n</sent_id>)', input_data, re.DOTALL)
    updated_sentences = []
    for sent in sentences:
        lines = sent.strip().split('\n')
        line_list = [line.strip().split() for line in lines if line.strip()]

        tat_entries = []
        for parts in line_list:
            if parts and re.fullmatch(r'\[\d+-tat_\d+\]', parts[0]) and len(parts) > 1:
                tat_entries.append((parts[0], parts[1]))
        if not tat_entries:
            updated_sentences.append(sent)
            continue

        for tag, tat_index in tat_entries:
            mods = []          # (word_index:int, concept) — noun modifiers only
            participles = []   # row-parts of wawCIlAxi participle members
            head_word = None
            member_idx_set = set()
            for parts in line_list:
                if len(parts) < 9:
                    continue
                dep, gnp, constr = parts[4], parts[3], parts[8]
                role = None
                if dep == f'{tat_index}:mod' or constr == f'{tat_index}:mod':
                    role = 'mod'
                elif dep == f'{tat_index}:head' or constr == f'{tat_index}:head':
                    role = 'head'
                if role == 'mod':
                    if 'wawCIlAxi' in gnp:
                        participles.append(parts)        # keep as separate verb
                    else:
                        mods.append((int(parts[1]), parts[0]))
                        member_idx_set.add(parts[1])
                elif role == 'head':
                    head_word = parts[0]
                    member_idx_set.add(parts[1])
            if not (head_word and (mods or participles)):
                continue
            mods.sort(key=lambda m: m[0])
            compound = '+'.join([w for _, w in mods] + [head_word])
            for parts in line_list:
                if len(parts) >= 2 and parts[1] == tat_index:
                    parts[0] = compound
            # redirect each wawCIlAxi participle to attach to the compound (the
            # [N-tat_n] index) as a present participle ('rvks' -> -ing form),
            # so it renders 'going' and groups with 'main railway line'.
            for p in participles:
                p[4] = f'{tat_index}:rvks'
                # rvks -> -ing; keep gnp 'wawCIlAxi' as a backstop for the form
            line_list = [p for p in line_list
                         if len(p) < 2 or p[1] not in member_idx_set]

        updated_lines = [' '.join(parts) for parts in line_list]
        updated_sentences.append('\n'.join(updated_lines))
    return '\n'.join(updated_sentences)


def is_nc(input_data):
    print("Input Data:\n", input_data)

    # Split by <sent_id> blocks
    sentences = re.findall(r'(<sent_id=.*?>\n.*?\n</sent_id>)', input_data, re.DOTALL)
    updated_sentences = []

    for sent in sentences:
        lines = sent.strip().split('\n')
        line_list = [line.strip().split() for line in lines if line.strip()]

        # Step 1: Find all [nc_*] tags and their indices
        nc_entries = []
        for parts in line_list:
            if parts and re.fullmatch(r'\[nc_\d+\]', parts[0]) and len(parts) > 1:
                nc_entries.append((parts[0], parts[1]))  # (tag, index)

        # Sort nc_entries by numeric part (strip trailing ']')
        nc_entries.sort(key=lambda x: int(x[0].split('_')[1].rstrip(']')))

        # If no [nc_*] tag, keep sentence unchanged
        if not nc_entries:
            updated_sentences.append(sent)
            continue

        # Step 2: Process each nc in order
        for tag, nc_index in nc_entries:
            mod_word = head_word = None
            mod_index = head_index = None

            # Map mod and head indices
            for parts in line_list:
                if len(parts) >= 9:
                    if parts[8] == f'{nc_index}:mod':
                        mod_index = parts[1]
                    elif parts[8] == f'{nc_index}:head':
                        head_index = parts[1]

            # Get words for mod and head
            for parts in line_list:
                if len(parts) >= 2:
                    if mod_index and parts[1] == mod_index:
                        mod_word = parts[0]
                    if head_index and parts[1] == head_index:
                        head_word = parts[0]

            # Replace [nc_*] with modifier+head.
            # English noun compounds are MODIFIER + HEAD ("railway station",
            # "mountain range"). handle_compound_nouns() treats the LAST '+'
            # component as the NC_head, so the head must be placed last here.
            if head_word and mod_word:
                for parts in line_list:
                    if len(parts) >= 2 and parts[1] == nc_index:
                        parts[0] = mod_word + '+' + head_word

            # Remove mod/head lines
            line_list = [parts for parts in line_list if len(parts) < 2 or parts[1] not in {mod_index, head_index}]

        # Rebuild lines
        updated_lines = [' '.join(parts) for parts in line_list]
        updated_sentences.append('\n'.join(updated_lines))

    return '\n'.join(updated_sentences)



import re

def merge_ne_lines_ignoring_dash(word_line, ne_line):
    """
    Merge word_line (with :begin/:inside) and [ne_x] line according to rules:
    - If both values exist and not '-', merge with '/'
    - If only one exists (not '-'), use it
    - If both are '-', keep '-'
    - Special handling for index 0 (word), 1 (index), and 8 (final tag)
    """
    merged = []
    for i in range(len(ne_line)):
        if i == 0:
            merged.append(word_line[0])  # use word from :begin line
        elif i == 1:
            merged.append(ne_line[1])  # keep index from [ne_x]
        elif i == 8:
            merged.append(ne_line[8])  # use final tag from [ne_x]
        else:
            val1 = word_line[i] if i < len(word_line) else "-"
            val2 = ne_line[i] if i < len(ne_line) else "-"
            if val1 == '-' and val2 == '-':
                merged.append('-')
            elif val1 != '-' and val2 != '-' and val1 != val2:
                merged.append(f"{val1}/{val2}")
            else:
                merged.append(val1 if val1 != '-' else val2)
    return merged


def is_ne(input_data):
    print("Input Data:\n", input_data)

    sentences = re.findall(r'(<sent_id=.*?>\n.*?\n</sent_id>)', input_data, re.DOTALL)
    updated_sentences = []

    for sent in sentences:
        lines = sent.strip().split('\n')

        header = lines[0]
        comment = lines[1] if lines[1].startswith("#") else ""
        content_lines = lines[2:-2] if comment else lines[1:-2]
        footer = lines[-2:]

        line_list = [line.strip().split() for line in content_lines if line.strip()]
        updated_lines = []

        # Step 1: Extract NE tags like [ne_1]
        ne_entries = [(parts[0], parts[1]) for parts in line_list if len(parts) >= 2 and re.fullmatch(r'\[ne_\d+\]', parts[0])]

        if not ne_entries:
            updated_sentences.append(sent)
            continue

        for tag, ne_index in ne_entries:
            ne_words = []
            word_line = None
            ne_tag_line = None

            for parts in line_list:
                if len(parts) >= 9 and parts[8] == f"{ne_index}:begin":
                    word_line = parts
                    ne_words.append(parts[0])
                elif len(parts) >= 9 and parts[8] == f"{ne_index}:inside":
                    ne_words.append(parts[0])
                elif parts[0] == tag and parts[1] == ne_index:
                    ne_tag_line = parts

            if not ne_words or not ne_tag_line or not word_line:
                continue  # Skip malformed NE

            merged_word = '+'.join(ne_words)
            word_line[0] = merged_word

            # Merge both lines
            merged_parts = merge_ne_lines_ignoring_dash(word_line, ne_tag_line)
            updated_lines.append((int(merged_parts[1]), ' '.join(merged_parts)))

        # Remove NE parts from line_list
        filtered_lines = []
        for parts in line_list:
            # A normal concept line has a numeric index in column 2. Anything
            # else (a stray %type token, a blank/malformed line, a line missing
            # its index) is kept verbatim at the end instead of crashing the run.
            if len(parts) < 2 or not parts[1].lstrip('-').isdigit():
                filtered_lines.append((10**9, ' '.join(parts)))
                continue
            if len(parts) >= 9 and (parts[8].endswith(":begin") or parts[8].endswith(":inside")):
                continue
            if parts[0].startswith("[ne_") and parts[1] in [i[1] for i in ne_entries]:
                continue
            filtered_lines.append((int(parts[1]), ' '.join(parts)))

        # Combine remaining lines with the new NE lines, sort by index
        combined = filtered_lines + updated_lines
        combined.sort(key=lambda x: x[0])  # sort by index

        # Rebuild the sentence
        sentence_text = '\n'.join([header] + ([comment] if comment else []) + [line for _, line in combined] + footer)
        updated_sentences.append(sentence_text)

    return '\n'.join(updated_sentences)


import re

def clean_concept(concept):
    """Removes numeric or grammatical suffixes from concepts like dAla_1, dAla_nf"""
    return re.sub(r"(_[0-9]+|_n[mf]|_v[mti])$", "", concept)


def load_fallback_dict(fallback_file):
    fallback_dict = {}
    try:
        with open(fallback_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 3:
                    hindi_word = parts[0].strip()
                    english_meaning = parts[2].strip().replace(" ", "_")  # ✅ Replace spaces with underscores
                    if hindi_word and english_meaning:
                        fallback_dict[hindi_word] = english_meaning
    except FileNotFoundError:
        print(f"Warning: Fallback dictionary '{fallback_file}' not found.")
    return fallback_dict



import re
import csv

import re
import csv

def process_input(input_text, store_cp_with_id, lang="eng",
                  concept_file="dictionaries/concept-to-mrs-rels.dat",
                  days_file="dictionaries/days.dat",
                  months_file="dictionaries/months.dat"):
    """
    Processes input text, replacing concepts using the dictionary,
    handling compounds and hyphenated words, checking days/months,
    and applying universal fallback from store_cp_with_id with recursive re-check.
    """

    def load_dict(file_path, key_col=0, val_col=1):
        d = {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for row in f:
                    cols = row.strip().split()
                    if len(cols) > max(key_col, val_col):
                        d[cols[key_col]] = cols[val_col]
        except FileNotFoundError:
            print(f"⚠️ Warning: File '{file_path}' not found.")
        return d

    # Load dictionaries
    column_to_check = 2 if lang == "skt" else 1
    concept_dict = load_dict(concept_file, key_col=column_to_check, val_col=3)
    months_dict = load_dict(months_file, key_col=0, val_col=2)
    days_dict = load_dict(days_file, key_col=0, val_col=2)

    print(f"✅ Loaded {len(concept_dict)} concept entries.")
    print(f"✅ Loaded {len(days_dict)} day entries.")
    print(f"✅ Loaded {len(months_dict)} month entries.")

    # Fallback function for unmatched words
    # Words that should NOT use fallback - they have default meanings
    SKIP_FALLBACK_WORDS = {
        'a_1', 'a_2', 'eka_1', 'eka_2', 'eka_3',  # quantifiers meaning 'a/one'
        'kI_1', 'kA_1', 'ke_1',  # postpositions
        'yaha_1', 'vaha_1',  # demonstratives
    }

    def apply_fallback(word, current_sent_id, store_cp_with_id):
        # Skip fallback for known quantifier/function words
        if word in SKIP_FALLBACK_WORDS:
            return word
        base_word = word.split('-')[0]
        for sent_key, fb_list in store_cp_with_id.items():
            for fb_id, fb_value in fb_list:
                if fb_id == current_sent_id:
                    fb_base = fb_value.split('_')[0].split('-')[0]
                    # Use exact base match, not substring match
                    if base_word == fb_base or word == fb_value:
                        print(f"🔁 Fallback match: {word} → {fb_value}")
                        return fb_value
        return word
    
    def replace_with_fallback(word, current_sent_id):
        # 0️⃣ Skip if word is purely a number
        if word.isdigit():
            return word

        visited = set()   # prevent flip-flop loops

        while True:
            if word in visited:
                break     # stop if looping
            visited.add(word)

            prev_word = word

            # 1️⃣ Direct concept dictionary
            if word in concept_dict:
                word = concept_dict[word]

            # 2️⃣ Hyphenated token (try full first, then base)
            elif '-' in word:
                parts = word.split('-')
                base = parts[0]
                suffix = '-'.join(parts[1:])

                # try full token first
                if word in concept_dict:
                    word = concept_dict[word]

                # else try base
                elif base in concept_dict:
                    word = concept_dict[base] + '-' + suffix

            # 3️⃣ Fallback on full word
            word_after_fb = apply_fallback(word, current_sent_id, store_cp_with_id)
            if word_after_fb != word:
                word = word_after_fb
                continue

            # 4️⃣ Fallback on hyphen base
            if '-' in word:
                parts = word.split('-')
                base = parts[0]
                suffix = '-'.join(parts[1:])

                fb_base = apply_fallback(base, current_sent_id, store_cp_with_id)
                if fb_base != base:
                    word = fb_base + '-' + suffix
                    continue

            # 5️⃣ Compound with '+'
            if '+' in word:
                parts = word.split('+')
                new_parts = []
                for part in parts:
                    new_parts.append(replace_with_fallback(part, current_sent_id))
                word = '+'.join(new_parts)
                continue

            # no further change
            break

        return word



    lines = input_text.split("\n")
    updated_lines = []
    current_sent_id = None

    for line in lines:
        if line.startswith("<sent_id="):
            current_sent_id = line.strip().split("=")[-1].rstrip(">")
            updated_lines.append(line)
            continue

        words = line.split()
        if not words or words[0].startswith(("<", "#", "%")):
            updated_lines.append(line)
            continue

        # Replace first word with recursive fallback + concept check
        original_word = words[0]

        # Apply replacement
        replaced_word = replace_with_fallback(original_word, current_sent_id)

        # If still not replaced, check days/months
        if replaced_word == original_word:
            if original_word in days_dict:
                replaced_word = days_dict[original_word]
            elif original_word in months_dict:
                replaced_word = months_dict[original_word]

        words[0] = replaced_word

        # Main verb TAM update (if applicable)
        valid_suffixes = ['main', 'rcloc','rcelab','rcdelim']
        if len(words) > 4 and ':' in words[4] and words[4].split(':')[-1] in valid_suffixes:
            main_verb_tam = words[0]
            base_word = main_verb_tam.split("-")[0]
            tam_term = identify_tam_terms(main_verb_tam)  # ensure this function exists
            if tam_term is not None:
                print(f"🔧 Updating TAM: {main_verb_tam} → {base_word}-{tam_term}")
                words[0] = base_word + '-' + tam_term

        updated_lines.append(" ".join(words))

        # Optional CSV logging
        with open("processed_output.csv", "a", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([" ".join(words)])

    return "\n".join(updated_lines)
