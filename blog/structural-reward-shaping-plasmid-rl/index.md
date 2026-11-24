---
title: "Structural Reward Shaping in RL-Trained Plasmid Generators"
description: "How multi-component bioinformatics rewards with GRPO raise strict plasmid QC pass rates from 4.3% to 71.6% while inducing unrewarded biophysical realism."
date: 2026-11-24
draft: true
tags: ["DNA language models", "Reinforcement learning", "GRPO", "Synthetic biology", "ICML 2026"]
references:
  - title: "Effects of Structural Reward Shaping on Biophysical Properties in RL-Trained Plasmid Generators (ICML 2026, PMLR Vol. 306)"
    url: https://openreview.net/forum?id=uiMxVE16m3
  - title: "PlasmidRL bioRxiv Preprint (DOI: 10.64898/2026.03.24.713963)"
    url: https://doi.org/10.64898/2026.03.24.713963
  - title: "PlasmidRL GitHub Repository"
    url: https://github.com/UCL-CSSB/PlasmidRL
  - title: "UCL-CSSB/PlasmidGPT-GRPO Model Checkpoints"
    url: https://huggingface.co/UCL-CSSB/PlasmidGPT-GRPO
  - title: "UCL-CSSB/PlasmidRL-ICML Evaluation & Artifact Archive"
    url: https://huggingface.co/datasets/UCL-CSSB/PlasmidRL-ICML
---

[TODO (McClain): 2–3 sentence TL;DR answering the core research question directly — how Group Relative Policy Optimization (GRPO) with structural reward shaping solves viability failures in autoregressive DNA language models like PlasmidGPT, boosting strict QC pass rate from **4.3%** (pretrained baseline) to **71.6%** across 4,000 generated sequences (8 prompts × 500 samples).]

## Why Unconstrained DNA Language Models Fail Biological QC

[TODO (McClain): Explain what makes a synthetic plasmid viable in the lab vs. merely fluent in nucleotide likelihood, and why standard next-token pretraining (`PlasmidGPT`) and supervised fine-tuning (`PlasmidGPT-SFT`) fail strict multi-component checks.]

Strict QC pass criteria enforced in `UCL-CSSB/PlasmidRL`:

- Exactly one functional origin of replication detected via BLAST (`>= 99%` identity and `>= 99%` subject coverage against the curated `oriDB`).
- At least one complete antibiotic resistance gene detected by `NCBI AMRFinderPlus` in nucleotide mode (`100%` identity and coverage).
- Zero exact direct repeats `>= 50 bp`.

## Headline Results Across 8 Prompts (4,000 Sequences / Model)

| Model | Hugging Face ID | Optimal Rejection-Sampling T | Strict QC Pass Rate (`n = 4,000`) | Notes |
| --- | --- | ---: | ---: | --- |
| PlasmidGPT (Base) | `UCL-CSSB/PlasmidGPT` | `1.00` | **4.3%** | Pretrained autoregressive baseline |
| PlasmidGPT-SFT | `UCL-CSSB/PlasmidGPT-SFT` | `1.00` | [TODO: confirm exact SFT %] | Supervised fine-tuning on curated *E. coli* corpus |
| **PlasmidGPT-GRPO (RL)** | `UCL-CSSB/PlasmidGPT-GRPO` | `1.15` | **71.6%** | Multi-component structural reward shaping via GRPO (~17× over Base) |

[TODO (McClain): Add the SFT pass rate, per-prompt comparison (structural ORI prompts vs. generic `ATG`/short seeds), and Best-of-K rejection-sampling numbers from Table 1 & Table 3 (`notebooks/01_pass_rate.py`, `notebooks/06_rejection_sampling.py`).]

## Multi-Component Reward Shaping & Ablations

The `full_reward` objective combines biological annotation scores (`ori_weight = 1.0`, `promoter_weight = 1.0`, `terminator_weight = 0.5`, `marker_weight = 1.0`, `cds_weight = 1.0`), a length prior (`3,000–6,000 bp` ideal window within `2,000–30,000 bp`), a `>= 50 bp` repeat penalty (`0.1` per repeat region), and a cassette-ordering bonus (`location_aware = True`). Full ablation parameter definitions are bundled in [data/ablation_reward_configs.csv](data/ablation_reward_configs.csv).

[TODO (McClain): Summarize the 5 reward ablations (`no_repeat_penalty`, `no_length_prior`, `no_cassette_bonus`, `cds_only`, `length_only` at `T = 0.95` and `T = 1.15`) and why the cassette ordering bonus is critical without collapsing sequence diversity (`1 - mean pairwise 21-mer Jaccard`, Addgene baseline `0.9245`).]

## Emergent Biophysical Realism Without Explicit Supervision

[TODO (McClain): Walk through the unrewarded properties observed after GRPO (minimum free energy / ViennaRNA stability, GC distribution, 3-mer spectrum, ORF structure, and held-out plasmid family coverage) and how this compares with baseline `PlasmidGPT` and generalist genomic LMs (`Evo 2`).]

## Running `PlasmidGPT-GRPO`

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("UCL-CSSB/PlasmidGPT-GRPO")
tokenizer = AutoTokenizer.from_pretrained("UCL-CSSB/PlasmidGPT-GRPO")

input_ids = tokenizer("ATG", return_tensors="pt").input_ids
outputs = model.generate(input_ids, max_new_tokens=512, do_sample=True, temperature=1.0)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

*(Paper protocol sampling temperatures: `T = 1.00` for Table 1 main comparison, `T = 0.95` for Table 7 ablations, and `T = 1.15` for RL rejection sampling.)*

## Limitations & Practical Guidance

[TODO (McClain): Note computational vs. wet-lab validation, dependence on reference bioinformatics annotation binaries (`BLAST`, `AMRFinderPlus`, `ViennaRNA`), and prompt sensitivity.]

## Citation

```bibtex
@inproceedings{thiel2026plasmidrl,
  title     = {Effects of Structural Reward Shaping on Biophysical Properties in {RL}-Trained Plasmid Generators},
  author    = {Thiel, McClain and Cunningham, Angus G. and Barnes, Chris P.},
  booktitle = {Proceedings of the 43rd International Conference on Machine Learning (ICML)},
  series    = {Proceedings of Machine Learning Research},
  volume    = {306},
  year      = {2026},
  publisher = {PMLR},
  url       = {https://openreview.net/forum?id=uiMxVE16m3},
}
```
