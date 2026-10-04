# Author truth freeze — GHSA-hx8v-g79f-8w5f

Recorded after anchor self-review, bundle assembly, and leak-check, and before either judge run.

- `requirement-truth.yaml` SHA-256:
  `02e269ae8517f36534d64c8317daa1ff3b5b943450022f79563b13af2ef060cc`
- `judge-prompt.md` SHA-256:
  `1ca9d10e4337fdf334bb2c825bf7dc3de694eebf75b7e990c04d3379b1c3e7ee`
- Aggregate judge-bundle SHA-256:
  `d6f153036c45890e550e5d3ce9aa758cc95f81cdce60a7bf90f06b4bcfb22212`

The aggregate was computed by sorting all regular paths under `judge-bundle/`, hashing each file,
and hashing the resulting ordered manifest. The author truth and prompt are immutable after a judge
sees this material, except for the charter's two-sided missing-item revision path.
