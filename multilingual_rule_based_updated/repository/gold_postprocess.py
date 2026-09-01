"""
gold_postprocess.py
===================

Feature-driven post-processing of the chunked English output.

Every rule in this module is keyed on a feature that is *read from the USR
itself* (its dependency relations, focus markers, construction rows, cardinals,
sentence type, …) — never on a sentence id.  The same rule therefore fires for
any USR that carries the same feature.

The entry point is ``apply_postprocess(chunked_data, usr_text, concept_dict)``.
It parses each sentence's USR rows once, derives a small feature record, and
rewrites the (already transliterated) chunk string.

Column layout of a USR data row (whitespace separated):

    0: concept (WX root, or a construction tag like [ne_1]/[nc_1])
    1: index
    2: category / NE-type (place, per, male, numex, moy, …)
    3: gnp / number (pl, …)
    4: dependency  "<head>:<relation>"      e.g. 8:k1, 10:k2s, 6:rn
    5: scope
    6: morpho-semantic / speaker-view marker (def, respect, BI_1, hI_1, sA_1, …)
    7: extra marker (a second BI_1/hI_1 can live here)
    8: construction  "<id>:<role>"          e.g. 3:begin, 14:inside, 9:mod,
                                             11:head, 12:count, 15:start
"""

import re

# Two-char WX sequences must be handled before single chars (mirrors
# common_v4.wx_to_english) so the post-processor can reproduce the exact
# transliterated surface form the main pipeline emits.
_TWO_CHAR_WX = {'dZ': 'ḍ', 'jZ': 'j', 'DZ': 'ḍh'}
_WX_TO_ENG = None  # filled lazily from common_v4


def _load_wx_table():
    global _WX_TO_ENG
    if _WX_TO_ENG is None:
        try:
            from repository.common_v4 import wx_to_eng
            _WX_TO_ENG = wx_to_eng
        except Exception:
            _WX_TO_ENG = {}
    return _WX_TO_ENG


def _wx(word):
    table = _load_wx_table()
    word = word.split('_')[0]
    out, i = '', 0
    while i < len(word):
        two = word[i:i + 2]
        if two in _TWO_CHAR_WX:
            out += _TWO_CHAR_WX[two]
            i += 2
        else:
            out += table.get(word[i], word[i])
            i += 1
    return out


def _strip_sense(el):
    """railway_2 -> railway ; sanctum-sanctorum_1 -> sanctum-sanctorum"""
    return re.sub(r'_\d+$', '', el)


_POS = None


def _load_pos(concept_file="dictionaries/concept-to-mrs-rels.dat"):
    """Lazy map concept(hl) -> mrsc tag (5th column), for POS checks."""
    global _POS
    if _POS is None:
        _POS = {}
        try:
            with open(concept_file, encoding='utf-8') as f:
                for row in f:
                    cols = row.strip().split()
                    if len(cols) > 4:
                        _POS[cols[1]] = cols[4]
        except FileNotFoundError:
            pass
    return _POS


def _is_adjective(concept):
    pos = _load_pos().get(concept) or _load_pos().get(concept.split('-')[0])
    return bool(pos and '_a_' in pos)


# ── USR parsing ───────────────────────────────────────────────────────────────

def parse_usr_blocks(usr_text):
    """Return {sent_id: {'rows': [...], 'type': str}}."""
    blocks = {}
    for m in re.finditer(r'<sent_id=([^\s>]+)>(.*?)</sent_id>', usr_text, re.S):
        sid, body = m.group(1), m.group(2)
        rows, stype = [], ''
        for ln in body.splitlines():
            s = ln.strip()
            if not s or s.startswith('#') or s.startswith('<'):
                continue
            if s.startswith('%'):
                stype = s[1:].strip()
                continue
            c = s.split()
            if len(c) >= 2 and (c[1].isdigit()):
                rows.append(c)
        blocks[sid] = {'rows': rows, 'type': stype}
    return blocks


def _comp_english(concept, concept_dict):
    """English surface for an NE/NC component concept (translate else translit)."""
    base = concept
    cand = [base, base.split('-')[0]]
    for key in cand:
        if key in concept_dict:
            return _strip_sense(concept_dict[key])
    return _wx(base)


def _parse_constructions(rows):
    """Map every construction id to its type and member roles.

    Returns {cid: {'type': 'dvandva'|'conj'|'nc'|'ne'|'spatial'|...,
                   'rel': (head_idx, rel) or None,
                   'roles': {role: [member_idx, ...]}}}
    """
    constr = {}
    # tag rows like '[dvandva_1] 5 ... 7:r6'
    for c in rows:
        m = re.fullmatch(r'\[([a-zA-Z]+)_\d+\]', c[0])
        if m:
            cid = c[1]
            rel = None
            if len(c) > 4 and ':' in c[4]:
                h, r = c[4].split(':', 1)
                rel = (h, r)
            constr.setdefault(cid, {'type': m.group(1), 'rel': rel,
                                    'roles': {}})
            constr[cid]['type'] = m.group(1)
            constr[cid]['rel'] = rel
    # member rows: last column 'cid:role'
    for c in rows:
        if len(c) >= 2 and ':' in c[-1]:
            cid, role = c[-1].split(':', 1)
            if role in ('op1', 'op2', 'op3', 'op4', 'mod', 'head', 'begin',
                        'inside', 'whole', 'part', 'start', 'end', 'unit',
                        'count', 'kriyAmUla', 'verbalizer', 'component'):
                constr.setdefault(cid, {'type': '', 'rel': None, 'roles': {}})
                constr[cid]['roles'].setdefault(role, []).append(c[1])

    # Fix: when begin/inside members point to a cid that has no [xxx_N] tag row
    # (type == ''), find an [ne_N] tag row whose dep head == that cid and
    # transfer the members to the NE's actual index.
    # This handles USR mismatch like `maWurA 18 ... 20:begin` with [ne_6] at
    # index 29 having dep `20:k1` — members should live under constr['29'].
    for cid in list(constr.keys()):
        roles = constr[cid]['roles']
        if not (roles.get('begin') or roles.get('inside')):
            continue
        if constr[cid]['type']:  # already has a recognised type → correct
            continue
        for c in rows:
            if not re.fullmatch(r'\[ne_\d+\]', c[0]):
                continue
            if len(c) < 5 or ':' not in c[4]:
                continue
            h, _ = c[4].split(':', 1)
            if h != cid:
                continue
            ne_idx = c[1]
            constr.setdefault(ne_idx, {'type': 'ne', 'rel': None, 'roles': {}})
            for role in ('begin', 'inside'):
                if role in roles:
                    constr[ne_idx]['roles'].setdefault(role, [])
                    constr[ne_idx]['roles'][role] = (
                        roles.pop(role) + constr[ne_idx]['roles'][role]
                    )
            if not constr[ne_idx]['type']:
                constr[ne_idx]['type'] = 'ne'
            break

    return constr


def _resolve_en(idx, rows, concept_dict, constr, _seen=None):
    """English phrase for a token index, resolving nested constructions."""
    if _seen is None:
        _seen = set()
    if idx in _seen:
        return ''
    _seen.add(idx)
    # construction?
    if idx in constr and constr[idx]['roles']:
        info = constr[idx]
        roles = info['roles']
        if 'op1' in roles or 'op2' in roles:          # coordination
            parts = []
            for r in ('op1', 'op2', 'op3', 'op4'):
                for m in roles.get(r, []):
                    parts.append(_resolve_en(m, rows, concept_dict, constr, _seen))
            join = ' or ' if info['type'] == 'disjunct' else ' and '
            return join.join(p for p in parts if p)
        if 'mod' in roles or 'head' in roles:          # NC: modifier + head
            seq = roles.get('mod', []) + roles.get('head', [])
            return ' '.join(_resolve_en(m, rows, concept_dict, constr, _seen)
                            for m in seq).strip()
        if 'begin' in roles or 'inside' in roles:      # NE
            seq = roles.get('begin', []) + roles.get('inside', [])
            return ' '.join(_resolve_en(m, rows, concept_dict, constr, _seen)
                            for m in seq).strip()
    # plain token: look up its concept then translate/transliterate
    for c in rows:
        if c[1] == idx:
            return _comp_english(c[0], concept_dict).lower()
    return ''


# ── chunk helpers ─────────────────────────────────────────────────────────────

_CHUNK_RE = re.compile(r'\[([^\]]*)\](_[A-Z]+)?')


def _split_chunks(chunk_str):
    """[a]_SUBJ [b] -> [('a','_SUBJ'), ('b','')] preserving order."""
    out = []
    for m in _CHUNK_RE.finditer(chunk_str):
        out.append([m.group(1).strip(), m.group(2) or ''])
    return out


def _join_chunks(chunks):
    return ' '.join(f"[{c}]{tag}" for c, tag in chunks)


# ── the rules ─────────────────────────────────────────────────────────────────

def _rule_split_joined(chunk_str, feats, concept_dict):
    """R1: split joined NE/NC surface tokens into their component words.

    For every NE (begin/inside) and NC (mod/head) group we reconstruct the
    ordered component english forms, build the glued form the pipeline may have
    produced, and expand it back to space separated words.
    """
    rows = feats['rows']
    groups = {}            # cid -> {'begin':[], 'inside':[], 'mod':[], 'head':[]}
    for c in rows:
        if len(c) < 9:
            continue
        constr = c[-1]
        if ':' not in constr:
            continue
        cid, role = constr.split(':', 1)
        if role in ('begin', 'inside', 'mod', 'head'):
            groups.setdefault(cid, {'begin': [], 'inside': [], 'mod': [],
                                    'head': []})[role].append(c[0])

    for cid, g in groups.items():
        if g['begin'] or g['inside']:
            ordered = g['begin'] + g['inside']
        elif g['mod'] or g['head']:
            ordered = g['mod'] + g['head']          # English: modifier + head
        else:
            continue
        if len(ordered) < 2:
            continue
        forms = [_comp_english(x, concept_dict).lower() for x in ordered]
        if any(' ' in f for f in forms):            # already multi-word; skip
            pass
        spaced = ' '.join(forms)
        glued = ''.join(forms)
        if glued == spaced:
            continue
        # also try the reverse (head+mod) glued order in case the pipeline
        # emitted the head first
        glued_rev = ''.join(reversed(forms))
        for cand in (glued, glued_rev):
            chunk_str = re.sub(r'(?<![\w])' + re.escape(cand) + r'(?![\w])',
                               spaced, chunk_str, flags=re.IGNORECASE)
    return chunk_str


def _rule_imperative_first(chunk_str, feats):
    """R5: %imperative -> the verb chunk goes first."""
    if feats['type'] != 'imperative':
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if tag == '_IMPERATIVE':
            chunks.insert(0, chunks.pop(i))
            break
    return _join_chunks(chunks)


def _rule_focus_trailing(chunk_str, feats):
    """R2: the post-positive focus particles भी/ही ('also'/'only').
       * 'only' (ही) is moved to the end of its chunk (post-positive).
       * 'also' (भी) is moved to the end of its chunk only when it sits
         *inside* a prepositional phrase (preceded by a preposition); a
         clause/subject-initial 'also' is left where the chunker placed it.
       Only fires when the sentence carries a BI_1/hI_1 marker."""
    if not feats['has_focus']:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for ci in range(len(chunks)):
        words = chunks[ci][0].split()
        if not words:
            continue
        # 'only' -> trail
        if 'only' in words and words[-1] != 'only':
            words = [w for w in words if w != 'only'] + ['only']
        # 'also' -> trail if PP-internal, OR if it sits on a cp-construction
        # subject (feats['also_trail']); otherwise clause-initial 'also' stays.
        if 'also' in words:
            i = words.index('also')
            pp_internal = 0 < i < len(words) - 1 and words[i - 1].lower() in _PREP_WORDS
            if (pp_internal or feats.get('also_trail')) and words[-1] != 'also':
                words = [w for w in words if w != 'also'] + ['also']
        chunks[ci][0] = ' '.join(words)
    return _join_chunks(chunks)


def _rule_prepositions(chunk_str, feats):
    """R3: realise prepositions the chunker dropped, from the relation:
        k7t (calendar/time)      -> 'on '   before a date chunk
        k5  on a bare demonstrative ('here'/'there') -> 'from '
        rt  (purpose)            -> leading 'to' becomes 'for'
    """
    chunks = _split_chunks(chunk_str)
    rels = feats['rels']
    rt_words = feats['rt_words']

    for ci, (c, tag) in enumerate(chunks):
        low = c.lower()
        words = c.split()
        # k7t date: a chunk that is <number> <monthword> with no leading prep
        if 'k7t' in rels and feats['has_calendar']:
            if words and words[0].isdigit() and not _starts_prep(low):
                chunks[ci][0] = 'on ' + c
                continue
        # k5 on bare demonstrative
        if 'k5' in rels and low in ('here', 'there'):
            chunks[ci][0] = 'from ' + c
            continue
        # rt purpose: 'to X' -> 'for X', but ONLY on the chunk that realises the
        # rt-dependent noun (never a verb chunk, never an unrelated 'to' chunk)
        if rt_words and words and words[0].lower() == 'to' \
                and tag not in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE') \
                and not any(w.lower() in _VERB_AUX for w in words) \
                and any(any(x.lower().startswith(rw) or rw.startswith(x.lower())
                            for x in words) for rw in rt_words):
            chunks[ci][0] = 'for ' + ' '.join(words[1:])
            continue
    return _join_chunks(chunks)


_PREP_WORDS = {'from', 'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
               'about', 'among', 'between', 'through', 'into', 'near', 'over',
               'under', 'after', 'before'}


def _starts_prep(low):
    return low.split()[0] in _PREP_WORDS if low.split() else False


def _rule_quant_several(chunk_str, feats):
    """R9: a 'kaI'/'aneka' quantifier ('several') the pipeline dropped is
    restored immediately before the noun it quantifies (plural-aware), wherever
    that noun surfaces; falls back to the subject chunk."""
    heads = list(feats.get('several_heads') or [])
    every = list(feats.get('every_heads') or [])
    if not heads and not every:
        return chunk_str
    chunks = _split_chunks(chunk_str)

    def _stem(w):
        return w.lower().rstrip('s')

    def _insert(word, head_list):
        for head in head_list:
            if not head:
                continue
            placed = False
            for ci, (c, tag) in enumerate(chunks):
                words = c.split()
                low = [w.lower() for w in words]
                if word in low:
                    placed = True
                    break
                for wi, w in enumerate(low):
                    if _stem(w) == _stem(head):
                        words.insert(wi, word)
                        chunks[ci][0] = ' '.join(words)
                        placed = True
                        break
                if placed:
                    break

    _insert('several', heads)
    # every_heads entries are (determiner_word, head_en) tuples so each carries its
    # own dictionary-resolved word ('all'/'each'/'every').
    for ev in every:
        if isinstance(ev, (tuple, list)) and len(ev) == 2:
            _insert(ev[0], [ev[1]])
        else:
            _insert('every', [ev])
    return _join_chunks(chunks)


def _rule_wh_word(chunk_str, feats):
    """An interrogative $kim is realised as the wh-word selected by its relation
    (k1/k2->what, k7t->when, k7p->where, krvn->how, …) and placed clause-initially.
    """
    wh = feats.get('kim_wh')
    if not wh:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    flat = ' '.join(c for c, _ in chunks).lower().split()
    if wh.split()[0] in flat:
        return chunk_str
    return _join_chunks([['' + wh, '']] + chunks)


def _rule_near_location(chunk_str, feats):
    """When a relative-location (rdl) noun heads a 'near/behind/…' k7p, no 'in'
    is generated and the relational word leads, with a focus 'only' trailing:
    'only in bhāgasū village near' -> 'near bhāgasū village only';
    'in caubaṭiyā near only' -> 'near caubaṭiyā only'."""
    if not feats.get('has_rdl'):
        return chunk_str
    SPATIAL = {'near', 'behind', 'beside', 'front', 'above', 'below',
               'around', 'opposite', 'outside'}
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        if tag in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
            continue
        words = c.split()
        low = [w.lower() for w in words]
        if any(s in low for s in SPATIAL):
            sp = [w for w in words if w.lower() in SPATIAL]
            only = ['only'] if 'only' in low else []
            mid = [w for w in words
                   if w.lower() not in SPATIAL and w.lower() not in ('in', 'only')]
            chunks[ci][0] = ' '.join(sp + mid + only)
    return _join_chunks(chunks)


def _rule_attach_article(chunk_str, feats):
    """A stray article chunk ('[a]'/'[the]') is merged onto the noun phrase it
    determines (after any leading preposition).  The target is, in order: the
    chunk realising the quantified noun (article_heads), else the nearest
    following/preceding noun-phrase chunk — never a verb, copula, adverb-led, or
    already-determined chunk.  ('[a] [railway station] [in the talaśśeri]' ->
    '[a railway station] …', not '[in a the talaśśeri]')."""
    ARTS = {'a', 'an', 'the'}              # NB: 'one' is a numeral, never moved
    advs = feats.get('krvn_en') or set()
    heads = [h for h in (feats.get('article_heads') or []) if h]
    chunks = _split_chunks(chunk_str)

    def _ok_target(cc, tt):
        if tt in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
            return False
        words = cc.split()
        if not words or cc.strip().lower() in ARTS:
            return False
        low = [w.lower() for w in words]
        if low[0] in advs:
            return False
        # already determined (starts with the/a/an, possibly after a prep)?
        j = 1 if low[0] in _PREP_WORDS else 0
        if j < len(low) and low[j] in ('the', 'a', 'an'):
            return False
        content = [w for w in low if w not in _PREP_WORDS]
        if content and all(w in _VERB_AUX or w in _PURE_COPULA for w in content):
            return False
        return True

    def _is_head_chunk(cc):
        low = [w.lower() for w in cc.split()]
        return any(h in low or h + 's' in low
                   or any(w.rstrip('s') == h.rstrip('s') for w in low)
                   for h in heads)

    i = 0
    while i < len(chunks):
        if chunks[i][0].strip().lower() in ARTS and len(chunks) > 1:
            art = chunks[i][0].strip()
            target = None
            # 1) the chunk that actually realises the quantified noun
            for hj, (cc, tt) in enumerate(chunks):
                if hj != i and _ok_target(cc, tt) and _is_head_chunk(cc):
                    target = hj
                    break
            # 2) nearest following, then preceding, valid noun-phrase chunk
            if target is None:
                for hj in list(range(i + 1, len(chunks))) + list(range(i - 1, -1, -1)):
                    if _ok_target(*chunks[hj]):
                        target = hj
                        break
            if target is not None:
                words = chunks[target][0].split()
                if words and words[0].lower() in _PREP_WORDS:
                    chunks[target][0] = words[0] + ' ' + art + ' ' + ' '.join(words[1:])
                else:
                    chunks[target][0] = art + ' ' + chunks[target][0]
                chunks[i] = None
                chunks = [x for x in chunks if x is not None]
                continue
        i += 1
    return _join_chunks(chunks)


def _rule_dist_meas_merge(chunk_str, feats):
    """A distance measure split from its direction/predicate is rejoined:
    '[35 kilometre] [away]' -> '[35 kilometre away]'.

    After merging, a leading 'at ' is stripped when the result contains a
    directional (non-locative) word — e.g. 'at 4 miles ahead' → '4 miles ahead'.
    These direction words never take 'at' in English; the 'at' comes from a
    generic k7p renderer that can't distinguish place-locations from directions.
    """
    if not feats.get('has_dist_meas'):
        return chunk_str
    DIRS = {'away', 'north', 'south', 'east', 'west', 'far',
            'northeast', 'northwest', 'southeast', 'southwest'}
    # Directional words that never take the 'at' preposition
    NOLOC_DIRS = {'away', 'ahead', 'forward', 'onward', 'onwards',
                  'beyond', 'further', 'farther', 'north', 'south',
                  'east', 'west', 'northeast', 'northwest', 'southeast', 'southwest'}
    chunks = _split_chunks(chunk_str)
    for ci in range(len(chunks) - 1):
        c, tag = chunks[ci]
        nc, ntag = chunks[ci + 1]
        w = c.split()
        if w and w[0].rstrip(',.').isdigit() \
                and ntag not in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE') \
                and any(x.lower() in DIRS for x in nc.split()):
            chunks[ci][0] = c + ' ' + nc
            chunks[ci + 1] = None
            break
    chunks = [x for x in chunks if x is not None]
    # Strip spurious 'at ' when merged chunk contains a directional word
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        if (words and words[0].lower() == 'at'
                and any(w.lower() in NOLOC_DIRS for w in words)):
            chunks[ci][0] = ' '.join(words[1:])
    return _join_chunks(chunks)


def _rule_krvn_after_verb(chunk_str, feats):
    """A krvn adverb the chunker placed before its verb/copula trails it:
    'basically were' -> 'were basically', 'completely is' -> 'is completely'."""
    advs = feats.get('krvn_en') or set()
    if not advs:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        if len(words) > 1 and words[0].lower() in advs:
            chunks[ci][0] = ' '.join(words[1:] + [words[0]])
    return _join_chunks(chunks)


def _rule_superlative(chunk_str, feats):
    """Replace the chunker's blanket 'most <adj>' with the grammatical English
    superlative for short adjectives ('most high' -> 'highest')."""
    pairs = feats.get('superl_adjs') or []
    if not pairs:
        return chunk_str
    out = chunk_str
    for adj, sup in pairs:
        if sup == 'most ' + adj:
            continue                       # long adjective: 'most X' is correct
        out = re.sub(r'\bmost\s+' + re.escape(adj) + r'\b', sup, out, flags=re.I)
        out = re.sub(r'\b' + re.escape(adj) + r'\b', sup, out, flags=re.I)
    return out


def _rule_as_complement(chunk_str, feats):
    """An 'as' complement marker leads its phrase: 'public as property' ->
    'as public property'; 'also musical as peak' -> 'also as musical peak'."""
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        w = c.split()
        low = [x.lower() for x in w]
        if 'as' in low:
            j = low.index('as')
            start = 1 if low and low[0] == 'also' else 0
            if j > start:
                w = w[:start] + ['as'] + w[start:j] + w[j + 1:]
                chunks[ci][0] = ' '.join(w)
    return _join_chunks(chunks)


def _rule_span_from_to(chunk_str, feats):
    """A span construction is realised as 'from START to END' (dropping a stray
    locative 'at'): 'at october november' -> 'from october to november'."""
    span = feats.get('span')
    if not span:
        return chunk_str
    start, end = span
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        low = [w.lower() for w in words]
        if start in low and end in low:
            # keep whatever trails the LAST mention of the end token (e.g. a
            # unit like 'meter'), and collapse any duplication
            last_end = max(i for i, w in enumerate(low) if w == end)
            trailing = words[last_end + 1:]
            core = 'from %s to %s' % (start, end)
            chunks[ci][0] = ' '.join([core] + trailing)
            break
    return _join_chunks(chunks)


def _rule_ne_mod_attach(chunk_str, feats):
    """A modifier stranded as its own chunk merges in front of the noun it
    modifies: '[martyr] … bhagata siṃha' -> '… martyr bhagata siṃha';
    '[bhūṃtara] … [air port]' -> '[bhūṃtara air port]'; '[yak and trout]
    [fish]' -> '[yak and trout fish]'."""
    mods = feats.get('mod_attach') or []
    if not mods:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for mod_surf, head_surf in mods:
        if not mod_surf or not head_surf:
            continue
        # the stranded chunk is exactly the modifier surface
        stray = None
        for ci, (c, tag) in enumerate(chunks):
            if c.strip().lower() == mod_surf:
                stray = ci
                break
        if stray is None:
            continue
        head_first = head_surf.split()[0]

        def _match(w):
            wl = w.lower()
            return (wl == head_first or wl == head_first + 's'
                    or wl == head_first + 'es' or wl.rstrip('s') == head_first.rstrip('s'))
        # Prefer non-SUBJ chunks; fall back to SUBJ only if no other match
        candidates = sorted(
            range(len(chunks)),
            key=lambda ci: (1 if chunks[ci][1] == '_SUBJ' else 0)
        )
        for cj in candidates:
            if cj == stray:
                continue
            c, tag = chunks[cj]
            words = c.split()
            pos = next((i for i, w in enumerate(words) if _match(w)), None)
            if pos is not None:
                words[pos:pos] = mod_surf.split()
                chunks[cj][0] = ' '.join(words)
                if chunks[stray][1] == '_SUBJ' and chunks[cj][1] != '_SUBJ':
                    chunks[cj][1] = '_SUBJ'
                chunks[stray] = None
                chunks = [x for x in chunks if x is not None]
                break
    return _join_chunks(chunks)


def _rule_ord_attach(chunk_str, feats):
    """An ordinal leads the noun phrase it modifies: '[biggest lake …] …
    [second]' -> '[second biggest lake …]'."""
    ords = feats.get('ord_attach') or []
    if not ords:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for ord_en, head_surf in ords:
        if not ord_en or not head_surf:
            continue
        stray = next((i for i, (c, t) in enumerate(chunks)
                      if c.strip().lower() == ord_en), None)
        if stray is None:
            continue
        head_first = head_surf.split()[0]
        for cj, (c, tag) in enumerate(chunks):
            if cj == stray:
                continue
            low = [w.lower() for w in c.split()]
            if head_first in low and ord_en not in low:
                chunks[cj][0] = ord_en + ' ' + chunks[cj][0]
                chunks[stray] = None
                chunks = [x for x in chunks if x is not None]
                break
    return _join_chunks(chunks)


def _rule_unit_merge(chunk_str, feats):
    """Merge a stray numeral with a stray measurement unit: '[30] … [acre]' ->
    '[30 acres]'."""
    UNITS = {'acre', 'foot', 'feet', 'metre', 'meter', 'mile', 'inch', 'yard',
             'kilometre', 'kilometer'}
    PLURAL = {'acre': 'acres', 'foot': 'feet', 'metre': 'metres',
              'meter': 'meters', 'mile': 'miles', 'inch': 'inches',
              'yard': 'yards', 'kilometre': 'kilometres', 'kilometer': 'kilometers'}
    chunks = _split_chunks(chunk_str)
    num_i = next((i for i, (c, t) in enumerate(chunks) if c.strip().isdigit()), None)
    unit_i = next((i for i, (c, t) in enumerate(chunks)
                   if c.strip().lower() in UNITS), None)
    if num_i is None or unit_i is None:
        return chunk_str
    n = chunks[num_i][0].strip()
    u = chunks[unit_i][0].strip().lower()
    if int(n) != 1:
        u = PLURAL.get(u, u + 's')
    chunks[num_i][0] = '%s %s' % (n, u)
    chunks[unit_i] = None
    chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_unit_plural(chunk_str, feats):
    """Pluralize a measurement unit that immediately follows a count greater than
    one, whether the unit is its own chunk or embedded in a phrase chunk:
    '35 kilometre away' -> '35 kilometres away', '40 kilometre' -> '40 kilometres'.
    English pluralizes at 2+, so the threshold is > 1."""
    UNIT_PL = {'acre': 'acres', 'foot': 'feet', 'metre': 'metres',
               'meter': 'meters', 'mile': 'miles', 'inch': 'inches',
               'yard': 'yards', 'kilometre': 'kilometres', 'kilometer': 'kilometers',
               'hectare': 'hectares', 'degree': 'degrees', 'hour': 'hours',
               'minute': 'minutes', 'day': 'days', 'year': 'years', 'metres': 'metres'}

    def repl(m):
        num, unit = m.group(1), m.group(2)
        try:
            if float(num) > 1:
                return '%s %s' % (num, UNIT_PL.get(unit.lower(), unit + 's'))
        except ValueError:
            pass
        return m.group(0)

    units = sorted(UNIT_PL, key=len, reverse=True)
    pattern = r'\b(\d+(?:\.\d+)?)\s+(' + '|'.join(units) + r')\b'
    return re.sub(pattern, repl, chunk_str, flags=re.I)


def _rule_drop_dup_operand(chunk_str, feats):
    """Remove a trailing chunk that merely repeats a coordination operand which
    already appears earlier ('… temples and cairns]_SUBJ … [monasteries,]')."""
    chunks = _split_chunks(chunk_str)
    if len(chunks) < 2:
        return chunk_str
    last = chunks[-1]
    if last[1] in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
        return chunk_str
    key = re.sub(r'[^\w]', '', last[0]).lower()
    if not key:
        return chunk_str
    for c, tag in chunks[:-1]:
        words = re.sub(r'[^\w ]', ' ', c).lower().split()
        if key in words:
            return _join_chunks(chunks[:-1])
    return chunk_str


def _rule_temporal_at(chunk_str, feats):
    """Remove spurious 'at' immediately before temporal words in any chunk.
    'at today' -> 'today', 'at daily at evening' -> 'daily evening'."""
    TEMPORAL = {'today', 'now', 'later', 'yesterday', 'tomorrow', 'morning',
                'evening', 'night', 'noon', 'afternoon', 'dawn', 'dusk',
                'midnight', 'daytime', 'nowadays', 'presently', 'daily',
                'january', 'february', 'march', 'april', 'may', 'june', 'july',
                'august', 'september', 'october', 'november', 'december'}
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        new_words = []
        i = 0
        while i < len(words):
            if (words[i].lower() == 'at' and
                    i + 1 < len(words) and
                    words[i + 1].lower() in TEMPORAL):
                i += 1  # skip 'at', keep the temporal word on next iteration
            else:
                new_words.append(words[i])
                i += 1
        chunks[ci][0] = ' '.join(new_words)
    return _join_chunks(chunks)


def _rule_fix_pron_postposition(chunk_str, feats):
    """Fix possessive-pronoun + postposition ordering inside a chunk.

    Hindi r6+postposition patterns render as 'his before' but English
    needs 'before him': swap the postposition to front and convert
    possessive -> object pronoun.
    Pattern: 'his before' -> 'before him', 'her front' -> 'in front of her'

    Also fixes $wyax with pl+distal/respect: generates 'its/his' but should
    be 'their'/'them' for honorific plural (unke/unhe).
    """
    rows = feats.get('rows', [])
    # Check if $wyax has plural + distal/respect → should use they/them/their
    wyax_is_pl_resp = any(
        c[0] == '$wyax' and len(c) > 3 and c[3] == 'pl'
        and len(c) > 6 and ('distal' in (c[6] or '') or 'respect' in (c[6] or ''))
        for c in rows
    )

    _POSS_TO_OBJ = {
        'his': 'him', 'her': 'her', 'their': 'them', 'its': 'it',
        'my': 'me', 'our': 'us', 'your': 'you',
    }
    if wyax_is_pl_resp:
        # Override: any singular pronoun that came from $wyax should be plural
        _POSS_TO_OBJ = {
            'his': 'them', 'her': 'them', 'its': 'them', 'their': 'them',
            'my': 'me', 'our': 'us', 'your': 'you',
        }
    _SPATIAL_POSTS = {'before', 'behind', 'beside', 'alongside', 'front',
                      'back', 'side', 'opposite', 'beneath', 'above', 'below',
                      'around', 'near'}
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.strip().split()
        if len(words) < 2:
            continue
        w0, w1 = words[0].lower(), words[-1].lower()
        if w0 in _POSS_TO_OBJ and w1 in _SPATIAL_POSTS:
            obj = _POSS_TO_OBJ[w0]
            # Prepend the postposition, replace possessive with object form
            remaining = words[1:-1]
            new_words = [words[-1]] + remaining + [obj]
            chunks[ci][0] = ' '.join(new_words)
    return _join_chunks(chunks)


_TIME_PERIOD_WORDS = {'times', 'time', 'age', 'ages', 'era', 'period',
                      'century', 'centuries', 'decade', 'epoch', 'yore',
                      'satayuga', 'satyuga', 'tretā', 'treta', 'dvāpara', 'dvapara',
                      'kaliyuga', 'kalikāla', 'kalikala', 'kali', 'yuga'}


def _rule_fix_temporal_preposition(chunk_str, feats):
    """Replace 'at' with 'in' for abstract time-period phrases (k7t).

    'at an ancient times' -> 'in ancient times'
    """
    if 'k7t' not in feats.get('rels', set()):
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        if not words or words[0].lower() not in ('at', 'on'):
            continue
        low_words = [w.lower() for w in words]
        if not any(w in _TIME_PERIOD_WORDS for w in low_words):
            continue
        # Replace 'at'/'on' with 'in' and drop a/an article if immediately after
        new_words = ['in']
        rest = words[1:]
        if rest and rest[0].lower() in ('a', 'an'):
            # Drop article before plural time noun ('an ancient times' -> 'ancient times')
            if rest[-1].lower() in _TIME_PERIOD_WORDS and rest[-1].lower().endswith('s'):
                rest = rest[1:]
        new_words.extend(rest)
        chunks[ci][0] = ' '.join(new_words)
    return _join_chunks(chunks)


def _rule_lift_r6_from_k5_to_head(chunk_str, feats):
    """Lift 'of <r6>' from a k5 source NE to the head noun when the k5 is inside
    a participial 'going from ... to ...' modifier.

    Pattern: '<head> going from <source> of <r6> to <dest>'
    Result:  '<head> of <r6> going from <source> to <dest>'

    This fires only when k7p is a conj construction (the locative is a conjunction).
    """
    rows = feats['rows']
    has_k7p_conj = any(
        len(c) >= 5 and c[4] and ':' in c[4]
        and c[4].split(':', 1)[1] == 'k7p'
        and c[0].startswith('[conj')
        for c in rows
    )
    if not has_k7p_conj:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        m = re.search(
            r'^(.*?)\s+going from\s+(.+?)\s+of\s+(.+?)\s+to\s+(.+)$',
            c, re.IGNORECASE
        )
        if m:
            head, source, r6, dest = m.group(1), m.group(2), m.group(3), m.group(4)
            chunks[i][0] = f'{head} of {r6} going from {source} to {dest}'
    return _join_chunks(chunks)


def _rule_merge_participial_into_locative_conj(chunk_str, feats):
    """When a k7p locative is a conjunction and the first operand has a participial
    (kqw) modifier with k5/k2p arguments, merge the scattered chunks:
      [going] [to dest] [op1 and in op2] [from source]
    into a single locative chunk:
      [on op1 going from source to dest and on op2]
    """
    rows = feats['rows']
    has_k7p_conj = any(
        c[0].startswith('[conj') and len(c) >= 5 and c[4] and ':' in c[4]
        and c[4].split(':', 1)[1] == 'k7p'
        for c in rows
    )
    has_kqw = any(len(c) >= 4 and c[3] == 'kqw' for c in rows)
    if not has_k7p_conj or not has_kqw:
        return chunk_str

    chunks = _split_chunks(chunk_str)

    # Find the untagged conj locative chunk (contains " and ", no special tag)
    conj_idx = next(
        (i for i, (c, t) in enumerate(chunks)
         if t == '' and ' and ' in c),
        None
    )
    if conj_idx is None:
        return chunk_str

    conj_c = chunks[conj_idx][0]

    # Find participial chunk (a bare verb like "going")
    part_idx = next(
        (i for i, (c, t) in enumerate(chunks)
         if t == '' and c.strip().lower() in ('going', 'coming', 'passing', 'running')),
        None
    )
    if part_idx is None:
        return chunk_str

    # Find "to X" destination and "from X" source chunks
    to_idx = next(
        (i for i, (c, t) in enumerate(chunks)
         if t == '' and c.strip().lower().startswith('to ')),
        None
    )
    from_idx = next(
        (i for i, (c, t) in enumerate(chunks)
         if t == '' and c.strip().lower().startswith('from ')),
        None
    )

    part_word = chunks[part_idx][0].strip()
    to_words = chunks[to_idx][0].strip() if to_idx is not None else ''
    from_words = chunks[from_idx][0].strip() if from_idx is not None else ''

    # Split conj chunk at " and " → op1, op2
    and_pos = conj_c.find(' and ')
    if and_pos < 0:
        return chunk_str
    op1 = conj_c[:and_pos].strip()
    op2 = conj_c[and_pos + 5:].strip()

    # Strip leading preposition from each operand ("in line" → "line")
    def _strip_prep(s):
        words = s.split()
        if words and words[0].lower() in ('in', 'on', 'at'):
            return ' '.join(words[1:])
        return s

    op1 = _strip_prep(op1)
    op2 = _strip_prep(op2)

    # Build participial phrase
    if from_words and to_words:
        part_phrase = f"{part_word} {from_words} {to_words}"
    elif from_words:
        part_phrase = f"{part_word} {from_words}"
    elif to_words:
        part_phrase = f"{part_word} {to_words}"
    else:
        part_phrase = part_word

    new_conj = f"on {op1} {part_phrase} and on {op2}"
    chunks[conj_idx][0] = new_conj

    # Remove the now-merged chunks (collect indices, remove largest first)
    to_remove = sorted({i for i in (part_idx, to_idx, from_idx) if i is not None}, reverse=True)
    for idx in to_remove:
        chunks.pop(idx)

    return _join_chunks(chunks)


def _rule_merge_rt_with_r6(chunk_str, feats):
    """Merge a purpose (rt) 'for X' chunk with its adjacent r6 genitive chunk.

    Pattern: [for see] [mother of goddess] -> [for see of mother goddess]
    Runs only when the sentence has both rt and r6 relations.
    """
    if 'rt' not in feats.get('rels', set()):
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if tag != '' or not c.strip().lower().startswith('for '):
            continue
        # The r6 genitive modifier of the rt noun typically comes BEFORE in the
        # chunk sequence — absorb the preceding untagged chunk.
        if i > 0 and chunks[i - 1][1] == '':
            prev_c = chunks[i - 1][0].strip()
            connector = '' if prev_c.lower().startswith(('of ', 'to ', 'for ')) else 'of '
            chunks[i][0] = c.strip() + ' ' + connector + prev_c
            chunks.pop(i - 1)
            break
    return _join_chunks(chunks)


def _rule_rkl_after_before(chunk_str, feats):
    """A relative-time word ('after'/'before') stranded after its noun is
    reattached in front: '[october] [after]' -> '[after october]'."""
    chunks = _split_chunks(chunk_str)
    for ci in range(len(chunks)):
        if chunks[ci][0].strip().lower() in ('after', 'before') and ci > 0:
            prev = chunks[ci - 1]
            if prev[1] not in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
                chunks[ci][0] = chunks[ci][0].strip() + ' ' + prev[0]
                chunks[ci - 1] = None
                chunks = [x for x in chunks if x is not None]
                break
    return _join_chunks(chunks)


def _rule_strip_index_artifacts(chunk_str, feats):
    """Remove leaked token/coref index artifacts like 'here(2)', 'this(13)',
    'maikloḍagaṃja(2)(2)', drop leaked construction-name words, tidy a malformed
    'along with that' gloss, and discard any chunk left empty."""
    chunks = _split_chunks(chunk_str)
    out = []
    for c, tag in chunks:
        t = re.sub(r'\(\d+\)', '', c)
        t = re.sub(r'^[\[\]]+$', '', t)          # drop stray bracket-only chunks
        t = re.sub(r'\balong with that\b', 'along with', t, flags=re.I)
        t = re.sub(r'\bso\s+(although|though)\b', r'\1', t, flags=re.I)
        t = re.sub(r'\bmost\s+jyādā\b', 'most', t, flags=re.I)
        t = re.sub(r'\bjyādā\b', 'most', t, flags=re.I)
        t = re.sub(r',\s*,', ',', t)
        t = re.sub(r'\s+,', ',', t)
        t = re.sub(r'\b(conjs?|disjuncts?|dvandvas?|xvanxvas?|dist[_ ]?meas)\b', '', t, flags=re.I)
        t = re.sub(r'\b(?:a|an)\s+(this|that|those|these)\b', r'\1', t, flags=re.I)
        t = re.sub(r'[ ]{2,}', ' ', t).strip()
        if t:                                  # drop chunks emptied by stripping
            out.append([t, tag])
    return _join_chunks(out)


def _rule_lone_also(chunk_str, feats):
    """A stray '[also]' chunk attaches (trailing) to the phrase it focuses —
    the nearest preceding non-verb chunk: '… [banārasa or vārāṇasī] [is] [also]'
    -> '… [banārasa or vārāṇasī also] [is]'."""
    chunks = _split_chunks(chunk_str)
    idx = None
    for ci, (c, tag) in enumerate(chunks):
        if c.strip().lower() == 'also':
            idx = ci
            break
    if idx is None:
        return chunk_str
    target = None
    for hj in range(idx - 1, -1, -1):
        if chunks[hj][1] not in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
            target = hj
            break
    if target is None:
        for hj in range(idx + 1, len(chunks)):
            if chunks[hj][1] not in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
                target = hj
                break
    if target is not None:
        chunks[target][0] = chunks[target][0] + ' also'
        chunks[idx] = None
        chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)
    return _join_chunks(chunks)


def _rule_merge_stranded_modifier(chunk_str, feats, concept_dict):
    """R13: a modifier ('mod'/superlative) of the subject head that the chunker
    left as its own chunk (e.g. '[the most nearest]') is merged to the front of
    the subject chunk it modifies."""
    rows = feats['rows']
    # Collect modifier english words whose head noun is the subject head.
    # Restricted to *superlative* attributive modifiers (col3 == 'superl'):
    # these are genuinely attributive (e.g. 'the most nearest'), unlike
    # predicate complements ('very popular', 'an influential king') which share
    # the 'mod' relation but must stay as separate predicate chunks.
    subj_mod_words = []
    for c in rows:
        if len(c) < 5 or ':' not in c[4]:
            continue
        if len(c) <= 3 or c[3] != 'superl':
            continue
        head_idx, rel = c[4].split(':', 1)
        if rel not in ('mod', 'card', 'dem', 'intf'):
            continue
        for d in rows:
            if d[1] == head_idx:
                dh = d[4].split(':', 1)[1] if (len(d) > 4 and ':' in d[4]) else ''
                if dh in ('k1', 'k1s', 'pk1'):
                    w = _comp_english(c[0], concept_dict).lower()
                    if w:
                        subj_mod_words.append(w)
    if not subj_mod_words:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    subj_ci = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_ci is None:
        return chunk_str
    for ci in list(range(len(chunks))):
        if ci == subj_ci:
            continue
        c, tag = chunks[ci]
        if tag:                       # only merge untagged modifier chunks
            continue
        words = c.lower().split()
        if any(mw in words for mw in subj_mod_words) and len(words) <= 4 \
                and not any(w in _PREP_WORDS for w in words):
            # prepend this chunk to the subject chunk, then drop it
            chunks[subj_ci][0] = c + ' ' + chunks[subj_ci][0]
            chunks[ci] = None
    chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_measure_about(chunk_str, feats):
    """R10: an 'approx' measurement modifier (wakarIbana = 'about') is realised
    in front of the measure chunk, and its unit noun is pluralised."""
    if not feats['has_approx']:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        # measure chunk = contains a standalone number
        if any(w.isdigit() for w in words):
            if words[0].lower() != 'about':
                # pluralise the trailing unit word (kilometre -> kilometres)
                if words and re.fullmatch(r'[a-zāīūṃṭḍ]+', words[-1].lower()) \
                        and not words[-1].lower().endswith('s'):
                    words[-1] = words[-1] + 's'
                chunks[ci][0] = 'about ' + ' '.join(words)
                break
    return _join_chunks(chunks)


def _rule_surface(chunk_str):
    """R11/R12: small, always-safe English surface fixes.
       * 'a of'/'an of'/'the of'  -> 'of a'/'of an'/'of the'
       * 'in <spatial-prep>'      -> drop the redundant 'in'
    """
    chunk_str = re.sub(r'\b(a|an|the) (of)\b', r'\2 \1', chunk_str)
    chunk_str = re.sub(r'\bin (near|behind|beside|under|over|inside|outside|'
                       r'opposite|between|among|atop)\b', r'\1', chunk_str)
    return chunk_str


_VERB_AUX = {'is', 'are', 'was', 'were', 'be', 'been', 'being', 'can', 'could',
             'will', 'would', 'shall', 'should', 'may', 'might', 'must',
             'have', 'has', 'had', 'do', 'does', 'did', 'get', 'got'}


def _rule_passive(chunk_str, feats):
    """R6: mark _PASSIVE when the main verb really contains a passive auxiliary
    (jA / jAwA as an *inline* component, not merely a [shade:jA] suggestion).
    Only the genuine verb chunk is (re)tagged, and only if nothing is already
    tagged _PASSIVE."""
    if not feats['is_passive']:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    if any(tag == '_PASSIVE' for _, tag in chunks):
        return chunk_str

    def is_verb_chunk(c, tag):
        if tag == '_SUBJ':
            return False
        if tag == '_ACTIVE':
            return True
        words = [w.lower() for w in c.split()]
        return any(w in _VERB_AUX for w in words)

    # prefer an existing _ACTIVE verb chunk; else the last verb-looking chunk
    target = None
    for ci, (c, tag) in enumerate(chunks):
        if tag == '_ACTIVE' and is_verb_chunk(c, tag):
            target = ci
    if target is None:
        for ci in range(len(chunks) - 1, -1, -1):
            c, tag = chunks[ci]
            if is_verb_chunk(c, tag):
                target = ci
                break
    if target is None:
        return chunk_str
    words = chunks[target][0].split()
    # a leading manner adverb (-ly) in a verb complex trails the verb
    if len(words) > 1 and words[0].endswith('ly'):
        chunks[target][0] = ' '.join(words[1:] + [words[0]])
    chunks[target][1] = '_PASSIVE'
    return _join_chunks(chunks)


# ── feature extraction ────────────────────────────────────────────────────────

def _english_superlative(adj):
    """Grammatical English superlative of a single adjective.
    Short adjectives take -est (high->highest, big->biggest, large->largest);
    longer adjectives take 'most' (beautiful->most beautiful)."""
    a = adj.lower().strip()
    if not a or any(ord(ch) > 127 for ch in a):
        return 'most ' + a            # transliterated / non-English: keep 'most'
    irregular = {'good': 'best', 'well': 'best', 'bad': 'worst',
                 'far': 'farthest', 'little': 'least', 'much': 'most',
                 'many': 'most', 'old': 'oldest'}
    if a in irregular:
        return irregular[a]
    if not a.isalpha():
        return 'most ' + a
    syl = len(re.findall(r'[aeiouy]+', a))
    two_ok = a.endswith(('y', 'le', 'ow', 'er'))
    if syl <= 1 or (syl == 2 and two_ok):
        if a.endswith('e'):
            return a + 'st'
        if a.endswith('y') and len(a) > 1 and a[-2] not in 'aeiou':
            return a[:-1] + 'iest'
        # double a final consonant after a single short vowel (big -> biggest)
        if syl <= 1 and re.search(r'[^aeiou][aeiou][^aeiouwxy]$', a):
            return a + a[-1] + 'est'
        return a + 'est'
    return 'most ' + a


def _build_features(rec, concept_dict):
    rows = rec['rows']
    feats = {'rows': rows, 'type': rec['type']}

    rels = set()
    rt_words = set()
    has_focus = False
    has_kai = False
    kai_head_en = None
    kai_head_subj = False
    has_approx = False
    has_calendar = False
    main_tam = ''
    for c in rows:
        # relation
        if len(c) > 4 and ':' in c[4]:
            rel = c[4].split(':', 1)[1]
            rels.add(rel)
            if c[4] == '0:main':
                main_tam = c[0]
            if rel == 'rt':
                rt_words.add(_comp_english(c[0], concept_dict).lower())
        # focus markers anywhere in the marker columns
        for col in c[5:9] if len(c) >= 9 else c[5:]:
            if col in ('BI_1', 'hI_1'):
                has_focus = True
        # kaI quantifier
        if c[0].startswith('kaI'):
            has_kai = True
            if len(c) > 4 and ':' in c[4]:
                head_idx = c[4].split(':', 1)[0]
                for d in rows:
                    if d[1] == head_idx:
                        kai_head_en = _comp_english(d[0], concept_dict).lower()
                        dh = d[4].split(':', 1)[1] if (len(d) > 4 and ':' in d[4]) else ''
                        if dh in ('k1', 'k1s', 'pk1'):
                            kai_head_subj = True
        # approximation modifier
        if any(tok.startswith('wakarIbana') for tok in c):
            has_approx = True
        # calendar construction
        if len(c) >= 3 and c[2] == 'moy':
            has_calendar = True
        if len(c) >= 9 and c[-1].endswith(':component'):
            has_calendar = True

    feats['rels'] = rels
    feats['rt_words'] = rt_words
    feats['constr'] = _parse_constructions(rows)

    # cp light-verb: kriyAmUla = adjectival/nominal complement, verbalizer =
    # a 'feel/seem/become' style finite verb -> render "verb complement".
    cp_lv = None
    for cid, info in feats['constr'].items():
        if info['type'] == 'cp' and 'kriyAmUla' in info['roles'] \
                and 'verbalizer' in info['roles']:
            kr = info['roles']['kriyAmUla'][0]
            vb = info['roles']['verbalizer'][0]
            kr_en = vb_en = None
            for c in rows:
                if c[1] == kr:
                    kr_en = _comp_english(c[0], concept_dict).lower()
                if c[1] == vb:
                    vb_en = _comp_english(c[0], concept_dict).lower()
            # only the 'laga' (feel/seem) light verb gets the V+complement order
            if kr_en and vb_en and any(c[1] == vb and c[0].startswith('laga')
                                       for c in rows):
                cp_lv = (kr_en, vb_en if not vb_en.endswith('s') else vb_en)
    feats['cp_lightverb'] = (cp_lv[0], 'feels') if cp_lv else None

    # focus particle भी ('also') is post-positive (trails its chunk) when it
    # sits on the k1 subject of a cp (light-verb) construction — e.g.
    # "wind mill भी attracts" -> "... wind mill also".  On a plain (non-cp)
    # clause the chunker's clause-initial 'also' is kept (matches human gold).
    cp_cids = {cid for cid, info in feats['constr'].items()
               if info['type'] == 'cp'}
    also_trail = False
    for c in rows:
        markers = c[5:9] if len(c) >= 9 else c[5:]
        if 'BI_1' in markers and len(c) > 4 and ':' in c[4]:
            head, rel = c[4].split(':', 1)
            if rel in ('k1', 'k1s', 'pk1') and head in cp_cids:
                also_trail = True
    feats['also_trail'] = also_trail
    feats['has_focus'] = has_focus
    feats['has_kai'] = has_kai
    feats['kai_head_en'] = kai_head_en
    feats['kai_head_subj'] = kai_head_subj
    feats['has_approx'] = has_approx
    feats['has_calendar'] = has_calendar

    # passive: detected via (a) the jA/jAwA passive morpheme in the main TAM,
    # OR (b) the sentence_type marker %pass_affirmative in the USR.
    # Using 'en'/'pp' TAM tokens is WRONG — present-perfect active sentences
    # (yA_hE_1 = "has gone") also have 'en' TAM but are NOT passive.
    is_passive = False
    if main_tam:
        body = main_tam
        if re.search(r'(_jA_|_jAwA|-jA_|jA_\d*wA)', body) or '_jAwA_' in body:
            is_passive = True
    # sentence_type 'pass_affirmative' / 'pass-affirmative' overrides TAM check
    stype = rec.get('type', '').lower()
    if 'pass' in stype and ('affirmative' in stype or 'negative' in stype):
        is_passive = True
    feats['is_passive'] = is_passive
    feats['main_tam'] = main_tam

    # --- features for the 067-098 feedback ---
    cdict = concept_dict
    # quantifiers that surface as 'several' (kaI/aneka); 'eka' is an article
    several_heads, article_heads, several_subj = [], [], False
    every_heads = []
    krvn_en = set()
    for c in rows:
        if len(c) > 4 and ':' in c[4]:
            hidx, rel = c[4].split(':', 1)
            if rel == 'quant':
                head_en = None
                head_subj = False
                for d in rows:
                    if d[1] == hidx:
                        head_en = _comp_english(d[0], cdict).lower()
                        dh = d[4].split(':', 1)[1] if (len(d) > 4 and ':' in d[4]) else ''
                        head_subj = dh in ('k1', 'k1s', 'pk1')
                base = c[0].split('_')[0]
                if base in ('kaI', 'kayI', 'aneka', 'anek', 'kaeka',
                            'hara', 'prawi'):
                    # Quantifier determiners that the pipeline drops are restored
                    # from the dictionary (sense-specific) — never hardcoded. e.g.
                    # kaI_3->'various', aneka_1->'many', hara_7->'all', hara_2->'every'.
                    # ('eka' is NOT handled here: it surfaces its own article/numeral
                    #  from the dictionary via the normal path, so re-inserting it
                    #  would duplicate the determiner.)
                    if head_en:
                        det_en = _comp_english(c[0], cdict).lower()
                        if det_en and not det_en.startswith('#'):
                            every_heads.append((det_en, head_en))
                            if base in ('kaI', 'kayI', 'aneka', 'anek', 'kaeka'):
                                several_subj = several_subj or head_subj
            if rel == 'krvn':
                # move the adverb after the verb ONLY when it modifies a verb;
                # a krvn modifying a predicate adjective/nominal (k1s etc.) keeps
                # its place ('equal favourite', not 'favourite equal')
                head_rel = ''
                for d in rows:
                    if d[1] == hidx:
                        head_rel = (d[4].split(':', 1)[1]
                                    if (len(d) > 4 and ':' in d[4]) else '')
                if head_rel not in ('k1', 'k1s', 'k2', 'k2s', 'pk1',
                                    'k4', 'k4a', 'r6', 'mod', 'k7p'):
                    krvn_en.add(_comp_english(c[0], cdict).lower())
    feats['several_heads'] = several_heads
    feats['several_subj'] = several_subj
    feats['article_heads'] = article_heads
    feats['every_heads'] = every_heads
    feats['krvn_en'] = krvn_en

    # interrogative $kim -> wh word chosen by its syntactic relation
    wh = None
    for c in rows:
        if c[0] == '$kim' and len(c) > 4 and ':' in c[4]:
            rel = c[4].split(':', 1)[1]
            wh = {'k7t': 'when', 'k7p': 'where', 'krvn': 'how',
                  'k5': 'from where', 'rh': 'why', 'rsk': 'why',
                  'rsm': 'how'}.get(rel, 'what')
    feats['kim_wh'] = wh

    # rdl (relative location) -> suppress 'in' on a 'near' k7p
    feats['has_rdl'] = any(len(c) > 4 and ':' in c[4]
                           and c[4].split(':', 1)[1] == 'rdl' for c in rows)
    # distance measure present
    feats['has_dist_meas'] = any(
        (len(c) > 4 and ':' in c[4] and c[4].split(':', 1)[1] == 'rmeas')
        or re.fullmatch(r'\[dist_meas_\d+\]', c[0]) for c in rows)

    # english of the BI_1-bearing token/construction (for a stray 'also')
    fh = None
    for c in rows:
        markers = c[5:9] if len(c) >= 9 else c[5:]
        if 'BI_1' in markers:
            fh = (_resolve_en(c[1], rows, cdict, feats['constr']).lower()
                  if c[1] in feats['constr']
                  else _comp_english(c[0], cdict).lower())
    feats['focus_host_en'] = fh

    # superlative adjectives (col-3 feature 'superl') -> proper English form
    superl = []
    for c in rows:
        if len(c) > 3 and c[3] == 'superl':
            en = _comp_english(c[0], cdict).lower()
            if en:
                superl.append((en, _english_superlative(en)))
    feats['superl_adjs'] = superl

    # span construction (start .. end) -> 'from START to END'
    span = None
    start_en = end_en = None
    for c in rows:
        marks = ' '.join(c[5:]) if len(c) > 5 else ''
        for tok in c[8:] if len(c) > 8 else []:
            if tok.endswith(':start'):
                start_en = _comp_english(c[0], cdict).lower()
            if tok.endswith(':end'):
                end_en = _comp_english(c[0], cdict).lower()
    if start_en and end_en:
        span = (start_en, end_en)
    feats['span'] = span

    # modifiers of a coordination construction (distribute over both operands):
    # 'simple' mod of conj -> 'simple sweater and shawl'
    conj_mods = {}
    for cid, info in feats['constr'].items():
        if info['type'] in ('conj', 'dvandva', 'disjunct'):
            for c in rows:
                if len(c) > 4 and ':' in c[4]:
                    h, r = c[4].split(':', 1)
                    if h == cid and r == 'mod':
                        conj_mods.setdefault(cid, []).append(
                            _comp_english(c[0], cdict).lower())
    feats['conj_mods'] = conj_mods

    # a modifier stranded from the noun it modifies should attach before that
    # noun's surface.  Covers an adjective/NE modifier ('martyr' -> bhagata
    # siṃha; 'bhūṃtara' -> air port) and a coordination acting as a modifier
    # ('yak and trout' -> fish).
    mod_attach = []
    nominal_rels = ('k1', 'k2', 'k7p', 'k7', 'k4', 'k5', 'rt', 'r6',
                    'k1s', 'k2s', 'mod', 'rdl')
    for c in rows:
        if len(c) > 4 and ':' in c[4] and c[4].split(':', 1)[1] == 'mod':
            h = c[4].split(':', 1)[0]
            head = next((d for d in rows if d[1] == h), None)
            if not head:
                continue
            head_rel = head[4].split(':', 1)[1] if (len(head) > 4 and ':' in head[4]) else ''
            head_is_noun = (head[0].startswith('[ne_') or head[0].startswith('[nc_')
                            or (head_rel in nominal_rels and not _is_adjective(head[0])))
            if not head_is_noun:
                continue
            mod_surf = (_resolve_en(c[1], rows, cdict, feats['constr'])
                        if c[1] in feats['constr']
                        else _comp_english(c[0], cdict)).lower()
            head_surf = _resolve_en(head[1], rows, cdict, feats['constr']).lower()
            if mod_surf and head_surf:
                mod_attach.append((mod_surf, head_surf))
    feats['mod_attach'] = mod_attach
    feats['ne_mods'] = []  # superseded by mod_attach

    # an ordinal modifier leads the noun phrase it modifies:
    # 'second' + 'biggest lake …' -> 'second biggest lake …'
    ord_attach = []
    for c in rows:
        if len(c) > 4 and ':' in c[4] and c[4].split(':', 1)[1] == 'ord':
            h = c[4].split(':', 1)[0]
            head = next((d for d in rows if d[1] == h), None)
            if head:
                ord_attach.append((_comp_english(c[0], cdict).lower(),
                                   _resolve_en(head[1], rows, cdict, feats['constr']).lower()))
    feats['ord_attach'] = ord_attach

    # english words that are adjectives (used to gate the 'as' reorder)
    adj_en = set()
    for c in rows:
        if _is_adjective(c[0]):
            adj_en.add(_comp_english(c[0], cdict).lower())
    feats['adj_en'] = adj_en

    # subject recovery: english surface of the main verb's k1/k1s/pk1, used only
    # to restore a subject the chunker dropped entirely (see recovery rule).
    subj_en = None
    main_idx = next((c[1] for c in rows if c[4] == '0:main'), None)
    if main_idx:
        for c in rows:
            if len(c) > 4 and ':' in c[4]:
                h, rel = c[4].split(':', 1)
                if h == main_idx and rel in ('k1', 'k1s', 'pk1'):
                    s = _resolve_en(c[1], rows, cdict, feats['constr'])
                    if s and s.strip():
                        subj_en = s.strip()
                    break
    feats['subj_en'] = subj_en

    # $wyax pl + distal + k1 relation → surface subject should be "they"
    feats['wyax_is_k1_pl_distal'] = any(
        c[0] == '$wyax' and len(c) > 3 and c[3] == 'pl'
        and len(c) > 4 and c[4] and ':' in c[4]
        and c[4].split(':', 1)[1] == 'k1'
        and len(c) > 6 and 'distal' in (c[6] or '')
        for c in rows
    )

    # NC constructions that act as r6 of a host noun → generate "NC host" not "host of NC"
    nc_r6_hosts = []
    for cid, info in feats['constr'].items():
        if info['type'] == 'nc' and info['rel'] and info['rel'][1] == 'r6':
            host_idx = info['rel'][0]
            nc_en = _resolve_en(cid, rows, cdict, feats['constr']).lower().strip()
            host_row = next((c for c in rows if c[1] == host_idx), None)
            if host_row:
                host_en = _comp_english(host_row[0], cdict).lower().strip()
                if nc_en and host_en:
                    nc_r6_hosts.append((nc_en, host_en))
    feats['nc_r6_hosts'] = nc_r6_hosts

    return feats


_STRUCT_TOKENS = {'cp', 'nc', 'ne', 'conj', 'waw', '#waw', 'disjunct',
                  'compound', 'timemeas', 'span', 'dvandva', 'spatial',
                  'dist', 'meas', 'meases', 'dist_meas', 'avayavi', 'avayavI', 'rsm',
                  'measure'}
_DUP_COLLAPSE = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
                 'to', 'from', 'and', 'or', 'is', 'are', 'only', 'also', 'near'}


def _rule_strip_struct_tokens(chunk_str):
    """R16: remove internal construction markers (cp/nc/conj/dvandva/spatial/…)
    that leaked into the surface, and any '<word>_<digits>' residue; drop a
    chunk left empty."""
    chunks = _split_chunks(chunk_str)
    out = []
    for c, tag in chunks:
        words = [w for w in c.split()
                 if w.lower() not in _STRUCT_TOKENS
                 and not re.fullmatch(r'[A-Za-z]+_\d+', w)
                 and not re.fullmatch(r'\[ne[_\d]*\]?', w, re.I)]
        if words:
            out.append([' '.join(words), tag])
    return _join_chunks(out)


def _rule_dedup_function_words(chunk_str):
    """R15: collapse an adjacent duplicated function word ('the the' -> 'the',
    'with with' -> 'with')."""
    chunks = _split_chunks(chunk_str)
    for ci in range(len(chunks)):
        words = chunks[ci][0].split()
        new = []
        for w in words:
            if new and w.lower() == new[-1].lower() and w.lower() in _DUP_COLLAPSE:
                continue
            new.append(w)
        chunks[ci][0] = ' '.join(new)
    return _join_chunks(chunks)


def _rule_coordination(chunk_str, feats, concept_dict):
    """R18: realise conj / dvandva (samasa) constructions.
       * operands are emitted in op1, op2, … order joined by 'and' ('or' for
         disjunction) — the construction word itself is never emitted;
       * the coordinated phrase is attached to the head it modifies (with the
         right preposition for an r6 genitive), and the scattered operand
         chunks are removed.
    """
    rows = feats['rows']
    constr = feats['constr']
    coords = [(cid, info) for cid, info in constr.items()
              if info['type'] in ('conj', 'dvandva', 'disjunct')
              and ('op1' in info['roles'] or 'op2' in info['roles'])]
    if not coords:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for cid, info in coords:
        op_idx = []
        for r in ('op1', 'op2', 'op3', 'op4'):
            op_idx += info['roles'].get(r, [])
        operands = [_resolve_en(m, rows, concept_dict, constr) for m in op_idx]
        operands = [o for o in operands if o]
        if len(operands) < 2:
            continue
        join = ' or ' if info['type'] == 'disjunct' else ' and '
        phrase = join.join(operands)
        # a modifier of the whole coordination distributes in front of it
        # ('simple' mod of conj -> 'simple sweater and shawl')
        cmods = (feats.get('conj_mods') or {}).get(cid, [])
        if cmods:
            phrase = ' '.join(cmods) + ' ' + phrase
        op_words = set(w for o in operands for w in o.split())
        op_words |= {w for m in cmods for w in m.split()}

        # locate chunks that consist only of operand words (+ connectors and
        # the construction's own preposition)
        connect = {'and', 'or', 'of', 'the', 'a', 'an'} | _PREP_WORDS
        op_chunk_ids = []
        for ci, (c, tag) in enumerate(chunks):
            if c is None:
                continue
            # strip trailing punctuation before matching ('[śiva,]' etc.)
            ws = [w.lower().rstrip(',.;:') for w in c.split()]
            if ws and all(w in op_words or w in connect for w in ws) \
                    and any(w in op_words for w in ws):
                op_chunk_ids.append(ci)
        if not op_chunk_ids:
            continue

        head_idx, rel = info['rel'] if info['rel'] else (None, None)

        # CASE 1 — operands already sit in a single chunk: put them in op1..opN
        # order and hoist the construction's own preposition to the FRONT
        # ('damana and in diyu' -> 'in damana and diyu').
        if len(op_chunk_ids) == 1:
            ci = op_chunk_ids[0]
            fw = chunks[ci][0].split()
            op_words_l = {w.lower() for o in operands for w in o.split()}
            lead = ''
            for w in fw:
                if w.lower() in _PREP_WORDS and w.lower() not in op_words_l:
                    lead = w + ' '
                    break
            chunks[ci][0] = lead + phrase
            # a coordinated phrase that is NOT a core subject must not stay _SUBJ
            # k1s is a predicate complement (adjective/nominal), not a grammatical subject
            if chunks[ci][1] == '_SUBJ' and rel not in ('k1', 'pk1'):
                chunks[ci][1] = ''
            # drop a now-duplicated standalone modifier chunk ('[simple]')
            if cmods:
                for cj in range(len(chunks)):
                    if cj != ci and chunks[cj] is not None \
                            and chunks[cj][0].strip().lower() in cmods:
                        chunks[cj] = None
                chunks = [x for x in chunks if x is not None]
            continue

        # CASE 2 — operands scattered across chunks: merge them. For an r6
        # (genitive) modifier, attach 'of <phrase>' to the head's chunk; for a
        # core argument, build a single standalone chunk.
        prep = 'of ' if rel == 'r6' else ''
        head_en = None
        head_is_subj = False
        for c in rows:
            if c[1] == head_idx:
                head_en = _comp_english(c[0], concept_dict).lower()
                hr = c[4].split(':', 1)[1] if (len(c) > 4 and ':' in c[4]) else ''
                if hr in ('k1', 'pk1'):
                    head_is_subj = True
        head_ci = None
        if rel in ('r6', 'mod') and head_en:
            hstem = head_en.rstrip('s')
            for ci, (c, tag) in enumerate(chunks):
                if c is None or ci in op_chunk_ids:
                    continue
                if tag in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
                    continue
                if any(w.lower().rstrip('s') == hstem for w in c.split()):
                    head_ci = ci
                    break
            if head_ci is None and head_is_subj:
                for ci, (c, tag) in enumerate(chunks):
                    if c is not None and ci not in op_chunk_ids and tag == '_SUBJ':
                        head_ci = ci
                        break
        if head_ci is not None:
            chunks[head_ci][0] = chunks[head_ci][0] + ' ' + prep + phrase
            for ci in op_chunk_ids:
                chunks[ci] = None
        else:
            first = op_chunk_ids[0]
            tag = chunks[first][1]
            chunks[first] = [phrase, tag]
            for ci in op_chunk_ids[1:]:
                chunks[ci] = None
        chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_part_whole(chunk_str, feats, concept_dict):
    """R20: a spatial part/whole construction is realised as ONE locative chunk
    in whole-then-part order ('in the bailāḍīlā in gesata hāusa'), placed before
    the verb.  Handles the case where the chunker trapped the 'whole' phrase
    inside the verb chunk (… stayed the bailāḍīlā in)."""
    rows = feats['rows']
    constr = feats['constr']
    spats = [(cid, info) for cid, info in constr.items()
             if ('whole' in info['roles'] and 'part' in info['roles'])]
    if not spats:
        return chunk_str
    _LOCFUNC = {'the', 'a', 'an', 'in', 'on', 'at', 'into', 'inside'}
    _PREPS = ('in', 'on', 'at', 'into', 'inside')

    def _verbal(c, tag):
        if tag in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
            return True
        return any(w.lower() in _VERB_AUX for w in c.split())

    chunks = _split_chunks(chunk_str)
    for cid, info in spats:
        whole_w = set()
        for m in info['roles'].get('whole', []):
            for w in _resolve_en(m, rows, concept_dict, constr).lower().split():
                if w not in _LOCFUNC:
                    whole_w.add(w)
        part_w = set()
        for m in info['roles'].get('part', []):
            for w in _resolve_en(m, rows, concept_dict, constr).lower().split():
                if w not in _LOCFUNC:
                    part_w.add(w)
        if not whole_w or not part_w:
            continue
        # the part chunk (a non-verb chunk that carries a part word)
        part_idx = None
        for ci, (c, tag) in enumerate(chunks):
            if _verbal(c, tag):
                continue
            if any(w.lower() in part_w for w in c.split()):
                part_idx = ci
                break
        if part_idx is None:
            continue
        # pull the whole phrase out of wherever it sits (incl. the verb chunk)
        whole_tokens = []
        for ci, (c, tag) in enumerate(chunks):
            if ci == part_idx:
                continue
            words = c.split()
            if not any(w.lower() in whole_w for w in words):
                continue
            out, buf = [], []
            for w in words:
                lw = w.lower()
                if lw in whole_w or lw in _LOCFUNC:
                    buf.append(w)
                else:
                    (whole_tokens if any(b.lower() in whole_w for b in buf)
                     else out).extend(buf)
                    buf = []
                    out.append(w)
            (whole_tokens if any(b.lower() in whole_w for b in buf)
             else out).extend(buf)
            if whole_tokens:
                if out:                       # verb (or other) words remain
                    chunks[ci][0] = ' '.join(out)
                else:                         # chunk was purely the whole phrase
                    chunks[ci] = None
                break
        if not whole_tokens:
            continue
        prep = [w for w in whole_tokens if w.lower() in _PREPS][:1] or ['in']
        det = [w for w in whole_tokens if w.lower() in ('the', 'a', 'an')][:1]
        nouns = [w for w in whole_tokens if w.lower() in whole_w]
        whole_surface = ' '.join(prep + det + nouns)
        chunks[part_idx][0] = whole_surface + ' ' + chunks[part_idx][0]
        chunks = [x for x in chunks if x is not None]
    # locative (merged) precedes the verb; detect verb chunks by content because
    # the passive tag is not applied until later (only part/whole sents reach here)
    nonverb = [c for c in chunks if not _verbal(c[0], c[1])]
    verb = [c for c in chunks if _verbal(c[0], c[1])]
    return _join_chunks(nonverb + verb)


def _rule_genitive_of_order(chunk_str, feats, concept_dict):
    """R19: a genitive 'of' that the chunker placed after an adjective is moved
    before it ('good of grade' -> 'of good grade'); fires only when the first
    word is a modifier (mod relation) of the noun that follows the 'of'."""
    rows = feats['rows']
    # english forms of *adjective* modifiers only (a noun-modifier like 'lime'
    # legitimately keeps 'lime of stone'; only true adjectives hoist the 'of')
    mod_en = set()
    for c in rows:
        if len(c) > 4 and ':' in c[4] and c[4].split(':', 1)[1] == 'mod' \
                and _is_adjective(c[0]):
            mod_en.add(_comp_english(c[0], concept_dict).lower())
    if not mod_en:
        mod_en = set()  # still fall through to the NE-modifier reorder below
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        if len(words) >= 3 and words[1].lower() == 'of' \
                and words[0].lower() in mod_en:
            chunks[ci][0] = 'of ' + words[0] + ' ' + ' '.join(words[2:])

    # NE-modifier genitive: "the <NE> of <head>" -> "the <head> of <NE>"
    # (e.g. "the ke.ke. of line" -> "the line of ke.ke."). Fires only when the
    # NE is the recorded 'mod' of the noun that follows 'of'.
    constr = feats['constr']
    ne_heads = set()   # english of the noun an NE modifies (lowercased)
    for c in rows:
        if re.fullmatch(r'\[ne_\d+\]', c[0]) and len(c) > 4 and ':' in c[4]:
            h, r = c[4].split(':', 1)
            if r == 'mod':
                head_en = _resolve_en(h, rows, concept_dict, constr).lower()
                if head_en:
                    ne_heads.add(head_en)
    if ne_heads:
        chunks = _split_chunks(_join_chunks(chunks))
        for ci, (c, tag) in enumerate(chunks):
            words = c.split()
            if len(words) == 4 and words[0].lower() == 'the' \
                    and words[2].lower() == 'of' \
                    and words[3].lower() in ne_heads:
                chunks[ci][0] = 'the ' + words[3] + ' of ' + words[1]
    return _join_chunks(chunks)


def _rule_cp_light_verb(chunk_str, feats):
    """R21: a light-verb predicate whose nominal/adjectival part and finite
    'feel/seem' verb were split ('… good … feels') is merged into one chunk in
    verb+complement order ('feels good')."""
    if not feats.get('cp_lightverb'):
        return chunk_str
    compl, verb = feats['cp_lightverb']
    chunks = _split_chunks(chunk_str)
    ci_compl = ci_verb = None
    for ci, (c, tag) in enumerate(chunks):
        ws = [w.lower().rstrip(',.;:') for w in c.split()]
        if ws == [compl]:
            ci_compl = ci
        if verb in ws and tag in ('_ACTIVE', '_PASSIVE', ''):
            ci_verb = ci
    if ci_compl is not None and ci_verb is not None and ci_compl != ci_verb:
        chunks[ci_verb][0] = verb + ' ' + compl
        chunks[ci_compl] = None
        chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_strip_struct_tokens2(chunk_str):
    return _rule_strip_struct_tokens(chunk_str)


# ── public entry point ─────────────────────────────────────────────────────────

_PURE_COPULA = {'is', 'are', 'was', 'were', 'be', 'been', 'am'}


_AN_KEEP_A = {'unique', 'university', 'union', 'unit', 'united', 'used', 'useful',
              'use', 'user', 'one', 'once', 'european', 'euro', 'universal',
              'utensil', 'ubiquitous', 'usual'}
_A_USE_AN = {'hour', 'honest', 'honour', 'honor', 'heir', 'honourable',
             'honorable', 'hourly'}


def _rule_article_phonetics(chunk_str, feats):
    """Choose 'a' vs 'an' by the SOUND of the next word, with the usual English
    exceptions ('a unique', 'an hour')."""
    def repl(m):
        art, w = m.group(1), m.group(2)
        wl = w.lower()
        vowel_sound = (wl[0] in 'aeio'
                       or (wl[0] == 'u' and wl not in _AN_KEEP_A)
                       or wl in _A_USE_AN)
        fixed = 'an' if vowel_sound else 'a'
        if art[0].isupper():
            fixed = fixed.capitalize()
        return '%s %s' % (fixed, w)
    return re.sub(r'\b([Aa]n?) ([A-Za-z]\w*)', repl, chunk_str)


def _rule_used_to(chunk_str, feats):
    """Normalise the habitual-past TAM that the chunker splits: a stray
    '[to used]' / '[used] [to]' becomes '[used to]' kept before the verb."""
    # the auxiliary may surface as its raw term 'use_to' / 'used_to'
    # (e.g. '[use_to go]') -> inflect to 'used to' ('used to go').
    chunk_str = re.sub(r'\buse[d]?_to\b', 'used to', chunk_str, flags=re.I)
    chunks = _split_chunks(chunk_str)
    # collapse 'to used' -> 'used to' inside a single chunk
    for ci, (c, tag) in enumerate(chunks):
        if re.fullmatch(r'to used', c.strip(), flags=re.I):
            chunks[ci][0] = 'used to'
    # merge an adjacent '[used]' and '[to]' pair
    for ci in range(len(chunks) - 1):
        a = chunks[ci][0].strip().lower()
        b = chunks[ci + 1][0].strip().lower()
        if a == 'used' and b == 'to':
            chunks[ci][0] = 'used to'
            chunks[ci + 1] = None
            chunks = [x for x in chunks if x is not None]
            break
    return _join_chunks(chunks)


def _rule_remove_lone_prepositions(chunk_str, feats):
    """Remove standalone preposition chunks and lone #-unknown nonfinite verb chunks.

    Case 1 — Lone prepositions: arise when a source pronoun was consumed by
    dist_meas merge but its postposition word remains as a residual chunk.
    e.g. [from] → removed.

    Case 2 — Lone #-unknown words with _ACTIVE tag: arise when a nonfinite
    verb (e.g. 'ho' from rsk relation) has its connector suppressed (because
    'via [place]' already covers the meaning from rp), but the verb token
    itself still gets chunked. Since the verb adds no meaning, remove it.
    e.g. [ho]_ACTIVE → removed (when [via kāśī] already present).
    """
    LONE_PREPS = {
        'from', 'in', 'on', 'at', 'to', 'by', 'of', 'for', 'with',
        'via', 'into', 'onto', 'upon', 'through', 'across',
    }
    chunks = _split_chunks(chunk_str)
    has_via = any(c.strip().lower().startswith('via ') for c, _ in chunks)
    new_chunks = []
    for c, tag in chunks:
        words = c.strip().split()
        # Case 1: lone preposition with no tag
        if len(words) == 1 and words[0].lower() in LONE_PREPS and not tag:
            print("[DEBUG] Removed lone preposition chunk: [%s]" % c)
            continue
        # Case 2: lone #-unknown word with _ACTIVE tag, when a [via X] chunk
        # is present — this is a suppressed rsk nonfinite verb (e.g. [ho]_ACTIVE)
        if (len(words) == 1 and words[0].startswith('#') and
                tag in ('_ACTIVE', '_PASSIVE', '') and has_via):
            print("[DEBUG] Removed suppressed rsk verb chunk: [%s]%s" % (c, tag))
            continue
        new_chunks.append([c, tag])
    return _join_chunks(new_chunks)


def _rule_inceptive_aux(chunk_str, feats):
    """Normalise inceptive auxiliary raw tokens that surface from the TAM pipeline:
    - begin_to / began_to  → 'began to'   (nA_lagA inceptive)
    - come_to_be / came_to_be → 'came to be' (yA_nA_lagA passive inceptive)
    These are multiword auxiliaries whose Apertium surface forms are not
    being picked up correctly, so we fix them in post-processing."""
    chunk_str = re.sub(r'\bbegan?_to\b', 'began to', chunk_str, flags=re.I)
    chunk_str = re.sub(r'\bbegin_to\b', 'began to', chunk_str, flags=re.I)
    chunk_str = re.sub(r'\bcame?_to_be\b', 'came to be', chunk_str, flags=re.I)
    chunk_str = re.sub(r'\bcome_to_be\b', 'came to be', chunk_str, flags=re.I)
    return chunk_str


def _rule_discourse_front(chunk_str, feats):
    """Move sentence-level discourse connectives to the very front of the output
    as their own standalone chunk. Connectives like 'but', 'although', 'however',
    'so', 'therefore', 'since', 'because', 'moreover', 'furthermore' belong at
    the sentence start, not inside subject/verb/pp chunks.

    Two cases handled:
    1. Connective appears alone in a mid-sentence chunk e.g. [but] → move to front
    2. Connective appears at the start of a verb/active chunk e.g. [so although is]
       → extract connective as [so although], leave [is]_ACTIVE
    """
    DISCOURSE_CONNECTIVES = {
        'but', 'however', 'yet', 'although', 'though', 'so', 'therefore',
        'hence', 'thus', 'since', 'because', 'moreover', 'furthermore',
        'nevertheless', 'nonetheless', 'otherwise', 'still', 'whereas',
        'while', 'whilst',
        'and',   # sentence-level coordinator (e.g. introducing a new clause)
        # NOTE: 'also' (BI_1) and 'only/even' (hI_1) are focus PARTICLES, not
        # discourse connectives — they stay attached to their focus constituent.
    }
    # Multi-word connectives that must be kept together
    MULTI_WORD = ['so although', 'so though', 'although so', 'but then',
                  'and yet', 'even though', 'even so', 'in spite of',
                  'on the other hand', 'on the contrary']

    chunks = _split_chunks(chunk_str)
    if not chunks:
        return chunk_str

    front_connectives = []
    new_chunks = []

    for c, tag in chunks:
        words = c.strip().split()
        if not words:
            new_chunks.append([c, tag])
            continue

        # Case 1: Entire chunk is just a connective (possibly multi-word)
        c_lower = c.strip().lower()
        is_pure_connective = (
            c_lower in DISCOURSE_CONNECTIVES or
            any(c_lower == mw for mw in MULTI_WORD)
        )
        if is_pure_connective and tag not in ('_SUBJ', '_ACTIVE', '_PASSIVE'):
            front_connectives.append(c.strip())
            continue

        # Case 2: Connective at the START of a verb/active chunk
        # e.g. "so although is" → extract "so although", keep "is"
        extracted = []
        remaining = list(words)

        # Try multi-word first
        for mw in sorted(MULTI_WORD, key=len, reverse=True):
            mw_words = mw.split()
            n = len(mw_words)
            if (len(remaining) > n and
                    [w.lower() for w in remaining[:n]] == mw_words):
                extracted = remaining[:n]
                remaining = remaining[n:]
                break

        # Then single word
        if not extracted and remaining and remaining[0].lower() in DISCOURSE_CONNECTIVES:
            extracted = [remaining[0]]
            remaining = remaining[1:]

        if extracted and remaining:
            front_connectives.append(' '.join(extracted))
            new_chunks.append([' '.join(remaining), tag])
        else:
            new_chunks.append([c, tag])

    if not front_connectives:
        return chunk_str

    # Rebuild: front connectives first, then remaining chunks
    # Deduplicate connectives (avoid "but but")
    seen = set()
    deduped = []
    for conn in front_connectives:
        if conn.lower() not in seen:
            deduped.append(conn)
            seen.add(conn.lower())

    result_chunks = [[conn, ''] for conn in deduped] + new_chunks
    return _join_chunks(result_chunks)


def _rule_recover_subject(chunk_str, feats):
    """If the USR's k1 subject is missing ENTIRELY from the output (a chunker
    drop) and a verb-concept was promoted to _SUBJ in its place, restore the
    real subject. Gated hard: fires only when the subject surface appears
    nowhere in the output, so stable sentences are never touched."""
    subj = feats.get('subj_en')
    if not subj or not re.fullmatch(r'[A-Za-z]{4,}', subj):
        return chunk_str          # only a single plain-alphabetic content word
    pref = subj.lower()[:5]
    words = re.findall(r'[a-z]+', chunk_str.lower())
    # present (even as a plural/hyphen/inflected variant) -> do nothing
    if any(w[:5] == pref for w in words):
        return chunk_str
    chunks = _split_chunks(chunk_str)
    subj_ci = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_ci is None:
        return chunk_str
    cur = chunks[subj_ci][0].strip()
    if len(cur.split()) != 1:
        return chunk_str
    chunks[subj_ci][1] = ''
    chunks.insert(0, [subj, '_SUBJ'])
    return _join_chunks(chunks)


def _rule_predicate_before_lexverb(chunk_str):
    """R14: a bare predicate nominal stranded *after* a non-copula lexical verb
    (e.g. '... [became]_ACTIVE [śiva ballabhapura]') moves before that verb,
    matching English 'X became Y'.  Pure copulas (is/are/was/were) are left
    alone — their complement legitimately follows them."""
    chunks = _split_chunks(chunk_str)
    if len(chunks) < 2:
        return chunk_str
    last_c, last_tag = chunks[-1]
    prev_c, prev_tag = chunks[-2]
    if last_tag:
        return chunk_str
    lw = [w.lower() for w in last_c.split()]
    if not lw or lw[0] in _PREP_WORDS or any(w in _VERB_AUX for w in lw):
        return chunk_str
    if prev_tag != '_ACTIVE':
        return chunk_str
    pv = [w.lower() for w in prev_c.split()]
    if not pv or all(w in _PURE_COPULA for w in pv):
        return chunk_str
    chunks[-2], chunks[-1] = chunks[-1], chunks[-2]
    return _join_chunks(chunks)


def _rule_copula_before_pp(chunk_str):
    """R4: a clause-final pure copula preceded by a prepositional-phrase
    complement is moved before that PP ('X [from Y] is' -> 'X is [from Y]'),
    provided a predicate chunk precedes the PP (a copular 'X is PRED [from Y]'
    frame)."""
    chunks = _split_chunks(chunk_str)
    if len(chunks) < 3:
        return chunk_str
    last_c, last_tag = chunks[-1]
    if last_tag != '_ACTIVE':
        return chunk_str
    lw = [w.lower() for w in last_c.split()]
    if not lw or not all(w in _PURE_COPULA for w in lw):
        return chunk_str
    pp_c, pp_tag = chunks[-2]
    if pp_tag:
        return chunk_str
    pw = pp_c.split()
    if not pw or pw[0].lower() not in _PREP_WORDS:
        return chunk_str
    pred_c, pred_tag = chunks[-3]
    if pred_tag == '_SUBJ' and len(chunks) == 3:
        return chunk_str
    chunks[-2], chunks[-1] = chunks[-1], chunks[-2]
    return _join_chunks(chunks)


def _rule_merge_route_through(chunk_str, feats):
    """Merge a standalone 'through'/'via' chunk with the adjacent place chunk.

    Two passes:
      1. Forward: [through]_ACTIVE [place] → [through place]   (chunker order for rsk)
      2. Backward: [place] [through]_ACTIVE → [through place]  (chunker order for rvks)
    Forward has priority; backward fires only if forward did not merge."""
    _VERB_TAGS = ('_ACTIVE', '_PASSIVE', '_IMPERATIVE', '_QUESTION', '_SUBJ')

    chunks = _split_chunks(chunk_str)
    n = len(chunks)

    # Pass 1 – forward
    result = []
    i = 0
    while i < n:
        c, tag = chunks[i]
        cw = c.strip().lower()
        if cw in ('through', 'via') and tag in ('_ACTIVE', ''):
            if (i + 1 < n and chunks[i + 1][1] not in _VERB_TAGS):
                nc, ntag = chunks[i + 1]
                result.append([c.strip() + ' ' + nc, ntag])
                i += 2
                continue
        result.append([c, tag])
        i += 1

    # Pass 2 – backward (only for any remaining standalone through/via)
    final = []
    for c, tag in result:
        cw = c.strip().lower()
        if cw in ('through', 'via') and tag in ('_ACTIVE', ''):
            merged = False
            for j in range(len(final) - 1, -1, -1):
                pc, pt = final[j]
                if pt not in _VERB_TAGS:
                    final[j] = [c.strip() + ' ' + pc, pt]
                    merged = True
                    break
            if not merged:
                final.append([c, tag])
        else:
            final.append([c, tag])
    return _join_chunks(final)


def _rule_pull_via_into_span(chunk_str, feats):
    """Absorb a [through X] / [via X] chunk into an adjacent route/span chunk.

    Two patterns handled:
    A) … [span] [through X] [verb]_ACTIVE → … [span through X] [verb]_ACTIVE
       (through X sits between span and verb)
    B) … [span] [verb]_ACTIVE [through X]  → … [span through X] [verb]_ACTIVE
       (through X sits after the verb — merger places it into the span before verb)
    """
    _ROUTE_PREPS = ('from ', 'also from ', 'to ', 'through ', 'via ')
    _VERB_TAGS = ('_ACTIVE', '_PASSIVE', '_IMPERATIVE', '_QUESTION')

    chunks = _split_chunks(chunk_str)
    n = len(chunks)
    for i in range(1, n):
        c, tag = chunks[i]
        if tag != '':
            continue
        cl = c.strip().lower()
        if not (cl.startswith('through ') or cl.startswith('via ')):
            continue

        # Pattern A: next chunk is a verb
        before_verb = (i + 1 < n and chunks[i + 1][1] in _VERB_TAGS)
        # Pattern B: previous chunk is a verb
        after_verb = (i > 0 and chunks[i - 1][1] in _VERB_TAGS)

        if not (before_verb or after_verb):
            continue

        # Look backward (skip over verb if pattern B) for a route/span chunk
        for j in range(i - 1, -1, -1):
            pc, ptag = chunks[j]
            if ptag == '_SUBJ':
                break
            if ptag in _VERB_TAGS:
                continue   # skip the verb chunk when searching backward
            pcl = pc.strip().lower()
            if any(pcl.startswith(prep) for prep in _ROUTE_PREPS):
                chunks[j] = [pc + ' ' + c, ptag]
                chunks[i] = None
                break
    chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_strip_spurious_r6_from_subj(chunk_str, feats):
    """Move spurious 'of X' r6 chains from _SUBJ to the k5 source chunk.

    The chunker sometimes pulls r6 modifiers of other NE compounds (k5, k7p)
    into the subject chunk due to shared lemma collisions (e.g. both lāina
    inside ne_2 and lāina_1 as k1 map to "line").  If the k1 USR node has
    no r6 dependents, strip 'of X' from _SUBJ and append it to the 'from …'
    source chunk so the information is preserved in the right place.
    """
    rows = feats['rows']
    is_passive = feats.get('is_passive', False)
    subject_rel = 'k2' if is_passive else 'k1'

    k1_idx = None
    for c in rows:
        if len(c) >= 5 and c[4] and ':' in c[4]:
            _, rel = c[4].split(':', 1)
            if rel == subject_rel:
                try:
                    k1_idx = float(c[1])
                except (ValueError, TypeError):
                    pass
                break
    if k1_idx is None:
        return chunk_str

    def _sf(s):
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    k1_has_r6 = any(
        len(c) >= 5 and c[4] and ':' in c[4]
        and c[4].split(':', 1)[1] == 'r6'
        and _sf(c[4].split(':', 1)[0]) == k1_idx
        for c in rows
    )
    if k1_has_r6:
        return chunk_str

    chunks = _split_chunks(chunk_str)
    extracted_tail = None
    for i, (c, tag) in enumerate(chunks):
        if tag != '_SUBJ':
            continue
        idx = c.find(' of ')
        if idx >= 0:
            extracted_tail = c[idx:].strip()   # " of X of Y …" → "of X of Y …"
            chunks[i][0] = c[:idx].strip()

    if not extracted_tail:
        return _join_chunks(chunks)

    # Append extracted tail to the 'from …' (k5 source) chunk
    from_idx = next(
        (i for i, (c, t) in enumerate(chunks)
         if t == '' and c.strip().lower().startswith('from ')),
        None
    )
    if from_idx is not None:
        chunks[from_idx][0] = chunks[from_idx][0].strip() + ' ' + extracted_tail
    return _join_chunks(chunks)


def _rule_move_trailing_from_before_active(chunk_str, feats):
    """Move a trailing 'from …' untagged chunk that follows _ACTIVE to before it.

    English source PPs (k5) and span constructions (k2p 'from X to Y')
    naturally precede the verb in this domain:
    '[goes]_ACTIVE [from mahū …]' → '[from mahū …] [goes]_ACTIVE'
    '[has gone]_ACTIVE [from X to Y]' → '[from X to Y] [has gone]_ACTIVE'
    """
    if 'k5' not in feats.get('rels', set()) and 'k2p' not in feats.get('rels', set()):
        return chunk_str
    chunks = _split_chunks(chunk_str)
    active_idx = next((i for i, (c, t) in enumerate(chunks) if '_ACTIVE' in t), None)
    if active_idx is None or active_idx + 1 >= len(chunks):
        return chunk_str
    changed = True
    while changed:
        changed = False
        if active_idx + 1 >= len(chunks):
            break
        next_c, next_t = chunks[active_idx + 1]
        if next_t != '' or not next_c.strip().lower().startswith('from '):
            break
        from_chunk = chunks.pop(active_idx + 1)
        chunks.insert(active_idx, from_chunk)
        active_idx += 1
        changed = True
    return _join_chunks(chunks)


def _rule_hortative_let_us(chunk_str, feats):
    """When main verb TAM is e_1 (hortative/cohortative):
    - prepend 'let us' to the verb chunk
    - move _ACTIVE from the verb to the destination (k2p 'to …') chunk
    - reorder so the verb chunk appears before the destination chunk
    Hindi 'chalEn' = 'let us go'.
    Also fires for CP constructions where the verbalizer carries e_1 TAM.
    Does NOT fire when shade:jA_1 is present (passive potential → 'should be done').
    """
    rows = feats.get('rows', [])
    main_tam = feats.get('main_tam', '')

    # If the main verb has shade:jA_1 marker, e_1 means passive potential, not hortative
    main_has_jA = any(
        len(c) >= 7 and c[4] == '0:main' and 'shade:jA_1' in (c[6] if len(c) > 6 else '')
        for c in rows
    )
    if main_has_jA:
        return chunk_str

    # For plain verbs: main_tam ends in -e_1
    has_e1 = bool(main_tam and re.search(r'-e_1$', main_tam))
    # For CP constructions: check if any verbalizer row has e_1 TAM (not e_2)
    # but also skip if that verbalizer has shade:jA_1
    if not has_e1:
        has_e1 = any(
            len(c) >= 9 and c[8] and 'verbalizer' in c[8]
            and re.search(r'-e_1$', c[0])
            and not ('shade:jA_1' in (c[6] if len(c) > 6 else ''))
            for c in rows
        )
    if not has_e1:
        return chunk_str
    chunks = _split_chunks(chunk_str)

    verb_idx = next((i for i, (c, t) in enumerate(chunks) if '_ACTIVE' in t), None)
    if verb_idx is None:
        return chunk_str

    # Prepend "let us" to verb and strip its _ACTIVE tag
    chunks[verb_idx][0] = 'let us ' + chunks[verb_idx][0].strip()
    chunks[verb_idx][1] = chunks[verb_idx][1].replace('_ACTIVE', '').strip('_')

    # Transfer _ACTIVE to the destination chunk (untagged "to …" chunk)
    dest_idx = next(
        (i for i, (c, t) in enumerate(chunks)
         if t == '' and c.strip().lower().startswith('to ')),
        None
    )
    if dest_idx is not None:
        chunks[dest_idx][1] = '_ACTIVE'
        # Reorder: verb first, then destination (swap if verb comes after dest)
        if verb_idx > dest_idx:
            chunks[verb_idx], chunks[dest_idx] = chunks[dest_idx], chunks[verb_idx]

    return _join_chunks(chunks)


def _to_pp_form(word):
    """Convert a verb stem to its English past-participle form (for passive construction)."""
    w = word.lower()
    _IRREGULARS = {
        'do': 'done', 'does': 'done', 'did': 'done',
        'go': 'gone', 'goes': 'gone', 'went': 'gone',
        'come': 'come', 'comes': 'come', 'came': 'come',
        'give': 'given', 'gives': 'given', 'gave': 'given',
        'take': 'taken', 'takes': 'taken', 'took': 'taken',
        'make': 'made', 'makes': 'made', 'made': 'made',
        'see': 'seen', 'sees': 'seen', 'saw': 'seen',
        'know': 'known', 'knows': 'known', 'knew': 'known',
        'hold': 'held', 'holds': 'held', 'held': 'held',
        'keep': 'kept', 'keeps': 'kept', 'kept': 'kept',
        'perform': 'performed', 'performs': 'performed',
        'offer': 'offered', 'offers': 'offered',
        'establish': 'established', 'establishes': 'established',
    }
    if w in _IRREGULARS:
        return _IRREGULARS[w]
    if w.endswith('ed') or w.endswith('en') or w.endswith('wn'):
        return w  # already participial
    if re.search(r'[^aeiou]y$', w):
        return w[:-1] + 'ied'
    if w.endswith('e') and len(w) > 2:
        return w + 'd'
    return w + 'ed'


def _rule_avasyaka_jA_passive_modal(chunk_str, feats):
    """Main verb with e_1 TAM + shade:jA_1 = passive jussive/potential.

    In Hindi: 'kiyA jAe' (e_1 + jA shade) = 'should be done'.
    The e_1 mood is subjunctive/hortative; shade:jA_1 makes it passive.
    Together they produce a passive potential meaning independent of any
    cross-sentence scope reference (e.g. AvaSyakawApariNAma).

    '[does]_ACTIVE' → '[should be done]_ACTIVE'
    """
    rows = feats.get('rows', [])
    has_e1_jA = any(
        c[4] == '0:main'
        and re.search(r'-e_1$', c[0])
        and 'shade:jA_1' in (c[6] if len(c) > 6 else '')
        for c in rows
    )
    if not has_e1_jA:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    # Find the _ACTIVE chunk that is NOT "killed" (rbks modifier)
    # We want only the main verb chunk
    for i, (c, tag) in enumerate(chunks):
        if '_ACTIVE' not in tag:
            continue
        words = c.strip().split()
        if not words:
            continue
        if words[0].lower() in ('should', 'will', 'must', 'can'):
            continue  # already modal
        verb = words[-1]
        pp = _to_pp_form(verb)
        prefix = ' '.join(words[:-1]) + ' ' if len(words) > 1 else ''
        chunks[i][0] = prefix + 'should be ' + pp
        chunks[i][1] = '_ACTIVE'
        break  # only transform the first _ACTIVE chunk (main verb)
    return _join_chunks(chunks)


def _rule_e2_jA_future_passive(chunk_str, feats):
    """e_2 / gA TAM + shade:jA_1 = future passive, whether the verb is a plain
    main verb (0:main) or a CP verbalizer.

    In Hindi: 'ho jAegA' / 'kiyA jAegA' (e_2/gA + jA shade) = 'will be done'.
    The e_2/gA marks future/potential; shade:jA_1 makes it passive.

    '[complete]_ACTIVE'      → '[will be completed]_ACTIVE'
    '[will complete]_PASSIVE' → '[will be completed]_ACTIVE'  (gA_1 case)
    """
    rows = feats.get('rows', [])
    has_e2_jA = any(
        re.search(r'-e_2$|-gA_', c[0])
        and 'shade:jA_1' in (c[6] if len(c) > 6 else '')
        and (
            # plain main verb
            (len(c) > 4 and c[4] == '0:main')
            or
            # CP verbalizer
            (len(c) >= 9 and c[8] and 'verbalizer' in c[8])
        )
        for c in rows
    )
    if not has_e2_jA:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if '_ACTIVE' not in tag and '_PASSIVE' not in tag:
            continue
        words = c.strip().split()
        if not words:
            continue
        if words[0].lower() == 'will':
            # Chunk already has 'will' (from gA TAM) — add passive 'be' if missing
            if 'be' not in [w.lower() for w in words]:
                verb = words[-1]
                pp = _to_pp_form(verb)
                chunks[i][0] = 'will be ' + pp
                chunks[i][1] = '_ACTIVE'
            continue
        # Convert last content word to PP form and prepend "will be"
        verb = words[-1]
        pp = _to_pp_form(verb)
        prefix = ' '.join(words[:-1]) + ' ' if len(words) > 1 else ''
        chunks[i][0] = prefix + 'will be ' + pp
        chunks[i][1] = '_ACTIVE'
    return _join_chunks(chunks)


def _rule_coord_mod_reorder(chunk_str, feats):
    """When a coordination/disjunct is a :mod of a noun (not :r6), the
    coordinated phrase is a pre-modifier and should NOT have 'of' between
    it and the noun it modifies.

    Pattern in chunk: '[A or B of noun]' → '[of A or B noun]'
    i.e. 'śiprā or kṣiprā of river' → 'of śiprā or kṣiprā river'
    (the 'of' belongs to the r6 relation above, not between mod and noun)

    Detection: a [conj_N]/[disjunct_N] row whose dependency relation is :mod.
    """
    rows = feats.get('rows', [])
    # Collect indices of conj/disjunct nodes that have a :mod dependency
    mod_conj_heads = set()
    for c in rows:
        if not re.fullmatch(r'\[(conj|disjunct)_\d+\]', c[0]):
            continue
        if len(c) < 5 or ':' not in (c[4] or ''):
            continue
        _, rel = c[4].split(':', 1)
        if rel == 'mod':
            # The head noun's English word — find it
            head_idx = c[4].split(':', 1)[0]
            for d in rows:
                if d[1] == head_idx:
                    mod_conj_heads.add(head_idx)
    if not mod_conj_heads:
        return chunk_str

    # In any chunk, fix "X or Y of noun" / "X and Y of noun"
    # where 'noun' is a single word that follows 'of'
    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        # Look for pattern: "...<coord phrase> of <single_word>"
        # coord phrase contains ' or ' or ' and '
        m = re.search(
            r'^(.*?)(.+?(?:\s+(?:or|and)\s+.+?)+)\s+of\s+(\S+)(.*)$',
            c, re.IGNORECASE
        )
        if m:
            prefix, coord, noun, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
            chunks[ci][0] = (prefix + 'of ' + coord.strip() + ' ' + noun + suffix).strip()
    return _join_chunks(chunks)


def _rule_k3_kqw_by_performing(chunk_str, feats, concept_dict):
    """A participial kqw verb with k3 (instrument/means) relation whose base
    concept is kara (do/perform) should generate 'by performing [k2_object]'
    rather than 'with [verb_translation]'.

    Pattern: kara_N with kqw + k3 → 'by performing <k2>'
    'with offer piṃḍadāna' → 'by performing piṃḍadāna'
    """
    rows = feats.get('rows', [])

    kara_k3 = None
    for c in rows:
        if len(c) < 5 or c[3] != 'kqw':
            continue
        if ':' not in (c[4] or ''):
            continue
        _, rel = c[4].split(':', 1)
        if rel != 'k3':
            continue
        if c[0].split('_')[0] == 'kara':
            kara_k3 = c
            break

    if kara_k3 is None:
        return chunk_str

    # Find k2 (object) of this kara
    kara_idx = kara_k3[1]
    k2_en = None
    constr = feats.get('constr', {})
    for c in rows:
        if len(c) < 5 or ':' not in (c[4] or ''):
            continue
        h, rel = c[4].split(':', 1)
        if h == kara_idx and rel == 'k2':
            k2_en = _resolve_en(c[1], rows, concept_dict, constr).lower()
            if not k2_en:
                k2_en = _comp_english(c[0], concept_dict).lower()
            break

    if not k2_en:
        return chunk_str

    kara_en = _comp_english(kara_k3[0], concept_dict).lower()
    chunks = _split_chunks(chunk_str)

    # Find 'with <kara_en>' chunk and a separate k2 chunk, then merge
    kara_ci = None
    for ci, (c, tag) in enumerate(chunks):
        words = [w.lower() for w in c.split()]
        if 'with' in words and kara_en in words:
            kara_ci = ci
            break

    if kara_ci is None:
        return chunk_str

    # Find the k2 word chunk to remove
    k2_words = k2_en.lower().split()
    k2_ci = None
    for ci, (c, tag) in enumerate(chunks):
        if ci == kara_ci:
            continue
        c_words = [w.lower() for w in c.split()]
        if k2_words and k2_words[0] in c_words:
            k2_ci = ci
            break

    chunks[kara_ci][0] = 'by performing ' + k2_en
    if k2_ci is not None:
        chunks[k2_ci] = None
        chunks = [x for x in chunks if x is not None]

    return _join_chunks(chunks)


# WX stems of Hindi concepts that denote a specific point in time (not a duration).
# k7t nouns with these stems get 'at' rather than 'in'.
_K7T_POINT_STEMS = {
    'samaya',   # time / moment / occasion
    'bAra',     # time / occasion / turn  (is bAra = this time)
    'pal',      # instant / moment
    'kSaNa',    # instant
    'Cana',     # instant / moment
    'din',      # day (as a named day)
    'xin',      # day (alternate WX)
    'roja',     # day (daily)
    'rAwa',     # night
    'subaha',   # morning
    'prAwa',    # morning
    'sAyaMkAla', # evening
    'saMjhA',   # evening
    'xopaharadina', # afternoon
    'prahara',  # watch/period of 3h — still a point in a day
    'tArikha',  # date
    'kSaNa',    # moment
}

# WX stems that are durations/periods — keep 'in'.
# (These are listed for documentation; the rule fires only for POINT stems.)
# mahInA=month, sAla=year, varsha=year, saptAha=week, yuga=era, kAla=age/era

def _rule_k7t_at_vs_in(chunk_str, feats):
    """For k7t (temporal) relations: use 'at' for point-in-time concepts
    (samaya/moment/day/night/morning…) and keep 'in' for durations/periods.

    The distinction is made by checking the WX stem of each k7t concept row
    against _K7T_POINT_STEMS.
    """
    rows = feats.get('rows', [])
    k7t_stems = set()
    for c in rows:
        if not (len(c) >= 5 and c[4] and ':' in c[4]):
            continue
        rel = c[4].split(':', 1)[1]
        if rel == 'k7t':
            stem = c[0].split('_')[0]   # strip sense number
            k7t_stems.add(stem)
        # Also include a dem modifier's concept when its head is k7t
        # (e.g. $wyax dem-modifier of samaya_1 → no additional stem needed)

    if not any(s in _K7T_POINT_STEMS for s in k7t_stems):
        return chunk_str

    # Change leading 'in ' → 'at ' in all untagged chunks
    # (k7t temporal chunks are always untagged; spatial k7p chunks may also
    # start with 'in', but when k7t is a point-word it is safe to fix both.)
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if tag == '' and c.strip().lower().startswith('in '):
            chunks[i][0] = 'at ' + c.strip()[3:]
    return _join_chunks(chunks)


def _rule_dedup_leading_prepositions(chunk_str, feats):
    """When a locative/topic relation prepends 'in'/'on'/'at' but the concept
    word ITSELF is a preposition (e.g. viRaya_20 → 'about'), the output gets
    'on about …'.  Strip the redundant structural preposition.
    """
    PREPOSITION_WORDS = {
        'about', 'concerning', 'regarding', 'over', 'around',
        'between', 'among', 'through', 'towards', 'toward',
    }
    STRUCTURAL_PREPS = {'in', 'on', 'at'}
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        words = c.strip().split()
        if (len(words) >= 2
                and words[0].lower() in STRUCTURAL_PREPS
                and words[1].lower() in PREPOSITION_WORDS):
            chunks[i][0] = ' '.join(words[1:])
    return _join_chunks(chunks)


def _rule_fix_passive_verb_forms(chunk_str, feats):
    """Fix known Apertium passive-verb misspellings in the output text.
    'saids' → 'said', 'sayed' → 'said', etc.

    Also strips spurious 'was' prepended to CP active verb forms when the
    verbalizer TAM is yA_wA_1 (simple past, not passive): 'was spent' → 'spent'.
    """
    _FIXES = {
        'saids': 'said',
        'fells': 'falls',
        'menaces': 'welcomes',
        'sayed': 'said',
        'tolds': 'told',
        'writed': 'written',
        'throughs': 'through',
        'theres': 'there',
        'sayed': 'said',
        'tolds': 'told',
        'writed': 'written',
        'throughs': 'through',
        'theres': 'there',
        # wrong Apertium verb translations (Cat 2)
        'cools': 'connects',
        'judes': 'connects',
        'fells': 'falls',
        'menaces': 'welcomes',
    }
    pattern = r'\b(' + '|'.join(re.escape(k) for k in _FIXES) + r')\b'
    chunk_str = re.sub(pattern, lambda m: _FIXES[m.group(0)], chunk_str)

    # Strip spurious 'was' from _ACTIVE chunks when the CP verbalizer TAM is
    # yA_wA (past habitual / past of kara) and sentence is not passive.
    rows = feats.get('rows', [])
    has_yA_wA_cp = any(
        'yA_wA' in c[0]
        for c in rows
        if len(c) >= 9 and c[8] and 'verbalizer' in c[8]
    )
    if has_yA_wA_cp and not feats.get('is_passive'):
        chunks = _split_chunks(chunk_str)
        for i, (c, tag) in enumerate(chunks):
            if '_ACTIVE' in tag:
                words = c.split()
                if words and words[0].lower() == 'was' and len(words) > 1:
                    chunks[i][0] = ' '.join(words[1:])
        chunk_str = _join_chunks(chunks)

    return chunk_str


def _rule_move_also_to_subj(chunk_str, feats):
    """When BI_1 (also) is on k5/k7p rather than k1, the chunker places 'also'
    at the start of the source/location chunk.  Move it to the SUBJ front so
    the output matches the natural English reading: 'also one line [goes]'.
    Does NOT fire when BI_1 is on k7t (temporal) — 'also this time' should
    remain as its own chunk before SUBJ, not merge into SUBJ.
    """
    rows = feats['rows']
    # BI_1 on k1 means 'also' is already in SUBJ — only act when it's on k5/k7p
    bi1_on_k1 = any(
        len(c) >= 7 and 'BI_1' in (c[6] if len(c) > 6 else '')
        and len(c) >= 5 and c[4] and ':' in c[4]
        and c[4].split(':', 1)[1] == 'k1'
        for c in rows
    )
    if bi1_on_k1:
        return chunk_str

    # BI_1 on k7t (temporal): 'also this time' stays as its own chunk —
    # handled by _rule_also_temporal_before_subj instead.
    bi1_on_k7t = any(
        len(c) >= 7 and 'BI_1' in (c[6] if len(c) > 6 else '')
        and len(c) >= 5 and c[4] and ':' in c[4]
        and c[4].split(':', 1)[1] == 'k7t'
        for c in rows
    )
    if bi1_on_k7t:
        return chunk_str

    bi1_on_non_k1 = any(
        len(c) >= 7 and 'BI_1' in (c[6] if len(c) > 6 else '')
        for c in rows
    )
    if not bi1_on_non_k1:
        return chunk_str

    chunks = _split_chunks(chunk_str)
    subj_idx = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_idx is None:
        return chunk_str

    # Find a non-SUBJ untagged chunk that starts with 'also'
    for i, (c, tag) in enumerate(chunks):
        if i == subj_idx or tag != '':
            continue
        words = c.strip().split()
        if words and words[0].lower() == 'also':
            # Move 'also' to front of SUBJ
            chunks[i][0] = ' '.join(words[1:]).strip()
            if not chunks[i][0]:
                chunks.pop(i)
            chunks[subj_idx][0] = 'also ' + chunks[subj_idx][0]
            break
    return _join_chunks(chunks)


def _rule_also_temporal_before_subj(chunk_str, feats):
    """When BI_1 is on a k7t (temporal) relation, 'also <time>' should appear
    as a separate chunk BEFORE the subject.  If the temporal chunk appears after
    the SUBJ chunk, move it before SUBJ.
    """
    rows = feats['rows']
    bi1_on_k7t = any(
        len(c) >= 7 and 'BI_1' in (c[6] if len(c) > 6 else '')
        and len(c) >= 5 and c[4] and ':' in c[4]
        and c[4].split(':', 1)[1] == 'k7t'
        for c in rows
    )
    if not bi1_on_k7t:
        return chunk_str

    chunks = _split_chunks(chunk_str)
    subj_idx = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_idx is None:
        return chunk_str

    # Find a non-SUBJ untagged chunk that starts with 'also' and is after SUBJ
    for i, (c, tag) in enumerate(chunks):
        if i <= subj_idx or tag != '':
            continue
        words = c.strip().split()
        if words and words[0].lower() == 'also':
            # Move this whole chunk to just before SUBJ
            chunk_item = chunks.pop(i)
            chunks.insert(subj_idx, chunk_item)
            break
    return _join_chunks(chunks)


def _rule_fix_respect_subj(chunk_str, feats):
    """Fix respect-marked NE in _SUBJ chunks.

    The morphology generator adds a plural -s to NE inside-members when the
    compound head has 'respect' marking (honorific plural in Hindi), but in
    English this is wrong.  Also converts the '_(respect)' annotation to the
    honorific suffix 'ji'.
    Pattern: [pitāmaha_(respect) brahmās]_SUBJ → [pitāmaha brahmā ji]_SUBJ
    """
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if '_(respect)' not in c:
            continue
        c_clean = re.sub(r'_\(respect\)', '', c)
        words = c_clean.split()
        if tag == '_SUBJ' and words:
            last = words[-1]
            # Strip honorific plural -s added by morph_gen for respect NEs in SUBJ
            if last.endswith('s') and not re.search(r'(is|us|ss|ous|ius|ais|eis)$', last.lower()):
                words[-1] = last[:-1]
        words.append('ji')
        chunks[i][0] = ' '.join(words)
    return _join_chunks(chunks)


def _rule_merge_consecutive_subj(chunk_str, feats):
    """Merge consecutive _SUBJ chunks into one (e.g. conj modifier + NE subject).
    Also strips leading bracket/space artifacts like '[ gaṃgā' → 'gaṃgā'.
    """
    def _clean(s):
        return re.sub(r'\[', '', s).strip()

    chunks = _split_chunks(chunk_str)
    changed = True
    while changed:
        changed = False
        for i in range(len(chunks) - 1):
            if chunks[i][1] == '_SUBJ' and chunks[i + 1][1] == '_SUBJ':
                c1 = _clean(chunks[i][0])
                c2 = _clean(chunks[i + 1][0])
                chunks[i][0] = (c1 + ' ' + c2).strip()
                chunks.pop(i + 1)
                changed = True
                break
    # Also clean any residual [ in standalone SUBJ chunks
    for i, (c, t) in enumerate(chunks):
        if t == '_SUBJ':
            chunks[i][0] = _clean(c)
    return _join_chunks(chunks)


def _rule_extract_rpk_from_active(chunk_str, feats):
    """When the _ACTIVE chunk starts with a present-participle (-ing) word that is
    an rpk verb, extract it and merge it with the immediately preceding untagged
    chunk (its k2 argument), forming a separate participial chunk.

    [mountainous area] [leaving enters]_ACTIVE →
    [leaving mountainous area] [enters]_ACTIVE
    """
    chunks = _split_chunks(chunk_str)
    active_idx = next((i for i, (c, t) in enumerate(chunks) if '_ACTIVE' in t), None)
    if active_idx is None:
        return chunk_str
    words = chunks[active_idx][0].strip().split()
    if len(words) < 2:
        return chunk_str
    first = words[0]
    if not first.lower().endswith('ing'):
        return chunk_str
    # Extract the -ing word; rest stays in _ACTIVE
    rest = ' '.join(words[1:])
    # Look for immediately preceding untagged chunk (rpk k2 argument)
    prev_idx = next(
        (j for j in range(active_idx - 1, -1, -1) if chunks[j][1] == ''),
        None
    )
    if prev_idx is not None:
        prev_content = chunks[prev_idx][0].strip()
        chunks[prev_idx][0] = first + ' ' + prev_content
        chunks[active_idx][0] = rest
    else:
        # No preceding untagged chunk: just create standalone chunk before _ACTIVE
        chunks.insert(active_idx, [first, ''])
        chunks[active_idx + 1][0] = rest
    return _join_chunks(chunks)


def _rule_absorb_trailing_location_into_active(chunk_str, feats):
    """Absorb all immediately following untagged PP chunks into the _ACTIVE chunk.

    [enters]_ACTIVE [in plain land] [in haridvāra] →
    [enters in plain land in haridvāra]_ACTIVE
    """
    preps = {'in', 'at', 'on', 'into', 'through', 'from', 'to', 'near', 'by', 'along'}
    chunks = _split_chunks(chunk_str)
    active_idx = next((i for i, (c, t) in enumerate(chunks) if '_ACTIVE' in t), None)
    if active_idx is None:
        return chunk_str
    absorbed = True
    while absorbed:
        absorbed = False
        if active_idx + 1 >= len(chunks):
            break
        next_c, next_t = chunks[active_idx + 1]
        if next_t != '':
            break
        first_word = next_c.strip().split()[0].lower() if next_c.strip() else ''
        if first_word not in preps:
            break
        # Don't absorb a combined span chunk (contains both 'from' and 'to') —
        # these express full journeys and belong as their own chunk
        nc_words = next_c.lower().split()
        if 'from' in nc_words and 'to' in nc_words:
            break
        # Don't absorb a 'from …' k5 source chunk when the sentence has k5
        if first_word == 'from' and 'k5' in feats.get('rels', set()):
            break
        chunks[active_idx][0] = chunks[active_idx][0].strip() + ' ' + next_c.strip()
        chunks.pop(active_idx + 1)
        absorbed = True
    return _join_chunks(chunks)


def _rule_merge_location_pps(chunk_str, feats):
    """Merge consecutive prepositional-phrase chunks that all depend on the same
    locative head (heuristic: they are contiguous, untagged, and each begins with
    a spatial preposition, sitting between the subject and the main verb).

    This collapses fragmented location descriptions like:
      [on go main line] [to amṛtasara] [of uttara relave] [from mugala sarāya]
    into a single chunk."""
    _SPATIAL_PREPS = {
        'on', 'in', 'at', 'to', 'from', 'of', 'for', 'by', 'near',
        'into', 'along', 'through', 'via', 'between', 'among', 'across',
    }
    _VERB_TAGS = ('_ACTIVE', '_PASSIVE', '_IMPERATIVE', '_QUESTION', '_SUBJ')

    chunks = _split_chunks(chunk_str)

    def _is_spatial_pp(c, tag):
        if tag not in ('', ):  # only untagged chunks
            return False
        first = c.strip().split()[0].lower() if c.strip() else ''
        return first in _SPATIAL_PREPS

    result = []
    run = []  # accumulates a run of spatial-PP chunks
    for c, tag in chunks:
        if _is_spatial_pp(c, tag):
            run.append(c)
        else:
            if len(run) > 1:
                result.append([' '.join(run), ''])
            elif run:
                result.append([run[0], ''])
            run = []
            result.append([c, tag])
    if len(run) > 1:
        result.append([' '.join(run), ''])
    elif run:
        result.append([run[0], ''])
    return _join_chunks(result)


def _rule_inject_missing_ne_mods(chunk_str, feats, concept_dict):
    """Inject mod modifiers of NE compound nodes that were lost from PP_fulldata.

    Pattern (Sent_25): paviwra_2 (sacred) is 20:mod but dropped upstream.
    This rule detects such missing mods from feats rows and inserts them
    before the first component word of their head compound in the chunks.
    """
    rows = feats['rows']
    # Build index: node_idx → list of row cols
    node_by_idx = {}
    for c in rows:
        if len(c) >= 2:
            try:
                node_by_idx[float(c[1])] = c
            except (ValueError, TypeError):
                pass

    # Find NE compound members: {compound_idx: [component_indices]}
    # Note: begin/inside relations appear in the LAST column (c[-1]), not c[4]
    compound_members = {}
    for c in rows:
        if len(c) < 2:
            continue
        # Check last column for begin/inside compound membership
        last = c[-1] if c else ''
        if not last or ':' not in str(last):
            continue
        head_str, rel = str(last).split(':', 1)
        if rel in ('begin', 'inside'):
            try:
                head_idx = float(head_str)
            except (ValueError, TypeError):
                continue
            try:
                comp_idx = float(c[1])
            except (ValueError, TypeError):
                continue
            compound_members.setdefault(head_idx, []).append(comp_idx)

    # For each mod token pointing to a compound head: inject if missing from output
    chunk_str_lower = chunk_str.lower()
    chunks = _split_chunks(chunk_str)
    changed = False

    for c in rows:
        if len(c) < 5 or not c[4] or ':' not in c[4]:
            continue
        head_str, rel = c[4].split(':', 1)
        if rel != 'mod':
            continue
        try:
            head_idx = float(head_str)
        except (ValueError, TypeError):
            continue
        if head_idx not in compound_members:
            continue  # only handle mod-of-compound
        if c[0].startswith('['):
            continue  # skip structural tokens ([conj_1], [ne_1], etc.)
        mod_en = _comp_english(c[0], concept_dict)
        if not mod_en or not mod_en.strip():
            continue
        mod_word = mod_en.strip().lower()
        if mod_word in chunk_str_lower:
            continue  # already present

        # Find English of compound components to locate the right chunk
        comp_indices = compound_members[head_idx]
        comp_english_words = []
        for ci in comp_indices:
            cr = node_by_idx.get(ci)
            if cr:
                en = _comp_english(cr[0], concept_dict)
                if en and en.strip():
                    comp_english_words.append(en.strip().lower())

        if not comp_english_words:
            continue

        # Find the chunk containing the first component word and inject mod before it
        for ci2, (cc, ctag) in enumerate(chunks):
            cc_lower = cc.lower()
            for comp_w in comp_english_words:
                idx_in_chunk = cc_lower.find(comp_w)
                if idx_in_chunk >= 0:
                    # Insert mod_en just before comp_w in the chunk
                    chunks[ci2][0] = cc[:idx_in_chunk] + mod_en.strip() + ' ' + cc[idx_in_chunk:]
                    changed = True
                    break
            if changed:
                break

    if not changed:
        return chunk_str
    return _join_chunks(chunks)


_DISCOURSE_SINGLE = {
    'but', 'however', 'yet', 'although', 'though', 'so', 'therefore',
    'hence', 'thus', 'since', 'because', 'moreover', 'furthermore',
    'nevertheless', 'nonetheless', 'otherwise', 'still', 'whereas',
    'while', 'whilst', 'and', 'also', 'or',
}


def _rule_presubj_modifier_merge(chunk_str, feats, concept_dict):
    """Demonstrative / cardinal pre-modifiers of the k1 subject that land in
    a separate chunk are prepended into the _SUBJ chunk.

    Pattern: [these seven] [religious place]_SUBJ →
             [these seven religious place]_SUBJ

    Safety guards:
    - Stop at any chunk that starts with a preposition (it belongs to a PP).
    - Stop at any single-word discourse connective (and/but/…) so that
      [and] [another]_SUBJ is never incorrectly merged."""
    chunks = _split_chunks(chunk_str)
    subj_idx = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_idx is None or subj_idx == 0:
        return chunk_str

    to_merge = []
    j = subj_idx - 1
    while j >= 0:
        pc, ptag = chunks[j]
        if ptag != '':
            break
        pw = pc.strip().split()
        if not pw:
            break
        fw = pw[0].lower()
        if fw in _PREP_WORDS:
            break
        if len(pw) == 1 and fw in _DISCOURSE_SINGLE:
            break
        to_merge.insert(0, j)
        j -= 1

    if not to_merge:
        return chunk_str

    prefix = ' '.join(chunks[jj][0] for jj in to_merge)
    chunks[subj_idx][0] = prefix + ' ' + chunks[subj_idx][0]
    remove = set(to_merge)
    chunks = [c for i, c in enumerate(chunks) if i not in remove]
    return _join_chunks(chunks)


def _rule_absorb_postsubj_card_dem(chunk_str, feats, concept_dict):
    """Card/dem modifiers of the k1 subject that land in a separate chunk
    AFTER _SUBJ are prepended into the _SUBJ chunk.

    Pattern: [religious place]_SUBJ [seven] → [seven religious place]_SUBJ
    """
    rows = feats['rows']
    # Find the k1 node (subject noun) index
    k1_noun_idx = None
    for c in rows:
        if len(c) >= 5 and c[4] and ':' in c[4]:
            head, rel = c[4].split(':', 1)
            if rel == 'k1':
                try:
                    k1_noun_idx = float(c[1])
                except (ValueError, TypeError):
                    pass
                break
    if k1_noun_idx is None:
        return chunk_str
    # Collect English of card/dem tokens pointing to the k1 noun
    card_dem_words = set()
    for c in rows:
        if len(c) < 5 or not c[4] or ':' not in c[4]:
            continue
        head, rel = c[4].split(':', 1)
        if rel not in ('card', 'dem'):
            continue
        try:
            if float(head) != k1_noun_idx:
                continue
        except (ValueError, TypeError):
            continue
        if rel == 'dem' and c[0].startswith('$'):
            # Pronoun-type dem: derive English from proximal/distal + number
            number = c[3] if len(c) > 3 else ''
            deixis = c[6] if len(c) > 6 else ''
            if 'proximal' in deixis:
                en = 'these' if number == 'pl' else 'this'
            else:
                en = 'those' if number == 'pl' else 'that'
            card_dem_words.add(en)
        else:
            en = _comp_english(c[0], concept_dict)
            if en and en.strip():
                card_dem_words.add(en.strip().lower())
    if not card_dem_words:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    subj_idx = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_idx is None:
        return chunk_str
    # Find ALL post-subj untagged chunks whose sole content exactly matches
    # a card/dem word — they can be anywhere after _SUBJ (not just consecutive)
    absorbed_indices = []
    for i in range(subj_idx + 1, len(chunks)):
        c, tag = chunks[i]
        if tag != '':
            continue
        cw = c.strip().lower()
        cw_words = cw.split()
        if cw in card_dem_words or (cw_words and all(w in card_dem_words for w in cw_words)):
            absorbed_indices.append(i)
    if not absorbed_indices:
        return chunk_str
    absorbed = [chunks[i][0].strip() for i in absorbed_indices]
    prefix = ' '.join(absorbed)
    chunks[subj_idx][0] = prefix + ' ' + chunks[subj_idx][0]
    remove_idxs = set(absorbed_indices)
    chunks = [c for i, c in enumerate(chunks) if i not in remove_idxs]
    return _join_chunks(chunks)


def _rule_subj_plural_agreement(chunk_str, feats, concept_dict):
    """If k1 noun has pl card/dem modifiers but surface form is singular, pluralize it."""
    rows = feats['rows']
    k1_noun_idx = None
    for c in rows:
        if len(c) >= 5 and c[4] and ':' in c[4]:
            _, rel = c[4].split(':', 1)
            if rel == 'k1':
                try:
                    k1_noun_idx = float(c[1])
                except (ValueError, TypeError):
                    pass
                break
    if k1_noun_idx is None:
        return chunk_str
    is_plural = False
    for c in rows:
        if len(c) < 5 or not c[4] or ':' not in c[4]:
            continue
        head, rel = c[4].split(':', 1)
        if rel not in ('card', 'dem'):
            continue
        try:
            if float(head) != k1_noun_idx:
                continue
        except (ValueError, TypeError):
            continue
        if len(c) > 3 and c[3] == 'pl':
            is_plural = True
            break
    if not is_plural:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    subj_idx = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_idx is None:
        return chunk_str
    words = chunks[subj_idx][0].strip().split()
    if not words:
        return chunk_str
    last = words[-1]
    low = last.lower()
    if not low.endswith('s'):
        if re.search(r'[^aeiou]y$', low):
            plural = last[:-1] + 'ies'
        elif re.search(r'(s|x|z|ch|sh)$', low):
            plural = last + 'es'
        else:
            plural = last + 's'
        words[-1] = plural
        chunks[subj_idx][0] = ' '.join(words)
    return _join_chunks(chunks)


def _rule_verb_subj_agreement(chunk_str, feats, concept_dict):
    """Fix is→are / was→were when the _SUBJ chunk is plural."""
    chunks = _split_chunks(chunk_str)
    subj_idx = next((i for i, (c, t) in enumerate(chunks) if t == '_SUBJ'), None)
    if subj_idx is None:
        return chunk_str
    rows = feats['rows']
    k1_noun_idx = None
    for c in rows:
        if len(c) >= 5 and c[4] and ':' in c[4]:
            _, rel = c[4].split(':', 1)
            if rel == 'k1':
                try:
                    k1_noun_idx = float(c[1])
                except (ValueError, TypeError):
                    pass
                break
    is_plural = False
    for c in rows:
        if len(c) < 5 or not c[4] or ':' not in c[4]:
            continue
        head, rel = c[4].split(':', 1)
        if rel not in ('card', 'dem'):
            continue
        try:
            if float(head) != k1_noun_idx:
                continue
        except (ValueError, TypeError):
            continue
        if len(c) > 3 and c[3] == 'pl':
            is_plural = True
            break
    if not is_plural:
        return chunk_str
    sg_to_pl = {'is': 'are', 'was': 'were', 'has': 'have'}
    for i, (c, tag) in enumerate(chunks):
        if '_ACTIVE' in tag or '_PASSIVE' in tag:
            words = c.split()
            chunks[i][0] = ' '.join(sg_to_pl.get(w.lower(), w) for w in words)
    return _join_chunks(chunks)


def _rule_recover_passive_k2_subject(chunk_str, feats, concept_dict):
    """In passive sentences the k2 node is the surface subject.  If it is
    absent from the chunk string, prepend it as the first chunk."""
    if not feats.get('is_passive'):
        return chunk_str
    rows = feats['rows']
    k2_node = None
    for c in rows:
        if len(c) >= 5 and c[4] and ':' in c[4]:
            _, rel = c[4].split(':', 1)
            if rel == 'k2':
                k2_node = c
                break
    if k2_node is None:
        return chunk_str
    # Derive English for the k2 node
    concept = k2_node[0]
    if concept.startswith('$'):
        # Pronoun: use proximal/distal + number
        number = k2_node[3] if len(k2_node) > 3 else ''
        deixis = k2_node[6] if len(k2_node) > 6 else ''
        # $wyax = यह (this/proximal); $vahax = वह (that/distal)
        if concept == '$wyax' or 'proximal' in str(deixis):
            en = 'these' if number == 'pl' else 'this'
        else:
            en = 'those' if number == 'pl' else 'that'
    elif re.match(r'^\[ne', concept, re.I):
        # NE compound: collect begin/inside tokens by matching last-column index
        k2_idx = k2_node[1]
        ne_words = []
        for c in rows:
            if not c or not c[-1]:
                continue
            last = c[-1]
            if re.match(r'^\d+:(?:begin|inside)$', last):
                parts = last.split(':')
                if parts[0] == str(k2_idx):
                    w = _comp_english(c[0], concept_dict).strip()
                    if not w:
                        w = c[0]
                    ne_words.append(w)
        en = ' '.join(ne_words).strip()
        if not en:
            return chunk_str
    else:
        en = _comp_english(concept, concept_dict).strip()
        if not en:
            return chunk_str
    # If subject already present in chunks, move it to front (after discourse words)
    chunks = _split_chunks(chunk_str)
    subj_idx = next(
        (i for i, (c, t) in enumerate(chunks) if en.lower() in c.lower() and t == ''),
        None
    )
    if subj_idx is not None:
        # Assign _SUBJ tag (was missing — chunk was found but tag never set)
        chunks[subj_idx][1] = '_SUBJ'
        # Move the subject chunk to position 0 (or after leading discourse chunks)
        disc_words = {'therefore', 'because', 'so', 'thus', 'hence', 'however',
                      'but', 'and', 'also', 'moreover', 'furthermore', 'although',
                      'since', 'after', 'before', 'meanwhile', 'then'}
        insert_at = 0
        for i, (c, t) in enumerate(chunks):
            if t == '' and c.strip().lower() in disc_words:
                insert_at = i + 1
            else:
                break
        if subj_idx != insert_at:
            subj_chunk = chunks.pop(subj_idx)
            chunks.insert(insert_at, subj_chunk)
        return _join_chunks(chunks)
    return '[' + en + '] ' + chunk_str


def _rule_verb_sg3_agreement(chunk_str, feats, concept_dict):
    """Fix have→has when the surface subject is 3rd-person singular.

    Covers passive sentences where k2 is the surface subject, and active
    sentences where k1 is singular (no pl card/dem modifiers).
    """
    rows = feats['rows']
    # Determine the surface-subject node: k2 in passive, k1 in active
    is_passive = feats.get('is_passive', False)
    subject_rel = 'k2' if is_passive else 'k1'

    subj_node = None
    for c in rows:
        if len(c) >= 5 and c[4] and ':' in c[4]:
            _, rel = c[4].split(':', 1)
            if rel == subject_rel:
                subj_node = c
                break

    if subj_node is None:
        return chunk_str

    # Singular: column 3 is not 'pl'
    number = subj_node[3] if len(subj_node) > 3 else ''
    if number == 'pl':
        return chunk_str

    # Also skip if k1 has a pl card/dem modifier (handled by _rule_verb_subj_agreement)
    try:
        subj_idx_float = float(subj_node[1])
    except (ValueError, TypeError):
        return chunk_str
    for c in rows:
        if len(c) < 5 or not c[4] or ':' not in c[4]:
            continue
        head, rel = c[4].split(':', 1)
        if rel in ('card', 'dem'):
            try:
                if float(head) == subj_idx_float and len(c) > 3 and c[3] == 'pl':
                    return chunk_str  # plural modifier present; other rule handles it
            except (ValueError, TypeError):
                pass

    pl_to_sg = {'have': 'has', 'were': 'was', 'are': 'is', 'do': 'does'}
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if '_ACTIVE' in tag or '_PASSIVE' in tag:
            words = c.split()
            chunks[i][0] = ' '.join(pl_to_sg.get(w.lower(), w) for w in words)
    return _join_chunks(chunks)


def _rule_wA_hE_present(chunk_str, feats, concept_dict):
    """wA_hE_1 TAM = habitual simple present.
    - Verb in -ed form in _ACTIVE chunk: prepend 'is' → 'is called'
    - Verb in base/uninflected form in _ACTIVE chunk: add -s → 'provides'
    - When _ACTIVE chunk is a pure copula ('is'/'are'): the semantic verb is in
      the immediately preceding untagged chunk — inflect that chunk instead.
    """
    rows = feats['rows']
    has_wA_hE = any(
        'wA_hE_1' in c[0]
        for c in rows
        if len(c) >= 5 and c[4] and ':' in c[4] and c[4].split(':', 1)[1] == 'main'
    )
    if not has_wA_hE:
        return chunk_str

    _PURE_COPULAS = {'is', 'are', 'was', 'were', 'be'}

    def _add_3sg_s(word):
        low = word.lower()
        if re.search(r'[^aeiou]y$', low):
            return word[:-1] + 'ies'
        elif re.search(r'(s|x|z|ch|sh)$', low):
            return word + 'es'
        else:
            return word + 's'

    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if '_ACTIVE' not in tag and '_PASSIVE' not in tag:
            continue
        words = c.strip().split()
        if not words:
            continue
        last = words[-1]
        low = last.lower()

        # Pure copula in _ACTIVE (e.g. 'is') — semantic verb is in prev untagged chunk
        if low in _PURE_COPULAS and len(words) == 1:
            prev = next(
                (j for j in range(i - 1, -1, -1) if chunks[j][1] == ''),
                None
            )
            if prev is not None:
                pw = chunks[prev][0].strip().split()
                if pw:
                    pl = pw[-1]
                    pl_low = pl.lower()
                    if not pl_low.endswith(('s', 'ed', 'ing', 'en')):
                        pw[-1] = _add_3sg_s(pl)
                        chunks[prev][0] = ' '.join(pw)
            continue

        # Case 1: past participle (-ed / -wn / -en) in _ACTIVE → prepend 'is'
        # -wn covers: known, blown, flown, grown, shown, thrown
        if (low.endswith('ed') or low.endswith('wn')) and words[0].lower() != 'is':
            chunks[i][0] = 'is ' + c.strip()
        # Case 2: uninflected base form in _ACTIVE → add -s
        elif not low.endswith(('s', 'ed', 'ing', 'en', 'wn')):
            words[-1] = _add_3sg_s(last)
            chunks[i][0] = ' '.join(words)
    return _join_chunks(chunks)


def _rule_k1s_absorb_pps(chunk_str, feats, concept_dict):
    """A standalone k1s predicate-adjective/participle absorbs adjacent
    prepositional-phrase chunks into a single chunk, with the k1s word first.

    Pattern: [on bank] [situated] [of sacred X] →
             [situated on bank of sacred X]

    Detection is purely tag-based (:k1s in the USR dependency) — no
    word-level filtering."""
    rows = feats['rows']

    k1s_surfaces = set()
    for c in rows:
        if len(c) < 5 or not c[4]:
            continue
        if ':' in c[4] and c[4].split(':', 1)[1] == 'k1s':
            en = _comp_english(c[0], concept_dict)
            if en and en.strip():
                k1s_surfaces.add(en.strip().lower())

    if not k1s_surfaces:
        return chunk_str

    chunks = _split_chunks(chunk_str)
    n = len(chunks)

    # Locate the k1s chunk (first word matches a k1s surface, untagged)
    k1s_idx = None
    for i, (c, tag) in enumerate(chunks):
        if tag != '':
            continue
        first = c.strip().lower().split()[0] if c.strip() else ''
        if first in k1s_surfaces:
            k1s_idx = i
            break

    if k1s_idx is None:
        return chunk_str

    # Collect preceding PP chunks (untagged, start with preposition)
    pre_pps = []
    j = k1s_idx - 1
    while j >= 0:
        pc, ptag = chunks[j]
        if ptag != '':
            break
        pw = pc.strip().split()
        if pw and pw[0].lower() in _PREP_WORDS:
            pre_pps.insert(0, j)
            j -= 1
        else:
            break

    # Collect following PP chunks
    post_pps = []
    j = k1s_idx + 1
    while j < n:
        nc, ntag = chunks[j]
        if ntag != '':
            break
        nw = nc.strip().split()
        if nw and nw[0].lower() in _PREP_WORDS:
            post_pps.append(j)
            j += 1
        else:
            break

    if not pre_pps and not post_pps:
        return chunk_str

    merged = chunks[k1s_idx][0]
    for jj in pre_pps:
        merged += ' ' + chunks[jj][0]
    for jj in post_pps:
        merged += ' ' + chunks[jj][0]

    remove = set(pre_pps) | set(post_pps)
    chunks[k1s_idx][0] = merged
    chunks = [c for i, c in enumerate(chunks) if i not in remove]
    return _join_chunks(chunks)


def _to_ing(word):
    """Convert an English verb stem to its present-participle (-ing) form."""
    w = word.lower()
    if w.endswith('ing'):
        return word                          # already -ing
    if w.endswith('ie'):
        return w[:-2] + 'ying'              # lie→lying, die→dying
    if w.endswith('e') and len(w) > 2 and w[-2] not in 'aeiou':
        return w[:-1] + 'ing'              # come→coming, make→making
    # CVC doubling (short words: run→running, sit→sitting, get→getting)
    if (len(w) >= 3 and
            w[-1] not in 'aeiouywx' and
            w[-2] in 'aeiou' and
            w[-3] not in 'aeiou' and
            len(w) <= 4):
        return w + w[-1] + 'ing'
    return w + 'ing'                        # go→going, walk→walking


_IRR_PAST_PARTS = {
    # irregular past participles (base form → pp differs)
    'held', 'done', 'gone', 'made', 'taken', 'given', 'known', 'seen',
    'built', 'brought', 'caught', 'fought', 'thought', 'bought', 'taught',
    'kept', 'left', 'lost', 'met', 'sent', 'told', 'led', 'won', 'put',
    'set', 'cut', 'hit', 'found', 'felt', 'spent', 'stuck', 'sat', 'stood',
    'laid', 'been', 'had', 'was', 'were', 'read', 'run', 'come', 'let',
    'cost', 'hurt', 'shut',
    # -en past participles (regular words ending in -en like 'happen'/'open' must NOT be here)
    'broken', 'spoken', 'written', 'stolen', 'frozen', 'risen', 'chosen',
    'driven', 'ridden', 'hidden', 'bitten', 'forgotten', 'gotten', 'proven',
    'woven', 'fallen', 'blown', 'flown', 'grown', 'shown', 'thrown', 'drawn',
}


def _is_past_participle(word):
    """Return True if word looks like an English past participle (not a base form).

    Only -ed words are caught by suffix; -en/-wn irregulars must be in the explicit
    set to avoid false-positives like 'happen', 'open', 'garden'.
    """
    w = word.lower()
    if w in _IRR_PAST_PARTS:
        return True
    return w.endswith('ed')


def _rule_kqw_mod_ing(chunk_str, feats, concept_dict):
    """Verbs with TAM=kqw and a :mod dependency are participial modifiers
    in Hindi (e.g. जा = go → going).  Convert their English base form to
    the -ing present-participle so 'main go line' becomes 'main going line'.

    Words that the dictionary already gave as past participles (established,
    held, …) are left unchanged — they function as adjectival past participles
    ('the established place', 'the annually held fair')."""
    rows = feats['rows']

    kqw_mod_bases = set()
    for c in rows:
        if len(c) < 5:
            continue
        if c[3] != 'kqw':
            continue
        if ':mod' not in (c[4] or ''):
            continue
        en = _comp_english(c[0], concept_dict)
        if en:
            kqw_mod_bases.add(en.strip().lower())

    if not kqw_mod_bases:
        return chunk_str

    chunks = _split_chunks(chunk_str)
    for ci, (c, tag) in enumerate(chunks):
        words = c.split()
        new_words = []
        for w in words:
            if w.lower() in kqw_mod_bases and not _is_past_participle(w):
                new_words.append(_to_ing(w))
            else:
                new_words.append(w)
        chunks[ci][0] = ' '.join(new_words)
    return _join_chunks(chunks)


def _rule_jk1_mk1(chunk_str, feats, concept_dict):
    """Jussive-causative construction: jk1 = instigator (becomes _SUBJ),
    mk1 = actual performer (prepend 'by ').

    Hindi: 'mahārāja śiva ne lord paraśurāma se X sthāpanā karāī'
    = 'mahārāja śiva had lord paraśurāma establish X'
    → [mahārāja śiva]_SUBJ … [by lord paraśurāma] … [k2]
    """
    rows = feats.get('rows', [])
    constr = feats.get('constr', {})

    jk1_node = None
    mk1_node = None
    for c in rows:
        if len(c) < 5 or ':' not in (c[4] or ''):
            continue
        _, rel = c[4].split(':', 1)
        if rel == 'jk1' and jk1_node is None:
            jk1_node = c
        elif rel == 'mk1' and mk1_node is None:
            mk1_node = c

    if jk1_node is None:
        return chunk_str

    jk1_en = _resolve_en(jk1_node[1], rows, concept_dict, constr).lower().strip()
    chunks = _split_chunks(chunk_str)

    # Assign _SUBJ to the jk1 chunk and move it to front
    jk1_first = jk1_en.split()[0] if jk1_en else ''
    jk1_ci = None
    for i, (c, tag) in enumerate(chunks):
        words_l = [w.lower() for w in c.split()]
        if jk1_first and jk1_first in words_l:
            jk1_ci = i
            break
    if jk1_ci is not None:
        # Remove _SUBJ from any current subject
        for j in range(len(chunks)):
            if chunks[j][1] == '_SUBJ':
                chunks[j][1] = ''
        chunks[jk1_ci][1] = '_SUBJ'
        # Move jk1 chunk to position 0 (after any discourse connector)
        disc_words = {'and', 'but', 'however', 'so', 'therefore', 'also'}
        insert_at = 0
        for i, (c, t) in enumerate(chunks):
            if t == '' and c.strip().lower() in disc_words:
                insert_at = i + 1
            else:
                break
        subj_chunk = chunks.pop(jk1_ci)
        chunks.insert(insert_at, subj_chunk)

    # Prepend 'by ' to mk1 chunk
    if mk1_node:
        mk1_en = _resolve_en(mk1_node[1], rows, concept_dict, constr).lower().strip()
        mk1_first = mk1_en.split()[0] if mk1_en else ''
        for i, (c, tag) in enumerate(chunks):
            if tag == '_SUBJ':
                continue
            words_l = [w.lower() for w in c.split()]
            if mk1_first and mk1_first in words_l:
                if not c.lower().strip().startswith('by '):
                    chunks[i][0] = 'by ' + c.strip()
                break

    return _join_chunks(chunks)


def _to_gerund(word):
    """Convert a base verb/noun to its -ing gerund form."""
    w = word.lower()
    _GERUND_IRREG = {
        'see': 'seeing', 'go': 'going', 'come': 'coming', 'run': 'running',
        'get': 'getting', 'sit': 'sitting', 'put': 'putting', 'cut': 'cutting',
        'set': 'setting', 'let': 'letting', 'hit': 'hitting', 'meet': 'meeting',
        'take': 'taking', 'make': 'making', 'give': 'giving', 'live': 'living',
        'have': 'having', 'write': 'writing', 'love': 'loving', 'use': 'using',
        'note': 'noting', 'settle': 'settling', 'arrive': 'arriving',
    }
    if w in _GERUND_IRREG:
        return _GERUND_IRREG[w]
    if w.endswith('ing'):
        return w  # already gerund
    if w.endswith('ed') or w.endswith('en') or w.endswith('wn'):
        return w  # past participle — leave unchanged
    if w.endswith('ie'):
        return w[:-2] + 'ying'
    if w.endswith('e') and len(w) > 2:
        return w[:-1] + 'ing'
    if re.search(r'[^aeiou][aeiou][^aeiouwxy]$', w) and len(w) <= 5:
        return w + w[-1] + 'ing'
    return w + 'ing'


def _rule_rt_gerund(chunk_str, feats):
    """Purpose (rt) chunks: convert the verb/noun immediately after 'for' to gerund.

    'for see of mother goddess' → 'for seeing of mother goddess'
    Only fires when sentence has rt relation.
    """
    if 'rt' not in feats.get('rels', set()):
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if tag in ('_ACTIVE', '_PASSIVE', '_IMPERATIVE'):
            continue
        words = c.split()
        if not words or words[0].lower() != 'for' or len(words) < 2:
            continue
        # The word right after "for" — convert to gerund if it looks like a base form
        candidate = words[1]
        low = candidate.lower()
        if low in ('the', 'a', 'an', 'peace', 'soul', 'holy', 'main',
                   'sacred', 'all', 'each', 'every'):
            continue  # nominal head — not a verb
        if not low.endswith(('ing', 'ed', 'en', 's')):
            words[1] = _to_gerund(candidate)
            chunks[i][0] = ' '.join(words)
    return _join_chunks(chunks)


def _rule_nc_r6_compound(chunk_str, feats):
    """NC construction as r6 of host noun: reorder 'host of nc' → 'nc host'.

    When an NC (noun compound: modifier+head) is the r6 genitive modifier of
    another noun, the result should be a compound adjective preceding the noun,
    not a genitive 'of' chain:
    'station of coastal' → 'coastal station'
    """
    nc_r6_hosts = feats.get('nc_r6_hosts') or []
    if not nc_r6_hosts:
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for nc_en, host_en in nc_r6_hosts:
        nc_words = nc_en.split()
        host_first = host_en.split()[0] if host_en else ''
        if not nc_words or not host_first:
            continue
        for i, (c, tag) in enumerate(chunks):
            words = c.split()
            low = [w.lower() for w in words]
            # Pattern: "host of NC" — host is first word, "of" follows, then NC words
            if not low or low[0] != host_first.lower():
                continue
            # Find 'of' in the chunk
            of_pos = next((j for j, w in enumerate(low) if w == 'of'), None)
            if of_pos is None:
                continue
            after_of = low[of_pos + 1:]
            # Check that at least the last NC word appears after 'of'
            nc_last = nc_words[-1]
            if not any(w == nc_last or w.startswith(nc_last) for w in after_of):
                continue
            # Remove 'of nc_words' from the chunk and prepend nc_words
            new_words = words[:of_pos] + words[of_pos + 1 + len(after_of):]
            # Rebuild: NC words + remaining host words
            chunks[i][0] = ' '.join(list(nc_words) + new_words)
            break
    return _join_chunks(chunks)


def _rule_pl_distal_they(chunk_str, feats):
    """$wyax pl+distal as k1 subject should use 'they', not 'that'/'those'.

    In Hindi: 've' (वे) = 3rd pl distal pronoun — English 'they'.
    When $wyax has pl + distal + k1 dependency (surface subject of an active
    clause), the chunk 'that'/'those' in SUBJ position is replaced with 'they'.
    """
    if not feats.get('wyax_is_k1_pl_distal'):
        return chunk_str
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        if tag == '_SUBJ' and c.strip().lower() in ('that', 'those'):
            chunks[i][0] = 'they'
    return _join_chunks(chunks)



def _rule_strip_trailing_rbks_active(chunk_str, feats):
    """Strip extra _ACTIVE chunks that appear after the main (0:main) verb.

    rpk/rsk/rbks constructions generate their own _ACTIVE-tagged chunks
    (e.g. [karA]_ACTIVE, [forested]_ACTIVE, [taken]_ACTIVE). Only the
    first _ACTIVE chunk (the main verb) is kept; trailing short _ACTIVE
    chunks from participial/rbks constructions are removed.
    """
    chunks = _split_chunks(chunk_str)
    active_indices = [i for i, (c, t) in enumerate(chunks) if '_ACTIVE' in t]
    if len(active_indices) <= 1:
        return chunk_str
    for i in active_indices[1:]:
        words = chunks[i][0].strip().split()
        if len(words) <= 3:   # short trailing rbks verb chunk
            chunks[i] = None
    chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_resolve_wyax_pronoun(chunk_str, feats):
    """Resolve raw 'wyax' in chunk text to the correct English pronoun.

    $wyax = Hindi 3rd-person pronoun (yah/wah/ve).  Surface form depends on:
      number: sg → it/its, pl → they/them/their
      case (derived from USR dependency relation):
        k1  → nominative  (it / they)
        k2  → objective   (it / them)
        r6  → genitive    (its / their)
        k4/k7p → objective (it / them)
    """
    if 'wyax' not in chunk_str.lower():
        return chunk_str
    rows = feats.get('rows', [])

    wyax_rel = 'r6'    # default: possessive context most common in this corpus
    wyax_number = 'sg'
    for c in rows:
        if c[0] != '$wyax':
            continue
        wyax_number = c[3] if len(c) > 3 else 'sg'
        if len(c) > 4 and c[4] and ':' in c[4]:
            wyax_rel = c[4].split(':', 1)[1]
        break

    if wyax_number == 'pl':
        pron_map = {'k1': 'they', 'k2': 'them', 'r6': 'their',
                    'k4': 'them', 'k7p': 'them', 'k7t': 'them'}
        default_pron = 'their'
    else:
        pron_map = {'k1': 'it', 'k2': 'it', 'r6': 'its',
                    'k4': 'it', 'k7p': 'it', 'k7t': 'it'}
        default_pron = 'its'

    pron = pron_map.get(wyax_rel, default_pron)

    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        words = c.split()
        chunks[i][0] = ' '.join(pron if w.lower() == 'wyax' else w for w in words)
    return _join_chunks(chunks)


def _rule_strip_trailing_rbks_active(chunk_str, feats):
    """Strip extra _ACTIVE chunks after the main verb (rpk/rsk/rbks artifacts).

    Only the first _ACTIVE chunk (0:main verb) is kept; trailing short
    _ACTIVE chunks from participial constructions are removed.
    """
    chunks = _split_chunks(chunk_str)
    active_indices = [i for i, (c, t) in enumerate(chunks) if '_ACTIVE' in t]
    if len(active_indices) <= 1:
        return chunk_str
    for i in active_indices[1:]:
        if len(chunks[i][0].strip().split()) <= 3:
            chunks[i] = None
    chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_resolve_wyax_pronoun(chunk_str, feats):
    """Resolve raw 'wyax' in chunk text to the correct English pronoun.

    $wyax = Hindi 3rd-person pronoun. Surface form chosen by number and
    USR dependency relation (k1=nominative, r6=genitive, k2=objective).
    """
    if 'wyax' not in chunk_str.lower():
        return chunk_str
    rows = feats.get('rows', [])
    wyax_rel = 'r6'
    wyax_number = 'sg'
    for c in rows:
        if c[0] != '$wyax':
            continue
        wyax_number = c[3] if len(c) > 3 else 'sg'
        if len(c) > 4 and c[4] and ':' in c[4]:
            wyax_rel = c[4].split(':', 1)[1]
        break
    if wyax_number == 'pl':
        pron_map = {'k1': 'they', 'k2': 'them', 'r6': 'their',
                    'k4': 'them', 'k7p': 'them', 'k7t': 'them'}
        default_pron = 'their'
    else:
        pron_map = {'k1': 'it', 'k2': 'it', 'r6': 'its',
                    'k4': 'it', 'k7p': 'it', 'k7t': 'it'}
        default_pron = 'its'
    pron = pron_map.get(wyax_rel, default_pron)
    chunks = _split_chunks(chunk_str)
    for i, (c, tag) in enumerate(chunks):
        chunks[i][0] = ' '.join(pron if w.lower() == 'wyax' else w for w in c.split())
    return _join_chunks(chunks)


def _rule_keep_first_subj(chunk_str, feats):
    chunks = _split_chunks(chunk_str)
    seen = False
    for i, (c, t) in enumerate(chunks):
        if '_SUBJ' in t:
            if seen:
                chunks[i][1] = t.replace('_SUBJ', '')
            else:
                seen = True
    return _join_chunks(chunks)


def _rule_propagate_shared_subject(chunk_str, feats):
    """Copy _SUBJ from previous clause into conjunction-led clause that lacks one."""
    b = _split_chunks(chunk_str)
    if any('_SUBJ' in t for _, t in b):
        return chunk_str
    if not b or b[0][0].lower().strip() not in ('and','but','or','while','whereas'):
        return chunk_str
    prev = feats.get('_prev_subj_chunk')
    if prev is None:
        return chunk_str
    b.insert(1, list(prev))
    return _join_chunks(b)


def _rule_strip_trailing_rbks_active(chunk_str, feats):
    chunks = _split_chunks(chunk_str)
    active_indices = [i for i,(c,t) in enumerate(chunks) if '_ACTIVE' in t]
    if len(active_indices) <= 1:
        return chunk_str
    for i in active_indices[1:]:
        if len(chunks[i][0].strip().split()) <= 3:
            chunks[i] = None
    chunks = [x for x in chunks if x is not None]
    return _join_chunks(chunks)


def _rule_resolve_wyax_pronoun(chunk_str, feats):
    if 'wyax' not in chunk_str.lower():
        return chunk_str
    rows = feats.get('rows', [])
    wyax_rel = 'r6'
    wyax_number = 'sg'
    for c in rows:
        if c[0] != '$wyax':
            continue
        wyax_number = c[3] if len(c) > 3 else 'sg'
        if len(c) > 4 and c[4] and ':' in c[4]:
            wyax_rel = c[4].split(':',1)[1]
        break
    if wyax_number == 'pl':
        pron_map = {'k1':'they','k2':'them','r6':'their','k4':'them','k7p':'them','k7t':'them'}
        default_pron = 'their'
    else:
        pron_map = {'k1':'it','k2':'it','r6':'its','k4':'it','k7p':'it','k7t':'it'}
        default_pron = 'its'
    pron = pron_map.get(wyax_rel, default_pron)
    chunks = _split_chunks(chunk_str)
    for i,(c,tag) in enumerate(chunks):
        chunks[i][0] = ' '.join(pron if w.lower()=='wyax' else w for w in c.split())
    return _join_chunks(chunks)

_COPULA_AUX_WORDS = {
    'is','are','was','were','be','been','being','am',
    'has','have','had','will','would','can','could',
    'should','shall','may','might','must','do','does','did',
    'get','gets','got','gotten',
}

def _rule_tag_untagged_copula(chunk_str, feats):
    """If no _ACTIVE/_PASSIVE chunk exists, tag the first pure-copula/aux chunk as _ACTIVE."""
    chunks = _split_chunks(chunk_str)
    if any(t in ('_ACTIVE', '_PASSIVE') for _, t in chunks):
        return chunk_str
    for i, (c, tag) in enumerate(chunks):
        if tag:
            continue
        words = [w.lower().strip('#') for w in c.strip().split()]
        if words and all(w in _COPULA_AUX_WORDS for w in words):
            chunks[i][1] = '_ACTIVE'
            return _join_chunks(chunks)
    return chunk_str


def _rule_subj_before_verb(chunk_str, feats):
    """Move _SUBJ chunks to before the first _ACTIVE/_PASSIVE if they appear after it."""
    chunks = _split_chunks(chunk_str)
    subj_idx = [i for i, (c, t) in enumerate(chunks) if '_SUBJ' in t]
    verb_idx = [i for i, (c, t) in enumerate(chunks) if t in ('_ACTIVE', '_PASSIVE')]
    if not subj_idx or not verb_idx:
        return chunk_str
    first_verb = min(verb_idx)
    if all(i < first_verb for i in subj_idx):
        return chunk_str
    subj_chunks = [chunks[i] for i in subj_idx]
    non_subj = [chunks[i] for i in range(len(chunks)) if i not in subj_idx]
    return _join_chunks(subj_chunks + non_subj)


def apply_postprocess(chunked_data, usr_text, concept_dict):
    blocks = parse_usr_blocks(usr_text)
    for sid, chunks in list(chunked_data.items()):
        rec = blocks.get(sid)
        if not rec:
            continue
        try:
            feats = _build_features(rec, concept_dict)
            new_chunks = []
            for chunk in chunks:
                ch = chunk
                if sid in ('Sent_30', 'Sent_31'):
                    import sys; sys.stderr.write(f'[INIT {sid}] ' + repr(ch[:160]) + '\n'); sys.stderr.flush()
                ch = _rule_split_joined(ch, feats, concept_dict)
                ch = _rule_strip_struct_tokens(ch)
                ch = _rule_wh_word(ch, feats)
                ch = _rule_coordination(ch, feats, concept_dict)
                ch = _rule_part_whole(ch, feats, concept_dict)
                ch = _rule_genitive_of_order(ch, feats, concept_dict)
                ch = _rule_superlative(ch, feats)
                ch = _rule_as_complement(ch, feats)
                ch = _rule_kqw_mod_ing(ch, feats, concept_dict)
                ch = _rule_span_from_to(ch, feats)
                ch = _rule_ne_mod_attach(ch, feats)
                ch = _rule_ord_attach(ch, feats)
                ch = _rule_cp_light_verb(ch, feats)
                ch = _rule_presubj_modifier_merge(ch, feats, concept_dict)
                ch = _rule_strip_spurious_r6_from_subj(ch, feats)
                ch = _rule_move_also_to_subj(ch, feats)
                ch = _rule_also_temporal_before_subj(ch, feats)
                ch = _rule_fix_respect_subj(ch, feats)
                ch = _rule_merge_consecutive_subj(ch, feats)
                ch = _rule_extract_rpk_from_active(ch, feats)
                ch = _rule_absorb_trailing_location_into_active(ch, feats)
                ch = _rule_absorb_postsubj_card_dem(ch, feats, concept_dict)
                ch = _rule_subj_plural_agreement(ch, feats, concept_dict)
                ch = _rule_verb_subj_agreement(ch, feats, concept_dict)
                ch = _rule_recover_passive_k2_subject(ch, feats, concept_dict)
                ch = _rule_verb_sg3_agreement(ch, feats, concept_dict)
                ch = _rule_wA_hE_present(ch, feats, concept_dict)
                ch = _rule_imperative_first(ch, feats)
                ch = _rule_focus_trailing(ch, feats)
                ch = _rule_prepositions(ch, feats)
                ch = _rule_temporal_at(ch, feats)
                ch = _rule_fix_temporal_preposition(ch, feats)
                ch = _rule_fix_pron_postposition(ch, feats)
                ch = _rule_rkl_after_before(ch, feats)
                ch = _rule_near_location(ch, feats)
                ch = _rule_quant_several(ch, feats)
                ch = _rule_attach_article(ch, feats)
                ch = _rule_dist_meas_merge(ch, feats)
                ch = _rule_unit_merge(ch, feats)
                ch = _rule_unit_plural(ch, feats)
                ch = _rule_merge_stranded_modifier(ch, feats, concept_dict)
                ch = _rule_measure_about(ch, feats)
                ch = _rule_passive(ch, feats)
                ch = _rule_k1s_absorb_pps(ch, feats, concept_dict)
                ch = _rule_inject_missing_ne_mods(ch, feats, concept_dict)
                ch = _rule_merge_route_through(ch, feats)
                ch = _rule_pull_via_into_span(ch, feats)
                ch = _rule_merge_location_pps(ch, feats)
                ch = _rule_krvn_after_verb(ch, feats)
                ch = _rule_surface(ch)
                ch = _rule_strip_struct_tokens(ch)
                ch = _rule_dedup_function_words(ch)
                ch = _rule_strip_index_artifacts(ch, feats)
                ch = _rule_lone_also(ch, feats)
                ch = _rule_drop_dup_operand(ch, feats)
                ch = _rule_used_to(ch, feats)
                ch = _rule_inceptive_aux(ch, feats)
                ch = _rule_remove_lone_prepositions(ch, feats)
                ch = _rule_discourse_front(ch, feats)
                ch = _rule_recover_subject(ch, feats)
                ch = _rule_article_phonetics(ch, feats)
                ch = _rule_predicate_before_lexverb(ch)
                ch = _rule_avasyaka_jA_passive_modal(ch, feats)
                ch = _rule_e2_jA_future_passive(ch, feats)
                ch = _rule_hortative_let_us(ch, feats)
                ch = _rule_coord_mod_reorder(ch, feats)
                ch = _rule_k3_kqw_by_performing(ch, feats, concept_dict)
                ch = _rule_k7t_at_vs_in(ch, feats)
                ch = _rule_jk1_mk1(ch, feats, concept_dict)
                ch = _rule_dedup_leading_prepositions(ch, feats)
                ch = _rule_fix_passive_verb_forms(ch, feats)
                ch = _rule_tag_untagged_copula(ch, feats)
                ch = _rule_keep_first_subj(ch, feats)
                ch = _rule_strip_trailing_rbks_active(ch, feats)
                ch = _rule_resolve_wyax_pronoun(ch, feats)
                # propagate subject from previous clause
                subj_chunk = next(((c,t) for c,t in _split_chunks(ch) if '_SUBJ' in t), None)
                if subj_chunk:
                    feats['_prev_subj_chunk'] = subj_chunk
                ch = _rule_propagate_shared_subject(ch, feats)
                ch = _rule_strip_trailing_rbks_active(ch, feats)
                ch = _rule_resolve_wyax_pronoun(ch, feats)
                ch = _rule_rt_gerund(ch, feats)
                ch = _rule_nc_r6_compound(ch, feats)
                ch = _rule_pl_distal_they(ch, feats)
                ch = _rule_merge_rt_with_r6(ch, feats)
                ch = _rule_merge_participial_into_locative_conj(ch, feats)
                ch = _rule_lift_r6_from_k5_to_head(ch, feats)
                ch = _rule_move_trailing_from_before_active(ch, feats)
                ch = _rule_subj_before_verb(ch, feats)
                ch = _rule_strip_index_artifacts(ch, feats)   # second pass
                new_chunks.append(ch)
            # List-level cleanup: remove lone single-word _ACTIVE chunks that are
            # suppressed rsk nonfinite verbs (e.g. [ho]_ACTIVE) when a [via X]
            # chunk is already present covering the same meaning.
            _NONFINITE_RESIDUALS = {
                'ho', 'kar', 'hote', 'karte', 'jaate', 'aate',
                'lete', 'dete', 'bante', 'rahte',
            }
            # new_chunks is a list of full chunk strings; split each to individual chunks
            final_chunks = []
            for ch_str in new_chunks:
                ind_chunks = _split_chunks(ch_str)
                has_via = any(
                    c.strip().lower().startswith('via ')
                    for c, _ in ind_chunks
                )
                if has_via:
                    kept = []
                    for c, tag in ind_chunks:
                        words = c.strip().split()
                        if len(words) == 1 and tag in ('_ACTIVE', '_PASSIVE', ''):
                            inner = words[0].lstrip('#').lower()
                            if inner in _NONFINITE_RESIDUALS:
                                print("[DEBUG] Removed suppressed rsk verb: [%s]%s" % (c, tag))
                                continue
                        kept.append([c, tag])
                    ch_str = _join_chunks(kept)
                final_chunks.append(ch_str)
            new_chunks = final_chunks

            chunked_data[sid] = new_chunks
        except Exception:
            continue
    return chunked_data


def load_concept_dict(concept_file="dictionaries/concept-to-mrs-rels.dat"):
    d = {}
    try:
        with open(concept_file, encoding='utf-8') as f:
            for row in f:
                cols = row.strip().split()
                if len(cols) > 3:
                    d[cols[1]] = cols[3]
    except FileNotFoundError:
        pass
    return d
