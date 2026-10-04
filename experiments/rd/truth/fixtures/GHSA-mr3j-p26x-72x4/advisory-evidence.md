# Advisory factual evidence — GHSA-mr3j-p26x-72x4

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GHSA-mr3j-p26x-72x4  (aliases: CVE-2026-33313, GO-2026-4797)
- Affected package: Go: code.vikunja.io/api
- Severity: CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N
- Published: 2026-03-20T17:25:30Z
- Summary: Vikunja has an IDOR in Task Comments Allows Reading Arbitrary Comments
- Source: https://github.com/go-vikunja/vikunja/security/advisories/GHSA-mr3j-p26x-72x4

## Details (verbatim, fix-attribution lines removed)

An authenticated user can read any task comment by ID, regardless of whether they have access to the task the comment belongs to, by substituting the task ID in the API URL with a task they do have access to.

## Details

The `GET /api/v1/tasks/{taskID}/comments/{commentID}` endpoint performs an authorization check against the task ID provided in the URL path, then loads the comment by its own ID without verifying it belongs to that task.

### Root Cause

In `pkg/models/task_comment_permissions.go`, `CanRead` constructs a `Task` using the `TaskID` from the URL and checks `Task.CanRead`:

```go
func (tc *TaskComment) CanRead(s *xorm.Session, a web.Auth) (bool, int, error) {
    t := Task{ID: tc.TaskID}
    return t.CanRead(s, a)
}
```

In `pkg/models/task_comments.go`, `getTaskCommentSimple` loads the comment by ID only, with `NoAutoCondition()` explicitly disabling XORM's implicit struct-field filtering:

```go
func getTaskCommentSimple(s *xorm.Session, tc *TaskComment) error {
    exists, err := s.
        Where("id = ?", tc.ID).
        NoAutoCondition().
        Get(tc)
    // ...
}
```

The generic web handler (`pkg/web/handler/read_one.go`) calls `CanRead` before `ReadOne`, so the permission check passes against the attacker-controlled task ID, and then `ReadOne` returns the comment from a completely different task.

### Attack Scenario

1. Attacker is authenticated and has read access to any task (task ID `A`) — e.g. their own task.
2. Attacker guesses or enumerates a comment ID (`C`) belonging to a task in another user's private project.
3. Attacker requests: `GET /api/v1/tasks/A/comments/C`
4. Authorization passes because the attacker can read task `A`.
5. The comment `C` is loaded by ID only and returned, leaking its contents and author.

## Credit

This vulnerability was found using [GitHub Security Lab Taskflows](https://github.com/GitHubSecurityLab/seclab-taskflows).

## References (fix-commit excluded)
- WEB: https://github.com/go-vikunja/vikunja/security/advisories/GHSA-mr3j-p26x-72x4
- ADVISORY: https://nvd.nist.gov/vuln/detail/CVE-2026-33313
- PACKAGE: https://github.com/go-vikunja/vikunja
- WEB: https://vikunja.io/changelog/vikunja-v2.2.0-was-released

## Redaction note
- 0 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.
