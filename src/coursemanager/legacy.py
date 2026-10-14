"""`coursemanager migrate`: a course file in the grammar of before 1.0, rewritten.

The loader (spec.py) reads ONE grammar and refuses the rest; this module is
the only place that still understands the earlier forms, and only to produce
the current one:

    package.toml, [package]        -> course.toml, [course]
    [subpackage.x] notebook = ...  -> [wave.x] content = [...]
    [wave.w] lab = "x" / id = "x"  -> [wave.x]   (the delivery's label is kept: the
                                      engine's `deploy x` commits name the lab)
    [wave.w] labs = ["a", "b"]     -> [wave.w.lab.a], [wave.w.lab.b]
    renderer, hub                  -> dropped (one renderer; the machine is the deployment's)
    released = true / "x"          -> released = []  (the cohorts are not known: name them)

Comments of the original file are not kept: the original stays next to the
result as `<file>.before-migrate` for the author to compare.
"""
import json
import tomllib
from pathlib import Path

from .spec import CourseError, FILE, COURSE_KEYS, LAB_KEYS, WAVE_KEYS

WAVE_ORDER = ("title", "content", "exclude", "files", "buckets", "who", "summary", "at", "released")
COURSE_ORDER = ("name", "title", "status", "delivery", "source", "published", "kernel", "teachers", "audience", "teacher", "moodle")


def _value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)


def _table(header, table, order):
    lines = ["[%s]" % header]
    for k in list(order) + [k for k in table if k not in order]:
        if k in table and table[k] is not None:
            lines.append("%s = %s" % (k, _value(table[k])))
    return "\n".join(lines) + "\n"


def convert(cfg):
    """The earlier grammar (a parsed TOML) -> (current cfg as text, notes)."""
    notes = []
    course = dict(cfg.get("course") or cfg.get("package") or {})
    if "package" in cfg:
        notes.append("[package] -> [course]")
    for k in ("renderer", "hub"):
        if k in course:
            course.pop(k); notes.append("[course] %s dropped" % k)
    unknown = [k for k in course if k not in COURSE_KEYS]
    if unknown:
        raise CourseError("migrate: [course] has keys this tool cannot place: %s" % ", ".join(unknown))

    subs = {}
    for name, s in (cfg.get("subpackage") or {}).items():
        s = dict(s)
        nb = Path(s.pop("notebook", None) or "%s/%s.py" % (name, name))
        s["content"] = [str(nb) if nb.parent == Path(".") else str(nb.parent) + "/"]
        s.pop("renderer", None)
        subs[name] = s
        notes.append("[subpackage.%s] -> lab %s (content %s)" % (name, name, s["content"][0]))

    waves = {}
    for wname, w in (cfg.get("wave") or {}).items():
        w = dict(w)
        if "renderer" in w:
            w.pop("renderer"); notes.append("[wave.%s] renderer dropped" % wname)
        lab = w.pop("lab", None)
        ident = w.pop("id", None)
        labs = w.pop("labs", None)
        if isinstance(w.get("released"), (bool, str)):
            notes.append("[wave.%s] released = %r cannot be migrated: the cohorts are not known, name them" % (wname, w["released"]))
            w["released"] = []
        if isinstance(lab, dict):
            for ln, spec in lab.items():
                spec = dict(spec); spec.pop("renderer", None)
                lab[ln] = {k: v for k, v in spec.items() if k in LAB_KEYS}
            w["lab"] = lab
            new = wname
        elif labs:
            w["lab"] = {l: {k: v for k, v in subs.pop(l, {}).items() if k in LAB_KEYS} for l in labs}
            new = wname
            notes.append("[wave.%s] labs = %s -> [wave.%s.lab.<x>] tables" % (wname, labs, wname))
        else:
            new = (lab if isinstance(lab, str) and lab else None) or (ident if isinstance(ident, str) and ident else None) or wname
            if new != wname:
                notes.append("[wave.%s] -> [wave.%s] (its lab's name, the label the engine knows)" % (wname, new))
            sub = subs.pop(new, {})
            for k in LAB_KEYS:
                if k in sub and k not in w:
                    w[k] = sub[k]
        if new in waves:
            raise CourseError("migrate: two waves would be named %s" % new)
        unknown = [k for k in w if k not in WAVE_KEYS]
        if unknown:
            raise CourseError("migrate: [wave.%s] has keys this tool cannot place: %s" % (wname, ", ".join(unknown)))
        waves[new] = w
    for name, s in subs.items():          # a subpackage no wave named: a draft wave
        waves[name] = {k: v for k, v in s.items() if k in LAB_KEYS}
        waves[name]["released"] = []
        notes.append("[subpackage.%s] had no wave: [wave.%s] released = []" % (name, name))

    out = ["# course.toml - rewritten by `coursemanager migrate`; the format is COURSE.md.\n"]
    out.append(_table("course", course, COURSE_ORDER))
    for name, w in waves.items():
        lab = w.pop("lab", None)
        out.append("\n" + _table("wave.%s" % name, w, WAVE_ORDER))
        for ln, spec in (lab or {}).items():
            out.append(_table("wave.%s.lab.%s" % (name, ln), spec, ("title", "content", "exclude", "files", "buckets")))
    return "".join(out), notes


def migrate(root):
    """Rewrite the course file of `root` in the current grammar. Returns the
    notes (what changed). The original is kept as `<file>.before-migrate`."""
    root = Path(root)
    src = next((root / n for n in (FILE, "package.toml") if (root / n).is_file()), None)
    if src is None:
        raise CourseError("migrate: no course.toml or package.toml in %s" % root)
    try:
        cfg = tomllib.loads(src.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise CourseError("migrate: %s: %s" % (src.name, e))
    text, notes = convert(cfg)
    backup = src.with_name(src.name + ".before-migrate")
    backup.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (root / FILE).write_text(text, encoding="utf-8")
    if src.name != FILE:
        src.unlink()
        notes.insert(0, "%s -> %s" % (src.name, FILE))
    notes.append("original kept as %s; comments are not carried over - compare, then delete it" % backup.name)
    return notes
