# Author truth freeze — GHSA-xcw4-53cc-hv32

Recorded after anchor self-review, bundle assembly, and leak-check, and before either judge run.

- `requirement-truth.yaml` SHA-256:
  `4d8fd4ee6d1290c4108ce7a948913014ec37956168817f591615a009f0920b6f`
- `judge-prompt.md` SHA-256:
  `853fffcb7336f1471e6c5acb864ffa94c526da070983cd86bcb4ae293f31e1f3`
- Aggregate judge-bundle SHA-256:
  `d8a5a264be5cc566c29cf7f14e3e29df1a5521a6e80f61d8d15b3eaf076e55f2`

The aggregate was computed by sorting all regular paths under `judge-bundle/`, hashing each file,
and hashing the resulting ordered manifest. The author truth and prompt are immutable after a judge
sees this material, except for the charter's two-sided missing-item revision path.
