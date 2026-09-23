# Offline quality smoke benchmark

Run from the repository root:

```bash
python benchmarks/evaluate.py
```

The script reports mean unigram-overlap ROUGE-1 F1 for three short, hand-written examples. This is a deterministic regression signal only, not a representative summarization benchmark. For model/algorithm comparisons, add a sufficiently large, licensed corpus with independently authored references and report standard metrics plus human review.
