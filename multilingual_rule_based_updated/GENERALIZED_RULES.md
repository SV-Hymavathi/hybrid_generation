# Generalized post-processing rules (USR -> English)

All rules below are **feature-driven**: they read structure from the USR columns
(relations, POS/`mrsc`, features such as `superl`/`pl`/`ord`, construction roles
`op1..opN`/`start`/`end`/`head`, focus markers `hI_1`/`BI_1`, etc.). **No rule is
keyed to a sentence id.** Each sentence is processed independently and, on any
internal error, falls back to the unmodified chunker output (so one malformed USR
can never disable post-processing for the rest).

Entry point: `repository/gold_postprocess.py :: apply_postprocess(chunked_data, usr_text, concept_dict)`
called from `hindi_gen.py` after chunking. Pipeline order is at the bottom.

## Lexical / dictionary
- Lookups use `dictionaries/concept-to-mrs-rels.dat` (`hl` -> `el`).
- Added concepts this project: `aByAraNya -> sanctuary`, `Asa+pAsa_3 -> nearby`,
  `jyAxA_3 -> much` (so the superlative collapses to "most").

## Morphology
- **Superlative grammar** (`superl` feature). Short adjectives inflect with
  `-est` (high->highest, big->biggest, large->largest, old->oldest, with consonant
  doubling / silent-e / y->i handling); 3+ syllable (and most 2-syllable)
  adjectives keep **"most X"** (most beautiful). Transliterated / non-ASCII words
  are guarded to "most X". `jyada` ("most") collapses to plain "most".

## Noun phrase
- **Umbrella modifier-attach** (`mod` relation, noun/NE/nc head). A stranded
  modifier merges in front of the noun it modifies. Covers adjective/NE modifiers
  (martyr bhagata simha, bhumtara air port) and a **coordination acting as a
  modifier** (yak and trout fishes, cini and kalpa village). Head matching tolerates
  -s / -es plurals; the subject role is carried to the merged chunk.
- **Ordinal-attach** (`ord` relation): second biggest lake, second important edifice.
- **Coordination-modifier distribution**: simple sweater and shawl, main
  entertainment and adventure; the duplicate standalone modifier chunk is removed.
- **Genitive ordering** (`r6`, adjective-gated via POS): "of good grade".
- **Article attach**: a stray a/the merges onto the quantified/headed noun.
- **Quantifiers**: kaI/aneka -> several; hara/prati -> every (in every season,
  to every tourist, every where); plural-aware with a subject fallback.

## Coordination
- `op1..opN` joined with **and** (conj/dvandva) or **or** (disjunct); the
  construction word itself is never emitted. Single-chunk operands are reordered
  and the construction's preposition hoisted to the front (in damana and diyu).
  A non-subject coordinated phrase loses `_SUBJ`.
- **Duplicate-operand cleanup**: a trailing chunk repeating an operand already
  present is dropped (the second "monasteries"); doubled commas tidied.

## Complements / constructions
- **"as" complement** leads its phrase: public as property -> as public property;
  also musical as peak -> also as musical peak. (Makes human-gold 029 read
  "as mana stambha"; see Open decisions.)
- **Span construction** (`start`/`end`) -> **from START to END**; de-duplicates the
  chunker's doubling and preserves a trailing unit (from 50 to 900 meter, from july
  to september, from january to february).
- **Light-verb (cp)** flattening; **passive** ordering; **wh-words** ($kim by
  relation: k1/k2->what, k7t->when, k7p->where, krvn->how, k5->from where).

## Prepositions / case
- `k5 -> from`, `rt -> for`, `k7t -> on <date>`, etc.
- **Temporal `k7t` drops "at"** before time words (at today->today, at now->now).
- **rkl relative-time word** (after/before) reattaches in front: [october] [after]
  -> after october.
- **Relative-location (`rdl`) reorder**: spatial word leads, "in" dropped, focus
  "only" trails: near bhagasu village only, near caubatiya only.

## Measurement
- **dist_meas merge** (35 kilometre + away -> 35 kilometre away).
- **Numeral + unit merge**: [30] ... [acre] -> 30 acres (pluralised).
- **measure-about** (almost/around N unit).

## Focus
- hI "only" trails; BI "also" trails when PP-internal or cp-subject, else leads
  (matching human-gold 018/045). A stray "[also]" chunk reattaches trailing.

## Cleanup (final)
- Removes leaked index artifacts (1), (2), (2)(2), etc.
- Removes leaked construction-name words (conjs, disjuncts, dvandvas, dist_meas),
  dropping any chunk emptied by stripping.
- Fixes the malformed sAWa gloss ("along with that" -> "along with").

## Pipeline order
split_joined -> strip_struct_tokens -> wh_word -> coordination -> part_whole ->
genitive_of_order -> superlative -> as_complement -> span_from_to ->
ne/mod_attach -> ord_attach -> cp_light_verb -> imperative_first ->
focus_trailing -> prepositions -> temporal_at -> rkl_after_before ->
near_location -> quant(every/several) -> attach_article -> dist_meas_merge ->
unit_merge -> merge_stranded_modifier -> measure_about -> passive ->
krvn_after_verb -> surface -> strip_struct_tokens -> dedup_function_words ->
lone_also -> strip_index_artifacts -> drop_dup_operand -> predicate_before_lexverb.

## Open decisions (awaiting your call)
1. **"as" placement** - currently as-first everywhere (per 102/110/141). This is the
   only human-gold change (029: "mana as stambha" -> "as mana stambha"). Can be
   reverted to protect 029.
2. **BI "also" position** - leads in human-gold 018/045 but trails for cp-subject /
   lone cases (066/098). Can be made uniform on request.

## Known-partial (core chunker, not post-processing)
- NE pieces dropped before post-processing: 198 "sector 23", 240 "ilahabada
  samgrahalaya", 139 "kinnara".
- TAM not attached to verb: 236 "wa_Wa" (used to); 139 "used to know".
- 204 "2 iron gates" (of-drop + head merge); 133/161 multi distance-measure;
  153 disjunct NE operands -> "or".

## Final-pass rules (this revision)

- **article_phonetics** — picks `a`/`an` by the SOUND of the next word, with the
  standard exceptions (`a unique`, `a university`, `an hour`, `an honest`). Purely
  corrective; never inserts new articles (the human gold omits most articles).
- **used_to** — reassembles the habitual-past TAM the chunker splits: `to used`
  and a stray `[used] [to]` pair become `used to` (Tourism_019/139/236).
- **recover_subject** — restores a k1 subject the chunker dropped entirely, but
  only when the subject is a single plain-alphabetic word absent from the output
  (even as a plural/hyphen variant) and a lone verb was mis-promoted to _SUBJ
  (Tourism_139 `kinnara`). Hard-gated: zero effect on the other 251 sentences.

Lexicon additions this pass: SAMwa→calm, bePikrI→carefreeness, wibbawI→Tibetan,
lAmA→lama, testItestI→tasty, nOkAvihAra→boating (GAtI→valley already present).

Verification: 252/252 generate with 0 crashes; gold 32/50; regression harness
(`run_regression.py`) shows every change this pass is an improvement, no losses.
