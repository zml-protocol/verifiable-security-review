# Author-label freeze — GHSA-xcw4-53cc-hv32 negative controls

Frozen before either independent judge received the prompt.

- procedure/candidate freeze commit: `1019665`
- author labels SHA-256: `23906c87fb3de0e85262330c1db1080cf18a05bfb452726f376ee2206be04ab2`
- factual evidence SHA-256: `3e1c6fa237e6269d885a2e2777e22116ff35e56faf8a3cf6e4b7ceec9792f159`
- byte-identical judge prompt SHA-256:
  `c81746ab17b4ed32dca04816687e665946b0ea38b549ee6d53b1834e5342e2e1`
- frozen candidate order: CWE-22, CWE-79, CWE-89
- prompt leak check: no author labels/rationales, real-truth key, selection reasoning, project chat,
  or other judge output (`author_id` occurrences are source identifiers in factual SQL excerpts)

No author label, evidence, candidate wording/order, or prompt byte may change after judge execution.
