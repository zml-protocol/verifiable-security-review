"""List FastAPI route handlers and whether they carry an authentication dependency.

    uv run python experiments/fieldwork/scan_fastapi_auth.py <backend-root>

Static AST walk over a FastAPI backend: for every function decorated with
`@<router>.<method>(...)` it records the HTTP method, path, source location, and the auth
signals it can see (parameter annotated with an auth alias, `Depends(auth_fn)`, or a
`dependencies=[...]` decorator kwarg). Router-level `APIRouter(dependencies=...)` is recorded
too, but the caller must still check `include_router` sites for their own kwargs.

Signals are intentionally conservative: "no signal" means "a human should look", not "public".
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

AUTH_ALIASES = {
    "CurrentActiveUser", "CurrentActiveMCPUser",
    # project-specific aliases/dependencies that already carry auth + ownership
    "AuthorizedReadFlow", "AuthorizedWriteFlow", "AuthorizedReadFolder",
}
AUTH_FNS = {
    "get_current_active_user", "get_current_user", "get_current_active_superuser",
    "get_current_active_user_mcp", "get_current_user_mcp", "api_key_security",
    "ws_api_key_security", "get_current_user_for_workflow", "get_current_user_optional",
    "get_optional_user", "get_user_store_api_key", "get_flow",
    # open-webui-style helpers
    "get_verified_user", "get_admin_user", "get_optional_verified_user",
    "get_verified_user_by_token", "get_verified_user_by_id", "get_scim_auth",
}
HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    return ""


def has_auth_call(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in AUTH_FNS:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in AUTH_FNS:
            return True
    return False


@dataclass
class Route:
    file: str
    line: int
    method: str
    path: str
    func: str
    auth: list[str] = field(default_factory=list)
    router_deps: list[str] = field(default_factory=list)


def scan_file(path: Path, root: Path) -> list[Route]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    rel = str(path.relative_to(root))

    router_deps: dict[str, list[str]] = {}
    router_prefix: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            name = dotted(node.value.func).split(".")[-1]
            if name == "APIRouter":
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                deps = []
                prefix = ""
                for kw in node.value.keywords:
                    if kw.arg == "dependencies" and has_auth_call(kw.value):
                        deps = [dotted(x) for x in ast.walk(kw.value) if isinstance(x, ast.Name) and x.id in AUTH_FNS]
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = kw.value.value
                for t in targets:
                    router_deps[t] = deps
                    router_prefix[t] = prefix

    routes: list[Route] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            attr = dec.func.attr
            if attr not in HTTP_METHODS and attr != "api_route":
                continue
            router_name = dotted(dec.func.value).split(".")[-1]
            methods = [attr.upper()] if attr != "api_route" else ["*"]
            if attr == "api_route" and dec.args and isinstance(dec.args[0], ast.Constant):
                methods = [dec.args[0].value]
            path = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else "?"
            auth: list[str] = []
            for kw in dec.keywords:
                if kw.arg == "dependencies" and has_auth_call(kw.value):
                    auth.append("decorator-dependencies")
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                ann = arg.annotation
                if ann is not None:
                    if any(n.id in AUTH_ALIASES for n in ast.walk(ann) if isinstance(n, ast.Name)):
                        auth.append(f"param:{arg.arg}(alias)")
                    elif has_auth_call(ann):
                        auth.append(f"param:{arg.arg}(Annotated/Depends)")
                default = None
                positional = [*node.args.posonlyargs, *node.args.args]
                if arg in positional:
                    idx = positional.index(arg) - (len(positional) - len(node.args.defaults))
                    default = node.args.defaults[idx] if idx >= 0 else None
                elif arg in node.args.kwonlyargs:
                    idx = node.args.kwonlyargs.index(arg)
                    if idx < len(node.args.kw_defaults):
                        default = node.args.kw_defaults[idx]
                if default is not None and has_auth_call(default):
                    auth.append(f"param:{arg.arg}(Depends)")
            routes.append(Route(rel, node.lineno, "/".join(methods), path, node.name,
                                sorted(set(auth)), router_deps.get(router_name, [])))
    return routes


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    routes: list[Route] = []
    for path in sorted(root.rglob("*.py")):
        if "/tests/" in str(path) or "/.venv/" in str(path):
            continue
        routes.extend(scan_file(path, root))
    noauth = [r for r in routes if not r.auth and not r.router_deps]
    print(f"total route handlers: {len(routes)}; without visible auth signal: {len(noauth)}\n")
    for r in sorted(noauth, key=lambda r: (r.file, r.line)):
        print(f"{r.file}:{r.line}  {r.method:<7} {r.path:<58} {r.func}")
    print("\n-- handlers with router-level auth --")
    for r in sorted(routes, key=lambda r: (r.file, r.line)):
        if r.router_deps and not r.auth:
            print(f"{r.file}:{r.line}  {r.method:<7} {r.path:<58} {r.func}  router={r.router_deps}")


if __name__ == "__main__":
    main()
