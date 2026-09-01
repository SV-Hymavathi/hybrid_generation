# Tool output vs gold — the 32 differences (Sheet1, columns E vs G)

Columns in the error sheet: **E = New Chunked output (tool)**, **F = a variant
run**, **G = CORRECT CHUNK (gold)**. Gold was hand-authored for ~the first 50
sentences; beyond that, G just mirrors the old E, so it is NOT real gold.

Of the 50, **32 rows** have gold that genuinely differs from the original tool
output. This turn, exact-gold matches on those 32 went **3 → 5**, with partial
improvements on others and **0 regressions** across all 252 sentences
(verified by snapshot-diffing every sentence before/after each change).

## Status per target

Legend: ✅ now matches gold · ◐ improved, not exact · ⛔ needs deeper
(reorder/agreement) work not safely automatable on 50/250 gold.

| Sent | Issue type | Tool → Gold | Status |
|------|-----------|-------------|--------|
| 001 | article | `a line` → `one line` (eka_2 counting) | ⛔ context (002 keeps "a") |
| 002 | verb-PP order | PP after verb in gold | ⛔ reorder |
| 003 | plural | `Hindu` → `Hindus` | ✅ (plural fallback) |
| 004 | imperative order | verb-first in gold | ⛔ reorder |
| 005 | prep | `13 navaṃbara` → `on 13 navaṃbara` | ⛔ k7t marker |
| 006 | NC + order | `pillar aśoka` → `aśoka pillar`; phrase reorder | ⛔ NC order |
| 007 | translit + split | `SivaballaBapura` → `śiva ballabhapura` | ◐ transliterated; split pending |
| 008 | NC + focus | `near aśoka pillar`; `also` to end | ⛔ NC order + focus |
| 009 | NE order | `ballabhapura śiva` → `śiva ballabhapura` | ⛔ NE component order |
| 010 | translit | `SivaballaBapura area` → `śiva ballabhapura area` | ◐ transliterated; split pending |
| 012 | voice tag | missing `_PASSIVE`; adverb to end | ⛔ passive detect |
| 013 | quantifier | `ways` → `several ways` | ⛔ quant missing |
| 015 | order + translit | `continuously go`→`go continuously`; `meraṭha`→`mīraṭha` | ⛔ adverb order + dict |
| 017 | measure | `105 kilometre` → `about 105 kilometres` | ⛔ measure plural + approx |
| 018 | focus | `in only hastināpura` → `in hastināpura only` | ⛔ focus placement |
| 019 | poss+prep | `his to visit` → `for his visit` | ◐ now `to his visit` (prep sense pending) |
| 023 | article on NE | `the ratna staṃbha` → `ratna staṃbha` | ⛔ NE article |
| 024 | copula | `called` → `is called`; NC split | ⛔ copula insert |
| 027 | focus | `also riding boat` → `riding boat also` | ⛔ focus placement |
| 032 | poss+prep | `its in charming beauty` → `in its charming beauty` | ✅ (poss/prep swap) |
| 033 | NC + order | `station railway …` → `… railway station …` | ⛔ NC order |
| 035 | order | `from to paṭanā` → `from paṭanā to` | ⛔ correlative prep order |
| 036 | article order | `a of king` → `of a king` | ⛔ prep/article order |
| 039 | poss+prep | `his to brother` → `to his brother` | ✅ (poss/prep swap) |
| 040 | NC | `stationrailway` → `railway station` | ⛔ NC spacing+order |
| 042 | focus | `from only birth` → `from birth only` | ⛔ focus placement |
| 043 | agreement | `validate` → `validates`; drop `of` | ⛔ agreement |
| 046 | order | reorder + `ranges mountains`→`mountains ranges` | ⛔ NC order |
| 047 | prep | `here` → `from here` | ⛔ k5 marker |
| 051 | missing word | `in mutually` → `in mutually joined` | ⛔ dropped participle |
| 052 | agreement+voice | `is`→`are`; `the`→`by the` (passive agent) | ⛔ agreement/voice |
| 053 | article+agree | `a influential`→`an influential` ✅; `were`→`was` ⛔ | ◐ article fixed; agreement pending |

## What the ⛔ items need (and why I did not auto-apply them)

They cluster into four engineering tasks, all in stages I cannot validate
against the 200 sentences that have no gold:

1. **Phrase reordering** (NC mod/head order, adverb/focus placement, imperative
   verb-first, correlative `from…to`): logic in `add_chinking`
   (`repository/common_v4.py`) and `repository/reorder.py`. "only"/"also"
   placement is context-dependent — gold fronts it in 002/020 but trails it in
   008/018/027 — so a blanket rule would regress as many as it fixes.
2. **Subject–verb agreement** (`is/are`, `was/were`, `validate/validates`):
   needs reliable subject-number detection feeding the verb morphology.
3. **Voice/copula** (`_PASSIVE` on 012, `is called` on 024): passive-TAM
   detection in the verb tagger.
4. **NE/NC component splitting** (`śivaballabhapura` → `śiva ballabhapura`):
   consult the construction row to split joined tokens before transliteration.

Each is doable, but should be done with gold coverage so changes are
regression-checked. That is exactly what `usr_review_all_250.csv` is for:
fill the gold column, and these can be fixed under the same
snapshot-before/after guard used this turn.

## Safe fixes actually applied this turn (general English rules, 0 regressions)

- `a` → `an` before a vowel-initial **content** word (skips `a of`, etc.).
- Possessive + preposition (`its in`, `his to`) → preposition + possessive.
  Verified: fixed 032 and 039 to gold, improved 019, and correctly fixed an
  unseen sentence (218: `her of life` → `of her life`).
