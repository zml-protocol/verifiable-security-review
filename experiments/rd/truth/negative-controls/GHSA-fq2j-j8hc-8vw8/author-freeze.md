# Author-label freeze — GHSA-fq2j-j8hc-8vw8 negative controls

Frozen before either independent judge received the prompt.

- procedure/candidate freeze commit: `1019665`
- author labels SHA-256: `b787dbe98e4ee5360dcea53b8c79482976dac77dd76d1ad392bbac2f561ad430`
- byte-identical judge prompt SHA-256:
  `68fbe379f976f5bac93ae4c4d228f2fa0a0a0360bf6691cf67ce55c82343fa12`
- complete inventory recomputation: 236 paths in both revisions; list hash matches prompt
- frozen candidate order: CWE-22, CWE-79, CWE-89
- prompt leak check: no author labels/rationales, real-truth key, selection reasoning, project chat,
  or other judge output

No author label, evidence, candidate wording/order, or prompt byte may change after judge execution.
