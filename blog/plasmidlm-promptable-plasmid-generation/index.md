---
title: "PlasmidLM: Promptable Plasmid Generation with Verifiable Rewards"
description: "Conditioning a 19.3M-parameter k-mer DNA language model on compositional part tokens and post-training with specificity-aware GRPO on a zero-overlap cluster split."
date: 2026-11-24
draft: true
tags: ["DNA language models", "Reinforcement learning", "GRPO", "Conditional generation", "Synthetic biology"]
references:
  - title: "PlasmidLM: A Promptable DNA Language Model via Verifiable-Reward Post-Training (bioRxiv)"
    url: https://doi.org/10.64898/2026.05.19.725242
  - title: "PlasmidLM GitHub Repository (McClain-Thiel/PlasmidLLM)"
    url: https://github.com/McClain-Thiel/PlasmidLLM
  - title: "McClain/PlasmidLM-kmer6-GRPO-plannotate Model Card"
    url: https://huggingface.co/McClain/PlasmidLM-kmer6-GRPO-plannotate
  - title: "McClain/PlasmidLM-kmer6 Base Model Card"
    url: https://huggingface.co/McClain/PlasmidLM-kmer6
  - title: "McClain/PlasmidLM-Eval Benchmark Summary & Token Vocabulary"
    url: https://huggingface.co/datasets/McClain/PlasmidLM-Eval
  - title: "PlasmidSpace Interactive Gradio Demo"
    url: https://huggingface.co/spaces/McClain/PlasmidSpace
---

[TODO (McClain): 2–3 sentence TL;DR explaining how `PlasmidLM` turns multi-part functional specifications (`<AMR_*>`, `<ORI_*>`, `<PROM_*>`, `<REPORTER_*>`, `<TAG_*>`, `<ELEM_*>`, `<VEC_*>`) into full plasmid sequences using a 19.3M-parameter k-mer Transformer and verifiable-reward GRPO (`58.0% ± 0.7%` single-shot and `85.5% ± 0.8%` Best-of-4 useful-plasmid yield on the cluster-disjoint `frozen_panel_v3` benchmark).]

## Why Compositional Prompting & Zero-Overlap Sequence Splits Matter

[TODO (McClain): Explain the limitation of unprompted or seed-only plasmid generation (`PlasmidGPT`) and why source-plasmid-ID splits overestimate generalization when Addgene backbones share high sequence identity — motivating the audited `cluster_v3` split (`103,567` prompt–sequence pairs from `19,867` Addgene plasmids partitioned into `11,352` circular clusters via `MMseqs2` + fixed-point `megablast` closure, with `0` cross-split BLAST hits at `>= 90%` identity and `>= 90%` bidirectional coverage).]

## Architecture, `k`-mer Tokenization, and Vocabulary

- **Backbone:** `10`-layer, `d = 384`, `8`-head RoPE + RMSNorm causal Transformer (`19.3M` parameters).
- **Vocabulary (`4,202` active / `4,208` padded tokens):** `4,096` overlapping `6`-mers (stride `3`, so `4,096` tokens cover `~12.3 kb`) plus `106` special tokens (`57` verifiable hard part tokens, `42` contextual soft metadata tokens, `7` structural tokens) documented in [data/special_tokens_v4.csv](data/special_tokens_v4.csv).

## Verifiable-Reward GRPO (`GRPO-v2`)

[TODO (McClain): Summarize the three-component verifiable reward (`0.6` hard-token `F1` via `pLannotate` / compact motif registry + `0.3` complete circular Table-11 `AMR` ORF intactness + `0.1` exact translated epitope tag matching, plus specificity penalties reducing extra unrequested ORI/AMR classes by `-0.155`) across `3` independent GRPO seeds (`42, 43, 44`; `1,000` steps, `G = 8`, `KL beta = 0.5`).]

## Cluster-Disjoint Benchmark Results (`frozen_panel_v3`, `n = 468` Clusters)

| Model / Checkpoint | Viable | Useful@0.5 | BoK-2 Useful | BoK-4 Useful | Covered AMRFinder Recall | Novelty (`<90%` cov.) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `PlasmidLM-kmer6 v2.0` (Base) | `74.15%` | `47.70%` | — | `78.42%` | `58.9%` | `72.2%` |
| **`PlasmidLM-kmer6-GRPO-plannotate v2.0`** (3-seed mean ± SD) | **`83.3 ± 0.2%`** | **`58.0 ± 0.7%`** | **`74.7 ± 0.9%`** | **`85.5 ± 0.8%`** | **`65.0 ± 0.3%`** | **`81.1 ± 0.9%`** |
| `exp2_v2_s44` (`main` checkpoint) | `83.49%` | `58.49%` | — | — | `65.37%` | — |

Full extracted benchmark metrics are available in [data/frozen_panel_v3_results.csv](data/frozen_panel_v3_results.csv).

[TODO (McClain): Add external baseline comparisons (`PlasmidGPT`, `PlasmidGPT-SFT`, retrieval, `Evo 2`), orthogonal `Prodigal v2.6.3` + `NCBI AMRFinderPlus v4.2.7` validation (`0` virulence hits across `7,488` generations), seen (`n = 360`) vs. unseen (`n = 108`) combination generalization, and the clean-prompt ceiling experiment (`75.8% -> 100.0%`).]

## Quick Start & Interactive Demo

You can test prompts interactively on Hugging Face Spaces at [`McClain/PlasmidSpace`](https://huggingface.co/spaces/McClain/PlasmidSpace), or generate sequences locally in `transformers`:

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

repo = "McClain/PlasmidLM-kmer6-GRPO-plannotate"
tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(repo, trust_remote_code=True, torch_dtype=torch.bfloat16).eval()

prompt = "<BOS><VEC_BACTERIAL><AMR_KANAMYCIN><ORI_COLE1><PROM_T7><SEQ>"
inputs = tok(prompt, return_tensors="pt")
out = model.generate(
    **inputs, do_sample=True, temperature=0.3, top_p=0.95, top_k=0,
    max_new_tokens=4096, pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id,
)
dna = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
```

## Known Failure Modes & Next Directions

[TODO (McClain): Discuss the `4,096`-token length drift (`70.8%` hitting max context, mean `11,138 bp`), rare low-copy origins (`<ORI_P15A>`, `<ORI_PSC101>`), `<COPY_LOW>`, and short translated `TAG_*` peptide specificity.]

## Citation

```bibtex
@article{thiel2026plasmidlm,
  title   = {{PlasmidLM}: A Promptable {DNA} Language Model via Verifiable-Reward Post-Training},
  author  = {Thiel, McClain and Barnes, Chris P.},
  journal = {bioRxiv},
  year    = {2026},
  doi     = {10.64898/2026.05.19.725242},
  url     = {https://doi.org/10.64898/2026.05.19.725242},
}
```
