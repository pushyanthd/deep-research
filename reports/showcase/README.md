# Research output evaluation — September 21, 2026

These are unedited generated reports. The original quick and deep reports in the parent directory
remain as historical failure examples. Start with the new [quick report](quick.md),
[deep comparison](deep.md), and [technical architecture brief](retrieval.md).

| Artifact | How generated | Words | Cited sources | Exact repeated paragraphs | Cited table rows | Fallback |
|---|---|---:|---:|---:|---:|---|
| Original quick | Historical full run | 1,079 | 5 | 1 | 0 | Yes |
| New quick | Fresh full run | 924 | 5 | 0 | 0 | No |
| Original deep | Historical full run | 3,293 | 21 | 10 | 0 | Yes |
| New deep | Writer replay, frozen evidence and review | 1,619 | 11 | 0 | 3 | No |
| Technical brief | Re-review and rewrite, frozen evidence | 949 | 4 | 0 | 0 | No |

All three new reports have zero unresolved citation IDs and zero empty evidence sections. These
counts describe structure, not factual correctness or semantic repetition. The original deep source
appendix listed more sources than were actually cited; this table counts references in the body.

The historical comparisons changed the evidence, models, and prompts. They do not isolate a causal
effect. A narrower deep-writer comparison held evidence and review constant: the previous writer
produced a 1,875-word fallback with 17 exact repeated paragraphs and no cited table rows; the updated
writer produced the new deep report above. This is one development example, not a held-out benchmark.

## Runtime and cost

All new artifacts used GPT-5.4 mini. The quick run completed in 283 seconds, with six searches and ten
fetched sources, at an estimated $0.308 in OpenAI usage. The deep writer replay cost $0.200; its
underlying full run took 797 seconds and cost $0.847, including the earlier writer attempt. The
technical re-review/rewrite cost $0.100, excluding its earlier evidence collection.

Across all development trials, the local ledger recorded approximately $2.29 of reported-token
usage, plus $0.40 reserved for uncertain attempts, against the authorized $17 ceiling. These are
conservative estimates using uncached input prices, not account billing. Search-provider charges are
excluded. [Machine-readable results](results.json) preserve artifact hashes and per-generation usage.

## What improved and what remains

The new reports give conditional recommendations, retain readable citations, and expose missing
evidence. The deep comparison includes a cited table and excludes a rejected successor-model claim
from its recommendations. The technical brief avoids inventing performance gains for an unseen corpus.

They still need human review. In particular, the deep report overuses “Inference,” repeats some
recommendations, and uses stronger comparative language about black levels and motion than the
available cross-model evidence warrants. Its listed prices are not comparable live offers and must
not drive a value ranking. The quick report retains a measurement conflict in its audit section;
some limitation messages still contain internal IDs. Zero exact duplicates does not mean concise
writing, and a valid reference does not prove sentence-level support.

The technical report is an architecture research example, not a load-tested implementation. Its
latency and throughput targets still require testing on the actual corpus. No independent factual
accuracy score is claimed for any sample.

## Reproduction

See [output quality](../../docs/output-quality.md) for commands, architecture changes, and limitations.
The three input cases are versioned in [evals/cases.json](../../evals/cases.json). Live execution is
explicitly opt-in. Full run checkpoints, evidence excerpts, captured model outputs, and replay
requests remain local under ignored `research-reports/`; they are not published with this portfolio.
Fresh searches will change with the web. The recorded hashes identify this evaluation's artifacts;
replays require the corresponding local captured requests.
