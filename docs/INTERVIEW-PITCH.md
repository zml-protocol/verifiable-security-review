# Interview Pitch

## 30 seconds

I came at this from penetration testing. I wanted to know whether an AI security reviewer could
produce evidence I would actually trust, not just a plausible vulnerability verdict. I built a
Python/Go and CodeQL workflow that reproduces real fixes, makes an isolated agent discover the exact
entry and security behavior, verifies typed evidence hops, and scores attribution separately. On
fresh fixes, the model got 3/5 attributions right but 0/5 complete verified chains. What I built is
really a system for knowing when security automation should not be trusted.

## 2 minutes

My background is penetration testing, and the project started with a practical review question:
when someone says a commit fixes a vulnerability, what evidence would make me comfortable signing
off on it?

I built a reproducible framework around that question. First, it selects real Go and Python fixes
and establishes executable truth with a fixed `TEST → POC → PROBE` workflow: use the fix's regression
test when possible, otherwise an advisory-linked PoC, otherwise a small time-boxed local probe. The
same trigger has to demonstrate the security effect on the parent and its absence on the fix.

Then I separate three jobs that ordinary benchmarks often collapse. The agent must discover the
claim-specific input entry and the exact statement that permits or blocks the effect. It must build
a path from typed evidence hops. CodeQL-backed providers verify each proposed hop, and only verified
edges can form a chain. Finally, attribution is scored separately. The evaluated agent never sees
the advisory answer, vulnerable/fixed labels, golden requirements, or reference path; the scorer
and providers are frozen before measured runs.

The main fresh result was revealing: on five real fixes, entry discovery was 3/5, behavior discovery
was 2/5, a fully verified chain was 0/5, but final fix attribution was still correct on 3/5. So the
model could often arrive at the right security conclusion without producing an artifact another
reviewer should trust. Earlier architecture work showed 18/30 full local chains when the evidence
contract was already known, which helped isolate requirement discovery as the harder problem.

The project also failed closed in practice. It preserved a context-leak rerun, a malformed-regex
harness defect, an ambiguous truth label, and an RD v3 contract mismatch that stopped all work
before a model call or dollar was spent. I did not repair or rescore those failures after seeing
them.

What I am demonstrating is not that I can call an LLM. It is that I can reproduce vulnerabilities,
review code, build static verification and automation, design false-positive controls, and decide
where automated evidence is strong enough—or not strong enough—for an AppSec workflow.

## 5 minutes

### The security problem

In penetration testing and AppSec, “this patch fixes the bug” is often supported by a diff and a
plausible explanation. That is not the same as evidence. I wanted to model the review I would do
manually: reproduce the behavior, identify attacker control, locate the decision that changes the
effect, trace the path, and make every claim reviewable by someone else.

### The system

I built four layers.

First is **vulnerability validation**. Candidate fixes come from a frozen snapshot and deterministic
selection process. I use the same trigger on parent and fix revisions. The route is fixed in advance:
a regression test from the patch, an advisory-linked PoC, or a minimal local probe with a strict
review boundary. This produced concrete Go and Python examples including local-file disclosure,
SSRF, broken authorization, denial of service, and signature-validation fixes.

Second is **requirement truth**. A security claim is reduced to the first claim-specific entry, the
exact behavior statement that permits or blocks the effect, and any necessary guard, config, or
dispatch qualifier. Author labels are independently adjudicated. Ambiguous or unexpressible truth
is rejected instead of forced into the sample.

Third is **evidence verification**. The agent proposes typed hops such as def-use, argument binding,
field flow, object composition, registry dispatch, or guard properties. Python orchestration and
CodeQL-backed providers check each hop. Runtime-minted anchors prevent the model from inventing line
references or citing code from the wrong revision. `UNVERIFIED`, `CONTRADICTED`, and `unsupported`
remain different states; only `VERIFIED` edges build the chain.

Fourth is **measurement integrity**. Construction and evaluation are separate roles. Measured
sessions use neutral revision names, empty temporary directories, empty memory, allowlisted tools,
budget/time caps, frozen scorers, and hash-bound artifacts. Scores are committed before transcript
review.

### What the results showed

The early provider work showed that local verification was feasible. In a 30-session chain
replication, 18 produced complete verified local chains: Authlib 10/10, Caddy 3/10, and File Browser
5/10. The gaps were meaningful—usually an omitted 2xx guard or choosing a later transformed value as
the entry.

The fresh RD v2 measurement asked the harder question: can the agent discover the evidence contract
on unseen fixes? Across five real tasks, entry was 3/5, behavior 2/5, full verified chain 0/5, and
fix attribution 3/5. The negative control was not falsely supported in either revision, although it
was only one control. Three correct attributions came with wrong or incomplete evidence artifacts.
That is the security lesson: a correct answer can still be unsafe to rely on.

### How failures were handled

I kept failures as evidence. An early run leaked condition context through the working directory,
so it was preserved but disqualified and rerun under a new frozen protocol. A malformed regex was
wrongly classified as a repository error; the result stayed frozen and the next harness version
fixed the classification. One provider truth boundary had two defensible interpretations, so the
blind label and downstream dependency were disclosed rather than rescored.

Finally, RD v3 stopped before any model execution. An independent curator reasonably used a Go send
statement as a complete statement, but the frozen validator accepted only a narrower node set that
the public contract had not exposed. The gate returned `CALIBRATION_INVALID`: zero model calls, zero
spend, no repaired case, and no replacement sample. That is exactly what I want from security
automation—a refusal to manufacture confidence when its own contract is inconsistent.

### Why this matters for the role

For an AppSec role, this shows secure code review, fix validation, evidence tracing, and static
analysis. For offensive security, it shows PoC interpretation, minimal reproductions, differential
testing, and disciplined exploitability reasoning. For a general Security Engineer role, it shows
Python automation, Go and CodeQL analysis, isolation, provenance, CI-style gates, and honest failure
handling.

The LLM is a useful investigator, but it is not the trust boundary. The real contribution is the
engineering around it: knowing what must be proven, checking what can be checked, exposing blind
spots, and escalating incomplete evidence to a human reviewer.
