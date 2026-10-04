# Author-label freeze — GHSA-mr3j-p26x-72x4 negative controls

Frozen before either independent judge received the prompt.

- procedure/candidate freeze commit: `1019665`
- author labels SHA-256: `cdf66b3148ad7e2329ddaf2d698b37a0a81e58098b52ab94b7ea9dbc9dc9241b`
- byte-identical judge prompt SHA-256:
  `bbc6c319ca3a874535c8f84247d36a1dd8dd96005cdba24d96211801b5090923`
- complete inventory recomputation: 394 paths in both revisions; list hash matches prompt
- frozen candidate order: CWE-918, CWE-502, CWE-601
- prompt leak check: no author labels/rationales, real-truth key, selection reasoning, project chat,
  or other judge output

No author label, evidence, candidate wording/order, or prompt byte may change after judge execution.
