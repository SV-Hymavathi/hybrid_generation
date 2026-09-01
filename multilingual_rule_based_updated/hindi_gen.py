import sys
import json
import os

# ─────────────────────────────────────────────────────────────────────────────
# Quiet mode: route ALL diagnostic / debug output to debug_hi_en.txt so the
# screen shows only the generated sentences. Everything the engine prints
# (including import-time chatter) is captured in the debug file, in order.
# Real stdout is restored at the end of __main__ to print the clean result.
# ─────────────────────────────────────────────────────────────────────────────
_REAL_STDOUT = sys.stdout
_DEBUG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_hi_en.txt')
try:
    _DEBUG_FH = open(_DEBUG_PATH, 'w', encoding='utf-8')
    sys.stdout = _DEBUG_FH
except Exception:
    _DEBUG_FH = None

# Message shown for a sentence whose main-verb TAM (tense/aspect/mood) could not
# be resolved -- such a sentence cannot be generated reliably, so we skip it.
TAM_ERROR_MSG = "since TAM is incorrect the system unable to process the output"


def _step(n, title):
    """Write an ordered step banner into the debug file."""
    print("\n===== STEP %s: %s =====" % (n, title))


def _segment_tam_broken(segment_text):
    """True if the segment's main verb has an unresolved TAM placeholder
    (concept ends in '-TAM'), which makes the sentence ungenerable."""
    for line in segment_text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', '%', '<')):
            continue
        parts = line.split()
        if not parts:
            continue
        concept = parts[0]
        # the broken concept looks like 'get_1-TAM' (TAM literally unresolved)
        if concept.endswith('-TAM') or '-TAM ' in line:
            return True
    return False


from repository.common_v4 import *
from repository.USR_to_JSON import USR_to_json
from repository.coref_discourse import *
from repository.constant import *
from map_concept import process_input,is_cp,is_nc,is_ne,is_tat
from repository.construction import *
from repository.reorder import rearrange_tuples,arrange_by_index_order
from repository.morph_gen import en_generate_morph,hi_generate_morph
from repository.preprocessing import process_segment,preprocess_id
from repository.identify_cat import identify_cat
from repository.process_cat import process_all_cat,process_change
import repository.process_cat as _pcat

# segment_id -> reason, for sentences where only the verb failed to generate.
VERB_FAIL_SEGMENTS = {}
# segment_id -> "stage: reason", for a non-fatal stage crash (construction,
# unprocessed-handling, etc.). The sentence still emits whatever chunks were
# built before the crash, plus a marker saying where it stopped and why.
SEGMENT_STAGE_ERRORS = {}
from repository.Check_words_in_dict import check_words_in_dict,identify_words_in_corpus, transform_data_star
from ppgenscript import checking_interrogative_words
try:
    from groq import Groq
except Exception:
    Groq = None  # Optional: only needed for the LLM [mask] filler
import argparse


def extract_ne_words_from_raw_usr(input_data):
    ne_words = {}  # cleaned_word -> original_word
    for line in input_data.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith(('#', '%', '<')):
            continue
        parts = line.split()
        if len(parts) >= 9:
            last_col = parts[-1]
            if 'begin' in last_col or 'inside' in last_col:
                word = parts[0]
                original = word  # keep @ke.ke. as original
                word = word.replace('dZ', 'd').replace('jZ', 'j').replace('DZ', 'D')
                word = word.split('_')[0]  # @ke.ke.
                # NOW strip @ and dots to get the chunk-level key
                cleaned_key = word.lstrip('@').replace('.', '')  # keke
                ne_words[cleaned_key] = original  # {'keke': '@ke.ke.'}
                print(f"[DEBUG extract_ne] Found NE word: cleaned_key={cleaned_key}, original={original}")
    return ne_words


def process_file_data(input_data, segment_id, eka_head_index, lang):
    global HAS_CONSTRUCTION_DATA, HAS_SPKVIEW_DATA, HAS_MORPHO_SEMANTIC_DATA, HAS_DISCOURSE_DATA, HAS_COREF
    global flag_conj, flag_disjunct, flag_span, flag_cp, flag_meas, flag_rate, flag_spatial, flag_waw, flag_cal, flag_xvanxva, flag_temporal_spatial, k1_not_need, has_changes, global_starred_words

    try:
        reset_global_dicts()
        rules_info = generate_rulesinfo(input_data)

        src_sentence = rules_info[0]
        root_words = rules_info[1]
        index_data = [int(x) for x in rules_info[2]]
        seman_data = rules_info[3]
        gnp_data = rules_info[4]
        depend_data = rules_info[5]
        discourse_data = rules_info[6]
        spkview_data = rules_info[7]
        scope_data = rules_info[8]
        construction_data = rules_info[9]
        sentence_type = rules_info[10]

        if sentence_type[1:] in pass_list:
            k1_not_need = True

        check_main_verb(depend_data)

        depend_data, spkview_data, HAS_CONSTRUCTION_DATA, flags = identify_and_assign_dep(
            root_words, construction_data, depend_data, index_data, spkview_data)

        words_info = generate_wordinfo(
            root_words, index_data, seman_data,
            gnp_data, depend_data, discourse_data,
            spkview_data, scope_data, construction_data)

        categorized_words_list = identify_cat(words_info, sentence_type, lang)

        # A main verb (0:main) whose TAM/lemma can't be resolved as a verb gets
        # mis-categorized as a NOUN and would surface as a garbage chunk
        # (e.g. 'guardWA'). Detect that, drop it from the noun list so it produces
        # no chunk, and flag the sentence so a [tam incorrect] marker is added.
        # Properly-recognized predicates (verbs, conjunct verbs, copulas) land in
        # the VERB category and are left untouched.
        _main_tam_broken = False
        _nouns_cat = categorized_words_list[3]
        if any(len(w) > 4 and w[4] == '0:main' for w in _nouns_cat):
            _main_tam_broken = True
            categorized_words_list[3] = [w for w in _nouns_cat
                                         if not (len(w) > 4 and w[4] == '0:main')]
            log('main verb mis-categorized (unresolved); dropping it, marking [tam incorrect]', 'WARNING')


        if spkview_data != [] or len(spkview_data) > 0:
            HAS_SPKVIEW_DATA = populate_spkview_dict(
                root_words,
                spkview_data, discourse_data, index_data, lang,
                gnp_data, construction_data, words_info,
                categorized_words_list[5],
                categorized_words_list[3],
                depend_data, eka_head_index
            )

        if any(discourse_data):
            HAS_DISCOURSE_DATA = True
        if any('coref' in item for item in discourse_data):
            HAS_COREF = True

        main_verb_tam = None
        for info in words_info:
            if info[4] == '0:main':
                main_verb_tam = info[1]

        if main_verb_tam and '-' in main_verb_tam:
            tam_term = main_verb_tam.split("-")[1]
        else:
            tam_term = None

        processed_foreign_words, processed_indeclinables, processed_nouns, processed_pronouns, processed_others, process_nominal_form, processed_verbs, processed_auxverbs, processed_adjectives, processed_words, verb_dict, nonfinite_dict = process_all_cat(
            categorized_words_list, index_data, gnp_data, seman_data, depend_data,
            spkview_data, sentence_type, words_info, k1_not_need, has_changes, lang)
        verb_dict_from_process_all_cat = verb_dict

        processed_words = arrange_by_index_order(processed_words)

        if HAS_CONSTRUCTION_DATA:
            try:
                processed_words, flags = process_construction(
                    processed_words, root_words, construction_data,
                    depend_data, gnp_data, index_data, flags, lang=lang)
            except Exception as _ce:
                _reason = (str(_ce).splitlines()[-1][:120]
                           if str(_ce).strip() else type(_ce).__name__)
                SEGMENT_STAGE_ERRORS[segment_id] = 'construction (%s: %s)' % (
                    type(_ce).__name__, _reason)
                log('process_construction failed for %s (%s); keeping '
                    'pre-construction chunks and continuing'
                    % (segment_id, _reason), 'WARNING')

        language_config = {
            'en': {
                'func': en_generate_morph,
                'args': ['processed_words', 'tam_term', 'depend_data', 'sentence_type', 'index_data']
            },
            'hi': {
                'func': hi_generate_morph,
                'args': ['processed_words']
            }
        }

        context = {
            'processed_words': processed_words,
            'tam_term': tam_term,
            'depend_data': depend_data,
            'sentence_type': sentence_type,
            'index_data': index_data,
            'lang': lang
        }

        handler = language_config[lang]['func']
        arg_names = language_config[lang]['args']
        call_args = [context[arg] for arg in arg_names]

        # Initialize all dictionaries
        interrogative_dict = {}
        foreign_words_dict = {}
        calendar_dict = {}
        indec_dict = {}
        verb_dict = {}
        nonfinite_dict = {}
        morph_mapping = {}
        rad_dict = {}

        try:
            result = handler(*call_args)
            # Handle both old (just outputData) and new (tuple) returns
            if isinstance(result, tuple):
                if len(result) == 9:
                    outputData, interrogative_dict, foreign_words_dict, calendar_dict, indec_dict, verb_dict, nonfinite_dict, morph_mapping, rad_dict = result
                elif len(result) == 8:
                    outputData, interrogative_dict, foreign_words_dict, calendar_dict, indec_dict, nonfinite_dict, morph_mapping, rad_dict = result
                    verb_dict = {}
                elif len(result) == 7:
                    outputData, interrogative_dict, foreign_words_dict, calendar_dict, indec_dict, morph_mapping, rad_dict = result
                    verb_dict = {}
                    nonfinite_dict = {}
                else:
                    outputData = result[0] if result else []
            else:
                outputData = result
        except Exception as e:
            
            import traceback
            log(f"Handler error: {e}", "ERROR")
            print("HANDLER_TRACEBACK:", traceback.format_exc(), flush=True)
            outputData = []
        verb_dict.update(verb_dict_from_process_all_cat)

        try:
            has_changes, processed_nouns = handle_unprocessed(
                index_data, depend_data, outputData, processed_nouns, construction_data)
        except Exception as _he:
            _reason = (str(_he).splitlines()[-1][:120]
                       if str(_he).strip() else type(_he).__name__)
            SEGMENT_STAGE_ERRORS.setdefault(
                segment_id, 'unprocessed-handling (%s: %s)' % (
                    type(_he).__name__, _reason))
            log('handle_unprocessed failed for %s (%s); skipping reprocess '
                'and continuing' % (segment_id, _reason), 'WARNING')
            has_changes = False

        if has_changes:
            processed_words, verb_dict, nonfinite_dict = process_change(
                rules_info,
                categorized_words_list,
                words_info,
                processed_nouns,
                processed_pronouns,
                processed_others,
                processed_foreign_words,
                processed_indeclinables,
                k1_not_need,
                lang
            )

            result = handler(*call_args)
            if isinstance(result, tuple):
                outputData = result[0]
            else:
                outputData = result
                
            if isinstance(outputData, str):
                outputData = ' '.join([
                    w[1:] if w.startswith('#') and w[1:].isdigit() else w
                    for w in outputData.split()
                ])

        outputData, global_starred_words, has_star = check_words_in_dict(
            outputData, processed_words, global_starred_words)

        processed_words_after_star = analyse_output_data(outputData, processed_words, morph_mapping)

        if has_star:
            if lang == "hi":
                outputData, response_data, replaced_indices = identify_words_in_corpus(
                    global_starred_words, outputData, lang)
                processed_words_after_star = analyse_output_data(outputData, processed_words, morph_mapping)
                result = handler(*call_args)
                if isinstance(result, tuple):
                    outputData = result[0]
                else:
                    outputData = result
                outputData = transform_data_star(response_data, replaced_indices, outputData)

        transformed_data = analyse_output_data(outputData, processed_words, morph_mapping)
        PP_fulldata = transformed_data

        if HAS_SPKVIEW_DATA:
            log(f'spkview: {spkview_dict}')
            PP_fulldata = add_spkview(transformed_data, spkview_dict)

        log(f'postpositions: {processed_postpositions_dict}')
        PP_fulldata = add_postposition(PP_fulldata, index_data, depend_data, processed_postpositions_dict)

        if HAS_CONSTRUCTION_DATA:
            log(f'construct: {construction_dict}')
            PP_fulldata = add_construction(PP_fulldata, construction_dict)

        HAS_MORPHO_SEMANTIC_DATA, PP_fulldata = populate_morpho_semantic_dict(
            index_data, gnp_data, PP_fulldata, words_info, lang)

        if HAS_MORPHO_SEMANTIC_DATA:
            log(f'MORPHO SEMANTIC: {MORPHO_SEMANTIC_DICT}')
            PP_fulldata = add_MORPHO_SEMANTIC(PP_fulldata, MORPHO_SEMANTIC_DICT)

        PP_fulldata_dict_with_id = {segment_id: PP_fulldata}

        # If the verb failed anywhere during processing (initial pass or reprocess),
        # remember it so the caller marks the chunk while keeping the other chunks.
        if _main_tam_broken:
            VERB_FAIL_SEGMENTS[segment_id] = 'tam incorrect'
        elif getattr(_pcat, 'LAST_VERB_FAILED', False):
            VERB_FAIL_SEGMENTS[segment_id] = getattr(_pcat, 'LAST_VERB_FAIL_REASON', '') or 'verb could not be generated'

        log(f'PP_fulldata_dict_with_id: {PP_fulldata_dict_with_id}')
        return PP_fulldata_dict_with_id, interrogative_dict, foreign_words_dict, calendar_dict, indec_dict, verb_dict, nonfinite_dict, morph_mapping, rad_dict
    
    except Exception as e:
        import traceback
        log(f'ERROR_2:{e}', 'ERROR')
        log("FULL_TRACEBACK: " + traceback.format_exc(), 'ERROR')
        # Do NOT inject an error string into the data flow: it can carry a None
        # key and get double-wrapped downstream ("None: ERROR: ERROR: ..."). Return
        # empty so the caller surfaces a single clean line for this sentence.
        return {}, {}, {}, {}, {}, {}, {}, {}, {}

def build_span_map(input_text):
    """
    Parse raw USR to build span map:
    {segment_id: {span_index: {'start': [], 'end': [], 'unit': []}}}
    """
    span_map = {}
    current_seg_id = None
    for line in input_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('<sent_id=') or line.startswith('<segment_id='):
            current_seg_id = line.split('=')[1].rstrip('>')
            span_map[current_seg_id] = {}
            continue
        if line.startswith(('#', '%', '</')):
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        token_index = parts[1]       # e.g. '6'
        construction_col = parts[8]  # e.g. '10:start'
        if ':' in construction_col:
            ref, rel = construction_col.split(':', 1)
            if rel in ('start', 'end', 'unit') and current_seg_id:
                if ref not in span_map[current_seg_id]:
                    span_map[current_seg_id][ref] = {'start': [], 'end': [], 'unit': []}
                span_map[current_seg_id][ref][rel].append(token_index)
                print(f"[DEBUG span_map] {current_seg_id} span:{ref} {rel}={token_index}")
    return span_map

def hindi_generation(input_text, eka_head_index, lang, ne_words_global=None):
    """
    Process input text, extracting sentences, segment IDs, and generating structured output.
    """
    PP_fulldata_dict_with_ids = {}
    interrogative_dict_all = {}
    foreign_words_dict_all = {}
    calendar_dict_all = {}
    indec_dict_all = {}
    verb_dict_all = {}
    rad_dict_all = {}
    nonfinite_dict_all = {}
    morph_mapping_all = {}
    
    span_map = build_span_map(input_text)
    print(f"[DEBUG] span_map built: {span_map}")
    _step(1, "read USR and convert concepts to English / build JSON")
    input_text = preprocess_id(input_text)
    segments = parse_segments(input_text)

    sentences, all_output, segment_ids = [], [], []
    parser = USR_to_json(input_text)
    parser.parse_input_text()
    try:
        construction_json = generate_construction_json(parser.parse_input_text())
    except Exception as e:
        log(f'construction json failed: {e}', 'WARN'); construction_json = {}
    try:
        coref_json, coref_dict, sentence_type_dict = process_coreferences(parser.parse_input_text())
    except Exception as e:
        log(f'coreference parse failed: {e}', 'WARN'); coref_json, coref_dict, sentence_type_dict = {}, {}, {}
    try:
        disource_json = transform_data(parser.parse_input_text())
    except Exception as e:
        log(f'discourse parse failed: {e}', 'WARN'); disource_json = {}

    with open('coreferences.json', 'w', encoding='utf-8') as f:
        json.dump(coref_json, f, ensure_ascii=False, indent=2)
    with open('construction.json', 'w', encoding='utf-8') as f:
        json.dump(construction_json, f, ensure_ascii=False, indent=2)
    with open("discource.json", "w") as file:
        json.dump(disource_json, file, indent=4)
    with open("output.json", "w") as file:
        json.dump(parser.parse_input_text(), file, indent=4)

    tam_broken_ids = []
    sentence_errors = {}          # sid -> error message, for sentences that fail
    VERB_FAIL_SEGMENTS.clear()
    SEGMENT_STAGE_ERRORS.clear()
    _step(2, "per sentence: identify categories, resolve verbs/TAM, morphology")
    for segment in segments:
        # Recover this segment's id up front so a crash can be attributed to it.
        _m = re.search(r'sent_id=([^\s>]+)', segment)
        _sid_guess = _m.group(1) if _m else None
        try:
            segment_id, sentence, output = process_segment(segment)
        except Exception as e:
            sid = _sid_guess or 'unknown'
            msg = str(e).splitlines()[-1][:160] if str(e).strip() else type(e).__name__
            print(f'[ERROR_segment] {sid}: {msg}')
            sentence_errors[sid] = msg
            if sid:
                segment_ids.append(sid)
            continue
        if segment_id:
            segment_ids.append(segment_id)
        # Skip sentences whose main-verb TAM did not resolve: they cannot be
        # generated correctly, so we emit a clear message instead of garbage.
        if segment_id and _segment_tam_broken(segment):
            # Main-verb TAM did not resolve. Don't skip the whole sentence any
            # more -- process it so every other chunk is still produced; the verb
            # chunk is dropped and replaced with a [tam incorrect] marker later.
            print("[TAM] %s: main-verb TAM unresolved; keeping other chunks" % segment_id)
            tam_broken_ids.append(segment_id)
        if output:
            try:
                output1, interrogative_dict, foreign_words_dict, calendar_dict, indec_dict, verb_dict, nonfinite_dict, morph_mapping, rad_dict = process_file_data(
                    output, segment_id, eka_head_index, lang)
                interrogative_dict_all[segment_id] = interrogative_dict
                foreign_words_dict_all[segment_id] = foreign_words_dict
                calendar_dict_all[segment_id] = calendar_dict
                indec_dict_all[segment_id] = indec_dict
                verb_dict_all[segment_id] = verb_dict
                nonfinite_dict_all[segment_id] = nonfinite_dict
                rad_dict_all[segment_id] = rad_dict
                morph_mapping_all[segment_id] = morph_mapping
                PP_fulldata_dict_with_ids.update(output1)
            except Exception as e:
                msg = str(e).splitlines()[-1][:160] if str(e).strip() else type(e).__name__
                print(f'[ERROR_3]: {segment_id}: {msg}')
                sentence_errors[segment_id] = msg

    # Coreference processing
    _step(3, "coreference and discourse linking")
    try:
        PP_fulldata_dict_with_ids = update_morph_dict_coref(coref_json, PP_fulldata_dict_with_ids)
    except Exception as e:
        log(f'coref linking skipped: {e}', 'WARN')
    try:
        filtered_data = filter_and_concat_data(PP_fulldata_dict_with_ids, sentence_type_dict)
    except Exception as e:
        log(f'filter_and_concat_data failed: {e}', 'WARN')
        filtered_data = {}

    # Enrich data using the accumulated dictionaries. Each enrichment is wrapped
    # so that a single malformed sentence cannot abort enrichment for the batch.
    def _enrich(fn, acc):
        nonlocal filtered_data, PP_fulldata_dict_with_ids
        if not acc:
            return
        try:
            filtered_data, PP_fulldata_dict_with_ids = fn(
                filtered_data, acc, PP_fulldata_dict_with_ids)
        except Exception as e:
            log(f'{getattr(fn, "__name__", "enrich")} skipped: {e}', 'WARN')

    if lang == "en":
        _enrich(add_interrogative_dict, interrogative_dict_all)
        _enrich(add_foreign_words_dict, foreign_words_dict_all)
        _enrich(add_calendar_dict, calendar_dict_all)
        _enrich(add_indec_dict, indec_dict_all)
        _enrich(add_verb_dict, verb_dict_all)
        _enrich(add_nonfinite_dict, nonfinite_dict_all)
        _enrich(add_rad_dict, rad_dict_all)

    with open('generated_data.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=4)

    try:
        filtered_data = update_discourse_sentences(disource_json, filtered_data)
    except Exception as e:
        log(f'update_discourse_sentences skipped: {e}', 'WARN')
    for key, sentence_list in list(filtered_data.items()):
        try:
            filtered_data[key] = [sentence.replace('+', ' ') for sentence in sentence_list]
        except Exception as e:
            log(f'+ cleanup skipped for {key}: {e}', 'WARN')

    print("filtered_data", filtered_data)
    sentences = [sentence for sentence_list in filtered_data.values() for sentence in sentence_list]

    # Filter PP_fulldata_dict_with_ids to remove construction_list tokens
    filtered_PP_fulldata_dict_with_ids = {}
    for key, token_list in PP_fulldata_dict_with_ids.items():
        if not isinstance(token_list, list):
            continue
        if not token_list or not isinstance(token_list[0], tuple):
            continue
        filtered_tokens = [
            token for token in token_list
            if isinstance(token, tuple) and len(token) > 1 and token[1] not in ['#nc', "#cp", "nc", "cp", "#waw", "waw"]
        ]
        filtered_PP_fulldata_dict_with_ids[key] = filtered_tokens

    # Apply chinking to all sentences
    _step(4, "assemble words into ordered chunks")
    chunked_data = {}
    for key, value in list(filtered_data.items()):
        try:
            if isinstance(value, str):
                value = [value]
            elif isinstance(value, set):
                value = list(value)

            if value and key in PP_fulldata_dict_with_ids:
                sentence = value[0]
                chunked_data[key] = [add_chinking(sentence, PP_fulldata_dict_with_ids, key, sentence_type_dict.get(key, ''), span_map.get(key, {}), ne_words_global or set(), lang=lang)]
        except Exception as e:
            msg = str(e).splitlines()[-1][:160] if str(e).strip() else type(e).__name__
            log(f'chunk assembly failed for {key}: {msg}', 'WARN')
            sentence_errors[key] = msg
    print("chunked_data =", chunked_data)
        
    # WX to Roman conversion
    # ── USR-tag-driven subject-number map (for verb agreement) ──────────────
    # A sentence's main-verb subject is plural if its k1 carries the 'pl'
    # morpho-semantic tag, or the k1 filler is a conjunction construction.
    def _build_plural_map():
        import re as _re
        pmap = {}
        try:
            blocks = _re.findall(r'<sent_id=.*?</sent_id>',
                                 open('gen_input.txt', encoding='utf-8').read(), _re.S)
        except Exception:
            return pmap
        for b in blocks:
            sid = _re.search(r'sent_id=([^\s>]+)', b)
            if not sid:
                continue
            sid = sid.group(1)
            rows = []
            for ln in b.splitlines():
                s = ln.strip()
                if not s or s.startswith('#') or s.startswith('<') or s.startswith('%'):
                    continue
                c = s.split()
                if len(c) < 2 or not c[1].isdigit():
                    continue
                rows.append(c)
            by_idx = {c[1]: c for c in rows}
            mv = next((c[1] for c in rows if len(c) > 4 and c[4] == '0:main'), None)
            if not mv:
                continue
            k1 = next((c for c in rows if len(c) > 4 and c[4] == '%s:k1' % mv), None)
            plural = False
            if k1:
                morph = k1[3] if len(k1) > 3 else '-'
                if morph == 'pl':
                    # Check if k1 noun has a universal quantifier (every/each/hara)
                    # Universal quantifiers force singular verb in English.
                    k1_idx = k1[1]
                    has_universal_quant = any(
                        c[0].startswith('hara') and len(c) > 4 and c[4] == '%s:quant' % k1_idx
                        for c in rows
                    )
                    if not has_universal_quant:
                        plural = True
                if k1[0].startswith('[conj') or k1[0].startswith('[disjunct'):
                    # Conjoined subjects: plural only if the operand nouns themselves
                    # have pl marking. If all operands are singular, keep singular.
                    conj_idx = k1[1]
                    operand_rows = [
                        c for c in rows
                        if len(c) > 8 and (
                            c[8].endswith(':op1') or c[8].endswith(':op2') or c[8].endswith(':op3')
                        ) and c[8].split(':')[0] == conj_idx
                    ]
                    if operand_rows:
                        # Check if any operand has pl in gnp field (col 3)
                        any_pl = any(c[3] == 'pl' for c in operand_rows)
                        plural = any_pl
                    else:
                        plural = True  # fallback: conj with no traceable operands
            pmap[sid] = plural
        return pmap
    plural_map = _build_plural_map()

    def _fix_agreement(ch, is_plural):
        if not is_plural:
            return ch
        # flip singular copula/aux to plural inside this sentence's chunks
        ch = re.sub(r'\bis\b', 'are', ch)
        ch = re.sub(r'\bwas\b', 'were', ch)
        ch = re.sub(r'\bhas\b', 'have', ch)
        return ch

    def _convert_one(key, chunks):
        updated_chunks = []
        ne_words = ne_words_global if ne_words_global else {}

        for chunk in chunks:
            parts = chunk.split('[')
            processed = []

            for i, part in enumerate(parts):
                if i == 0:
                    processed.append(part)
                    continue

                if ']' in part:
                    content, rest = part.split(']', 1)
                    words = content.split()
                    new_words = []

                    for word in words:
                        trailing_punct = ''
                        word_for_check = word
                        if word and word[-1] in '.,;:!?':
                            trailing_punct = word[-1]
                            word_for_check = word[:-1]

                        if word.startswith('#') or word.startswith('^'):
                            base_word = word[1:]
                            if '_(respect)' in base_word:
                                base = base_word.split('_(respect)')[0]
                                converted = wx_to_english(base.split('_')[0])
                                new_words.append(converted + '_(respect)')
                            else:
                                new_words.append(wx_to_english(base_word.split('_')[0]))

                        elif (word_for_check in ne_words or
                            word_for_check.split('_')[0] in ne_words or
                            any(word_for_check.lower() == ne.lower() for ne in ne_words) or
                            any(word_for_check.split('_')[0].lower() == ne.lower() for ne in ne_words)):
                            if '_(respect)' in word_for_check:
                                base = word_for_check.split('_(respect)')[0]
                                original = ne_words.get(base.split('_')[0], base.split('_')[0])
                                if original.startswith('@'):
                                    converted = clean_abbreviation(original)
                                else:
                                    converted = wx_to_english(base.split('_')[0])
                                new_words.append(converted + '_(respect)' + trailing_punct)
                            else:
                                cleaned = word_for_check.split('_')[0]
                                original = ne_words.get(cleaned, cleaned)
                                if original.startswith('@'):
                                    converted = clean_abbreviation(original)
                                else:
                                    converted = wx_to_english(cleaned)
                                new_words.append(converted + trailing_punct)

                        else:
                            if '_(respect)' in word_for_check:
                                base = word_for_check.split('_(respect)')[0]
                                base_clean = base.split('_')[0]
                                if (base_clean in ne_words or
                                        any(base_clean.lower() == ne.lower() for ne in ne_words)):
                                    original = ne_words.get(base_clean, base_clean)
                                    if original.startswith('@'):
                                        converted = clean_abbreviation(original)
                                    else:
                                        converted = wx_to_english(base_clean)
                                    new_words.append(converted + '_(respect)' + trailing_punct)
                                else:
                                    new_words.append(base + '_(respect)' + trailing_punct)
                            else:
                                word_clean = word_for_check.split('_')[0]
                                is_ne_word = (
                                    word_clean in ne_words or
                                    any(word_clean.lower() == ne.lower() for ne in ne_words)
                                )
                                if is_ne_word:
                                    original = ne_words.get(word_clean, word_clean)
                                    if original.startswith('@'):
                                        new_words.append(clean_abbreviation(original) + trailing_punct)
                                    else:
                                        new_words.append(wx_to_english(word_clean) + trailing_punct)
                                else:
                                    # Leftover untransliterated WX root: a real
                                    # WX token has internal uppercase letters
                                    # (e.g. 'SivaballaBapura'); ordinary English or
                                    # proper nouns carry at most an initial capital
                                    # ('Hindus'), so only convert on internal caps.
                                    if re.search(r'\B[A-Z]', word_clean) or re.search(r'[A-Z].*[A-Z]', word_clean):
                                        new_words.append(wx_to_english(word_clean) + trailing_punct)
                                    else:
                                        new_words.append(word)

                    processed.append(f"[{' '.join(new_words)}]{rest}")
                else:
                    processed.append(part)

            updated_chunks.append(''.join(processed))

        # Surface fix: indefinite article 'a' -> 'an' before a vowel-initial word.
        # Restricted to a/e/i/o (leaving 'u' as 'a' to avoid 'a university'/'a unique')
        # and skipped before function words (of/in/on/as/...) so a misordered
        # 'a of king' is not turned into 'an of king'.
        _FUNC_AFTER_A = {'of', 'in', 'on', 'at', 'as', 'or', 'is', 'are', 'and',
                         'a', 'an', 'the'}
        def _a_to_an(ch):
            def repl(m):
                nxt = m.group(1)
                if nxt.lower() in _FUNC_AFTER_A:
                    return 'a ' + nxt
                return 'an ' + nxt
            return re.sub(r'\ba ([aeioAEIO]\w*)', repl, ch)
        updated_chunks = [_a_to_an(ch) for ch in updated_chunks]

        # Surface fix: a possessive pronoun immediately followed by a preposition
        # ('its in', 'his to') is never correct English word order; swap to
        # 'preposition + possessive' ('in its', 'to his').
        _POSS = {'its', 'his', 'her', 'their', 'my', 'our', 'your', 'whose', 'own'}
        _PREP = {'from', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'about',
                 'among', 'between', 'through', 'into', 'of'}
        def _swap_poss_prep(ch):
            def repl(m):
                return f"{m.group(2)} {m.group(1)}"
            poss = '|'.join(_POSS); prep = '|'.join(_PREP)
            return re.sub(rf'\b({poss}) ({prep})\b', repl, ch, flags=re.I)
        updated_chunks = [_swap_poss_prep(ch) for ch in updated_chunks]
        if plural_map.get(key):
            updated_chunks = [_fix_agreement(ch, True) for ch in updated_chunks]

        return updated_chunks

    # Run the per-sentence WX conversion; isolate failures so one bad sentence
    # cannot abort conversion for the rest of the batch.
    for key, chunks in list(chunked_data.items()):
        try:
            chunked_data[key] = _convert_one(key, chunks)
        except Exception as e:
            msg = str(e).splitlines()[-1][:160] if str(e).strip() else type(e).__name__
            log(f'WX conversion failed for {key}: {msg}', 'WARN')
            sentence_errors[key] = msg

    # ── Feature-driven post-processing (general rules, read from the USR) ──────
    try:
        _step(5, "grammar post-processing (articles, agreement, ordering)")
        from repository.gold_postprocess import apply_postprocess, load_concept_dict
        raw_usr = open('gen_input.txt', encoding='utf-8').read()
        concept_dict = load_concept_dict()
        chunked_data = apply_postprocess(chunked_data, raw_usr, concept_dict)
    except Exception as e:
        log(f'postprocess skipped: {e}', 'WARN')

    # ── Partial-output markers ────────────────────────────────────────────────
    # Helper: pull the chunk string out of the (list) value.
    def _cstr(v):
        if isinstance(v, list):
            return v[0] if v else ''
        return v or ''

    VERB_TAG_RE = re.compile(r'\[[^\]]*\]_(?:ACTIVE|PASSIVE|QUESTION|IMPERATIVE)')

    # TAM unresolved: keep all the other chunks, drop the verb chunk, mark it.
    for bid in tam_broken_ids:
        cs = _cstr(chunked_data.get(bid)).strip()
        cs = VERB_TAG_RE.sub('', cs)                 # remove the (bad) verb chunk
        cs = re.sub(r'\s+', ' ', cs).strip()
        chunked_data[bid] = [(cs + ' [tam incorrect]').strip() if cs else 'all chunks dropped [tam incorrect]']

    # Verb failed for another reason: the verb is already absent; keep the rest
    # and add a marker. (Skip ones already handled as TAM-broken.)
    for sid, reason in VERB_FAIL_SEGMENTS.items():
        if sid in tam_broken_ids:
            continue
        marker = '[tam incorrect]' if 'tam' in str(reason).lower() else '[verb error: %s]' % reason
        cs = _cstr(chunked_data.get(sid)).strip()
        if cs:
            chunked_data[sid] = [cs + ' ' + marker]
        else:
            chunked_data[sid] = [marker]

    # Any sentence that errored entirely (and produced nothing usable): surface it
    # in place rather than dropping it.
    for sid, msg in sentence_errors.items():
        existing = chunked_data.get(sid)
        has_output = bool(existing and (existing[0] if isinstance(existing, list) else existing))
        if not has_output:
            chunked_data[sid] = ["error generating this usr: %s" % msg]

    # A stage (construction / unprocessed-handling) crashed but the sentence was
    # NOT discarded: emit whatever chunks were built before the crash and append a
    # marker naming the stage and reason. If nothing at all was built, make the
    # marker the line itself so the failure is visible and attributable.
    for sid, stage in SEGMENT_STAGE_ERRORS.items():
        cs = _cstr(chunked_data.get(sid)).strip()
        marker = '[stopped at %s]' % stage
        if cs and marker not in cs:
            chunked_data[sid] = [cs + ' ' + marker]
        elif not cs:
            chunked_data[sid] = ['no output before error ' + marker]

    log(global_starred_words, 'Global starred words with categories')
    log(f'hindi_generation output : {chunked_data}')
    return chunked_data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process linguistic input and generate output.')
    parser.add_argument('--lang', type=str, default='en', help='Language code (e.g., "en" or "hi")')

    args = parser.parse_args()
    lang = args.lang

    file_path = './gen_input.txt'
    input_data = read_file(file_path)
    # Normalize line endings and strip trailing whitespace from every line. A
    # stray space or carriage-return after a tag (e.g. '<sent_id=Sent_13> ')
    # breaks the '<sent_id=...>\n' segment-boundary regexes, causing the lazy
    # match to span into the next sentence and merge two USRs into one. Cleaning
    # it here protects every downstream parser regardless of how the file was
    # saved (Windows CRLF, trailing spaces, etc.).
    input_data = '\n'.join(
        _ln.rstrip()
        for _ln in input_data.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    )
    lines = input_data.strip().split('\n')
    eka_head_index = ''

    for line in lines:
        line = line.strip()
        if not line or line.startswith(("#", "%", "<", "</")):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[0].startswith("eka"):
            head_index = parts[4]
            index = parts[1]
            eka_head_index = (head_index[0], index)
            print("Stored Head Index:", head_index[0])
            break

    ne_words_global = extract_ne_words_from_raw_usr(input_data)
    print(f"[DEBUG] Global NE words extracted: {set(ne_words_global.keys())}")

    if lang == 'en':
        input_data, store_cp_with_id = is_cp(input_data)
        input_data = is_tat(input_data)
        input_data = is_nc(input_data)
        input_data = is_ne(input_data)
        input_data = process_input(input_data, store_cp_with_id)

    result = hindi_generation(input_data, eka_head_index, lang, ne_words_global)

    # ── Restore the real screen and show ONLY the generated sentences ─────────
    if _DEBUG_FH is not None:
        print("\n===== STEP FINAL: output ready =====")
        sys.stdout = _REAL_STDOUT
        try:
            _DEBUG_FH.close()
        except Exception:
            pass
    # ── Normalize result keys to their canonical sentence id ─────────────────
    # A combination step or a stray character on a sent_id can leave a key like
    # 'Sent_13>' or 'Sent_13 ', which then surfaces as a separate merged line
    # while the real id prints "no output". Fold each key onto its trimmed id
    # (whitespace + trailing '>' removed) and keep the non-empty value. This is
    # a no-op for already-clean keys and never discards content.
    if isinstance(result, dict) and result:
        def _txt_of(v):
            if isinstance(v, list):
                return (v[0] if v else '')
            return v or ''
        _norm = {}
        for _k, _v in result.items():
            _ck = str(_k).strip().rstrip('>').strip() or str(_k)
            if _ck not in _norm or (not str(_txt_of(_norm[_ck])).strip()
                                    and str(_txt_of(_v)).strip()):
                _norm[_ck] = _v
        result = _norm
    # ── Print every USR in the SAME order it appears in the input file ────────
    # Failed / TAM-broken / empty sentences stay in their position instead of
    # being dropped or pushed to the end. A sentence that generated nothing gets
    # an explicit placeholder line.
    NO_OUTPUT_MSG = "no output generated from the usr"
    try:
        _raw_for_order = read_file('./gen_input.txt')
    except Exception:
        _raw_for_order = ''
    ordered_sids, _seen = [], set()
    for _sid in re.findall(r'<sent_id=([^\s>]+)>', _raw_for_order):
        if _sid not in _seen:
            _seen.add(_sid)
            ordered_sids.append(_sid)
    # Append any result keys that were not captured from the file (safety net).
    if result:
        for _sid in result:
            if _sid not in _seen:
                _seen.add(_sid)
                ordered_sids.append(_sid)

    if ordered_sids:
        for sid in ordered_sids:
            if sid is None or sid == 'None':
                continue
            chunks = result.get(sid) if result else None
            if isinstance(chunks, list):
                text = chunks[0] if chunks else ''
            else:
                text = chunks or ''
            text = (text or '').strip()
            if not text:
                text = NO_OUTPUT_MSG
            print(f"{sid}: {text}")
    elif result:
        for sid, chunks in result.items():
            text = chunks[0] if isinstance(chunks, list) and chunks else chunks
            print(f"{sid}: {text}")
    else:
        print("No output generated.")