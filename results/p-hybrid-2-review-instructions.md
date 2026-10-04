# P-Hybrid-2 blind review: instructions (PREREGISTRATION.md §11.6)

Give a reviewer ONLY `p-hybrid-2-review-sheet.md` and this file. Nothing else from the project.

## Who may review

- **Primary**: a person who has not taken part in this project and has not seen its golden
  answers, verifiers or protocol, nor any experiment arm, phase or verdict.
- **Secondary**: a brand-new ChatGPT conversation (no earlier history), given the sheet and
  the prompt below.
- If no such person can be found, the new-conversation model review becomes the primary and
  is reported as model-blind adjudication (weaker evidence), never as human review.

## Task

Each item states one link between two places in the code of one revision, typed with a
relation whose definition is given. Decide, from the code shown (and general knowledge of
the language), whether the link holds under that definition:

- `TRUE`: it holds.
- `FALSE`: it does not hold (for example the value does not reach that field, the object is
  not the one stored there, the call cannot run that method).
- `INDETERMINATE`: the code shown does not settle it.

Judge each item on its own. A short note is welcome but optional.

## Output (YAML, all fields required)

```yaml
reviewer:
  type: human            # or: model
  name: <name, or e.g. "ChatGPT, new conversation, <model name>">
  date: 2026-..-..
  attestation:
    independent: true    # not involved in this project; never saw its answers or protocol
    saw_arms: false
    saw_verdicts: false
labels:
  R001: {label: TRUE, note: ""}
  R002: {label: FALSE, note: "..."}
  # ... one entry for every item R001..R035
```

## Prompt for the secondary (new ChatGPT conversation)

> You will review 35 items from a code-reading exercise. Each item states one link between
> two places in the code of one revision of an open-source repository, typed with a relation
> whose definition is given in the item. For each item, decide from the code shown whether
> the link holds under that definition: TRUE, FALSE, or INDETERMINATE (the code shown does
> not settle it). Judge each item independently. Reply with YAML exactly in this form, one
> entry per item: `reviewer: {type: model, name: "<your model name>, new conversation",
> date: <today>, attestation: {independent: true, saw_arms: false, saw_verdicts: false}}`
> followed by `labels:` with `R001: {label: ..., note: "..."}` and so on. The items follow.

(then paste the whole of `p-hybrid-2-review-sheet.md`)
