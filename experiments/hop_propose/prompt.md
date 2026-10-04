You are laying out the evidence path for one security hypothesis about a code change.

Use only the `secreview` tools. Do not run shell commands or read files by any other means.

1. Call `get_task` to read the hypothesis, its hints, the hop format, the relations and the rules.
2. Examine the code in BOTH revisions (`base` = before the change, `head` = after it).
3. Express the path as typed hops. Check hops with `validate_hop` as you go.
4. Call `submit_hops` once with your complete set of hops, then end your turn. Do not state a verdict about the hypothesis.
