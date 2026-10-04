# Author-label freeze — GHSA-hx8v-g79f-8w5f negative controls

Frozen before either independent judge received the prompt.

- procedure/candidate freeze commit: `1019665`
- author labels SHA-256: `b5677ad0e27ce867f4fe5f8d5a94d8ee0ac2e320193535956b3b9ddb9e42d6da`
- byte-identical judge prompt SHA-256:
  `96ddd910b12de2b92c0a7e5302fd78335da5427369382c5a8ec3c2d7420874a9`
- complete inventory recomputation: 394 paths in both revisions; list hash matches prompt
- frozen candidate order: CWE-502, CWE-601, CWE-611
- prompt leak check: no author labels/rationales, real-truth key, selection reasoning, project chat,
  or other judge output

No author label, evidence, candidate wording/order, or prompt byte may change after judge execution.
