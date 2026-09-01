# A Faithful Hybrid Pipeline for Natural Language Generation from Universal Semantic Representation

**Paper:** A Faithful Hybrid Pipeline for Natural Language Generation from Universal Semantic Representation  
**Authors:** Veera Hymavathi Sirisipalli, Sukhada, Tejaswi Naga Swetha Poppoppu, Soma Paul  
**Affiliations:** Department of Humanistic Studies, IIT (BHU), Varanasi | Language Technologies Research Centre, IIIT Hyderabad  
**Manuscript:** NLP-D-26-00261 | Natural Language Processing Journal, Elsevier  
**Status:** Under Review

---

## Overview

This repository contains all data, system outputs, evaluation scripts, and the eight-step rule-based generation tool associated with the above paper. The paper presents the first hybrid NLG pipeline built on Universal Semantic Representation (USR) for Hindi-to-English generation. The pipeline separates faithfulness (handled by deterministic rules) from fluency (handled by a large language model), achieving faithfulness F1 of 0.900–0.922 against 0.435–0.528 for all neural baselines.

---

## Repository Structure

```
USR_NLG_Submission_Toolkit/
│
├── DATA
│   ├── 02_USR_to_chunks_accuracy_and_USR_interannotator.xlsx
│   │     250 Hindi sentences | validated USR annotations (annotators 1 & 2) |
│   │     gold English chunks | current tool output | IAA scores
│   │
│   ├── 03_direct_Hindi_to_English_translation_faithfulness.xlsx
│   │     250 Hindi sentences | gold English translations |
│   │     Llama 4 Scout / Mistral Small / Gemma 3 direct translation outputs |
│   │     per-sentence faithfulness F1 | error notes |
│   │     Google Translate outputs + F1 | IndicTrans2 outputs + F1
│   │
│   ├── baseline_google_translations.csv
│   │     sent_id | Hindi | Google Translate English output
│   │
│   └── baseline_indictrans2_translations.csv
│         sent_id | Hindi | IndicTrans2 English output
│
├── SYSTEM OUTPUTS
│   ├── 04_raw_USR_to_English_generation.xlsx
│   │     Outputs from Llama / Mistral / Gemma given raw USR as input (Condition 2)
│   │
│   ├── 05_hybrid_chunks_to_sentence_3model_BLEU_chrF.xlsx
│   │     Stage 1 chunk sequences | hybrid pipeline English outputs |
│   │     BLEU and chrF scores for Llama / Mistral / Gemma (Condition 4)
│   │
│   └── 11_ablation_USR_with_guidelines_results.csv
│         USR + guidelines condition outputs (Condition 3) for all 3 LLMs
│
├── HUMAN EVALUATION
│   ├── 06_hybrid_human_evaluation_and_interannotator_kappa.xlsx
│   │     Human fluency / adequacy / comprehension ratings (3 annotators) |
│   │     50 randomly sampled hybrid outputs per LLM | kappa scores
│   │
│   └── 07_human_evaluation_comparative_50sent.xlsx
│         Comparative evaluation across 4 systems (hybrid, direct LLM,
│         Google Translate, IndicTrans2) on the same 50 sentences |
│         system names hidden | 3 annotators | 600 ratings total
│
├── AGGREGATE SCORES
│   ├── 09_faithfulness_scores_all_systems.csv
│   │     Mean faithfulness F1, BLEU, chrF for all 8 experimental conditions
│   │
│   └── 10_sacrebleu_BLEU_chrF_with_signatures.csv
│         Official sacreBLEU scores with version signatures for reproducibility
│
├── EVALUATION SCRIPTS
│   ├── 12_faithfulness_scorer.py       — token-F1 faithfulness metric
│   ├── 13_compute_sacrebleu.py         — BLEU and chrF via sacreBLEU
│   └── 14_usr_fewshot_ablation.py      — USR + guidelines ablation script
│
└── GENERATION TOOL
    └── multilingual_rule_based_tool/   — Eight-step rule-based generation tool
          Takes validated USR as input, produces English chunk sequences
          See tool/README.md for usage instructions
```

---

## Key Results

| System | Faithfulness F1 | BLEU | chrF2 |
|---|---|---|---|
| **Hybrid Pipeline (Mistral Small)** | **0.922** | **65.3** | **79.7** |
| **Hybrid Pipeline (Llama 4 Scout)** | **0.911** | **61.9** | **81.0** |
| **Hybrid Pipeline (Gemma 3)** | **0.900** | **62.5** | **79.1** |
| Google Translate | 0.528 | 14.3 | 44.4 |
| IndicTrans2 | 0.516 | 14.5 | 43.6 |
| Mistral Small (direct) | 0.500 | 14.4 | 43.1 |
| Llama 4 Scout (direct) | 0.485 | 14.2 | 42.1 |
| Gemma 3 (direct) | 0.473 | 11.7 | 40.3 |
| Raw USR → LLM | 0.075–0.191 | 0.3–1.4 | 14.0–22.1 |

---

## Experimental Conditions

The paper evaluates eight conditions on the same 250 sentences:

| Condition | Description |
|---|---|
| C1–C3 | Direct Hindi → English translation (Llama, Mistral, Gemma) |
| C4 | Google Translate (baseline MT) |
| C5 | IndicTrans2 (dedicated Indian language MT) |
| C6 | Raw USR → English (LLM given USR, no guidance) |
| C7 | USR + guidelines → English (USR + tag specification + examples) |
| C8 | **Hybrid pipeline** (8-step rules + concept dictionary + LLM surface realiser) |

---

## Models Used

| Model | Checkpoint | Parameters | Provider | Access Date |
|---|---|---|---|---|
| Llama 4 Scout | meta-llama/llama-4-scout-17b-16e-instruct | 17B (16E MoE) | Groq API | March 2026 |
| Mistral Small | mistral-small-3.1-24b-instruct | 24B | Mistral API | March 2026 |
| Gemma 3 | gemma-3-27b-it | 27B | Groq API | March 2026 |
| Google Translate | Cloud Translation API v3 | — | Google Cloud | March 2026 |
| IndicTrans2 | ai4bharat/indictrans2-indic-en-1B | 1B | HuggingFace | March 2026 |

**Decoding configuration (all LLMs):** temperature = 0.1, max_tokens = 200, no top-p/top-k constraints, no stop conditions beyond provider default, single generation per sentence, no manual selection or regeneration.

---

## Running the Evaluation Scripts

### Requirements
```bash
pip install openpyxl sacrebleu
```

### Faithfulness F1
```bash
# Put all data files in the same folder as the script, then:
python3 12_faithfulness_scorer.py
# Output: faithfulness_scores.csv
```

### BLEU and chrF
```bash
python3 13_compute_sacrebleu.py
# Output: sacrebleu_scores.csv with official signatures
```

### USR + Guidelines Ablation
```bash
# Requires API keys for Groq/Mistral
python3 14_usr_fewshot_ablation.py
```

---

## Eight-Step Rule-Based Generation Tool

The tool takes validated USR annotations as input and produces English chunk sequences through eight deterministic steps:

1. **Lexical mapping** — concept dictionary lookup (sense-disambiguated)
2. **Morphological realisation** — tense, aspect, number, definiteness
3. **Preposition assignment** — karaka relations to English prepositions
4. **Named entity transliteration** — WX-to-Roman converter
5. **Speaker's view processing** — approximation, negation, discourse markers
6. **Dependency ordering** — head-index based linearisation
7. **Construction handling** — conjunctions, measure, span constructions
8. **Chunk assembly** — role-tagged chunk sequence output

### Tool accuracy on 250-sentence evaluation set

| Version | Exact match accuracy |
|---|---|
| Version used in paper experiments | 93.2% (233/250) |
| **Current repository version** | **96.4% (240/249)** |

The repository version reflects improvements made after paper submission. The 233 sentences where both versions agree reproduce the paper results exactly.

### Usage
```bash
cd multilingual_rule_based_tool/
# Place your USR file in the input folder
# See tool/README.md for full usage instructions
python3 common_v4.py
```

---

## Dataset

**250 Hindi tourism sentences** from the ILCI Hindi Tourism Corpus, manually annotated with Universal Semantic Representation (USR) by two trained computational linguists with expert adjudication.

- Average sentence length: 10.2 words (range 3–22)
- Domains: pilgrimage, historical facts, route/distance, nature/wildlife, festival/culture
- Annotation levels: lexico-conceptual, relational, discourse
- Inter-annotator agreement: line level 0.80, relation tag level 0.84
- Expert adjudication: third annotator with 4+ years USR experience

---

## Human Evaluation

**Section 3.2.1 — Single-system evaluation:**
- 50 randomly sampled sentences × 3 LLMs × 3 annotators = 450 ratings
- Criteria: fluency, adequacy, comprehension (1–5)
- Mean Cohen κ = 0.905 (near perfect agreement)
- Best result: Mistral Small hybrid — 4.85/5

**Section 3.2.4 — Comparative evaluation across systems:**
- Same 50 sentences × 4 systems × 3 annotators = 600 ratings
- Systems: hybrid pipeline, direct LLM, Google Translate, IndicTrans2
- System names hidden, outputs randomly ordered
- Adequacy differences significant at p < 0.001 (Wilcoxon) vs all baselines

---

## Concept Dictionary

The multilingual concept dictionary (~142,622 entries) maps USR concept IDs to verified English lemmas. It was incrementally validated during USR annotation to ensure complete coverage for all 250 evaluation sentences. Dictionary files are included in the generation tool folder.

---

## Citation

If you use this data or tool in your research, please cite:

```
@article{sirisipalli2026faithful,
  title={A Faithful Hybrid Pipeline for Natural Language Generation 
         from Universal Semantic Representation},
  author={Sirisipalli, Veera Hymavathi and Sukhada and 
          Poppoppu, Tejaswi Naga Swetha and Paul, Soma},
  journal={Natural Language Processing Journal},
  publisher={Elsevier},
  year={2026},
  note={Under review, Manuscript NLP-D-26-00261}
}
```

---

## License

Data and evaluation scripts: CC BY 4.0  
Generation tool: MIT License  


---

## Contact

For questions about the data, scripts, or tool:  
**Veera Hymavathi Sirisipalli** — sirisipallivhymavathi.rs.hss24@itbhu.ac.in  
Department of Humanistic Studies, IIT (BHU), Varanasi, India
