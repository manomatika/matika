"""Canonical i18n-completeness checker for the ManoMatika ecosystem.

This is the ONE canonical implementation of the build-validation i18n-completeness
contract (manomatika/eyerate#73, phase 2). matika OWNS the i18n mechanism
(see ``matika/i18n.py``), so it owns this checker too. eyerate's L1 suite and the
ahimsa product-build gate both IMPORT and invoke this module — neither reimplements
the merge/scan logic (standing rule 18: one canonical implementation, fail loud).

Stdlib-only by design: ahimsa imports this file by path against the pinned matika
source tree at build time, without installing matika's package or its dependencies.

The contract enforces two rules against the locale catalogs and the i18n keys
actually referenced in source, mirroring ``I18nService`` merge semantics
(core catalog first, then each applug catalog ``dict.update``-ed over it):

  R1 — reference coverage. Every i18n key referenced in source (templates, routes,
       and menu/manifest/metadata JSON declarations) MUST resolve in the merged
       catalog for EVERY locale the product ships. Catches the eyerate#73 failure
       class: a key shipped to the UI that has no catalog entry (raw-key leak).

  R2 — locale parity. Within each audited component, every key present in any of
       its locale catalogs MUST be present in ALL of its locale catalogs. Catches
       silent English-fallback gaps (e.g. a key in en.json missing from es.json).

A violation names the offending key, the locale, and the source file (rule 18).

Key DISCOVERY is a static scan. Because no i18n key is dynamically constructed in
the ecosystem today (no f-strings/concatenation building key names), a static
harvest is sound. The two known blind spots are handled:
  * Data-driven keys (``label_key``/``title_key`` selected at runtime from JSON):
    harvested directly from the JSON declarations, not the template.
  * Genuinely dynamic keys (would require runtime construction): none exist; the
    contract is that keys are literals. R2 parity is a backstop — a key reachable
    only dynamically is still required to exist in every locale if it exists in one.
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Directories never scanned for references or catalogs.
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "tests",
        "test",
        "scripts",
    }
)

# Locale catalogs themselves are not reference sources.
_LOCALES_DIRNAME = "locales"

# JSON fields that carry an i18n key by contract (menus, applug.json, metadata).
_I18N_JSON_FIELDS = frozenset({"label_key", "title_key"})

# dict methods/attributes that are NOT translation keys when written ``t.<name>``.
_DICT_ATTRS = frozenset(
    {
        "get",
        "items",
        "keys",
        "values",
        "update",
        "pop",
        "popitem",
        "setdefault",
        "copy",
        "clear",
        "fromkeys",
    }
)

# A valid i18n key identifier (matches the flat, prefix-namespaced convention).
_KEY = r"[A-Za-z_][A-Za-z0-9_]*"

# Template reference patterns. ``t`` is the per-request translation dict injected
# into every Jinja context. Attribute form ``t.key`` and literal-subscript form
# ``t['key']`` / ``t["key"]``. The negative lookbehind keeps ``t`` from matching
# the tail of a larger identifier (e.g. ``object.t``). Non-literal subscripts
# (``t[col.label_key]``) are intentionally NOT matched here — those keys are
# harvested from the JSON declarations they are driven by.
_TPL_ATTR = re.compile(r"(?<![\w.])t\.(" + _KEY + r")")
_TPL_SUBSCRIPT = re.compile(r"(?<![\w.])t\[\s*(['\"])(" + _KEY + r")\1\s*\]")


@dataclass(frozen=True)
class Violation:
    """A single i18n-completeness defect. ``source`` is the file to fix."""

    rule: str  # "reference" | "parity"
    key: str
    locale: str
    source: str
    detail: str

    def render(self) -> str:
        return (
            f"  [{self.rule}] key '{self.key}' locale '{self.locale}'\n"
            f"      file: {self.source}\n"
            f"      {self.detail}"
        )


@dataclass
class Component:
    """A unit that ships locale catalogs and/or references i18n keys.

    ``locales_dir`` holds ``<lang>.json`` catalogs. ``source_roots`` are files or
    directories scanned for key references. ``is_core`` marks the matika core
    catalogs that every component's references resolve against (merge base).
    ``audit`` False means "use this component's catalogs as a resolution base only,
    do not audit it" (e.g. core when an applug suite checks itself).
    """

    name: str
    locales_dir: str
    source_roots: List[str] = field(default_factory=list)
    is_core: bool = False
    audit: bool = True


class I18nCompletenessError(Exception):
    """Raised when the i18n-completeness contract is violated. Fail loud (rule 18)."""

    def __init__(self, violations: List[Violation]):
        self.violations = violations
        header = (
            f"i18n-completeness gate FAILED: {len(violations)} violation(s).\n"
            "Every referenced i18n key must resolve in every shipped locale (R1),\n"
            "and every key must be present in all locales of its component (R2).\n"
        )
        body = "\n".join(v.render() for v in violations)
        super().__init__(header + body)


# --------------------------------------------------------------------------- #
# Catalog loading
# --------------------------------------------------------------------------- #
def discover_catalogs(locales_dir: str) -> Dict[str, Dict[str, str]]:
    """Load every ``<lang>.json`` in ``locales_dir`` → {lang: {key: value}}."""
    catalogs: Dict[str, Dict[str, str]] = {}
    if not os.path.isdir(locales_dir):
        return catalogs
    for entry in sorted(os.listdir(locales_dir)):
        if not entry.endswith(".json"):
            continue
        lang = entry[: -len(".json")]
        path = os.path.join(locales_dir, entry)
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise I18nCompletenessError(
                [
                    Violation(
                        "parity",
                        "<catalog>",
                        lang,
                        path,
                        "catalog file is not a JSON object of key->string",
                    )
                ]
            )
        catalogs[lang] = data
    return catalogs


# --------------------------------------------------------------------------- #
# Reference harvesting
# --------------------------------------------------------------------------- #
def _iter_source_files(root: str):
    """Yield source files under ``root`` (a file or dir), applying skip rules."""
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and d != _LOCALES_DIRNAME
        ]
        for name in filenames:
            yield os.path.join(dirpath, name)


def _harvest_template(path: str) -> List[Tuple[str, int]]:
    refs: List[Tuple[str, int]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            for m in _TPL_ATTR.finditer(line):
                key = m.group(1)
                if key not in _DICT_ATTRS:
                    refs.append((key, lineno))
            for m in _TPL_SUBSCRIPT.finditer(line):
                refs.append((m.group(2), lineno))
    return refs


def _scope_local_nodes(scope: ast.AST):
    """Yield nodes belonging to ``scope`` itself, not to nested function scopes."""
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield child
        yield from _scope_local_nodes(child)


def _harvest_python(path: str) -> List[Tuple[str, int]]:
    """Harvest i18n key refs from Python, scope-aware.

    Within each scope, a name bound to a ``*.get_text(...)`` call IS the translation
    dict; only its ``name.get("literal")`` and ``name["literal"]`` accesses are
    harvested. This precisely avoids the ``manifest.get("id")`` false-positive class
    where an unrelated dict is also in scope.
    """
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError:
        return []

    scopes: List[ast.AST] = [tree]
    scopes += [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    refs: List[Tuple[str, int]] = []
    for scope in scopes:
        local = list(_scope_local_nodes(scope))
        bound: Set[str] = set()
        for node in local:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute) and func.attr == "get_text":
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            bound.add(tgt.id)
        if not bound:
            continue
        for node in local:
            # t.get("literal", ...)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in bound
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                refs.append((node.args[0].value, node.lineno))
            # t["literal"]
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id in bound
            ):
                sl = node.slice
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    refs.append((sl.value, node.lineno))
    return refs


def _walk_json_for_keys(obj, found: List[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _I18N_JSON_FIELDS and isinstance(v, str) and v:
                found.append(v)
            else:
                _walk_json_for_keys(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_json_for_keys(item, found)


def _harvest_json(path: str) -> List[Tuple[str, int]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []
    found: List[str] = []
    _walk_json_for_keys(data, found)
    return [(k, 0) for k in found]


def harvest_references(source_roots: List[str]) -> List[Tuple[str, str]]:
    """Return [(key, source_file)] for every i18n key referenced under the roots."""
    refs: List[Tuple[str, str]] = []
    for root in source_roots:
        for path in _iter_source_files(root):
            if path.endswith(".html"):
                refs += [(k, path) for k, _ in _harvest_template(path)]
            elif path.endswith(".py"):
                refs += [(k, path) for k, _ in _harvest_python(path)]
            elif path.endswith(".json"):
                refs += [(k, path) for k, _ in _harvest_json(path)]
    return refs


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def analyze(components: List[Component]) -> List[Violation]:
    """Run R1 + R2 over the components; return all violations (possibly empty)."""
    core = next((c for c in components if c.is_core), None)
    core_catalogs = discover_catalogs(core.locales_dir) if core else {}

    catalogs_by_name: Dict[str, Dict[str, Dict[str, str]]] = {}
    shipped_locales: Set[str] = set(core_catalogs)
    for comp in components:
        cat = discover_catalogs(comp.locales_dir)
        catalogs_by_name[comp.name] = cat
        shipped_locales |= set(cat)

    violations: List[Violation] = []

    # R2 — locale parity, per audited component.
    for comp in components:
        if not comp.audit:
            continue
        cat = catalogs_by_name[comp.name]
        if not cat:
            continue
        union: Set[str] = set().union(*[set(d) for d in cat.values()])
        present_langs = sorted(cat)
        for lang in present_langs:
            missing = union - set(cat[lang])
            for key in sorted(missing):
                others = sorted(L for L in present_langs if key in cat[L])
                violations.append(
                    Violation(
                        rule="parity",
                        key=key,
                        locale=lang,
                        source=os.path.join(comp.locales_dir, f"{lang}.json"),
                        detail=(
                            f"present in {comp.name} locale(s) {others} but missing "
                            f"from '{lang}'"
                        ),
                    )
                )

    # R1 — reference coverage, per audited component, against the merged catalog.
    for comp in components:
        if not comp.audit:
            continue
        refs = harvest_references(comp.source_roots)
        # Deduplicate (key, file) pairs to keep the report concise.
        seen: Set[Tuple[str, str]] = set()
        for lang in sorted(shipped_locales):
            merged = dict(core_catalogs.get(lang, {}))
            merged.update(catalogs_by_name[comp.name].get(lang, {}))
            for key, src in refs:
                if key in merged:
                    continue
                dedup = (key, src, lang)
                if dedup in seen:
                    continue
                seen.add(dedup)
                violations.append(
                    Violation(
                        rule="reference",
                        key=key,
                        locale=lang,
                        source=src,
                        detail=(
                            f"referenced i18n key not defined in '{lang}' catalog "
                            f"(merged core + {comp.name})"
                        ),
                    )
                )

    return violations


def assert_complete(components: List[Component]) -> None:
    """Run the gate; raise I18nCompletenessError if any violation is found."""
    violations = analyze(components)
    if violations:
        raise I18nCompletenessError(violations)


# --------------------------------------------------------------------------- #
# Layout-aware convenience wrappers (the three consumers)
# --------------------------------------------------------------------------- #
def matika_core_component(matika_src_root: str, *, audit: bool = True) -> Component:
    """The matika core component, given matika's ``src`` dir (package at src/matika)."""
    pkg = os.path.join(matika_src_root, "matika")
    return Component(
        name="matika-core",
        locales_dir=os.path.join(pkg, "locales"),
        source_roots=[pkg],
        is_core=True,
        audit=audit,
    )


def applug_component(applug_repo_root: str, applug_name: str) -> Component:
    """An applug component from its repo root (package at src/<name>).

    Scans the package dir (templates, routes, metadata) plus the root-level
    ``applug.json`` and ``*menus*.json`` manifest declarations.
    """
    pkg = os.path.join(applug_repo_root, "src", applug_name)
    roots: List[str] = [pkg]
    manifest = os.path.join(applug_repo_root, "applug.json")
    if os.path.isfile(manifest):
        roots.append(manifest)
    for entry in sorted(os.listdir(applug_repo_root)):
        if entry.endswith(".json") and "menus" in entry:
            roots.append(os.path.join(applug_repo_root, entry))
    return Component(
        name=applug_name,
        locales_dir=os.path.join(pkg, "locales"),
        source_roots=roots,
        is_core=False,
        audit=True,
    )


def frozen_tree_components(source_root: str) -> List[Component]:
    """Components for the runtime/frozen layout ahimsa builds.

    ``source_root`` is the matika tree (e.g. ``build/matika``): core at
    ``src/matika``, applugs at ``plugins/<name>`` (package at
    ``plugins/<name>/src/<name>``), exactly per ``I18nService`` discovery.
    All components are audited — this is the full product gate.
    """
    components = [matika_core_component(os.path.join(source_root, "src"), audit=True)]
    plugins_dir = os.path.join(source_root, "plugins")
    if os.path.isdir(plugins_dir):
        for name in sorted(os.listdir(plugins_dir)):
            plugin_root = os.path.join(plugins_dir, name)
            if not os.path.isdir(plugin_root):
                continue
            if not os.path.isdir(os.path.join(plugin_root, "src", name, "locales")):
                continue
            components.append(applug_component(plugin_root, name))
    return components
