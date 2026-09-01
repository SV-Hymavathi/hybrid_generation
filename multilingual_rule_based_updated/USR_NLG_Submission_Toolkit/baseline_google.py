#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
baseline_google.py — External baseline: Google Translate (Hindi->English) on the 250.

Easiest baseline. No API key. Uses the free 'deep-translator' wrapper.

    pip install deep-translator openpyxl
    python3 baseline_google.py gen_input.txt

Output: baseline_google_translations.csv  (sent_id, hindi, google_english)
Reads the '#...' Hindi line from each <sent_id> block (same as your other scripts).
"""
import sys, re, csv, time
from deep_translator import GoogleTranslator

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
        print("usage: python3 baseline_google.py gen_input.txt"); return
    pairs=extract_hindi(open(sys.argv[1],encoding="utf-8").read())
    print(f"{len(pairs)} Hindi sentences found.")
    tr=GoogleTranslator(source='hi', target='en')
    with open("baseline_google_translations.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["sent_id","hindi","google_english"])
        for i,(sid,hi) in enumerate(pairs,1):
            try:
                en=tr.translate(hi)
            except Exception as e:
                en=f"ERROR: {str(e)[:120]}"
            w.writerow([sid,hi,en]); f.flush()
            print(f"[{i}/{len(pairs)}] {sid:16} -> {en[:60]}")
            time.sleep(0.5)   # be gentle; raise to 1-2 if you get rate-limited
    print("\nDone. Saved baseline_google_translations.csv")

if __name__=="__main__":
    main()
