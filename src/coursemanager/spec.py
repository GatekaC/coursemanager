"""The course file: one loader, for the command line and a deploy engine.

A course lives in one organisation of a git forge; its `solution` repository
holds a `course.toml`. The format is described key by key in COURSE.md; this
module is its only reader, so what `coursemanager check` accepts and what an
engine deploys cannot drift apart.

ONE GRAMMAR. A key this module does not know is refused, never ignored: a
misspelt key would otherwise be a silent no-op. The forms of before 1.0
(`package.toml`, `[package]`, `[subpackage]`, `lab = "x"`, `id`, `labs`,
`notebook`, `renderer`, `hub`) are refused with one answer: run
`coursemanager migrate` (legacy.py reads them, once, to rewrite the file).

Nothing here prints or exits: problems raise CourseError, and the caller
decides what a problem means (a CLI stops, the engine marks the course).
"""
import re
import tomllib
from pathlib import Path

NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")   # labs may be numbered: 00-getting-started
LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
FILE = "course.toml"
STATUSES = ("active", "past")                    # [course] status; absent = active
DELIVERIES = ("engine", "external")              # [course] delivery; absent = engine

TOP_KEYS = {"course", "wave"}
COURSE_KEYS = {"name", "title", "status", "delivery", "source", "published", "kernel",
               "teachers", "audience", "teacher", "moodle"}
LAB_KEYS = {"title", "content", "exclude", "files", "buckets"}
WAVE_KEYS = LAB_KEYS | {"who", "summary", "released", "at", "lab"}
# The earlier grammar, named so the error can say `migrate` instead of `unknown`.
LEGACY = {"package": "[package] is now [course]", "subpackage": "[subpackage.<x>] is now [wave.<x>]",
          "id": "`id` is gone: the wave's name is what it delivers", "labs": "`labs = [...]` is now [wave.<w>.lab.<x>] tables",
          "notebook": "`notebook` is now `content`", "renderer": "`renderer` is gone: there is one renderer",
          "hub": "`hub` is gone: the machine belongs to the deployment"}
MIGRATE = " - run `coursemanager migrate`"


class CourseError(Exception):
    """A course file or a lab that cannot be used as it is."""


def course_file(root):
    """The course file of a folder, or None."""
    f = Path(root) / FILE
    return f if f.is_file() else None


def find_root(start=None):
    """The folder holding course.toml, from `start` upwards."""
    here = Path(start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if course_file(d):
            return d
    if (here / "package.toml").is_file():
        raise CourseError("package.toml is the earlier grammar" + MIGRATE)
    raise CourseError("no course.toml here or above: run this inside a course (or `coursemanager init <course>`)")


def parse(text):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise CourseError("course.toml: %s" % e)


def _refuse_unknown(table, allowed, where):
    for k in table:
        if k in allowed:
            continue
        if k in LEGACY:
            raise CourseError("course.toml: %s: %s%s" % (where, LEGACY[k], MIGRATE))
        raise CourseError("course.toml: %s: unknown key %r (COURSE.md lists them)" % (where, k))


def course_table(cfg):
    """The [course] table, checked key by key."""
    for k in cfg:
        if k not in TOP_KEYS:
            if k in LEGACY:
                raise CourseError("course.toml: %s%s" % (LEGACY[k], MIGRATE))
            raise CourseError("course.toml: unknown table [%s]" % k)
    course = cfg.get("course")
    if not isinstance(course, dict):
        raise CourseError("course.toml: no [course] table")
    _refuse_unknown(course, COURSE_KEYS, "[course]")
    return course


def _list(v):
    return [v] if isinstance(v, str) else list(v or [])


def status_of(course):
    """[course] status: active (default) or past - a past course is kept as a
    record, nothing is deployed from it."""
    s = str(course.get("status") or "active").strip().lower()
    if s not in STATUSES:
        raise CourseError("course.toml: status must be active or past (got %r)" % s)
    return s


def delivery_of(course):
    """[course] delivery: "engine" (the default: the deploy engine writes the
    labs into each person's repository) or "external" - a course delivered by
    its own tool, which the platform shows and never deploys to, nor changes
    the teams of. An external course's file lives with the platform
    (`courses/<org>/course.toml`), not in the organisation."""
    d = str(course.get("delivery") or "engine").strip().lower()
    if d not in DELIVERIES:
        raise CourseError("course.toml: delivery must be engine or external (got %r)" % d)
    return d


def teachers_of(course):
    """[course] teachers: the forge logins of the course's teachers, or
    [] (the platform's teachers then)."""
    t = _list(course.get("teachers"))
    t = [str(x).strip() for x in t if str(x).strip()]
    bad = [x for x in t if not LOGIN.match(x)]
    if bad:
        raise CourseError("course.toml: teachers must be forge logins (got %s)" % ", ".join(map(repr, bad)))
    return list(dict.fromkeys(t))


def audience_of(course):
    """[course] audience as wave recipients: "m2.students", "@m2.students",
    or a list of either -> ["@m2.students", ...]; empty -> []."""
    a = course.get("audience") or []
    a = a.split() if isinstance(a, str) else [str(x) for x in a]
    return [x if x.startswith("@") or x == "all" else "@" + x for x in a if x]


def labs_of(cfg):
    """{lab: spec}. A LAB is what one deployment writes into a person's
    repository, at the paths it has in `solution`. Declared by the waves:

        [wave.microintro]
        content = ["microintro/"]        # default: <lab>/
        exclude = ["runs/"]              # delivered to nobody

    Several labs in one wave: [wave.<name>.lab.<x>], one table each."""
    course = course_table(cfg)
    teacher = _list(course.get("teacher"))
    labs = {}

    def add(name, spec, title, wave, where):
        if not NAME.match(name):
            raise CourseError("course.toml: lab name %r is not valid (lowercase letters, digits, _ or -)" % name)
        if name in labs:
            raise CourseError("course.toml: lab %s is declared twice" % name)
        _refuse_unknown(spec, LAB_KEYS if where != "[wave.%s]" % name else WAVE_KEYS, where)
        labs[name] = {"name": name, "title": spec.get("title") or title or name, "wave": wave,
                      "content": _list(spec.get("content")) or [name + "/"],
                      "exclude": _list(spec.get("exclude")), "teacher": teacher,
                      "buckets": _list(spec.get("buckets")), "files": _list(spec.get("files"))}

    for wave, w in (cfg.get("wave") or {}).items():
        if not isinstance(w, dict):
            raise CourseError("course.toml: [wave.%s] must be a table" % wave)
        _refuse_unknown(w, WAVE_KEYS, "[wave.%s]" % wave)
        lab = w.get("lab")
        if lab is None:
            add(wave, w, w.get("title"), wave, "[wave.%s]" % wave)
        elif isinstance(lab, dict):
            for name, spec in lab.items():
                if not isinstance(spec, dict):
                    raise CourseError("course.toml: [wave.%s.lab.%s] must be a table" % (wave, name))
                add(name, spec, w.get("title"), wave, "[wave.%s.lab.%s]" % (wave, name))
        else:
            raise CourseError("course.toml: [wave.%s]: `lab = %r` is the earlier grammar (the wave's name is the lab)%s" % (wave, lab, MIGRATE))
    return labs


def wave_labs(w, wave=""):
    """The deliveries of a wave: its [wave.<w>.lab.<x>] tables, or itself."""
    lab = w.get("lab")
    return list(lab) if isinstance(lab, dict) else [wave]


def released_to(r, who):
    """`released` -> (the cohorts the wave has been deployed to, problems).

    A RECORD, written by the deploy engine after each deployment (a commit
    "<wave> deployed to <cohorts>"), not a gate: any cohort of `who` can
    receive the wave. One syntax, a list of cohorts of `who`:

        released = []                                   not deployed yet (also: absent)
        released = ["@m2.students"]                     M2 has it, M1 not yet

    true/false and a bare string are refused. "m2.students" and
    "@m2.students" name the same cohort."""
    if r is None:
        return [], []
    if not isinstance(r, list):
        return [], ["released must be a list of cohorts, e.g. released = [\"@m2.students\"] (got %r)" % (r,)]
    out, bad = [], []
    for x in (str(x) for x in r):
        c = x if x in who else "@" + x if "@" + x in who else None
        if c is None:
            bad.append("released to %s, which is not in who" % x)
        elif c not in out:
            out.append(c)
    return out, bad


def waves(cfg, labs=None):
    """{wave: {title, labs, who, at, released, summary, order[, error]}} - what
    the engine deploys, in the order of the file (`order`: its position, for
    readers that do not keep key order). `at` has the wave deployed on its own
    at that time."""
    course = course_table(cfg)
    labs = labs_of(cfg) if labs is None else labs
    out = {}
    for name, w in (cfg.get("wave") or {}).items():
        ls = wave_labs(w, name)
        who = w.get("who") or audience_of(course) or "all"
        who = who.split() if isinstance(who, str) else [str(x) for x in who]
        at = w.get("at") or ""
        if hasattr(at, "isoformat"):
            at = at.isoformat()
        released, problems = released_to(w.get("released"), who)
        out[name] = {"title": w.get("title") or name, "labs": ls, "who": who, "at": str(at),
                     "released": released, "order": len(out),
                     # The README's {{program}}: shown to a person once the wave reached them.
                     "summary": " ".join(str(w.get("summary") or "").split())}
        bad = [l for l in ls if l not in labs]
        if bad:
            problems.append("unknown lab(s): " + ", ".join(bad))
        if problems:
            out[name]["error"] = "; ".join(problems)
    return out


def load(root):
    """(course, labs) of the course in `root`: what the command line works on."""
    f = course_file(root)
    if not f:
        if (Path(root) / "package.toml").is_file():
            raise CourseError("package.toml is the earlier grammar" + MIGRATE)
        raise CourseError("no course.toml in %s" % root)
    cfg = parse(f.read_text(encoding="utf-8"))
    course = course_table(cfg)
    if not NAME.match(course.get("name", "")):
        raise CourseError("course.toml: [course] name must be lowercase letters, digits, _ or -")
    status_of(course)
    delivery_of(course)
    teachers_of(course)
    return course, labs_of(cfg)
