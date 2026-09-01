# Edited files in this build (replace these in your system)

All changes are behavior-preserving except the targeted fixes below.
Each fix was regression-tested against the full sentence set (0 unintended changes).

## repository/morph_gen.py
- Past-tense COPULA now carries person+number so singular subjects produce
  "was" (not always "were"). Restricted to 'be' so lexical past verbs
  (appeared/made/took) are unaffected.

## repository/construction.py
- Coordination block and conjunction-word insertion now also fire for
  'xvanxva' (the dvandva connector), so it produces "X and Y".

## repository/common_v4.py
- new_to_old_convert_construction_conj_dis(): operand-index map now includes
  'xvanxva'.
- {'conj','disjunct'} construct-filter sets extended to include 'xvanxva'.
- handle_compound_nouns(): compound MODIFIERS stay singular; only the NC_head
  inherits plural ("mountain ranges", "cara dhamas"). Numeral components that
  clean() would wipe are preserved ("sector 23").

## repository/gold_postprocess.py
- _rule_unit_plural (NEW): pluralizes a measurement unit after a count > 1
  ("40 kilometres", "60 feet"), registered after _rule_unit_merge.
- connector-strip regex now also removes the literal 'xvanxva'.

## repository/USR_to_JSON.py  &  repository/coref_discourse.py
- Default sentence type to 'affirmative' when the %type line is missing
  (prevents a KeyError crash).

## dictionaries/concept-to-mrs-rels.dat
- alaga+kara_1 : disconnect -> differentiate
- GUma_1       : stroll     -> roam
- pahAdZI_1    : hilldwelling -> mountainous
- laga+jA_1    : ADDED -> touch   (fixes spurious "cow touch")
- ropeve_1     : ADDED -> ropeway

A backup of the original dictionary is at
dictionaries/concept-to-mrs-rels.dat.bak

## Build update (pronoun + romanization)
- common_v4.py: WX->Roman table now maps the candra-marker 'Y' to silent, so
  'POYla' (फॉल) romanizes as 'phaula' instead of 'phauYla' (Tourism_59).
- Possessive-pronoun gender ($wyax) resolves to his/her from the referent's
  gender where available (Tourism_039 'his brother', Tourism_019 'his visit').
  Cases still showing 'its/her/this' are USR-driven (the annotation marks the
  pronoun as dem, or as female) and were left unchanged per instruction.

## Build update (possessive pronoun gender)
- process_cat.py: $wyax/$apanA possessive now outputs his/her whenever the USR
  marks the pronoun male/female (the marker may sit in the gender OR the
  animacy/semcat slot). Previously it required animacy to be literally 'anim'/'per',
  so a 'male' marking fell through to 'its'. Genuinely inanimate referents still
  give 'its' (0 regressions on the baseline).

## Build update (habitual past "used to <verb>")
- morph_gen.py: output-word alignment is now multiword-aware. An Apertium multiword
  token ("use<vblex><past># to" -> "used to") expands to 2 surface words; the old
  zip(tokens, words) dropped the extra word, deleting the main verb (e.g. "used to go"
  became "used to"). Tokens containing "# " now consume 2 words so following tokens
  (the lexical verb) stay aligned.
- gold_postprocess.py: _rule_used_to also normalises a raw 'use_to'/'used_to' term to
  'used to'. Result: Tourism_019 -> "used to go" (verb restored).

## Build update (output ordering + portability)
- hindi_gen.py: output is now printed in the SAME order the USRs appear in the
  input file. TAM-broken / error sentences stay in their position (previously
  pushed to the end), and a USR that generates nothing now prints an explicit
  "no output generated from the usr" line in place instead of being dropped.
- Apertium English binary paths (eng.automorf.bin / eng.autogen.bin) are now
  resolved relative to the tool folder, so the hardcoded /home/lc4eu/... path no
  longer causes "Cannot open file" errors regardless of where the tool is installed.
