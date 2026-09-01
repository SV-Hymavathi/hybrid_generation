#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
baseline_indictrans2_noTK.py — IndicTrans2 (AI4Bharat) Hindi->English baseline,
WITHOUT the IndicTransToolkit dependency (which breaks on newer transformers).

Only needs:  pip install torch transformers sentencepiece openpyxl

    python3 baseline_indictrans2_noTK.py gen_input.txt

Output: baseline_indictrans2_translations.csv  (sent_id, hindi, indictrans2_english)

Notes:
- Uses the distilled 200M model by default (much faster on CPU). To use the
  full 1B model instead, change MODEL below.
- The model's tokenizer (trust_remote_code) handles IndicTrans2's script
  processing internally, so the external toolkit is not required. We prepend the
  language tags the model expects.
"""
import sys, re, csv
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MODEL = "prajdabre/rotary-indictrans2-indic-en-dist-200M"   # fast. Or "...-indic-en-1B"
SRC_TAG, TGT_TAG = "hin_Deva", "eng_Latn"

def extract_hindi(text):
    out=[]
    for b in re.findall(r"<sent_id=.*?</sent_id>", text, re.S):
        m=re.search(r"<sent_id=([^>\n]+)>", b)
        sid=(m.group(1) if m else "unknown").strip()
        hi=""
        for ln in b.split("\n"):
            s=ln.strip()
            if s.startswith("#"): hi=s.lstrip("#").strip(); break
        if hi: out.append((sid,hi))
    return out

def main():
    if len(sys.argv)<2:
        print("usage: python3 baseline_indictrans2_noTK.py gen_input.txt"); return
    pairs=extract_hindi(open(sys.argv[1],encoding="utf-8").read())
    print(f"{len(pairs)} Hindi sentences found. Loading {MODEL} (first run downloads the model)...")
    tok=AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    model=AutoModelForSeq2SeqLM.from_pretrained(MODEL, trust_remote_code=True)
    model.eval()

    # IndicTrans2 expects each source line prefixed with: "<src_tag> <tgt_tag> sentence"
    def tag(s): return f"{SRC_TAG} {TGT_TAG} {s}"

    B=4
    with open("baseline_indictrans2_translations.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["sent_id","hindi","indictrans2_english"])
        for start in range(0,len(pairs),B):
            chunk=pairs[start:start+B]
            src=[tag(hi) for _,hi in chunk]
            enc=tok(src, padding=True, truncation=True, max_length=256, return_tensors="pt")
            with torch.no_grad():
                out=model.generate(**enc, max_length=256, num_beams=5)
            dec=tok.batch_decode(out, skip_special_tokens=True)
            for (sid,hi),en in zip(chunk,dec):
                en=en.strip()
                w.writerow([sid,hi,en]); f.flush()
                print(f"[{start+1}-{start+len(chunk)}/{len(pairs)}] {sid:16} -> {en[:55]}")
    print("\nDone. Saved baseline_indictrans2_translations.csv")

if __name__=="__main__":
    main()
