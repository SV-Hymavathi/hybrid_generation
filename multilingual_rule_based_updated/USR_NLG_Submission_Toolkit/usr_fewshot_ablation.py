#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usr_fewshot_ablation.py — RAW USR -> English, but now WITH few-shot examples.

This is the ablation a reviewer will ask for: does giving the model a few worked
USR->sentence examples (and a short chain-of-thought nudge) fix the raw-USR
failure?  Run it, score it the same way, and compare to the zero-shot raw-USR
numbers (Llama 0.191 / Mistral 0.174 / Gemma 0.075).

Models see ONLY the USR graph (Hindi '#' line is stripped), exactly like before.

    pip install openai
    # cloud models:
    python3 usr_fewshot_ablation.py gen_input.txt
    # (Gemma runs locally via Ollama automatically if its key slot is left blank)

Output: usr_fewshot_results.csv  (sent_id, provider, model, generated_sentence, original_sentence)
"""
import os, sys, re, csv, time
from openai import OpenAI

# ── KEYS (regenerate the ones you exposed earlier!) ──────────────────────────
KEYS = {
    "groq":    "PASTE_GROQ_KEY",
    "gemini":  "PASTE_GEMINI_KEY",
    "mistral": "PASTE_MISTRAL_KEY",
    "ollama":  "ollama",            # local Gemma, no real key
}
PROVIDERS = {
    "groq":    ("https://api.groq.com/openai/v1",                           "GROQ_API_KEY"),
    "gemini":  ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1",                                "MISTRAL_API_KEY"),
    "ollama":  ("http://localhost:11434/v1",                               "OLLAMA_KEY"),
}
MODELS = [
    ("gemini",  "gemini-flash-latest"),
    ("groq",    "meta-llama/llama-4-scout-17b-16e-instruct"),
    ("mistral", "mistral-small-latest"),
    ("ollama",  "gemma3:4b"),
]
RATE = {"gemini":6.0,"groq":2.0,"mistral":1.2,"ollama":0.0}
_last={}; MAX_RETRIES=5

SYSTEM = """You convert a Universal Semantic Representation (USR) into ONE English sentence.
A USR is a line-based graph: each row is "concept id - - dep" where dep like "4:k1" or
"0:main" links it to another row. Relations: k1=subject/agent, k2=object, k4=recipient,
k5=source/from, k7=location, k7t=time, r6=possessive, mod=modifier, quant/card=number,
main=root predicate. Tokens like "hE_1-pres" carry tense; %affirmative = affirmative mood.
Concept roots are romanized Hindi (WX). Proper nouns stay spelled as given.
Read the graph, then output ONLY the single most natural English sentence it encodes.
No explanation, no notes."""

# 3 worked examples (chain-of-thought kept in the assistant turn, final line is the answer)
FEWSHOT = [
("""ek 1 - - 4:card - - - -
reKā 2 - - 4:k1 - - - -
ceṃgalapaṭa 3 - - 4:k5 - - - -
arakonama 4 - - 0:main - - - -
veVlYlYu 4 - - 0:main - - - -
%affirmative""",
"A line goes from Chengalpattu to Arakonam."),
("""dvArakA 1 male - - 4:k1 - - -
cAra 2 - - 3:quant - - - -
XAma 3 - - 4:k2 - - - -
hE 4 - - 0:main - - - -
%affirmative""",
"Dwaraka is one of the four dhamas."),
("""vESAlI 1 female - - 4:k1 - - -
aba 2 - - 4:k7t - - - -
bihAra 3 male - - 7:r6 - - -
eka 5 - - 7:quant - - - -
CotA 6 - - 7:mod - - - -
Sahara 7 - - 4:k1s - - - -
hE-pres 4 - - 0:main - - - -
%affirmative""",
"Vaishali is now a small town in Bihar."),
]

def build(usr):
    msgs=[{"role":"system","content":SYSTEM}]
    for u,a in FEWSHOT:
        msgs.append({"role":"user","content":"USR:\n"+u})
        msgs.append({"role":"assistant","content":a})
    msgs.append({"role":"user","content":"USR:\n"+usr})
    return msgs

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
        clean,sent=strip_hindi(b)
        out.append((sid,clean,sent))
    return out

def call(p,c,model,usr):
    for a in range(MAX_RETRIES):
        throttle(p)
        try:
            r=c.chat.completions.create(model=model,messages=build(usr),temperature=0.1,max_tokens=120)
            return r.choices[0].message.content.strip().replace("\n"," ")
        except Exception as e:
            msg=str(e).lower()
            if any(k in msg for k in("429","rate","quota","exhaust","overload")):
                time.sleep(RATE.get(p,2)* (2**a)); continue
            return f"ERROR: {str(e)[:150]}"
    return "ERROR: retries"

def main():
    if len(sys.argv)<2: print("usage: python3 usr_fewshot_ablation.py gen_input.txt"); return
    usrs=split_usrs(open(sys.argv[1],encoding="utf-8").read())
    print(f"{len(usrs)} USRs (few-shot, Hindi stripped).")
    active=[(p,m,client_for(p)) for p,m in MODELS if client_for(p)]
    active=[(p,m,c) for p,m,c in active if c]
    if not active: print("No keys/clients."); return
    with open("usr_fewshot_results.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["sent_id","provider","model","generated_sentence","original_sentence"])
        for i,(sid,usr,sent) in enumerate(usrs,1):
            for p,m,c in active:
                out=call(p,c,m,usr)
                w.writerow([sid,p,m,out,sent]); f.flush()
                print(f"[{i}/{len(usrs)}] {sid:14} {p:8} -> {out[:55]}")
    print("\nDone -> usr_fewshot_results.csv")

if __name__=="__main__": main()
