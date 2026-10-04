# RD negative-control adjudication — GHSA-mr3j-p26x-72x4

You are one of two independent adjudicators. Work only from this message; do not use outside project
knowledge. Return only the YAML object requested at the end.

For each candidate and each canonical revision, assess this package-wide existential claim:

> In the Vikunja Go product, attacker-controlled input may lead to the candidate CWE.

Use exactly one label:

- `SUPPORTED`: the evidence establishes at least one instance of the claim in that revision.
- `NOT_SUPPORTED`: the evidence establishes that the claim is false in that revision.
- `INDETERMINATE`: neither conclusion is justified by the evidence.

Judge all six cells independently. A text search match does not by itself establish a CWE. No search
match is sufficient for `NOT_SUPPORTED` only when the complete inventory and package surface make
the missing primitive dispositive; otherwise use `INDETERMINATE`. Do not infer a label from the
candidate order or from the fact that this is a negative-control task.

Candidates, in frozen order:

1. `candidate-01`: CWE-918 Server-Side Request Forgery
2. `candidate-02`: CWE-502 Deserialization of Untrusted Data
3. `candidate-03`: CWE-601 Open Redirect

---

# Factual evidence

## Revision and complete inventory

- `vuln`: `2da89258e53068253dcf8ef17d4dad141dba7d31`
- `fixed`: `bc6d843ed4df82a6c89f10aa676a7a33d27bf2fd`
- Product source is tracked `.go` excluding `_test.go`, `vendor/`, and `testdata/`.
- Both revisions have the same complete sorted inventory: 394 files, list SHA-256
  `7885bc39362ad27a1f11bc0aa53bc963e4fb632f28239d7f894c68a8ffa924db`.
- Product-source line counts are 75,005 (`vuln`) and 75,006 (`fixed`).

```text
examples/plugins/example/main.go
frontend/embed.go
magefile.go
main.go
pkg/caldav/caldav.go
pkg/caldav/parsing.go
pkg/caldav/priority.go
pkg/cmd/cmd.go
pkg/cmd/doctor.go
pkg/cmd/dump.go
pkg/cmd/healthcheck.go
pkg/cmd/migrate.go
pkg/cmd/repair.go
pkg/cmd/repair_file_mime_types.go
pkg/cmd/repair_orphan_positions.go
pkg/cmd/repair_projects.go
pkg/cmd/repair_task_positions.go
pkg/cmd/restore.go
pkg/cmd/testmail.go
pkg/cmd/user.go
pkg/cmd/version.go
pkg/cmd/web.go
pkg/config/config.go
pkg/cron/cron.go
pkg/db/db.go
pkg/db/dump.go
pkg/db/helpers.go
pkg/db/test.go
pkg/db/test_fixtures.go
pkg/doctor/config.go
pkg/doctor/database.go
pkg/doctor/doctor.go
pkg/doctor/files.go
pkg/doctor/files_unix.go
pkg/doctor/files_windows.go
pkg/doctor/output.go
pkg/doctor/services.go
pkg/doctor/system.go
pkg/doctor/system_unix.go
pkg/doctor/system_windows.go
pkg/doctor/types.go
pkg/doctor/userns_linux.go
pkg/doctor/userns_other.go
pkg/e2etests/integrations.go
pkg/events/events.go
pkg/events/listeners.go
pkg/events/testing.go
pkg/files/db.go
pkg/files/diagnostics_unix.go
pkg/files/diagnostics_windows.go
pkg/files/dump.go
pkg/files/error.go
pkg/files/filehandling.go
pkg/files/files.go
pkg/files/repair.go
pkg/files/storage.go
pkg/files/storage_local.go
pkg/files/storage_mem.go
pkg/files/storage_s3.go
pkg/health/health.go
pkg/i18n/i18n.go
pkg/initialize/events.go
pkg/initialize/init.go
pkg/log/echo_logger.go
pkg/log/logging.go
pkg/log/mail_logger.go
pkg/log/noop.go
pkg/log/watermill_logger.go
pkg/log/xorm_logger.go
pkg/mail/mail.go
pkg/mail/send_mail.go
pkg/mail/testing.go
pkg/metrics/active_users.go
pkg/metrics/metrics.go
pkg/migration/20190324205606.go
pkg/migration/20190328074430.go
pkg/migration/20190430111111.go
pkg/migration/20190511202210.go
pkg/migration/20190514192749.go
pkg/migration/20190524205441.go
pkg/migration/20190718200716.go
pkg/migration/20190818210133.go
pkg/migration/20190920185205.go
pkg/migration/20190922205826.go
pkg/migration/20191008194238.go
pkg/migration/20191010131430.go
pkg/migration/20191207204427.go
pkg/migration/20191207220736.go
pkg/migration/20200120201756.go
pkg/migration/20200219183248.go
pkg/migration/20200308205855.go
pkg/migration/20200308210130.go
pkg/migration/20200322214440.go
pkg/migration/20200322214624.go
pkg/migration/20200417175201.go
pkg/migration/20200418230432.go
pkg/migration/20200418230605.go
pkg/migration/20200420215928.go
pkg/migration/20200425182634.go
pkg/migration/20200509103709.go
pkg/migration/20200515172220.go
pkg/migration/20200515195546.go
pkg/migration/20200516123847.go
pkg/migration/20200524221534.go
pkg/migration/20200524224611.go
pkg/migration/20200614113230.go
pkg/migration/20200621214452.go
pkg/migration/20200801183357.go
pkg/migration/20200904101559.go
pkg/migration/20200905151040.go
pkg/migration/20200905232458.go
pkg/migration/20200906184746.go
pkg/migration/20201025195822.go
pkg/migration/20201121181647.go
pkg/migration/20201218152741.go
pkg/migration/20201218220204.go
pkg/migration/20201219145028.go
pkg/migration/20210207192805.go
pkg/migration/20210209204715.go
pkg/migration/20210220222121.go
pkg/migration/20210221111953.go
pkg/migration/20210321185225.go
pkg/migration/20210328191017.go
pkg/migration/20210403145503.go
pkg/migration/20210403220653.go
pkg/migration/20210407170753.go
pkg/migration/20210411113105.go
pkg/migration/20210411161337.go
pkg/migration/20210413131057.go
pkg/migration/20210527105701.go
pkg/migration/20210603174608.go
pkg/migration/20210709191101.go
pkg/migration/20210709211508.go
pkg/migration/20210711173657.go
pkg/migration/20210713213622.go
pkg/migration/20210725153703.go
pkg/migration/20210727204942.go
pkg/migration/20210727211037.go
pkg/migration/20210729142940.go
pkg/migration/20210802081716.go
pkg/migration/20210829194722.go
pkg/migration/20211212151642.go
pkg/migration/20211212210054.go
pkg/migration/20220112211537.go
pkg/migration/20220616145228.go
pkg/migration/20220815200851.go
pkg/migration/20221002120521.go
pkg/migration/20221113170740.go
pkg/migration/20221228112131.go
pkg/migration/20230104152903.go
pkg/migration/20230307171848.go
pkg/migration/20230611170341.go
pkg/migration/20230824132533.go
pkg/migration/20230828125443.go
pkg/migration/20230831155832.go
pkg/migration/20230903143017.go
pkg/migration/20230913202615.go
pkg/migration/20231022144641.go
pkg/migration/20231108231513.go
pkg/migration/20231121191822.go
pkg/migration/20240114224713.go
pkg/migration/20240304153738.go
pkg/migration/20240309111148.go
pkg/migration/20240311173251.go
pkg/migration/20240313230538.go
pkg/migration/20240314214802.go
pkg/migration/20240315093418.go
pkg/migration/20240315104205.go
pkg/migration/20240315110428.go
pkg/migration/20240329170952.go
pkg/migration/20240406125227.go
pkg/migration/20240603172746.go
pkg/migration/20240919130957.go
pkg/migration/20241028131622.go
pkg/migration/20241118123644.go
pkg/migration/20241119115012.go
pkg/migration/20250317174522.go
pkg/migration/20250323212553.go
pkg/migration/20250402173109.go
pkg/migration/20250624092830.go
pkg/migration/20250813093602.go
pkg/migration/20251001113831.go
pkg/migration/20251108154913.go
pkg/migration/20251118125156.go
pkg/migration/20260123000717.go
pkg/migration/20260224113347.go
pkg/migration/20260224122023.go
pkg/migration/20260224215050.go
pkg/migration/20260225114726.go
pkg/migration/migration.go
pkg/models/api_routes.go
pkg/models/api_tokens.go
pkg/models/api_tokens_permissions.go
pkg/models/bulk_task.go
pkg/models/error.go
pkg/models/events.go
pkg/models/export.go
pkg/models/favorites.go
pkg/models/kanban.go
pkg/models/kanban_permissions.go
pkg/models/kanban_task_bucket.go
pkg/models/label.go
pkg/models/label_permissions.go
pkg/models/label_task.go
pkg/models/label_task_permissions.go
pkg/models/link_sharing.go
pkg/models/link_sharing_permissions.go
pkg/models/listeners.go
pkg/models/mentions.go
pkg/models/message.go
pkg/models/models.go
pkg/models/notifications.go
pkg/models/notifications_database.go
pkg/models/permissions.go
pkg/models/project.go
pkg/models/project_duplicate.go
pkg/models/project_permissions.go
pkg/models/project_repair.go
pkg/models/project_team.go
pkg/models/project_team_permissions.go
pkg/models/project_users.go
pkg/models/project_users_permissions.go
pkg/models/project_view.go
pkg/models/project_view_permissions.go
pkg/models/reaction.go
pkg/models/reaction_permissions.go
pkg/models/saved_filters.go
pkg/models/saved_filters_permissions.go
pkg/models/sessions.go
pkg/models/sessions_permissions.go
pkg/models/setup_tests.go
pkg/models/subscription.go
pkg/models/subscription_permissions.go
pkg/models/task_assignees.go
pkg/models/task_assignees_permissions.go
pkg/models/task_attachment.go
pkg/models/task_attachment_permissions.go
pkg/models/task_collection.go
pkg/models/task_collection_filter.go
pkg/models/task_collection_sort.go
pkg/models/task_comment_permissions.go
pkg/models/task_comments.go
pkg/models/task_duplicate.go
pkg/models/task_overdue_reminder.go
pkg/models/task_position.go
pkg/models/task_relation.go
pkg/models/task_relation_permissions.go
pkg/models/task_reminder.go
pkg/models/task_search.go
pkg/models/task_unread_statuses.go
pkg/models/tasks.go
pkg/models/tasks_permissions.go
pkg/models/team_members.go
pkg/models/team_members_permissions.go
pkg/models/team_sync.go
pkg/models/teams.go
pkg/models/teams_permissions.go
pkg/models/unsplash.go
pkg/models/user_delete.go
pkg/models/user_project.go
pkg/models/users.go
pkg/models/webhooks.go
pkg/models/webhooks_permissions.go
pkg/modules/auth/auth.go
pkg/modules/auth/ldap/ldap.go
pkg/modules/auth/openid/cron.go
pkg/modules/auth/openid/openid.go
pkg/modules/auth/openid/providers.go
pkg/modules/avatar/avatar.go
pkg/modules/avatar/empty/empty.go
pkg/modules/avatar/gravatar/gravatar.go
pkg/modules/avatar/initials/initials.go
pkg/modules/avatar/ldap/ldap.go
pkg/modules/avatar/marble/marble.go
pkg/modules/avatar/openid/openid.go
pkg/modules/avatar/upload/upload.go
pkg/modules/background/background.go
pkg/modules/background/handler/background.go
pkg/modules/background/handler/errors.go
pkg/modules/background/unsplash/proxy.go
pkg/modules/background/unsplash/unsplash.go
pkg/modules/background/upload/upload.go
pkg/modules/dump/dump.go
pkg/modules/dump/restore.go
pkg/modules/keyvalue/error/error.go
pkg/modules/keyvalue/keyvalue.go
pkg/modules/keyvalue/memory/memory.go
pkg/modules/keyvalue/redis/redis.go
pkg/modules/migration/create_from_structure.go
pkg/modules/migration/db.go
pkg/modules/migration/errors.go
pkg/modules/migration/handler/common.go
pkg/modules/migration/handler/events.go
pkg/modules/migration/handler/handler.go
pkg/modules/migration/handler/handler_file.go
pkg/modules/migration/handler/listeners.go
pkg/modules/migration/handler/notifications.go
pkg/modules/migration/helpers.go
pkg/modules/migration/microsoft-todo/microsoft_todo.go
pkg/modules/migration/migration_status.go
pkg/modules/migration/migrator.go
pkg/modules/migration/ticktick/ticktick.go
pkg/modules/migration/todoist/todoist.go
pkg/modules/migration/trello/trello.go
pkg/modules/migration/vikunja-file/vikunja.go
pkg/notifications/database.go
pkg/notifications/db.go
pkg/notifications/mail.go
pkg/notifications/mail_render.go
pkg/notifications/notification.go
pkg/notifications/testing.go
pkg/plugins/interfaces.go
pkg/plugins/manager.go
pkg/plugins/registry.go
pkg/red/redis.go
pkg/routes/api/v1/avatar.go
pkg/routes/api/v1/docs.go
pkg/routes/api/v1/info.go
pkg/routes/api/v1/link_sharing_auth.go
pkg/routes/api/v1/login.go
pkg/routes/api/v1/notifications.go
pkg/routes/api/v1/task_attachment.go
pkg/routes/api/v1/testing.go
pkg/routes/api/v1/token_check.go
pkg/routes/api/v1/user_caldav_token.go
pkg/routes/api/v1/user_confirm_email.go
pkg/routes/api/v1/user_deletion.go
pkg/routes/api/v1/user_export.go
pkg/routes/api/v1/user_list.go
pkg/routes/api/v1/user_password_reset.go
pkg/routes/api/v1/user_register.go
pkg/routes/api/v1/user_settings.go
pkg/routes/api/v1/user_show.go
pkg/routes/api/v1/user_totp.go
pkg/routes/api/v1/user_update_email.go
pkg/routes/api/v1/user_update_password.go
pkg/routes/api/v1/user_webhooks.go
pkg/routes/api/v1/webhooks.go
pkg/routes/api_tokens.go
pkg/routes/caldav/auth.go
pkg/routes/caldav/handler.go
pkg/routes/caldav/listStorageProvider.go
pkg/routes/error_handler.go
pkg/routes/healthcheck.go
pkg/routes/metrics.go
pkg/routes/rate_limit.go
pkg/routes/routes.go
pkg/routes/sentry_middleware.go
pkg/routes/static.go
pkg/routes/validation.go
pkg/swagger/docs.go
pkg/user/caldav_token.go
pkg/user/db.go
pkg/user/delete.go
pkg/user/error.go
pkg/user/events.go
pkg/user/listeners.go
pkg/user/notifications.go
pkg/user/test.go
pkg/user/token.go
pkg/user/totp.go
pkg/user/update_email.go
pkg/user/user.go
pkg/user/user_create.go
pkg/user/user_email_confirm.go
pkg/user/user_password_reset.go
pkg/user/users_project.go
pkg/user/validator.go
pkg/utils/avatar.go
pkg/utils/duration.go
pkg/utils/humanize_duration.go
pkg/utils/md5_string.go
pkg/utils/normalize_hex.go
pkg/utils/random.go
pkg/utils/retry.go
pkg/utils/sha256.go
pkg/utils/slice_difference.go
pkg/utils/strings.go
pkg/utils/time.go
pkg/utils/umask_unix.go
pkg/utils/umask_windows.go
pkg/utils/userns_linux.go
pkg/utils/userns_other.go
pkg/utils/write_to_zip.go
pkg/utils/zip.go
pkg/version/version.go
pkg/web/handler/create.go
pkg/web/handler/delete.go
pkg/web/handler/helper.go
pkg/web/handler/read_all.go
pkg/web/handler/read_one.go
pkg/web/handler/update.go
pkg/web/web.go
pkg/webtests/integrations.go
```

## Candidate 01 — CWE-918 Server-Side Request Forgery

Exact case-insensitive regex:

```text
ssrf|requests\.(get|post|request)|urlopen|http\.(get|post)|client\.do\(|fetch\(
```

Both revisions have 14 matching lines. All product-code matches outside generated embedded API docs
are listed here; three generated-doc matches contain minified lines hundreds of kilobytes long and
are explicitly omitted after identifying their paths/lines (`pkg/routes/api/v1/docs.go:74,105` and
`pkg/swagger/docs.go:33`).

```text
magefile.go:372: resp, err := client.Do(req)
pkg/doctor/services.go:315: resp, err := client.Do(req)
pkg/models/webhooks.go:302: // SSRF protection: block connections to non-globally-routable IPs unless
pkg/models/webhooks.go:303: // explicitly allowed. Uses daenney/ssrf which validates resolved IPs
pkg/models/webhooks.go:307: guardian := ssrf.New(ssrf.WithAnyPort())
pkg/models/webhooks.go:358: res, err := client.Do(req)
pkg/models/webhooks.go:43: "code.dny.dev/ssrf"
pkg/routes/api/v1/docs.go:1447: background-color: ${e=>e.theme.colors.http.get};
pkg/routes/api/v1/docs.go:1451: background-color: ${e=>e.theme.colors.http.post};
pkg/routes/routes.go:147: e.Logger = log.NewEchoLogger(...)
pkg/routes/routes.go:150: if config.LogEnabled.GetBool() && config.LogHTTP.GetString() != "off" {
pkg/routes/routes.go:151: httpLogger := log.NewHTTPLogger(...)
```

The webhook URL is supplied through the authenticated webhook object. Both revisions contain this
unchanged request and transport logic:

```go
if !strings.HasPrefix(w.TargetURL, "http") {
    return InvalidFieldError([]string{"target_url"})
}

if !config.WebhooksAllowNonRoutableIPs.GetBool() {
    guardian := ssrf.New(ssrf.WithAnyPort())
    transport.DialContext = (&net.Dialer{Control: guardian.Safe}).DialContext
}

req, err := http.NewRequestWithContext(context.Background(), http.MethodPost,
    w.TargetURL, bytes.NewReader(payload))
client := getWebhookHTTPClient()
res, err := client.Do(req)
```

The source comment says the guardian validates resolved IPs against IANA special-purpose registries
after DNS resolution to prevent DNS rebinding. An operator configuration can explicitly allow
non-routable webhook targets. The evidence does not include an execution showing a protected target
being reached or proving no other SSRF flow exists.

## Candidate 02 — CWE-502 Deserialization of Untrusted Data

Exact case-insensitive regex:

```text
pickle|marshal|shelve|yaml\.(load|unsafe_load)|gob\.newdecoder|deserialize|objectinputstream
```

Both revisions have 74 matching lines. The sorted output is explicitly truncated after 20 lines
(54 further matches omitted in each revision):

```text
magefile.go:1384: err = json.Unmarshal(msg.Payload, event)
magefile.go:1617: err = json.Unmarshal(jsonData, &root)
magefile.go:718: if err := json.Unmarshal(data, &translationsMap); err != nil {
pkg/config/config.go:683: err := maxSize.UnmarshalText([]byte(size))
pkg/db/dump.go:50: data[name], err = json.Marshal(entries)
pkg/db/test.go:101: pretty, err := json.MarshalIndent(all, "", "    ")
pkg/db/test.go:115: pretty, err := json.MarshalIndent(all, "", "    ")
pkg/events/events.go:213: content, err := json.Marshal(event)
pkg/events/testing.go:65: content, err := json.Marshal(event)
pkg/i18n/i18n.go:119: if err := json.Unmarshal(data, &nestedData); err != nil {
pkg/migration/20220815200851.go:47: err = json.Unmarshal([]byte(filterJSON), &filter)
pkg/migration/20220815200851.go:85: filtersJSON, err := json.Marshal(filter)
pkg/migration/20251001113831.go:101: if err := json.Unmarshal(configuration.Filter, &filterString); err != nil {
pkg/migration/20251001113831.go:111: if err := json.Unmarshal(configuration.Filter, &existingFilter); err != nil {
pkg/migration/20260224122023.go:103: if err := json.Unmarshal(trimmed, &existingFilter); err != nil {
pkg/migration/20260224122023.go:92: if err := json.Unmarshal(trimmed, &filterString); err != nil {
pkg/models/error.go:114: // MarshalJSON implements json.Marshaler ...
pkg/models/error.go:116: // losing structured data. By implementing json.Marshaler ...
pkg/models/error.go:117: func (err ValidationHTTPError) MarshalJSON() ([]byte, error) {
pkg/models/error.go:118: return json.Marshal(struct {
```

Across the complete 74-line result, the only match for an object/binary decoder named by the frozen
regex is `gob.NewDecoder`; the other matches are JSON/CSV/text marshal/unmarshal operations or
comments. The unchanged Redis code pairs that decoder with its own encoder and decodes into a value
whose concrete destination type is supplied by the caller:

```go
func (s *Storage) Put(key string, value interface{}) (err error) {
    var v interface{}
    switch value.(type) {
    case int:
        v = value
    case int8:
        v = value
    case int16:
        v = value
    case int32:
        v = value
    case int64:
        v = value
    default:
        var buf bytes.Buffer
        enc := gob.NewEncoder(&buf)
        err = enc.Encode(value)
        if err != nil { return err }
        return s.client.Set(context.Background(), key, buf.Bytes(), 0).Err()
    }
    return s.client.Set(context.Background(), key, v, 0).Err()
}

func (s *Storage) GetWithValue(key string, value interface{}) (exists bool, err error) {
    b, err := s.client.Get(context.Background(), key).Bytes()
    if err != nil { ... }
    var buf bytes.Buffer
    _, err = buf.Write(b)
    if err != nil { return }
    dec := gob.NewDecoder(&buf)
    err = dec.Decode(value)
    return true, err
}
```

Call sites use fixed application cache keys and concrete destinations such as an avatar byte slice,
active-user maps, or OpenID provider structures. The evidence contains no path by which a request
supplies serialized bytes directly to Redis or this decoder.

## Candidate 03 — CWE-601 Open Redirect

Exact case-insensitive regex:

```text
redirect|location[[:space:]]*:|http\.redirect|redirectresponse
```

Both revisions have 24 matching lines. The only three minified generated-doc lines are explicitly
truncated; the remaining complete match set consists of configuration keys/defaults, OAuth/migration
`redirect_uri` values, descriptions, and CSS/API-documentation strings. No match is an HTTP redirect
response call (`http.Redirect`, Echo `Redirect`, or `RedirectResponse`). Representative complete
matches are:

```text
pkg/config/config.go:176: MigrationTodoistRedirectURL Key = `migration.todoist.redirecturl`
pkg/config/config.go:179: MigrationTrelloRedirectURL Key = `migration.trello.redirecturl`
pkg/config/config.go:183: MigrationMicrosoftTodoRedirectURL Key = `migration.microsofttodo.redirecturl`
pkg/config/config.go:645: if MigrationTodoistRedirectURL.GetString() == "" {
pkg/config/config.go:646: MigrationTodoistRedirectURL.Set(ServicePublicURL.GetString() + "migrate/todoist")
pkg/config/config.go:649: if MigrationTrelloRedirectURL.GetString() == "" {
pkg/config/config.go:650: MigrationTrelloRedirectURL.Set(ServicePublicURL.GetString() + "migrate/trello")
pkg/config/config.go:653: if MigrationMicrosoftTodoRedirectURL.GetString() == "" {
pkg/config/config.go:654: MigrationMicrosoftTodoRedirectURL.Set(ServicePublicURL.GetString() + "migrate/microsoft-todo")
pkg/modules/auth/openid/openid.go:118: // HandleCallback handles the auth request callback after redirecting from the provider with an auth code
pkg/modules/auth/openid/openid.go:120: // @Description After a redirect from the OpenID Connect provider to the frontend ...
pkg/modules/auth/openid/openid.go:441: provider.Oauth2Config.RedirectURL = cb.RedirectURL
pkg/modules/auth/openid/openid.go:45: // Callback contains the callback after an auth request was made and redirected
pkg/modules/auth/openid/openid.go:49: RedirectURL string `json:"redirect_url"`
pkg/modules/migration/microsoft-todo/microsoft_todo.go:138: "&redirect_uri=" + config.MigrationMicrosoftTodoRedirectURL.GetString() +
pkg/modules/migration/microsoft-todo/microsoft_todo.go:163: "redirect_uri": []string{config.MigrationMicrosoftTodoRedirectURL.GetString()},
pkg/modules/migration/todoist/todoist.go:496: "redirect_uri": []string{config.MigrationTodoistRedirectURL.GetString()},
pkg/modules/migration/trello/trello.go:107: "&return_url=" + config.MigrationTrelloRedirectURL.GetString()
pkg/routes/api/v1/docs.go:507: &.tab-redirect {
pkg/routes/api/v1/docs.go:508: color: ${e=>e.theme.colors.responses.redirect.tabTextColor};
pkg/swagger/docs.go:33: "description": "After a redirect from the OpenID Connect provider ..."
pkg/swagger/docs.go:9632: "redirect_url": {
```

In the OpenID callback, the request-bound `RedirectURL` is assigned to the OAuth client config and
used as the `redirect_uri` during token exchange; the displayed code does not emit an HTTP redirect:

```go
type Callback struct {
    Code string `query:"code" json:"code"`
    Scope string `query:"scope" json:"scope"`
    RedirectURL string `json:"redirect_url"`
}
...
provider.Oauth2Config.RedirectURL = cb.RedirectURL
oauth2Token, err := provider.Oauth2Config.Exchange(context.Background(), cb.Code)
```

---

Return exactly this schema with all labels replaced, and no Markdown fence or prose:

labels:
  candidate-01: {vuln: LABEL, fixed: LABEL}
  candidate-02: {vuln: LABEL, fixed: LABEL}
  candidate-03: {vuln: LABEL, fixed: LABEL}
