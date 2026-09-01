# Quick start

## Generate English from USRs

1. Put your USRs in `gen_input.txt` (one or more `<sent_id=...> ... </sent_id>` blocks).
2. Run:

```
python3 hindi_gen.py --lang en
```

The screen now shows **only the output**, one clean line per sentence:

```
Sent_1: [mokṣa]_SUBJ [with visit of the saptapuri] [gets]_ACTIVE
```

### Where did all the debug text go?
Everything the engine prints (category identification, morphology, chunking,
etc.) is written, in order, to **`debug_hi_en.txt`** with step banners
(STEP 1 read USR ... STEP 5 grammar post-processing ... STEP FINAL). Open that
file whenever you want to see how a sentence was built; otherwise ignore it.

### Sentences with a bad TAM
If a sentence's main-verb TAM (tense/aspect/mood) cannot be resolved, the engine
no longer prints a garbled result. It generates every other sentence normally and
for the broken one prints:

```
Bad_1: since TAM is incorrect the system unable to process the output
```

So one faulty verb never blocks the rest of the file.

## USR corrector (offline, guideline v4.2.1)

`usr_corrector.py` repairs a USR file before generation. Unlike a blind default,
it decides each kaaraka relation from the **vibhakti (post-position)** that
follows the token in the Hindi `#` sentence (the guideline's kaaraka table):

  ne -> k1   ko -> k2/k4/k4a   se -> k5/k3/k5prk   meM,para -> k7p
  ke lie -> rt   ke kAraNa -> rh   kA/kI/ke -> r6   ke anusAra -> k7a
  ke pAsa -> rsm   kI ora/taraPa -> rd   ke bAxa -> rkrl   se pahale -> rkl
  dwArA -> k3 (agent)

It transliterates the Devanagari sentence to WX, aligns each token, and reads the
post-position. When no post-position governs a token, structure decides
(copula complement -> k1s; nominal modifier -> mod) and the choice is FLAGGED in
the log for review. It also does the structural repairs (duplicate 0:main,
malformed `-_1` verbalizer, broken head refs, column padding, genitive
clause-subject -> k1) and validates every construction
([ne_/nc_/cp_/conj_/disjunct_/span_/spatial_/temporal_/calendar_/meas_]) for its
required component roles.

```
python3 usr_corrector.py my_usrs.txt                 # writes my_usrs.corrected.txt + change log
python3 usr_corrector.py my_usrs.txt -o fixed.txt
python3 usr_corrector.py my_usrs.txt --generate      # correct, then print English chunks
python3 usr_corrector.py my_usrs.txt --quiet
```

Honest scope: post-position -> kaaraka resolves the large majority correctly.
A few are genuinely ambiguous from the post-position alone (se: k3 vs k5;
ko: k2 vs k4 vs k4a) — the corrector uses verb context where it can and flags the
rest. It does not invent constructions that are absent (that is the chunker's job).
