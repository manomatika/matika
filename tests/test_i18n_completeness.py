"""L1 suite for the canonical i18n-completeness checker (manomatika/eyerate#73).

matika owns the checker (``matika.core.i18n_completeness``); eyerate and the ahimsa
build gate consume the SAME module. These tests assert matika core passes its own
STRICT gate AND that the checker is non-vacuous — it must actually detect a missing
reference, a locale-parity gap, and must NOT mistake an unrelated ``dict.get`` for an
i18n key (rule 22: a gate that cannot fail is worthless).
"""

import os

import matika
from matika.core import i18n_completeness as ic


def _matika_src() -> str:
    # matika.__file__ -> <src>/matika/__init__.py ; two dirnames -> <src>
    return os.path.dirname(os.path.dirname(matika.__file__))


def test_matika_core_i18n_is_complete():
    """matika core must satisfy its own STRICT gate: every referenced key resolves
    in every shipped locale (R1) and all locales are at parity (R2)."""
    violations = ic.analyze([ic.matika_core_component(_matika_src())])
    assert violations == [], "matika core i18n incomplete:\n" + "\n".join(
        v.render() for v in violations
    )


def test_checker_detects_missing_reference(tmp_path):
    loc = tmp_path / "locales"
    loc.mkdir()
    (loc / "en.json").write_text('{"present": "Present"}', encoding="utf-8")
    (loc / "es.json").write_text('{"present": "Presente"}', encoding="utf-8")
    tpl = tmp_path / "templates"
    tpl.mkdir()
    (tpl / "x.html").write_text("<p>{{ t.absent }}</p>", encoding="utf-8")
    comp = ic.Component(
        name="probe", locales_dir=str(loc), source_roots=[str(tmp_path)], is_core=True
    )
    vs = ic.analyze([comp])
    assert any(v.rule == "reference" and v.key == "absent" for v in vs)


def test_checker_detects_parity_gap(tmp_path):
    loc = tmp_path / "locales"
    loc.mkdir()
    (loc / "en.json").write_text('{"a": "A", "b": "B"}', encoding="utf-8")
    (loc / "es.json").write_text('{"a": "A"}', encoding="utf-8")  # 'b' missing
    comp = ic.Component(
        name="probe", locales_dir=str(loc), source_roots=[], is_core=True
    )
    vs = ic.analyze([comp])
    assert any(v.rule == "parity" and v.key == "b" and v.locale == "es" for v in vs)


def test_checker_detects_json_label_key_reference(tmp_path):
    """Data-driven keys declared in menu/manifest JSON are harvested."""
    loc = tmp_path / "locales"
    loc.mkdir()
    (loc / "en.json").write_text("{}", encoding="utf-8")
    (tmp_path / "x_menus.json").write_text(
        '{"items": [{"label_key": "menu_undefined"}]}', encoding="utf-8"
    )
    comp = ic.Component(
        name="probe", locales_dir=str(loc), source_roots=[str(tmp_path)], is_core=True
    )
    vs = ic.analyze([comp])
    assert any(
        v.rule == "reference" and v.key == "menu_undefined" for v in vs
    )


def test_python_harvest_ignores_non_i18n_dict_get(tmp_path):
    """``manifest.get("id")`` must NOT be harvested — only a name bound to
    ``*.get_text(...)`` is the translation dict (the false-positive class that a
    blind ``t.get`` regex would have flagged)."""
    loc = tmp_path / "locales"
    loc.mkdir()
    (loc / "en.json").write_text('{"real_key": "Real"}', encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "routes.py").write_text(
        "def handler(request):\n"
        "    t = request.app.state.i18n.get_text('en')\n"
        "    manifest = {'id': 'plug', 'entry_point': 'mod:Cls'}\n"
        "    plugin_id = manifest.get('id')\n"
        "    entry = manifest.get('entry_point')\n"
        "    label = t.get('real_key')\n"
        "    return plugin_id, entry, label\n",
        encoding="utf-8",
    )
    comp = ic.Component(
        name="probe", locales_dir=str(loc), source_roots=[str(pkg)], is_core=True
    )
    vs = ic.analyze([comp])
    assert vs == [], (
        "non-i18n dict.get() was wrongly harvested as i18n keys:\n"
        + "\n".join(v.render() for v in vs)
    )
