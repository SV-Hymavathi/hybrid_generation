#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USR corrector (offline, guideline-driven) -- USR Guideline v4.2.1.

Pipeline:  read USRs  ->  correct  ->  write corrected USRs (+ change log)
           ->  (optional) run the generator and print the English chunks.

Column layout (per the guideline, 9 fields per token row):
  0 concept | 1 index | 2 semcat | 3 morpho | 4 DEPENDENCY (head:rel)
  5 discourse | 6 speaker's-view | 7 scope | 8 CONSTRUCTION (head:role)

How relations are decided (not blind defaults):
  The kaaraka relation of a participant is fixed by the *vibhakti*
  (post-position) that follows it in the Hindi sentence. The corrector
  transliterates the '#' Devanagari sentence to WX, aligns each token, reads the
  following post-position, and assigns the relation the guideline prescribes:

     ne -> k1        ko -> k2 (k4/k4a in ditransitive/experiential)
     se -> k5 (k3 if dwArA-agent / instrument; k5prk for 'se banA')
     meM/para -> k7p     ke lie -> rt        ke kAraNa -> rh
     kA/kI/ke -> r6      ke anusAra -> k7a    ke pAsa -> rsm
     kI ora/taraPa -> rd  ke bAxa -> rkrl     se pahale -> rkl
     dwArA -> k3 (agent)

  When no post-position governs the token, structure decides:
     - adjective/noun immediately under a copula  -> k1s (subject complement)
     - a nominal modifier inside a compound        -> mod
  Such fallbacks are flagged in the log so you can review them.

Structural repairs (each logged):
  duplicate 0:main, malformed '-_1' verbalizer, broken head refs, column
  padding, and a genitive clause-subject ($wyax r6 on a verbal noun) -> k1
  (which prevents the chunker's "GNP ... k1 is missing" crash).

Construction validation:
  every [ne_/nc_/cp_/conj_/disjunct_/span_/spatial_/temporal_/calendar_/meas_/
  dist_meas_] token is checked for a dependency relation and for the component
  roles the guideline requires; problems are reported.

Usage:
  python3 usr_corrector.py my_usrs.txt                 # -> my_usrs.corrected.txt
  python3 usr_corrector.py my_usrs.txt -o out.txt
  python3 usr_corrector.py my_usrs.txt --generate
  python3 usr_corrector.py my_usrs.txt --quiet
"""

import re, sys, os, argparse, subprocess

NCOL = 9
COPULA = ('hE', 'WA', 'raha', 'ho_')
VERBALIZER_DEFAULT = 'kara_1'

# ---- vibhakti (post-position) -> kaaraka relation (guideline tables 1-12) ----
SIMPLE_POSTPOS = {
    'ne': 'k1', 'nE': 'k1',
    'ko': 'k2',                       # may resolve to k4 / k4a (see context)
    'se': 'k5',                       # may resolve to k3 / k5prk (see context)
    'meM': 'k7p', 'mEM': 'k7p', 'me': 'k7p',
    'para': 'k7p', 'par': 'k7p', 'pe': 'k7p',
    'kA': 'r6', 'kI': 'r6', 'ke': 'r6',
    'waka': 'k7t', 'wak': 'k7t',
}
# "ke / kI / se + WORD" multi-word post-positions
KE_COMPOUNDS = {
    'lie': 'rt', 'liye': 'rt', 'liE': 'rt',
    'kAraNa': 'rh', 'kAraN': 'rh',
    'pAsa': 'rsm', 'pAs': 'rsm',
    'anusAra': 'k7a', 'anusAr': 'k7a',
    'sAWa': 'k7as', 'sAW': 'k7as',
    'bAxa': 'rkrl', 'bAx': 'rkrl',
    'binA': 'krvnneg',
    'xvArA': 'k3', 'dvArA': 'k3',
}
KI_COMPOUNDS = {'ora': 'rd', 'oara': 'rd', 'waraPa': 'rd', 'waraP': 'rd', 'wulanA': 'rv'}
SE_COMPOUNDS = {'pahale': 'rkl', 'pahle': 'rkl', 'lekara': 'span', 'lekar': 'span'}
STANDALONE = {'xvArA': 'k3', 'dvArA': 'k3', 'jEsA': 'ru', 'jEse': 'ru', 'samAna': 'ru'}
PARTICLES = {'hI', 'BI', 'wo', 'waka', 'na', 'nahIM', 'evaM', 'waWA', 'Ora', 'yA', 'aura'}
EXPERIENCER_VERBS = ('pasaMxa', 'buKAra', 'acCA_lag', 'pasanx', 'cAhi', 'mila')


# ----------------------------------------------------------------- parsing ----
def parse_blocks(text):
    out = []
    for m in re.finditer(r'<sent_id=([^>\s]+)>(.*?)</sent_id>', text, re.S):
        sid, body = m.group(1), m.group(2)
        sentence, stype, rows = '', '', []
        for ln in body.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith('#'):
                sentence = s
            elif s.startswith('%'):
                stype = s
            else:
                c = s.split()
                if len(c) >= 2 and c[1].isdigit():
                    rows.append(c)
        out.append([sid, sentence, rows, stype])
    return out


def pad(r):
    r = list(r)
    while len(r) < NCOL:
        r.append('-')
    return r[:NCOL]


def headrel(r):
    c = r[4]
    if c and c != '-' and ':' in c:
        h, rel = c.split(':', 1)
        return h, rel
    return None, None


def set_rel(r, h, rel, log, sid, why):
    old = r[4]
    r[4] = '%s:%s' % (h, rel)
    if old != r[4]:
        log.append("  [%s] '%s' %s -> %s:%s  (%s)" % (sid, r[0], old, h, rel, why))


def crole(r):
    c = r[8] if len(r) > 8 else '-'
    if c and c != '-' and ':' in c:
        return c.split(':', 1)
    return None, None


def is_copula(c):
    return any(c.startswith(p) for p in COPULA) or '_hE_' in c or c.endswith('hE_1') or c.endswith('-pres') or c.endswith('-past')


def is_verbish(c):
    if c.startswith('[cp') or c.startswith('[conj') or c.startswith('[disjunct'):
        return True
    return bool(re.search(r'(-pres|-past|_hE_|_WA_|_gayA|_jAwA|_jA_|-wA|-yA|-e_1|_kara|_ho_)', c)) or is_copula(c)


# ---- transliterate the '#' sentence to WX and tokenise --------------------
def sentence_wx(sentence):
    s = sentence.lstrip('#').strip()
    s = re.sub(r'[।\.\|,\'"\(\)\-]', ' ', s)
    if re.search(r'[\u0900-\u097F]', s):                 # Devanagari -> WX
        try:
            from wxconv import WXC
            s = WXC(order='utf2wx').convert(s)
        except Exception:
            return []
    return [t for t in s.split() if t]


def stem(concept):
    """Reduce a USR concept to a matchable WX surface stem (drop sense/TAM/MWE).
    WX is case-sensitive (A != a), so case is preserved."""
    c = concept
    if c.startswith('['):
        return None
    c = c.split('-')[0]            # drop TAM (kara_1-yA_1 -> kara_1)
    c = c.split('+')[0]            # first part of an MWE
    c = re.sub(r'_\d+$', '', c)    # drop sense number
    return c


def find_postpos(anchor, toks):
    """Return the kaaraka relation implied by the post-position following the
    anchor surface in the WX sentence, or None.  Matching is case-sensitive
    (WX), with a case-insensitive fallback for the anchor only."""
    if not anchor or not toks:
        return None, None

    def match(i):
        t = toks[i]
        return t == anchor or t.startswith(anchor) or anchor.startswith(t) \
            or t.lower() == anchor.lower()
    pos = next((i for i in range(len(toks)) if match(i)), None)
    if pos is None:
        return None, None
    nxt = toks[pos + 1] if pos + 1 < len(toks) else ''
    nxt2 = toks[pos + 2] if pos + 2 < len(toks) else ''
    if nxt in ('ke', 'kI', 'kA', 'ki'):
        if nxt2 in KE_COMPOUNDS:
            return KE_COMPOUNDS[nxt2], "post-position 'ke %s'" % nxt2
        if nxt in ('kI', 'ki') and nxt2 in KI_COMPOUNDS:
            return KI_COMPOUNDS[nxt2], "post-position 'kI %s'" % nxt2
        return 'r6', "post-position '%s'" % nxt
    if nxt == 'se' and nxt2 in SE_COMPOUNDS:
        rel = SE_COMPOUNDS[nxt2]
        return (rel if rel != 'span' else 'k5'), "post-position 'se %s'" % nxt2
    if nxt in STANDALONE:
        return STANDALONE[nxt], "marker '%s'" % nxt
    if nxt in SIMPLE_POSTPOS:
        return SIMPLE_POSTPOS[nxt], "post-position '%s'" % nxt
    return None, None


# ----------------------------------------------------------- correction ----
def ne_last_surface(rows, ne_idx):
    """Stem of the last component word of an [ne_X]/compound construction."""
    comps = [r for r in rows if crole(r)[0] == ne_idx
             and crole(r)[1] in ('begin', 'inside', 'head', 'op2', 'op1', 'inside')]
    if not comps:
        return None
    return stem(comps[-1][0])


def correct_block(sid, sentence, rows, log):
    rows = [pad(r) for r in rows]
    idx_set = {r[1] for r in rows}
    by_idx = {r[1]: r for r in rows}
    toks = sentence_wx(sentence)

    mains = [r for r in rows if r[4] == '0:main']
    main_idx = mains[0][1] if mains else None
    main_is_cop = bool(mains) and is_copula(mains[0][0])
    main_stem = (stem(mains[0][0]) or '') if mains else ''

    # (A) duplicate 0:main -> keep the verb, demote others to k1s ------------
    if len(mains) > 1:
        keep = next((r for r in mains if is_verbish(r[0])), mains[-1])
        main_idx, main_is_cop = keep[1], is_copula(keep[0])
        for r in mains:
            if r is not keep:
                set_rel(r, keep[1], 'k1s', log, sid, 'duplicate 0:main demoted')

    # (B) malformed verbalizer ----------------------------------------------
    for r in rows:
        if crole(r)[1] == 'verbalizer' and r[0] in ('-', '-_1', '_', '_1'):
            log.append("  [%s] verbalizer '%s' -> %s" % (sid, r[0], VERBALIZER_DEFAULT))
            r[0] = VERBALIZER_DEFAULT

    # (C) genitive clause-subject on a verbal noun -> k1 (crash fix) ---------
    kriyamula = {r[1] for r in rows if crole(r)[1] == 'kriyAmUla'}
    for r in rows:
        h, rel = headrel(r)
        if rel == 'r6' and h in kriyamula and r[0].startswith('$wyax'):
            set_rel(r, h, 'k1', log, sid, 'genitive subject of embedded clause')

    # (D) resolve invalid relations (dep, or NE-intf) via vibhakti ----------
    def anchor_for(r):
        if r[0].startswith('['):
            return ne_last_surface(rows, r[1])
        return stem(r[0])

    for r in rows:
        h, rel = headrel(r)
        if rel not in ('dep', 'intf'):
            continue
        if rel == 'intf' and not (r[0].startswith('[ne_') or r[2] in ('place', 'per', 'org')):
            continue                                   # keep adverbial intensifier
        newrel, why = find_postpos(anchor_for(r), toks)
        if newrel:
            # context refinements the post-position alone cannot give
            if newrel == 'k2' and r[2] == '-' and any(
                    main_stem.startswith(e) for e in EXPERIENCER_VERBS):
                newrel, why = 'k4a', why + ' + experiential verb'
            if newrel == 'k5' and ('banA' in main_stem or 'nirmiwa' in main_stem
                                   or 'bana' in main_stem):
                newrel, why = 'k5prk', why + ' + material/agent'
            set_rel(r, h, newrel, log, sid, why)
        elif h == main_idx and main_is_cop:
            set_rel(r, h, 'k1s', log, sid, 'predicate complement under copula')
        else:
            set_rel(r, h, 'mod', log, sid, 'no post-position; modifier default (verify r6/mod)')

    # (E) broken head references --------------------------------------------
    has_main = any(r[4] == '0:main' for r in rows)
    for r in rows:
        h, rel = headrel(r)
        if h is None or h == '0' or h in idx_set:
            continue
        if r[0].startswith('[cp') and not has_main:
            set_rel(r, '0', 'main', log, sid, 'broken head -> 0:main')
            has_main = True
        elif main_idx:
            set_rel(r, main_idx, rel or 'mod', log, sid, 'broken head retargeted to main')

    # (F) construction validation (report-only) -----------------------------
    REQUIRED = {
        'cp': {'kriyAmUla', 'verbalizer'}, 'conj': {'op1'}, 'disjunct': {'op1'},
        'span': {'start', 'end'}, 'spatial': {'whole', 'part'},
        'temporal': {'whole', 'part'}, 'nc': set(), 'ne': set(), 'calendar': set(),
        'meas': set(), 'dist_meas': set(),
    }
    for r in rows:
        m = re.match(r'\[([a-zA-Z]+)_', r[0])
        if not m:
            continue
        kind = m.group(1)
        crole_head, crole_role = crole(r)
        # a construction token that is itself a component/operand of a parent
        # construction (has a construction role) gets its relation via the
        # parent, so it need not carry a direct dependency relation
        is_component = crole_role is not None
        if (r[4] in ('-', '') or ':' not in (r[4] or '')) and r[4] != '0:main' \
                and not is_component:
            log.append("  [%s] construction %s has no dependency relation (review)" % (sid, r[0]))
        need = REQUIRED.get(kind)
        if need:
            have = {crole(x)[1] for x in rows if crole(x)[0] == r[1]}
            miss = need - have
            if miss:
                log.append("  [%s] construction %s missing component role(s): %s"
                           % (sid, r[0], ', '.join(sorted(miss))))
    return rows


def render(sid, sentence, rows, stype):
    out = ['<sent_id=%s>' % sid]
    if sentence:
        out.append(sentence)
    out += [' '.join(r) for r in rows]
    out.append(stype or '%affirmative')
    out.append('</sent_id>')
    return '\n'.join(out)


def correct_text(text):
    log = []
    out = []
    for sid, sentence, rows, stype in parse_blocks(text):
        out.append(render(sid, sentence, correct_block(sid, sentence, rows, log), stype))
    return '\n\n'.join(out) + '\n', log


# --------------------------------------------------------------- generate ---
def run_generator(path):
    here = os.path.dirname(os.path.abspath(__file__))
    import shutil
    shutil.copy(path, os.path.join(here, 'gen_input.txt'))
    p = subprocess.run([sys.executable, 'hindi_gen.py', '--lang', 'en'],
                       cwd=here, capture_output=True, text=True)
    # hindi_gen.py now prints one clean "sid: text" line per sentence on stdout
    # (all debug noise goes to debug_hi_en.txt).
    result = {}
    for ln in p.stdout.splitlines():
        ln = ln.strip()
        if ln and ': ' in ln and not ln.startswith(('=', '[', 'No ')):
            sid, text = ln.split(': ', 1)
            result[sid] = [text]
    if not result:
        return None, p.stderr[-500:]
    return result, None


def main():
    ap = argparse.ArgumentParser(description='Correct USRs (guideline v4.2.1), then optionally generate.')
    ap.add_argument('input')
    ap.add_argument('-o', '--output')
    ap.add_argument('--generate', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    text = open(a.input, encoding='utf-8').read()
    corrected, log = correct_text(text)
    out = a.output or re.sub(r'(\.[^.]+)?$', '.corrected.txt', a.input, count=1)
    open(out, 'w', encoding='utf-8').write(corrected)

    print('Corrected %d block(s) -> %s' % (corrected.count('<sent_id='), out))
    print('%d change(s)/note(s).' % len(log))
    if log and not a.quiet:
        print('\n--- change log ---')
        print('\n'.join(log))
    if a.generate:
        print('\n--- generating English chunks ---')
        res, err = run_generator(out)
        if res is None:
            print('Generation failed:', err); sys.exit(1)
        for sid in sorted(res):
            print('%s: %s' % (sid, res[sid][0]))


if __name__ == '__main__':
    main()
