# Execution evidence (observed facts) — GHSA-mr3j-p26x-72x4

Observed behaviour of the two revisions under one identical input. Facts only; no conclusion is
drawn about which program point is the entry or the behaviour.

- Input (one model call / request): `TaskComment.ReadOne` with `TaskID = 1`, `ID = 2`, where comment
  `2`'s real owning task is `2` (i.e. `GET /tasks/1/comments/2` for a comment that belongs to task 2).

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| `ReadOne(TaskID=1, ID=2)` | returns the comment owned by task 2, `err == nil` | returns `ErrTaskCommentDoesNotExist{ID: 2, TaskID: 1}`; no comment |

Same input, the comment is returned on the vuln revision and not on the fixed revision.
