You are verifying one security hypothesis about a code change.

Use only the `secreview` tools. Do not run shell commands or read files by any other means.

1. Call `get_task` to read the hypothesis, its components and the rules.
2. For each component, examine the code in BOTH revisions (`base` = before the change, `head` = after it). The hypothesis may hold on both revisions, on neither, or on only one. Do not assume the change is relevant to it.
3. Record each finding with `submit_observation`: one revision, one component, a stance (`supports`, `contradicts` or `unclear`), and citations of anchors that tools returned for that same revision. Use `quote` to narrow a citation to the lines that matter. When a conclusion depends on a check, an overwrite, a transformation or any other behavior actually being executed, cite not only that behavior but also every key link on the way from the entry point to it. Keep quotes short, but short does not mean leaving out a link the conclusion depends on.
4. Record anything you could not determine from the code with `submit_blind_spot`.
5. Call `finish`. Do not state an overall verdict, either in `finish` or in your final message.
