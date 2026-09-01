import json
from repository.common_v4 import *


def remove_construction_info(words_info):
    return [
        wordtuple for wordtuple in words_info
        if not any(str(wordtuple[1]).replace('[', '').replace(']', '').startswith(constr)
                   for constr in repository.constant.construction_list)
    ]


# def identify_and_assign_dep(root_words, construction_data, depend_data, index_data, spkview_data):
#     HAS_CONSTRUCTION_DATA = False
#     flags = {
#         "conj": False, "disjunct": False, "xvanxva": False, "span": False,
#         "cp": False, "meas": False, "rate": False, "waw": False,
#         "compound": False, "calender": False, "temporal_spatial": False
#     }

#     def update_flags_and_data(flag_key, func, *args):
#         nonlocal HAS_CONSTRUCTION_DATA, depend_data
#         flags[flag_key] = True
#         HAS_CONSTRUCTION_DATA = True
#         depend_data = func(*args)
    
#     for i, concept in enumerate(root_words):
#         cleaned_concept = clean(concept)
        
#         if cleaned_concept in ['conj', 'disjunct', 'xvanxva']:
#             update_flags_and_data("conj", construction_row_conj_disj_xvanxva, i, construction_data, depend_data, index_data)
#         elif 'span' in concept:
#             update_flags_and_data("span", construction_row_span, i, construction_data, depend_data, index_data)
#         elif 'cp' in concept:
#             update_flags_and_data("cp", construction_row_cp, i, construction_data, depend_data, index_data, spkview_data)
#         elif 'meas' in concept:
#             update_flags_and_data("meas", construction_row_meas, i, construction_data, depend_data, index_data)
#         elif 'rate' in concept:
#             update_flags_and_data("rate", construction_row_rate, i, construction_data, depend_data, index_data)
#         elif 'waw' in concept or cleaned_concept in ('compound', 'waw'):
#             update_flags_and_data("waw", construction_row_waw, i, construction_data, depend_data, index_data)
#         elif 'calender' in concept:
#             update_flags_and_data("calender", construction_row_calender, i, construction_data, depend_data, index_data)
#         elif 'temporal' in concept or 'spatial' in concept:
#             update_flags_and_data("temporal_spatial", construction_row_temporal_spatial, i, construction_data, depend_data, index_data)
#         elif 'ne' in concept:
#             update_flags_and_data("ne", construction_row_ne, i, construction_data, depend_data, index_data)
    
#     return depend_data, HAS_CONSTRUCTION_DATA, flags

# def process_construction_data(i, construction_data1, depend_data, index_data1, condition_func, update_func=None):
#     dep1 = depend_data[i]
#     for j, text in enumerate(construction_data1):
#         if condition_func(text) and dep1:
#             depend_data[j] = update_func(dep1) if update_func else dep1
#         elif construction_data1[i]:
#             head = construction_data1[i].split(':')[0]
#             ind = index_data1.index(int(head))
#             depend_data[ind] = depend_data[ind]
#     return depend_data


# def construction_row_conj_disj_xvanxva(i, construction_data1, depend_data, index_data1):
#     return process_construction_data(i, construction_data1, depend_data, index_data1, lambda text: 'op' in text)


# def construction_row_temporal_spatial(i, construction_data1, depend_data, index_data1):
#     def update_temporal(dep1):
#         dep_ind = dep1.split(':')[0]
#         return dep_ind + ':r6'
    
#     return process_construction_data(
#         i, construction_data1, depend_data, index_data1,
#         lambda text: 'whole' in text or 'part' in text,
#         update_temporal
#     )


# def construction_row_span(i, construction_data1, depend_data, index_data1):
#     return process_construction_data(i, construction_data1, depend_data, index_data1, lambda text: 'start' in text or 'end' in text)


# def construction_row_ne(i, construction_data1, depend_data, index_data1):
#     return process_construction_data(i, construction_data1, depend_data, index_data1, lambda text: 'begin' in text or 'inside' in text)


# def construction_row_cp(i, construction_data1, depend_data, index_data1, spkview_data):
#     dep1 = depend_data[i]
#     spk_data = spkview_data[i]
#     for j, text in enumerate(construction_data1):
#         if 'verbalizer' in text and dep1:
#             depend_data[j] = dep1
#             spkview_data[j] = spk_data
#         elif construction_data1[i]:
#             head = construction_data1[i].split(':')[0]
#             ind = index_data1.index(int(head))
#             depend_data[ind] = depend_data[ind]
#     return depend_data


# def construction_row_meas(i, construction_data1, depend_data, index_data1):
#     return process_construction_data(i, construction_data1, depend_data, index_data1, lambda text: 'count' in text or 'unit' in text)


# def construction_row_waw(i, construction_data1, depend_data, index_data1):
#     return process_construction_data(i, construction_data1, depend_data, index_data1, lambda text: any(x in text for x in ['mod', 'head', 'avayavI', 'avayava']))


# def construction_row_calender(i, construction_data1, depend_data, index_data1):
#     return process_construction_data(i, construction_data1, depend_data, index_data1, lambda text: 'component' in text)


# def construction_row_rate(i, construction_data1, depend_data, index_data1):
#     return process_construction_data(i, construction_data1, depend_data, index_data1, lambda text: 'unit_every' in text or 'unit_value' in text)

def identify_and_assign_dep(root_words, construction_data, depend_data, index_data, spkview_data):
    HAS_CONSTRUCTION_DATA = False
    flags = {
        "conj": False, "disjunct": False, "xvanxva": False, "span": False,
        "cp": False, "meas": False, "rate": False, "waw": False,
        "compound": False, "calender": False, "temporal_spatial": False
    }
    
    for i, concept in enumerate(root_words):
        cleaned_concept = clean(concept)
        if cleaned_concept in ['conj', 'disjunct', 'xvanxva']:
            flags["conj"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data = construction_row_conj_disj_xvanxva(i, construction_data, depend_data, index_data)
        elif 'span' in concept:
            flags["span"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data = construction_row_span(i, construction_data, depend_data, index_data)
        # elif 'cp' in concept:
        #     flags["cp"] = True
        #     HAS_CONSTRUCTION_DATA = True
        #     depend_data = construction_row_cp(i, construction_data, depend_data, index_data, spkview_data)
        elif 'meas' in concept:
            flags["meas"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data = construction_row_meas(i, construction_data, depend_data, index_data)
        elif 'rate' in concept:
            flags["rate"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data = construction_row_rate(i, construction_data, depend_data, index_data)
        elif 'waw' in concept or cleaned_concept in ('compound', 'waw'):
            flags["waw"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data = construction_row_waw(i, construction_data, depend_data, index_data)
        elif 'calender' in concept:
            flags["calender"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data = construction_row_calender(i, construction_data, depend_data, index_data)
        elif 'temporal' in concept or 'spatial' in concept:
            flags["temporal_spatial"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data = construction_row_temporal_spatial(i, construction_data, depend_data, index_data)
        elif 'ne' in concept:
            flags["ne"] = True
            HAS_CONSTRUCTION_DATA = True
            depend_data,spkview_data = construction_row_ne(i, construction_data, depend_data, index_data, spkview_data, root_words=root_words)
    
    return depend_data,spkview_data, HAS_CONSTRUCTION_DATA, flags

def process_construction(processed_words, root_words, construction_data, depend_data, 
                                gnp_data, index_data, flags, lang='en'):
    if flags["conj"] or flags["disjunct"]:
        processed_words, flags["conj"], flags["disjunct"] = process_construction_conj_disjunct(
            processed_words, root_words, construction_data, depend_data, 
            gnp_data, index_data, root_words, flags["conj"], flags["disjunct"], lang=lang
        )
    if flags["span"]:
        processed_words, flags["span"] = process_construction_span(
            processed_words, construction_data, index_data, flags["span"]
        )
    if flags["rate"]:
        processed_words, flags["rate"] = process_construction_rate(
            processed_words, construction_data, index_data, flags["rate"]
        )
    if flags["temporal_spatial"]:
        processed_words, flags["temporal_spatial"] = process_construction_spatial_temporal(
            processed_words, construction_data, index_data, flags["temporal_spatial"]
        )
    if flags["xvanxva"]:
        processed_words, flags["xvanxva"] = process_construction_xvanxva(
            processed_words, construction_data, index_data, flags["xvanxva"]
        )
    # if flags["cp"]:
    #     processed_words, flags["cp"] = process_construction_cp(
    #         processed_words,depend_data,processed_words, construction_data, index_data, flags["cp"]
    #     )
    
    return processed_words, flags

def construction_row_conj_disj_xvanxva(i,construction_data1,depend_data,index_data1):
    dep1=depend_data[i]
    try:
        my_idx = str(index_data1[i])
    except (IndexError, TypeError):
        my_idx = None
    for j, text in enumerate(construction_data1):
        # Only copy this conjunction's dependency to op-members that belong to THIS
        # conjunction (text like '35:op1' must reference my_idx). Without this scope
        # check, a conjunction would stamp its relation onto another conjunction's
        # members (which have empty deps), merging the two groups and duplicating
        # their words in the output.
        if ('op' in text and ':' in text and my_idx is not None
                and text.split(':')[0] == my_idx and dep1 and depend_data[j]==''):
            depend_data[j]=dep1
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    return depend_data

def construction_row_temporal_spatial(i,construction_data1,depend_data,index_data1):
    dep1=depend_data[i]
    for j, text in enumerate(construction_data1):
        if 'whole' in text and dep1!='':
            dep_ind = dep1.split(':')[0]
            depend_data[j]=dep_ind+':r6'
        elif 'part' in text and dep1:
            depend_data[j]=dep1
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    return depend_data

def construction_row_span(i,construction_data1,depend_data,index_data1):
    dep1=depend_data[i]
    for j, text in enumerate(construction_data1):
        if 'start' in text and dep1!='':
            depend_data[j]=dep1
        elif 'end' in text and dep1:
            depend_data[j]=dep1
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    return depend_data

def construction_row_ne(i,construction_data1,depend_data,index_data1,spkview_data,
                        root_words=None):
    for j, text in enumerate(construction_data1):
        if 'begin' in text or 'inside' in text:
            head=construction_data1[j].split(':')[0]
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            # If the cid row is not itself an [ne_N] tag (e.g. it resolved to the
            # main verb due to a USR index mismatch), fall back to the current
            # ne_N row's own dependency so NE members get the correct syntactic role.
            cid_is_ne = (root_words is not None
                         and ind < len(root_words)
                         and root_words[ind].startswith('[ne'))
            if not cid_is_ne and root_words is not None:
                dep1 = depend_data[i]
                spk1 = spkview_data[i]
            else:
                dep1 = depend_data[ind]
                spk1 = spkview_data[ind]
            depend_data[j]=dep1
            spkview_data[j]=spk1
    return depend_data,spkview_data

def construction_row_cp(i,construction_data1,depend_data,index_data1,spkview_data):
    dep1=depend_data[i]
    spk_data = spkview_data[i]
    for j, text in enumerate(construction_data1):
        # if 'kriyAmUla' in text and dep1:
        #     # op_indexes.append(i)
        #     depend_data[j]=dep1
        if 'verbalizer' in text and dep1:
            depend_data[j]=dep1
            spkview_data[j]=spk_data
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    # ##print(depend_data,'cp')
    return depend_data

def construction_row_meas(i,construction_data1,depend_data,index_data1):
    dep1=depend_data[i]
    for j, text in enumerate(construction_data1):
        if 'count' in text or 'unit' in text and dep1:
            # op_indexes.append(i)
            depend_data[j]=dep1
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    # ##print(depend_data,'meas')
    return depend_data

def construction_row_waw(i, construction_data1, depend_data, index_data1):
    dep1 = depend_data[i]
    for j, text in enumerate(construction_data1):
        if any(x in text for x in ['mod', 'head', 'avayavI', 'avayava']) and dep1:
            depend_data[j] = dep1
        elif construction_data1[i]:
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    return depend_data

def construction_row_spatial(i,construction_data1,depend_data,index_data1):
    dep1=depend_data[i]
    for j, text in enumerate(construction_data1):
        # if 'whole' in text or 'part' in text and dep1:
        if 'part' in text and dep1:
            dep1_ind = dep1.split(':')[0]
            depend_data[j]=dep1_ind+':r6'
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    # ##print(depend_data,'meas')
    return depend_data

def construction_row_calender(i,construction_data1,depend_data,index_data1):
    dep1=depend_data[i]
    for j, text in enumerate(construction_data1):
        if 'component' in text and dep1:
            # op_indexes.append(i)
            depend_data[j]=dep1
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
    # ##print(depend_data,'calen')
    return depend_data

def construction_row_rate(i,construction_data1,depend_data,index_data1):
    dep1=depend_data[i]
    for j, text in enumerate(construction_data1):
        if 'unit_every' in text or 'unit_value' in text and dep1:
            # op_indexes.append(i)
            depend_data[j]=dep1
        elif construction_data1[i]!='':
            head=construction_data1[i].split(':')[0]
            # ##print(index_data1)
            try:
                ind=index_data1.index(int(head))
            except (ValueError, TypeError):
                continue  # construction head not defined in USR; skip gracefully
            dep1=depend_data[ind]
            depend_data[ind]=dep1
            # multi_construction(j,construction_data1,depend_data)
    return depend_data

# def process_construction_cp(processed_words,depend_data,processed_words, construction_data, index_data, flag_cp):
#     process_data = processed_words
#     # dep_gender_dict = {}
#     a = 'after'
#     b = 'before'
#     for i,cons in enumerate(construction_data):
#         if 'count' in cons and 'per_unit' in construction_data[i+1]:
#             start_idx = index_data[i]
#             temp = (b, 'prawyeka')
#             if float(start_idx) in construction_dict:
#                 construction_dict[float(start_idx)].append(temp)
#                 flag_rate=False
#             else:
#                 construction_dict[float(start_idx)] = [temp]
#         if float(index_data[i]) in processed_postpositions_dict:
#             del processed_postpositions_dict[float(index_data[i])]
            
#     return process_data,flag_rate


def process_construction_conj_disjunct(processed_words, root_words,construction_data1, depend_data, gnp_data, index_data,conj_concept,flag_conj,flag_disjunct, lang='en'):
    # Adding Ora or yA as a tuple to be sent to morph/ adding it at join_compounds only
    # if k1 in conj, all k1s and main verb g - m and n - pl
    # if all k1 male or mix - k1s g - male else g - f
    # cons list - can be more than one conj
    # k1 ka m/f/mix nikalkr k1s and verb ko g milega    index dep:gen
    # map to hold conj kaha aega
    # construction_dict.clear()
    process_data = processed_words
    dep_gender_dict = {}
    a = 'after'
    b = 'before'
    if gnp_data != []:
        gender = []
        for i in range(len(gnp_data)):
            gnp_info = gnp_data[i]
            gnp_info = gnp_info.strip().strip('][')
            gnp = gnp_info.split(' ')
            gender.append(gnp[0])

    if depend_data != []:
        dependency = []
        for dep in depend_data:
            if dep != '':
                dep_val = dep.strip().split(':')[1]
                dependency.append(dep_val)
    index=new_to_old_convert_construction_conj_dis(index_data,construction_data1,conj_concept)
    print('conj',index)
    # ##print(construction_data,'conda')
    for i, dep, g in zip(index_data, dependency, gender):
        dep_gender_dict[str(i)] = dep + ':' + g

    # Build index -> gnp_string lookup so we can check 'pl' per token
    gnp_index_dict = {}
    for idx, gnp_str in zip(index_data, gnp_data):
        gnp_index_dict[idx] = gnp_str.strip()

    def _en_pluralize_word(word):
        """Apply basic English pluralization to a word.
        Used for disjunct/conj operands that carry pl information."""
        if not word or word.startswith('#') or word.startswith('@'):
            return word  # starred/NE words handled elsewhere
        # Strip WX sense suffix like _1 before pluralizing
        import re as _re
        base = _re.sub(r'_\d+$', '', word)
        irregular = {
            'child': 'children', 'man': 'men', 'woman': 'women',
            'tooth': 'teeth', 'foot': 'feet', 'mouse': 'mice',
            'person': 'people', 'goose': 'geese',
        }
        low = base.lower()
        if low in irregular:
            out = irregular[low]
            return out.capitalize() if base[:1].isupper() else out
        if _re.search(r'(s|x|z|ch|sh)$', low):
            return base + 'es'
        if _re.search(r'[^aeiou]y$', low):
            return base[:-1] + 'ies'
        if low.endswith('f') and not low.endswith('ff'):
            return base[:-1] + 'ves'
        if low.endswith('fe'):
            return base[:-2] + 'ves'
        return base + 's'

    def make_token_plural(processed_words, target_index):
        """Set number='p' on the token at target_index.
        For noun tokens: also pluralize the surface word directly so that
        the already-generated morph string is overridden with the plural form.
        For adj tokens acting as conj/disjunct operands: pluralize the word
        directly since morph is built before construction and won't re-run."""
        result = []
        for t in processed_words:
            if t[0] == target_index:
                t_list = list(t)
                if len(t_list) > 5:
                    t_list[5] = 'p'
                # For adj tokens (conj/disjunct operands like nagara→place,
                # sapwapuri): pluralize the surface word directly since morph
                # was already built before pl propagation runs.
                if t_list[2] == 'adj' and len(t_list) > 1:
                    from repository.common_v4 import wx_to_english
                    word = t_list[1]
                    # Only pluralize if single clean word (no spaces, not already plural)
                    if word and ' ' not in word and not word.endswith('s'):
                        # Apply WX→Roman first if WX-encoded, then pluralize
                        roman = wx_to_english(word)
                        t_list[1] = _en_pluralize_word(roman)
                result.append(tuple(t_list))
            else:
                result.append(t)
        return result
    
    # ##print(construction_data,'cccd')
    # if construction_data != '*nil' and len(construction_data) > 0:
    # construction = construction_data1.strip().split(' ')
    for ind, cons in zip(index_data,root_words):
        # conj_type = cons.split(':')[0].strip().lower()
        # index = cons.split('@')[1].strip().strip('][').split(',') if '@' in cons else cons.strip().strip('][').split(',')
        # index = cons.split(':')[1].strip().strip('][').split(',')
        # ##print(index)
        # length_index = list(index.keys())[0]  # Extracting the key (e.g., 6)

        if 'conj' in cons or 'disjunct' in cons or 'xvanxva' in cons:
            length_index = list(index[ind])
            cnt_m = 0
            cnt_f = 0
            PROCESS = False

            for key, value in index.items():  # Iterating over dictionary
                for i, op in value:  # Extract index and operation from tuple
                    relation = dep_gender_dict.get(str(i), '')  # Get relation if exists
                    if relation:
                        dep = relation.split(':')[0]
                        gen = relation.split(':')[1]

                        if dep == 'k1':
                            PROCESS = True
                            if gen == 'm':
                                cnt_m += 1
                            elif gen == 'f':
                                cnt_f += 1

            if PROCESS and lang == 'hi':
                # For Hindi: set gender/number agreement on adj and verb tokens
                # For English: skip this — English verb agreement is determined
                # by the actual number of the k1 subject noun, not by conjunction.
                if cnt_f == length_index:  # Using key as length_index
                    g = 'f'
                    num = 'p'
                else:
                    g = 'm'
                    num = 'p'
                process_data = set_gender_make_plural(processed_words, g, num)

            # ── Plural propagation from disjunct/conj node to its operands ────
            # Rule 1: if 'pl' is on the disjunct node itself, all operands become plural
            # Rule 2: if 'pl' is directly on an individual op node, only that op becomes plural
            if 'disjunct' in cons or 'conj' in cons or 'xvanxva' in cons:
                disjunct_gnp = gnp_index_dict.get(ind, '')
                disjunct_is_pl = 'pl' in disjunct_gnp
                if ind in index:
                    for op_index, op_label in index[ind]:
                        op_gnp = gnp_index_dict.get(op_index, '')
                        op_is_pl = 'pl' in op_gnp
                        if disjunct_is_pl or op_is_pl:
                            process_data = make_token_plural(process_data, op_index)
                            print(f"[PL_PROPAGATE] {op_label} (index {op_index}) set to plural (disjunct_pl={disjunct_is_pl}, op_pl={op_is_pl})")

            for key in index:
                index[key] = sorted(index[key])
            if len(index[ind])==2:
                update_index = index[ind][0]  # Using the key instead of array index
            else:
                update_index = index[ind][-2]

            # check if update index is NC
            #if true then go till NC_head index update same index in construction dict and remove ppost if any from processed
            for op_val in index[ind]:
                op_index = op_val[0]
                op_num = op_val[1]
                if op_val == update_index:
                    if is_update_index_NC(op_index, processed_words):
                        index_NC_head = fetch_NC_head(op_index, processed_words)
                        op_index = index_NC_head
                    if 'conj' in cons or 'xvanxva' in cons:
                        flag_conj=False
                        temp = (a, 'and')
                        # ##print(temp,'varsk')
                    elif 'disjunct' in cons:
                        flag_disjunct=False
                        flag_conj=False
                        temp = (a, 'or')
                    break
                elif len(index[ind])>2:
                    temp = (a, ',')
                    if float(op_index) in construction_dict:
                        construction_dict[float(op_index)].append(temp)
                    else:
                        construction_dict[float(op_index)] = [temp]

                    # if i in ppost_dict remove ppost rAma kA Ora SAma kA -> rAma Ora SAma kA
                    if float(op_index) in processed_postpositions_dict:
                        del processed_postpositions_dict[float(op_index)]

            if float(op_index) in construction_dict:
                construction_dict[float(op_index)].append(temp)
            else:
                construction_dict[float(op_index)] = [temp]

            if float(op_index) in processed_postpositions_dict:
                del processed_postpositions_dict[float(op_index)]

        elif cons == 'list':
            length_list = len(index)
            for i in range(len(index)):
                if i == length_list - 1:
                    break

                if i == 0:
                    temp = (b, 'jEse')
                    if index[i] in construction_dict:
                        construction_dict[index[i]].append(temp)
                    else:
                        construction_dict[index[i]] = [temp]
                    temp = (a, ',')

                elif i < length_list - 1:
                    temp = (a, ',')

                if index[i] in construction_dict:
                    construction_dict[index[i]].append(temp)
                else:
                    construction_dict[index[i]] = [temp]
    # ##print('process_construction : ',construction_dict)
    return process_data,flag_conj,flag_disjunct

def process_construction_span(processed_words, construction_data,index_data,flag_span):
    # construction_dict.clear()
    process_data = processed_words
    dep_gender_dict = {}
    a = 'after'
    b = 'before'
    # construction_data=new_to_old_convert_construction_span(index_data,construction_data1,span_concept)
    # if construction_data != '*nil' and len(construction_data) > 0:
    # construction = construction_data.strip().split(' ')
    for i,cons in enumerate(construction_data):
        # conj_type = cons.split(':')[0].strip().lower()
        # index = cons.split(':')[1].strip(' ').strip().strip('][').split(',')
        # length_index = len(index)
        if 'start' in cons:
            start_idx = index_data[i]
            # ##print(processed_postpositions_dict)
            temp = (b, 'from')
            # del processed_postpositions_dict[index_data[i]]
            if float(start_idx) in construction_dict:
                construction_dict[float(start_idx)].append(temp)
                flag_span=False
            else:
                construction_dict[float(start_idx)] = [temp]
            if float(start_idx) in processed_postpositions_dict:
                del processed_postpositions_dict[float(i)]

        elif 'end' in cons:
            end_idx = index_data[i]
            temp = (b, 'to')
            # del processed_postpositions_dict[index_data[i]]
            if float(end_idx) in construction_dict:
                construction_dict[float(end_idx)].append(temp)
                flag_span=False
            else:
                construction_dict[float(end_idx)] = [temp]
            if float(end_idx) in processed_postpositions_dict:
                del processed_postpositions_dict[float(i)]
    print(construction_dict,'dict')
    return process_data,flag_span

# {4.0: [('after', 'se')], 7.0: [('after', 'waka')]}

def process_construction_rate(processed_words, construction_data,index_data,flag_rate):
    # construction_dict.clear()
    process_data = processed_words
    # dep_gender_dict = {}
    a = 'after'
    b = 'before'
    for i,cons in enumerate(construction_data):
        if 'count' in cons and 'per_unit' in construction_data[i+1]:
            start_idx = index_data[i]
            temp = (b, 'prawyeka')
            if float(start_idx) in construction_dict:
                construction_dict[float(start_idx)].append(temp)
                flag_rate=False
            else:
                construction_dict[float(start_idx)] = [temp]
        if float(index_data[i]) in processed_postpositions_dict:
            del processed_postpositions_dict[float(index_data[i])]
            
    return process_data,flag_rate


def process_construction_spatial_temporal(processed_words, construction_data,index_data,flag_spatial):
    # construction_dict.clear()
    # process_data = processed_words
    # dep_gender_dict = {}
    a = 'after'
    b = 'before'
    for i,cons in enumerate(construction_data):
        if 'whole' in cons in construction_data[i]:
            start_idx = index_data[i]
            # temp = (b, 'prawyeka')
            # del processed_postpositions_dict[index_data[i]]
            temp = (a, 'in')
            if float(start_idx) in construction_dict:
                construction_dict[float(start_idx)].append(temp)
                flag_spatial=False
            else:
                construction_dict[float(start_idx)] = [temp]
        # if float(index_data[i]) in processed_postpositions_dict:
        #     del processed_postpositions_dict[float(index_data[i])]
            
    return processed_words,flag_spatial
def process_construction_xvanxva(processed_words, construction_data,index_data,flag_xvanxva):
    # construction_dict.clear()
    process_data = processed_words
    # dep_gender_dict = {}
    a = 'after'
    b = 'before'
    for i,cons in enumerate(construction_data):
        if 'op' in cons in construction_data[i]:
            start_idx = index_data[i]
            # temp = (b, 'prawyeka')
            # del processed_postpositions_dict[index_data[i]]
            temp = (a, '-')
            if float(start_idx) in construction_dict:
                construction_dict[float(start_idx)].append(temp)
                flag_xvanxva=False
            else:
                construction_dict[float(start_idx)] = [temp]
                flag_xvanxva=False
            break
        if float(index_data[i]) in processed_postpositions_dict:
            del processed_postpositions_dict[float(index_data[i])]

    return process_data,flag_xvanxva


def generate_construction_json(input_list):
    constructions_dict = {}
    
    priority_order = [
        ['count', 'unit'],
        ['start', 'stop'],
        ["op1", "op2", "op3", "op4", "op5"],
        ['mod', 'head'],
        ['kriyamul', 'verbalizer'],
        ['count_every', 'count_value'],
        ['whole', 'part']
    ]

    def get_sort_key(value):
        for group_idx, group in enumerate(priority_order):
            if value in group:
                return (group_idx, group.index(value))
        return (len(priority_order), 0)

    def remove_duplicate_constructions(constructions):
        unique_constructions = []
        seen = set()
        
        for construction in constructions:
            key = (
                construction['original_concept']['index'],
                construction['original_concept']['concept'],
                construction['original_concept']['dep_rel'],
                construction['original_concept']['dep_head'],
                tuple(sorted((rt['constr_value'], rt['concept'], rt['index']) for rt in construction['related_tokens']))
            )
            if key not in seen:
                seen.add(key)
                unique_constructions.append(construction)
        
        return unique_constructions

    for entry in input_list:
        text = entry.get('text', '')
        usr_id = entry.get('usr_id', '')
        tokens = entry.get('tokens', [])
        
        key = (text, usr_id)
        if key not in constructions_dict:
            constructions_dict[key] = {
                'text': text,
                'usr_id': usr_id,
                'constructions': []
            }
        
        for token in tokens:
            concept = token.get('concept', '')
            if isinstance(concept, str) and concept.startswith('[') and concept.endswith(']'):
                original_index = token.get('index')
                original_dep_rel = token.get('dep_rel', '-')
                original_dep_head = token.get('dep_head', '-')
                
                related_tokens = []
                for t in tokens:
                    constr_ci = t.get('constr_concept_index', '')
                    try:
                        if constr_ci not in ['-', '', None] and int(constr_ci) == original_index:
                            related_info = {
                                'constr_value': t.get('constr_value', '-'),
                                'concept': t.get('concept', ''),
                                'index': t.get('index')
                            }
                            related_tokens.append(related_info)
                    except (ValueError, TypeError):
                        continue
                
                if related_tokens:
                    related_tokens.sort(key=lambda x: get_sort_key(x['constr_value']))
                    construction_entry = {
                        'original_concept': {
                            'index': original_index,
                            'concept': concept,
                            'dep_rel': original_dep_rel,
                            'dep_head': original_dep_head
                        },
                        'related_tokens': related_tokens
                    }
                    constructions_dict[key]['constructions'].append(construction_entry)
        
        constructions_dict[key]['constructions'] = remove_duplicate_constructions(constructions_dict[key]['constructions'])
    
    return {'constructions': list(constructions_dict.values())}






# # Example usage:
# input_data = [
#     {
#         "text": "बड़ा पैन 1 चुटकी धनिया 2 करी पत्ता भून ।",
#         "usr_id": "Test_1_0008",
#         "sent_type": "imperative",
#         "tokens": [
#             {
#                 "index": 1,
#                 "concept": "BUna_1",
#                 "tam": "o_1",
#                 "is_combined_tam": True,
#                 "type": None,
#                 "dep_rel": "main",
#                 "dep_head": 0,
#                 "constr_value": "-",
#                 "constr_concept_index": "-"
#             },
#             {
#                 "index": 2,
#                 "concept": "pEna_1",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "k2p",
#                 "dep_head": 1,
#                 "constr_value": "-",
#                 "constr_concept_index": "-"
#             },
#             {
#                 "index": 3,
#                 "concept": "badZA_1",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "mod",
#                 "dep_head": 2,
#                 "constr_value": "-",
#                 "constr_concept_index": "-"
#             },
#             {
#                 "index": 4,
#                 "concept": "XaniyA_1",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "-",
#                 "dep_head": "-",
#                 "constr_value": "op1",
#                 "constr_concept_index": 11,
#                 "cxn_construct": "op1",
#                 "construct_head": 11
#             },
#             {
#                 "index": 5,
#                 "concept": "[meas_1]",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "rmeas",
#                 "dep_head": 4,
#                 "constr_value": "-",
#                 "constr_concept_index": "-"
#             },
#             {
#                 "index": 6,
#                 "concept": "cutakI_1",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "-",
#                 "dep_head": "-",
#                 "constr_value": "unit",
#                 "constr_concept_index": 5,
#                 "cxn_construct": "unit",
#                 "construct_head": 5
#             },
#             {
#                 "index": 7,
#                 "concept": "1",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "-",
#                 "dep_head": "-",
#                 "constr_value": "count",
#                 "constr_concept_index": 5,
#                 "cxn_construct": "count",
#                 "construct_head": 5
#             },
#             {
#                 "index": 8,
#                 "concept": "karI+pawwA_1",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "-",
#                 "dep_head": "-",
#                 "constr_value": "op2",
#                 "constr_concept_index": 11,
#                 "cxn_construct": "op2",
#                 "construct_head": 11
#             },
#             {
#                 "index": 9,
#                 "concept": "[meas_2]",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "rmeas",
#                 "dep_head": 8,
#                 "constr_value": "-",
#                 "constr_concept_index": "-"
#             },
#             {
#                 "index": 10,
#                 "concept": "2",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": None,
#                 "dep_rel": "-",
#                 "dep_head": "-",
#                 "constr_value": "count",
#                 "constr_concept_index": 9,
#                 "cxn_construct": "count",
#                 "construct_head": 9
#             },
#             {
#                 "index": 11,
#                 "concept": "[conj_1]",
#                 "tam": None,
#                 "is_combined_tam": False,
#                 "type": "conjunction",
#                 "dep_rel": "k2",
#                 "dep_head": 1,
#                 "constr_value": "-",
#                 "constr_concept_index": "-"
#             }
#         ]
#     }
# ]

# # Uncomment to process actual data
# # with open('input.json') as f:
# #     input_data = json.load(f)

# output_data = generate_construction_json(input_data)

# # Save to construction.json
# with open('construction.json', 'w', encoding='utf-8') as f:
#     json.dump(output_data, f, ensure_ascii=False, indent=2)