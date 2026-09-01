#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usr_with_guidelines.py — RAW USR -> English with (a) a tag reference from USR
Guideline v4.2.1 AND (b) an explicit explanation that concept roots are WX
romanized Hindi that must be decoded to Hindi and then translated to English.
A few worked WX->English examples are included. Output is cleaned so no
"Step 1 / reasoning" text leaks into the CSV.

Models: Llama 4 Scout (Groq), Mistral Small (Mistral), Gemma 3 (local Ollama).
Hindi '#' line is stripped, so the model works from the USR alone.

    pip install openai
    python3 usr_with_guidelines.py gen_input.txt
Output: usr_guidelines_results.csv
"""
import os, sys, re, csv, time
from openai import OpenAI

KEYS = {
    "groq":    "PASTE_GROQ_KEY",
    "mistral": "PASTE_MISTRAL_KEY",
    "ollama":  "ollama",
}
PROVIDERS = {
    "groq":    ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1",      "MISTRAL_API_KEY"),
    "ollama":  ("http://localhost:11434/v1",      "OLLAMA_KEY"),
}
MODELS = [
    ("groq",    "meta-llama/llama-4-scout-17b-16e-instruct"),
    ("mistral", "mistral-small-latest"),
    ("ollama",  "gemma3:4b"),
]
RATE = {"groq": 2.0, "mistral": 1.2, "ollama": 0.0}
_last = {}; MAX_RETRIES = 5

SPEC = """You convert a Universal Semantic Representation (USR) into ONE English sentence.

STEP A — DECODE THE WORDS. Every concept root in the USR is a HINDI word written
in WX romanization (a transliteration scheme), NOT English. You must first read
each root as its Hindi word, then translate that Hindi word into English.
Examples of WX root -> Hindi -> English:
  laina -> लाइन -> line        reKA -> रेखा -> line/line
  steSana -> स्टेशन -> station   nadI -> नदी -> river
  meM -> में -> in              se -> से -> from        waka -> तक -> up to / to
  pavixra -> पवित्र -> holy/sacred   SaRa -> शहर -> city/town
  hE -> है -> is                 jAwI -> जाती -> goes
Proper nouns (place/person names) stay as names; just keep their spelling and capitalize.
Do NOT guess an unrelated English word; if a root is a common Hindi word, translate it.

STEP B — USE THE TAG REFERENCE (USR Guideline v4.2.1). A USR is line-based; each
row is "concept index [features] X:rel", linking it to row X by relation rel:
  k1=agent/subject, k2=object, k3=instrument, k4=recipient, k5=source/"from",
  k7=about/regarding, k7t=time, k7p=location, r6=possessive ("X of Y"),
  mod=modifier, quant/card=number, 0:main=root predicate (the verb).
SPEAKER'S VIEW: deixis proximal "yaha"=this/here vs distal "vaha/vahAM"=that/there;
def=definite ("the"); 2nd-person Apa(respect)/wU(informal)="you"; honorific="-ji/honorable";
particles hI="only", BI="also/too". ADDRESSEE = the unstated subject of a command.
TAM/MOOD: a token like "hE-pres" gives tense; %affirmative=statement; %interrogative=question("?").

STEP C — WRITE. Reorder into natural English (subject-verb-…; put "from" before "to").
Add only the articles/prepositions English grammar needs. Add no facts; drop nothing."""

TASK = """Decode and translate the USR below into ONE faithful English sentence.
Output ONLY the final sentence — no analysis, no steps, no notes, no "Step 1",
no JSON, no brackets, no explanation.

USR:
{usr}

Final sentence:"""

# few-shot: full pipeline (USR -> faithful English), teaches WX decoding by example
FEWSHOT = [
("""ek 1 - - 4:card
reKA 2 - - 4:k1
ceMgalapata_steSana 3 - - 4:k5
arakonama 4 - - 0:main
jAwI_hE 4 - - 0:main
%affirmative""",
"A line goes from Chengalpattu Station to Arakonam."),
("""xvArakA 1 - - 4:k1
cAra 2 - - 3:quant
XAma 3 - - 4:k2
hE 4 - - 0:main
%affirmative""",
"Dwarka is one of the four dhamas."),
("""gaMgA 1 - - 3:r6
pavixra 2 - - 3:mod
naxI 3 - - 0:main
hE 3 - - 0:main
%affirmative""",
"The Ganga is a holy river."),
]

def build(usr):
    msgs=[{"role":"system","content":SPEC}]
    for u,a in FEWSHOT:
        msgs.append({"role":"user","content":"USR:\n"+u+"\n\nFinal sentence:"})
        msgs.append({"role":"assistant","content":a})
    msgs.append({"role":"user","content":TASK.format(usr=usr)})
    return msgs

def clean(text):
    """Remove leaked reasoning / headers and keep ONE sentence."""
    t=(text or "").strip()
    # drop markdown headers / step lines
    t=re.sub(r'(?is)^\s*#+.*?(?=\n|$)', '', t)
    t=re.sub(r'(?is)\bstep\s*\d+\s*:.*?(?=\n|$)', '', t)
    # if model wrote "Final sentence:" take what's after the last one
    if 'final sentence' in t.lower():
        t=re.split(r'(?i)final sentence\s*:?', t)[-1]
    t=t.replace("\n"," ").strip().strip('"').strip()
    t=re.sub(r'^(english|sentence|answer)\s*:\s*','',t,flags=re.I)
    # keep first sentence ending in . ? !
    m=re.search(r'.*?[.?!]', t)
    result=(m.group(0) if m else t).strip()
    if not result:   # model emitted only reasoning -> take last non-empty line
        lines=[ln.strip(' #*->').strip() for ln in (text or "").splitlines() if ln.strip()]
        result=lines[-1] if lines else "ERROR: empty"
    return result

def throttle(p):
    gap=RATE.get(p,2.0); w=gap-(time.time()-_last.get(p,0))
    if w>0: time.sleep(w)
    _last[p]=time.time()

def client_for(p):
    base,env=PROVIDERS[p]; key=(KEYS.get(p) or "").strip()
    if key.startswith("PASTE_") or key=="": key=os.environ.get(env)
    if p=="ollama": key=key or "ollama"
    return OpenAI(base_url=base,api_key=key) if key else None

def strip_hindi(block):
    kept,sent=[],""
    for ln in block.split("\n"):
        s=ln.strip()
        if s.startswith("#"):
            if not sent: sent=s.lstrip("#").strip()
            continue
        if s.startswith("<sent_id") or s.startswith("</sent_id"): continue
        kept.append(ln)
    return "\n".join(kept).strip(), sent

def split_usrs(text):
    out=[]
    for b in re.findall(r"<sent_id=.*?</sent_id>",text,re.S):
        m=re.search(r"<sent_id=([^>\n]+)>",b)
        sid=(m.group(1) if m else "unknown").strip()
        clean_usr,sent=strip_hindi(b)
        out.append((sid,clean_usr,sent))
    return out

def call(p,c,model,usr):
    for a in range(MAX_RETRIES):
        throttle(p)
        try:
            r=c.chat.completions.create(model=model,messages=build(usr),
                                        temperature=0.1,max_tokens=200)
            return clean(r.choices[0].message.content)
        except Exception as e:
            msg=str(e).lower()
            if any(k in msg for k in("429","rate","quota","exhaust","overload")):
                time.sleep(RATE.get(p,2)*(2**a)); continue
            return f"ERROR: {str(e)[:150]}"
    return "ERROR: retries"

def main():
    if len(sys.argv)<2: print("usage: python3 usr_with_guidelines.py gen_input.txt"); return
    usrs=split_usrs(open(sys.argv[1],encoding="utf-8").read())
    print(f"{len(usrs)} USRs (guideline + WX decoding; Hindi stripped).")
    active=[(p,m,client_for(p)) for p,m in MODELS]
    active=[(p,m,c) for p,m,c in active if c]
    if not active: print("No keys/clients ready."); return
    with open("usr_guidelines_results.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["sent_id","provider","model","generated_sentence","original_sentence"])
        for i,(sid,usr,sent) in enumerate(usrs,1):
            for p,m,c in active:
                out=call(p,c,m,usr)
                w.writerow([sid,p,m,out,sent]); f.flush()
                print(f"[{i}/{len(usrs)}] {sid:14} {p:8} -> {out[:55]}")
    print("\nDone -> usr_guidelines_results.csv")

if __name__=="__main__": main()
