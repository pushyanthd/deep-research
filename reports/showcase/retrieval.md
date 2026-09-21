# BM25-only vs Hybrid Retrieval for an English Internal Documentation Assistant

## Executive summary

Inference: default to hybrid BM25 + dense retrieval + reranking, but keep BM25-only as the fallback when exact codes and operational simplicity dominate the decision. The consequential trade-off is recall versus simplicity: hybrid is better at recovering paraphrased technical context and ranking the right passages higher, while BM25 is the safer lexical baseline for verbatim identifiers. [S1] [S2]

The strongest benchmark evidence here shows hybrid + rerank outperforming single-stage retrieval on mixed text-and-table documents, while BM25 remains competitive and even beats the dense retriever, so dense search is not a universal upgrade. For this corpus, the architecture choice should be gated by an offline test on your own query mix rather than assumed from the literature. [S1] [S2]

## Methodology

Used only the approved, review-passed claims mapped to the four outline sections and synthesized them into a short decision brief without adding new sources. Retrieval-quality claims come from the benchmark papers; failure-mode and evaluation claims come from the benchmarking-framework paper’s guidance on Recall@k and separate runtime measurement. [S1] [S2] [S3] [S4]

## Recommendation

Inference: choose hybrid BM25 + dense retrieval + reranking as the default architecture for this assistant, because the best available evidence here says the hybrid-rerank path gives the strongest retrieval quality and that neither lexical nor dense retrieval alone is sufficient when queries mix exact identifiers with paraphrased context. [S1]

Inference: keep BM25-only as the production fallback when the corpus is heavily identifier-driven or when the simpler path is materially easier to operate and evaluate; the benchmark also shows BM25 is competitive and can outperform dense retrieval on domain-specific documents, so dense search is not a blanket improvement. [S1] [S2]

## Key tradeoffs for technical documentation retrieval

- Retrieval quality: hybrid + rerank delivered the strongest measured retrieval quality in the benchmark, with Recall@5 of 0.816 versus 0.695 for hybrid RRF and 0.644 for BM25. [S1]
- Exact identifiers: BM25 remains the safer baseline for verbatim technical identifiers because lexical matching is strong, and the benchmark found BM25 outperformed the dense retriever on the tested domain-specific corpus. [S1]
- Operational burden: hybrid requires dense embeddings, fusion, and a second-stage reranker, so it adds moving parts that BM25-only avoids. [S1] [S2]
- Inference: if the query mix is mostly exact codes, BM25-only is the simpler default; if paraphrased context is common, hybrid is the better bet. [S1] [S2]

## Likely failure modes

- BM25-only failure mode: it is more likely to miss paraphrased or disambiguating queries because lexical overlap is not enough when the wording changes. [S4]
- Hybrid failure mode: reranking adds a configurable stage that introduces top-K, model-choice, precision, and decoding trade-offs, so quality gains can be erased by tuning or runtime overhead. [S3]
- Hybrid efficiency failure mode: too-small top-K limits reranking gains, while too-large top-K adds cost with diminishing returns. [S3]

## Offline evaluation plan

- Use a held-out query set with manually annotated relevant contexts, and make Recall@k the primary metric for this single-answer retrieval task. [S3]
- Measure end-to-end latency and throughput separately from retrieval quality so BM25-only and hybrid are compared on both accuracy and runtime behavior. [S4]
- Inference: tune reranker candidate depth/top-K on a development split, then freeze it for the final comparison; pick hybrid only if it materially improves Recall@k without violating the runtime budget. [S3] [S4]

## Limitations

- The strongest comparative benchmark is on financial text-and-table documents, not the target technical-documentation corpus, so the default recommendation is only partially generalizable.
- Several operational and latency claims rely on vendor or blog sources rather than original measurements or official docs.
- No source here directly quantifies the 1-second p95 and 20 QPS target on this exact workload, so those constraints remain inferential.
- q_failure_eval remains partial: The plan covers metrics and dataset design, but the exact-match identifier emphasis is stated without direct supporting evidence.
- section_failure_modes remains partial: Most failure modes are supported, but the identifier-heavy evaluation point is asserted without evidence.
- section_offline_eval remains partial: The offline evaluation recipe is mostly supported, but one key test-set recommendation lacks direct evidence.
- The identifier-heavy test-set and string-exact judgment requirement has no linked excerpt support, yet it is central to the evaluation plan.
- The same-corpus, same-budget comparison rule is reasonable but has no direct supporting excerpt and is material to the offline decision process.
- The approved research budget was exhausted before all gaps closed.
- Several operational and latency claims rely on benchmarking-framework sources rather than direct measurements on the user’s exact workload.
- q_failure_eval remains partial: the plan covers metrics and dataset design, but the exact-match identifier emphasis is stated without direct supporting evidence.
- section_failure_modes remains partial: most failure modes are supported, but the identifier-heavy evaluation point is asserted without evidence.
- section_offline_eval remains partial: the recipe is mostly supported, but one key test-set recommendation lacks direct evidence.
- The same-corpus, same-budget comparison rule is reasonable but has no direct supporting excerpt.

## Conclusion

Inference: default to hybrid BM25 + dense retrieval + reranking if the offline test shows a meaningful Recall@k gain on your real query mix; otherwise keep BM25-only as the safer production default for identifier-heavy, simplicity-first deployments. The best evidence here favors hybrid for retrieval quality, but BM25 stays competitive and even beats dense retrieval on the reference corpus, so dense search is not a universal upgrade. [S1] [S2]

## Follow-up topics

- How to size reranker candidate depth so the system stays inside latency budget
- How to build a judged query set that separates exact-code queries from paraphrased technical queries
- How to define the final acceptance threshold for Recall@k versus runtime before rollout

## Sources

- [S1] From BM25 to Corrective RAG: Benchmarking Retrieval Strategies for Text-and-Table Documents; accessed 2026-09-21; web_page. <https://arxiv.org/html/2604.01733v1>
- [S2] A Hybrid Approach to Information Retrieval and Answer Generation for Regulatory Texts; accessed 2026-09-21; web_page. <https://arxiv.org/html/2502.16767v1>
- [S3] LLM Optimization Unlocks Real-Time Pairwise Reranking; accessed 2026-09-21; web_page. <https://arxiv.org/html/2511.07555v1>
- [S4] RAGPerf: An End-to-End Benchmarking Framework for Retrieval-Augmented Generation Systems; accessed 2026-09-21; web_page. <https://arxiv.org/html/2603.10765v1>
