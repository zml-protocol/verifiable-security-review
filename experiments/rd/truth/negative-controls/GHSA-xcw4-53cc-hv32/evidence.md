# Negative-control factual evidence — GHSA-xcw4-53cc-hv32

## Revision and package scope

- Distribution under adjudication: Python package `mnemosyne-memory`, whose two installed source
  package roots here are `mnemosyne/` and `hermes_memory_provider/`.
- `vuln`: `6cba87a3c2f08e127c7df4893a306737e8064859`
- `fixed`: `a0b6b8711a1a485304971710dc3571e29ff9dbeb`
- The only changed product-source file is `mnemosyne/core/sync_server.py`; the fix verifies JWT
  signatures and does not change the source excerpts below.

## Complete product-source inventory

Tracked `.py` files under the installed package roots, excluding the frozen Python non-product path
components, give byte-identical sorted inventories in both revisions: 75 files, list SHA-256
`74f547d08a0a456a6075bbd61d2ab9592802002e3aca7c993e1fb7f9f83b603d`.

```text
hermes_memory_provider/__init__.py
hermes_memory_provider/audit.py
hermes_memory_provider/cli.py
hermes_memory_provider/hermes_llm_adapter.py
hermes_memory_provider/persona_adapter.py
hermes_memory_provider/persona_tools.py
hermes_memory_provider/sync_adapter.py
mnemosyne/__init__.py
mnemosyne/cli.py
mnemosyne/core/__init__.py
mnemosyne/core/aaak.py
mnemosyne/core/annotations.py
mnemosyne/core/banks.py
mnemosyne/core/beam.py
mnemosyne/core/binary_vectors.py
mnemosyne/core/canonical.py
mnemosyne/core/chat_normalize.py
mnemosyne/core/content_sanitizer.py
mnemosyne/core/cost_log.py
mnemosyne/core/embeddings.py
mnemosyne/core/entities.py
mnemosyne/core/episodic_graph.py
mnemosyne/core/extraction.py
mnemosyne/core/importers/__init__.py
mnemosyne/core/importers/agentic.py
mnemosyne/core/importers/base.py
mnemosyne/core/importers/cognee.py
mnemosyne/core/importers/hindsight.py
mnemosyne/core/importers/holographic.py
mnemosyne/core/importers/honcho.py
mnemosyne/core/importers/letta.py
mnemosyne/core/importers/mem0.py
mnemosyne/core/importers/supermemory.py
mnemosyne/core/importers/zep.py
mnemosyne/core/llm_backends.py
mnemosyne/core/llm_conflict_detector.py
mnemosyne/core/local_llm.py
mnemosyne/core/memory.py
mnemosyne/core/mmr.py
mnemosyne/core/orchestrator.py
mnemosyne/core/patterns.py
mnemosyne/core/persona.py
mnemosyne/core/plugins.py
mnemosyne/core/polyphonic_recall.py
mnemosyne/core/query_cache.py
mnemosyne/core/query_intent.py
mnemosyne/core/recall_diagnostics.py
mnemosyne/core/shmr.py
mnemosyne/core/streaming.py
mnemosyne/core/sync.py
mnemosyne/core/sync_server.py
mnemosyne/core/synonyms.py
mnemosyne/core/temporal_parser.py
mnemosyne/core/token_counter.py
mnemosyne/core/triples.py
mnemosyne/core/typed_memory.py
mnemosyne/core/veracity_consolidation.py
mnemosyne/core/weibull.py
mnemosyne/diagnose.py
mnemosyne/dr/__init__.py
mnemosyne/dr/recovery.py
mnemosyne/extraction/__init__.py
mnemosyne/extraction/client.py
mnemosyne/extraction/diagnostics.py
mnemosyne/extraction/prompts.py
mnemosyne/install.py
mnemosyne/integrations/__init__.py
mnemosyne/integrations/auto_save_openwebui.py
mnemosyne/integrations/memory_browser.py
mnemosyne/integrations/openclaw.py
mnemosyne/integrations/openwebui_tool.py
mnemosyne/mcp_server.py
mnemosyne/mcp_tools.py
mnemosyne/migrations/__init__.py
mnemosyne/migrations/e6_triplestore_split.py
```

The inventory contains 36,232 lines in `vuln` and 36,268 in `fixed`.

## Frozen-regex scans

All scans were case-insensitive and line-numbered over exactly the 75 paths above, with matches
sorted by byte order.

### Candidate 01 — CWE-22 Path Traversal

Exact regex:

```text
path|filepath|realpath|normpath|clean\(|join\(|open\(|readfile|writefile|\.\.[\\/]
```

Both revisions have 977 matching lines. The sorted output is explicitly truncated after the first
20 lines (957 further matches omitted in each revision); these first 20 are identical:

```text
hermes_memory_provider/__init__.py:1076:        self._shared_surface_path: Optional[Path] = None
hermes_memory_provider/__init__.py:1098:        # sleep/consolidation path in the Hermes provider.  Cron skipping is
hermes_memory_provider/__init__.py:1170:            db_path = getattr(self._beam, "db_path", None)
hermes_memory_provider/__init__.py:1171:            if db_path:
hermes_memory_provider/__init__.py:1172:                self._audit = AuditLog(Path(db_path))
hermes_memory_provider/__init__.py:1173:                logger.debug("Audit log initialized: %s", db_path)
hermes_memory_provider/__init__.py:1197:        text (e.g. a filesystem path supplied via MNEMOSYNE_DATA_DIR).
hermes_memory_provider/__init__.py:1302:        shared_surface_path = kwargs.get("shared_surface_path")
hermes_memory_provider/__init__.py:1303:        if shared_surface_path is None:
hermes_memory_provider/__init__.py:1304:            shared_surface_path = self._read_config_key("shared_surface_path")
hermes_memory_provider/__init__.py:1305:        if shared_surface_path:
hermes_memory_provider/__init__.py:1306:            self._shared_surface_path = Path(str(shared_surface_path)).expanduser()
hermes_memory_provider/__init__.py:1385:            config_path = os.path.join(self._hermes_home, "config.yaml") if self._hermes_home else ""
hermes_memory_provider/__init__.py:1386:            if not config_path or not os.path.exists(config_path):
hermes_memory_provider/__init__.py:1388:            with open(config_path, "r") as f:
hermes_memory_provider/__init__.py:1428:            {"key": "shared_surface_path", "description": "SQLite path for shared surface memories. Default is <mnemosyne>/data/shared/mnemosyne.db.", "default": "data/shared/mnemosyne.db"},
hermes_memory_provider/__init__.py:1439:            config_path = os.path.join(hermes_home, "config.yaml") if hermes_home else ""
hermes_memory_provider/__init__.py:1440:            if not config_path or not os.path.exists(config_path):
hermes_memory_provider/__init__.py:1442:            with open(config_path, "r") as f:
hermes_memory_provider/__init__.py:1446:            with open(config_path, "w") as f:
```

Relevant unchanged source excerpt:

```python
def _resolve_db_path(bank: str = "default") -> str:
    data_dir = Path(
        os.environ.get("MNEMOSYNE_DATA_DIR")
        or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")) + "/mnemosyne/data"
    )
    return str(data_dir / f"{bank}.db")

def _get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA query_only = 1")
    return conn

@app.get("/api/stats")
async def api_stats(bank: str = default_bank):
    db_path = _resolve_db_path(bank)
    stats = get_memory_stats(db_path)
```

`bank` is a FastAPI query parameter. The displayed path construction performs no validation or
containment check before passing its result to `sqlite3.connect`.

### Candidate 02 — CWE-79 Cross-site Scripting

Exact regex:

```text
xss|innerhtml|outerhtml|document\.write|html/template|text/template|markupsafe|escape|safehtml|javascript:
```

Both revisions have these same 6 matching lines; there is no truncation:

```text
mnemosyne/core/beam.py:2331:    conditions = " OR ".join(f"content LIKE ? ESCAPE '\\'" for _ in cjk_chars)
mnemosyne/core/beam.py:2493:        ["_py_lower(content) LIKE ? ESCAPE '\\'"] * len(q_words)
mnemosyne/core/extraction.py:220:        # than letting it escape to the outer wrapper where it'd be
mnemosyne/core/extraction.py:344:    escape) are recorded under the synthetic `wrapper` tier with
mnemosyne/extraction/diagnostics.py:55:# `wrapper` is a synthetic tier for failures that escaped through the
mnemosyne/integrations/memory_browser.py:288:  document.getElementById('stats').innerHTML = html;
```

Relevant unchanged source excerpt:

```python
# PAGE_HTML
<input type="text" id="search" placeholder="Search memories..." value="{query}">

def _build_html(memories, query: str = "", source: str = "", tier: str = "", sort: str = ""):
    results = "".join(
        f"""<div class="memory-card">
          <span>source: {m.get('source', 'unknown')}</span>
          <div class="memory-content">{str(m.get('content', ''))[:500]}</div>
        </div>"""
        for m in memories
    )
    return PAGE_HTML.format(query=query, source_options=source_opts, results_html=results, ...)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, q: str = "", src: str = "", ...):
    memories = search_memories(db_path, query=q, source=src, ...)
    return _build_html(memories, query=q, source=src, ...)
```

`q` and `src` are FastAPI query parameters. The displayed HTML interpolations contain no HTML
escaping call. Memory `source` and `content` values are also interpolated into the response.

### Candidate 03 — CWE-89 SQL Injection

Exact regex:

```text
sql|select[[:space:]]|insert[[:space:]]|update[[:space:]]|delete[[:space:]]|query\(|exec\(|database
```

Both revisions have 1,044 matching lines. The sorted output is explicitly truncated after the first
20 lines (1,024 further matches omitted in each revision); these first 20 are identical:

```text
hermes_memory_provider/__init__.py:1059:    """Mnemosyne native memory — local SQLite with vector + FTS5 hybrid search."""
hermes_memory_provider/__init__.py:1127:        # Mnemosyne bank (separate SQLite DB). Default OFF for backward compatibility.
hermes_memory_provider/__init__.py:1191:        Truncates the exception message to 200 chars so a verbose SQLite
hermes_memory_provider/__init__.py:1427:            {"key": "profile_isolation", "description": "Enable per-profile memory isolation via Mnemosyne banks. Each Hermes profile gets its own SQLite database under mnemosyne/data/banks/<profile>/. Default false for backward compatibility.", "default": False},
hermes_memory_provider/__init__.py:1428:            {"key": "shared_surface_path", "description": "SQLite path for shared surface memories. Default is <mnemosyne>/data/shared/mnemosyne.db.", "default": "data/shared/mnemosyne.db"},
hermes_memory_provider/__init__.py:1621:            # update that adds "identity" to the recognized memory kinds
hermes_memory_provider/__init__.py:1741:        active session_id with a direct, query-independent SQL read. Strictly
hermes_memory_provider/__init__.py:1751:                "SELECT content, importance, timestamp FROM working_memory "
hermes_memory_provider/__init__.py:1935:                # Use session-scoped sleep to avoid timeout on large databases.
hermes_memory_provider/__init__.py:1937:                # so it gets its own SQLite connection via _thread_local.
hermes_memory_provider/__init__.py:2013:                return self._handle_triple_query(args)
hermes_memory_provider/__init__.py:2035:                return self._handle_graph_query(args)
hermes_memory_provider/__init__.py:2358:        or delete any memory in either bank. Original author_id is preserved.
hermes_memory_provider/__init__.py:2394:            "SELECT id, author_id, content FROM working_memory WHERE id = ?",
hermes_memory_provider/__init__.py:2410:                conn.execute("DELETE FROM working_memory WHERE id = ?", (memory_id,))
hermes_memory_provider/__init__.py:2413:                    "UPDATE working_memory SET content = ?, validator = ?, "
hermes_memory_provider/__init__.py:2421:                    "UPDATE working_memory SET valid_until = CURRENT_TIMESTAMP, "
hermes_memory_provider/__init__.py:2429:                    "UPDATE working_memory SET validator = ?, "
hermes_memory_provider/__init__.py:2438:                "INSERT INTO memory_validations "
hermes_memory_provider/__init__.py:2513:    def _handle_triple_query(self, args: Dict[str, Any]) -> str:
```

The same HTTP search surface shown above builds some SQL structure dynamically but binds the query
and source values:

```python
target_tables = []
if tier in ("", "working") and "working_memory" in tables:
    target_tables.append("working_memory")
if tier in ("", "episodic") and "episodic_memory" in tables:
    target_tables.append("episodic_memory")
if not target_tables and "memories" in tables:
    target_tables.append("memories")
for table in target_tables:
    if query:
        where_clauses.append("content LIKE ?")
        params.append(f"%{query}%")
    if source:
        where_clauses.append("source = ?")
        params.append(source)
    order = "timestamp DESC" if sort == "recent" else "importance DESC"
    sql = f"SELECT * FROM {table}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += f" ORDER BY {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor.execute(sql, params)
```

