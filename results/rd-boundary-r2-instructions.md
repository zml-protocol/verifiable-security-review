# RD definition check, round 2: instructions for the operator (PREREGISTRATION.md §15.1)

Two adjudicators label the same sheet independently. Give each ONLY `rd-boundary-r2-sheet.md` and
`rd-boundary-r2-labels.template.yaml`. Nothing else from the project.

## Who may label

- Two **brand-new** model conversations, neither of them Claude (the agent under test is Claude).
  Best: two different non-Claude model families. If only ChatGPT is available, use two separate
  Temporary Chats (or memory off); the report then says they are not independent model families.
- Neither may see the other's answers, the author's labels, this project's history, or any earlier
  conversation about it. Run them in any order.
- A conversation that has seen this project (including the one relaying this) may not label.

## Steps

1. Open a new conversation (Temporary Chat / memory off), attach both files, paste the prompt below.
2. Check the reply has a label for every id (relations r.., requirements q..) and a filled reviewer
   block. If the YAML does not parse, you may ask the same conversation once to fix the format only.
3. Save the reply verbatim as `results/rd-boundary-r2-judge-a.yaml` (first adjudicator) or
   `results/rd-boundary-r2-judge-b.yaml` (second). Do not edit labels or notes.

## Prompt

> You will label cases for a definition check. The attached sheet gives a set of definitions, some
> source code, and cases with ids. Label every case strictly against the definitions in the sheet,
> using only the sheet and general knowledge of Go and Python. Part 2: for each
> requirement item, "REQUIRED", "NOT_REQUIRED" or "INDETERMINATE". Judge each case on its own.
> Reply with YAML exactly in the form of the attached template: fill the reviewer block (type
> "model", your model name followed by ", new conversation", today's date as "YYYY-MM-DD", and
> the attestation as given), then a label and an optional short note for every id. Write every
> label and the date as quoted strings.
