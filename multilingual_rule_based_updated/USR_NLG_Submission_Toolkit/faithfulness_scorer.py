#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faithfulness_scorer.py — ONE consistent scorer for every system in the paper.

It compares each system's English output against your manually-created gold and
reports a transliteration-tolerant token-F1 (the "faithfulness" score), plus a
corpus BLEU and chrF for reference. Running EVERYTHING through this one file is
what keeps the paper's numbers on the same scale.

WHAT IT SCORES (reads your existing files automatically if present):
  • Direct LLMs   (Llama / Mistral / Gemma)  -> from the direct-translation analysis xlsx
  • Baselines     (Google Translate / IndicTrans2) -> from the two baseline CSVs
  • Hybrid        (Llama / Mistral / Gemma)  -> from the hybrid 3-model xlsx

USAGE (put this file in the folder with your data files, then):
    pip install openpyxl
    python3 faithfulness_scorer.py

It writes:  faithfulness_scores.csv   (one row per system: F1, BLEU, chrF, n)
and prints the same table to the screen.

If your filenames differ, edit the FILES section near the top.
"""
import csv, re, math, unicodedata, statistics as st, os
from collections import Counter
from openpyxl import load_workbook

# ------------------------------------------------------------------ FILES
DIRECT_XLSX  = "03_direct_Hindi_to_English_translation_faithfulness.xlsx"
HYBRID_XLSX  = "05_hybrid_chunks_to_sentence_3model_BLEU_chrF.xlsx"
GOOGLE_CSV   = "baseline_google_translations.csv"
INDIC_CSV    = "baseline_indictrans2_translations.csv"
# =================================================================== METRIC
def norm(s):
    """Lowercase, strip diacritics/accents (so transliteration spelling differences
    like 'Dvaraka' vs 'Dwarka' don't count as errors), drop punctuation, split."""
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return [w for w in re.sub(r'[^a-z0-9\s]', ' ', s).split() if w]

def token_f1(gold, out):
    """Set-based token F1 = harmonic mean of precision and recall over content
    word TYPES. 1.0 = identical word set; 0.0 = no shared words. This is the
    'faithfulness' score: does the output carry the same words/meaning as the gold,
    ignoring spelling and word order."""
    G, O = set(norm(gold)), set(norm(out))
    if not G and not O: return 1.0
    if not G or not O:   return 0.0
    inter = len(G & O)
    if not inter: return 0.0
    p = inter/len(O)        # precision: how much of the output is in the gold
    r = inter/len(G)        # recall:    how much of the gold the output covered
    return 2*p*r/(p+r)

def _tok(s): return re.findall(r"\w+", (s or '').lower())
def corpus_bleu(hyps, refs):
    pn=[0]*4; pd=[0]*4; hl=rl=0
    for h,r in zip(hyps,refs):
        ht,rt=_tok(h),_tok(r); hl+=len(ht); rl+=len(rt)
        for n in range(1,5):
            hg=Counter(tuple(ht[i:i+n]) for i in range(len(ht)-n+1))
            rg=Counter(tuple(rt[i:i+n]) for i in range(len(rt)-n+1))
            pn[n-1]+=sum((hg&rg).values()); pd[n-1]+=max(len(ht)-n+1,0)
    ps=[(pn[i]+(0 if pn[i] else .5))/(pd[i] or 1) for i in range(4)]
    s=math.exp(sum(.25*math.log(p) for p in ps if p>0))
    bp=1 if hl>rl else math.exp(1-rl/max(hl,1))
    return bp*s*100
def corpus_chrf(hyps, refs, n=6, beta=2):
    tp=fp=fn=0
    for h,r in zip(hyps,refs):
        hc=(h or '').replace(' ',''); rc=(r or '').replace(' ','')
        for k in range(1,n+1):
            hg=Counter(hc[i:i+k] for i in range(len(hc)-k+1))
            rg=Counter(rc[i:i+k] for i in range(len(rc)-k+1))
            ov=sum((hg&rg).values()); tp+=ov; fp+=sum(hg.values())-ov; fn+=sum(rg.values())-ov
    p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0; b2=beta*beta
    return 0 if p+r==0 else (1+b2)*p*r/(b2*p+r)*100

def score(name, pairs):
    """pairs: list of (gold, output). Returns dict of metrics."""
    pairs=[(g,o) for g,o in pairs if g]    # skip rows with empty gold
    f1=st.mean([token_f1(g,o) for g,o in pairs])
    g=[x[0] for x in pairs]; o=[x[1] for x in pairs]
    return {"system":name,"faithfulness_F1":round(f1,3),
            "BLEU":round(corpus_bleu(o,g),1),"chrF":round(corpus_chrf(o,g),1),"n":len(pairs)}

# =================================================================== LOADERS
def load_direct():
    """gold + the 3 direct-translation model outputs from the analysis xlsx."""
    wb=load_workbook(DIRECT_XLSX, data_only=True); ws=wb['Analysis']
    gold={}; sysout={'Llama (direct)':{}, 'Mistral (direct)':{}, 'Gemma (direct)':{}}
    for r in list(ws.iter_rows(values_only=True))[1:]:
        sid,hi,g,lla,lf,li,mis,mf,mi,gem,gf=r[:11]
        if not sid: continue
        gold[sid]=g; sysout['Llama (direct)'][sid]=lla
        sysout['Mistral (direct)'][sid]=mis; sysout['Gemma (direct)'][sid]=gem
    return gold,sysout

def load_csv(path,col):
    return {row['sent_id'].strip():row.get(col,'') for row in csv.DictReader(open(path,encoding='utf-8-sig'))}

def load_hybrid():
    wb=load_workbook(HYBRID_XLSX, data_only=True); ws=wb['comparison']
    rows=[r for r in list(ws.iter_rows(values_only=True))[1:] if r[0] and r[3]]
    gold={r[0]:r[3] for r in rows}
    return gold, {'Llama (hybrid)':{r[0]:r[4] for r in rows},
                  'Mistral (hybrid)':{r[0]:r[6] for r in rows},
                  'Gemma (hybrid)':{r[0]:r[8] for r in rows}}

# =================================================================== MAIN
def main():
    results=[]
    gold,direct=load_direct()
    sids=list(gold)
    for name,out in direct.items():
        results.append(score(name,[(gold[s],out.get(s,'')) for s in sids]))
    # baselines (scored against the SAME direct gold)
    if os.path.exists(GOOGLE_CSV):
        g=load_csv(GOOGLE_CSV,'google_english')
        results.append(score('Google Translate',[(gold[s],g.get(s,'')) for s in sids]))
    if os.path.exists(INDIC_CSV):
        ind=load_csv(INDIC_CSV,'indictrans2_english')
        results.append(score('IndicTrans2',[(gold[s],ind.get(s,'')) for s in sids]))
    # hybrid (scored against the hybrid gold)
    if os.path.exists(HYBRID_XLSX):
        hg,hyb=load_hybrid()
        hs=list(hg)
        for name,out in hyb.items():
            results.append(score(name,[(hg[s],out.get(s,'')) for s in hs]))

    cols=["system","faithfulness_F1","BLEU","chrF","n"]
    print("\n{:18} {:>16} {:>6} {:>6} {:>5}".format(*cols))
    for r in results:
        print("{system:18} {faithfulness_F1:>16} {BLEU:>6} {chrF:>6} {n:>5}".format(**r))
    with open("faithfulness_scores.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
        for r in results: w.writerow(r)
    print("\nSaved faithfulness_scores.csv")

if __name__=="__main__":
    main()
