# USR→Language tool — changes made and rules still missing

This document records (1) what was changed in this pass, (2) how it was verified,
(3) the rules/behaviours still not handled, and (4) the honest status of
"multilingual" generation. It is intentionally specific so the next person can
continue without re-deriving the analysis.

## 1. Environment / dependencies (was undocumented)

The tool does NOT run on a bare Python install. It needs:

- Python packages: `wxconv`, `indic_transliteration`, `pandas`, `requests`
  (and optionally `groq`).
- The **Apertium** command-line toolchain on PATH:
  `lt-proc`, `apertium-destxt`, `apertium-retxt`
  (install: `apt-get install apertium lttoolbox`).
- The English morphology binaries shipped in `apertium_eng/`
  (`eng.autogen.bin`, `eng.automorf.bin`) and the Hindi ones in `repository/`.

If Apertium is missing, English surface forms are never generated and every
sentence silently degrades. This was the main reason the tool appeared "broken".

## 2. Bugs fixed in this pass (verified)

1. **Crash: `KeyError: 'cat'`** in `repository/identify_cat.py`
   (`check_nominal_verb`) and `repository/process_cat.py` (`process_adjectives`).
   Both did `tag['cat']` on dictionary tags that don't always carry a `cat` key.
   Changed to `tag.get('cat')`.
   *Effect:* the full 252-sentence set now runs with **0 crashes** (previously
   many sentences returned `ERROR: 'cat'`).

2. **Untransliterated WX tokens leaking into output**
   (`hindi_gen.py`, final WX→Roman loop). Tokens that were neither `#`-marked
   nor recognised named entities fell through unconverted
   (e.g. `SivaballaBapura`, `awiSayakRewra`). Added a fallback: a token with an
   **internal** uppercase letter is a true WX root and is transliterated via
   `wx_to_english`. The "internal" test is deliberate so legitimately
   capitalised English/proper words (`Hindus`) are left alone.
   *Effect:* WX-leak tokens across the 85 documented sentences dropped to 3,
   all of which are source-data artefacts (`phauYla`, the `ke.ke` abbreviation).

3. **Plural feature silently lost** for nouns absent from Apertium's English
   dictionary (`repository/morph_gen.py`, `en_generate_morph`). Apertium returns
   `#lemma` for unknown lemmas, so `<num:pl>` was dropped and the noun came out
   singular (`Hindu` instead of `Hindus`). Added a regular English-plural
   fallback (handles `-s/-es/-ies/-ves` and common irregulars) applied only when
   Apertium failed on a `<n><pl>` request.
   *Effect:* `Hindus`, etc. now pluralise correctly.

4. **Security / portability:** removed a hardcoded Groq API key from
   `repository/common_v4.py` and `repository/backup filecommon_v4.py`
   (now `os.getenv("GROQ_API_KEY")` only). Made the top-level `groq` import in
   `hindi_gen.py` optional so the tool runs without the package.
   **ACTION REQUIRED:** the leaked key must be rotated/revoked — it was committed
   in plaintext and shared.

## 3. Important finding about the error sheet

The `hindi_usrs_error_analysis.xlsx` notes are **stale relative to the code that
was shipped**. The single largest documented class — "duplicate token"
(31 cases, e.g. "muktesvara muktesvara", "lake lake") — is already fixed in this
code version: across the 85 documented sentences only **3** show a repeated
content word, and 2 of those are genuine open relation/grouping questions
(Tourism_082/085 "temple temple"), 1 is a conjunction "and". So most of the
sheet's errors no longer reproduce.

## 4. Rules still NOT handled (the real remaining work)

These are ordered by how often they appear in the gold comparison.

1. **Chunk word-order / reordering** (largest remaining gap). The gold reorders:
   - adverbs: `go continuously` (tool: `continuously go`), `in hastināpura only`
     (tool: `only in hastināpura`), `from only afar` (tool: `only from afar`).
   - imperative verb-first: gold `[go]_IMPERATIVE [to …]`; tool keeps the verb
     last for some imperatives.
   - measurement: gold `about 105 kilometres`; tool `105 kilometre`.
   The reorder logic lives in `add_chinking` (`repository/common_v4.py`,
   ~line 1530+) and `repository/reorder.py`. There is no general
   adverb/PP-placement model yet.

2. **NE / Noun-Compound splitting into components.** When the source concept is a
   single joined token (`SivaballaBapura`, `awiSayakRewra`), the gold splits it
   into IAST words (`śiva ballabhapura`, `atiśaya area`). The construction row is
   not consulted to split joined NE/NC tokens; only transliteration happens.

3. **Measurement / span / calendar constructions.** Number not pluralised
   (`kilometre`→`kilometres`), no approximation word (`about`), span/rate split
   into multiple chunks instead of one (sheet rows 18, 60, 62). The
   `[x_meas]`, `[span]`, `[calendar]`, `[rate]` schemas from the guideline
   (Construction section) are only partially realised in `construction.py`.

4. **Reduplication (xviwva).** `ghara-ghara`, repeated-action aspect is dropped
   (sheet rows 20, 42, 47, 70). The morpho-semantic `xviwva` tag is not rendered.

5. **Number-word → word/digit mapping** for words not in the concept dictionary
   (`cAra`→`four`). Pure dictionary gap; add to `concept-to-mrs-rels.dat` or a
   numeral table.

6. **`eka_2` → "one" vs "a".** Gold uses "one line" (counting) where the tool
   emits "a line". Needs the quant-vs-article distinction from speaker's view.

7. **Passive detection.** Gold marks `_PASSIVE` for forms like
   "can been reached easily" (sheet rows 12, 53) that the tool tags `_ACTIVE`.
   Passive TAM detection in `identify_verb_tag` is incomplete.

8. **Specific dependency relations** raised as open questions in the sheet:
   `rpk` (row 61), `rbks` producing stray "after" (row 52), `rn` over-application
   (row 68). These need rule decisions, not just code.

9. **Abbreviations / `@` tokens and `ke.ke`** (row 62) are mis-joined.

10. **Honorific rendering.** NOTE: the gold *keeps* the literal `_(respect)`
    marker (Tourism_009/011), so the current behaviour is actually correct for
    this dataset — do not "fix" it by stripping the marker.

## 5. Honest status of "multilingual"

The repository generates **English only**. `--lang hi` runs without error but
returns empty strings, because the concept-mapping pipeline
(`is_cp`/`is_nc`/`is_ne`/`process_input` in `hindi_gen.py`’s `__main__`) is
gated behind `if lang == 'en'`. There is Hindi morphology scaffolding
(`hi_generate_morph`, `repository/hi.gen_LC.bin`) but it is not wired end-to-end.

To add a genuine target language X you need ALL of:
- a bilingual **concept→X dictionary** (analogue of `concept-to-mrs-rels.dat`),
- an **X morphological generator** (Apertium `.bin` or equivalent) plus
  `language_rules/X.py` with `AUX_MAP_FILE` and TAM mappings,
- **X word-order / agreement rules** inside the chunking/reorder stage,
- to remove the `lang == 'en'` gate and route X through `process_input`.

This is per-language work; it cannot be produced by editing the existing English
rules. Claiming the tool is "100% correct for every language" would be false.

## 6. How to reproduce the measurements

```
apt-get install apertium lttoolbox
pip install wxconv indic_transliteration pandas requests
# put the USRs to generate, separated by blank lines, in gen_input.txt
python3 hindi_gen.py --lang en
# final output is the dict on the log line "hindi_generation output : {...}"
```
