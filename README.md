# coursemanager

**The course standard** — one source per lab, two versions, delivered in waves.

A teacher writes a lab once, answers included, with the markers of
[Otter Grader](https://otter-grader.readthedocs.io/en/latest/otter_assign/notebook_format.html)
(`# SOLUTION`, `# BEGIN SOLUTION … # END SOLUTION`, prompts) — in Python
notebooks and modules, and in C, C++ and CUDA sources with `//`. `coursemanager`
renders the **student version** (answers removed, prompts shown, outputs
cleared, teacher files left out) and the **teacher version** (everything), and
refuses any render in which a solution line reaches the student. A
`course.toml` declares the course, its labs and its **waves** — the releases —
with `released` as the record of where each wave went.

The format, key by key, and the rules a deployer honours: **[COURSE.md](COURSE.md)**.

```
pip install coursemanager

coursemanager init <course>     the standard skeleton, with course.toml
coursemanager new <lab>         a lab and a draft wave
coursemanager check [lab]       markers balanced, no answer reaching the student version
coursemanager preview [lab]     both versions under ~/preview/<course>/
coursemanager status            every wave, its lab, who it is released to
coursemanager build [lab]       what is delivered, under build/ (a deploy engine runs this)
coursemanager migrate           rewrite a course.toml written in an earlier grammar
coursemanager --version
```

## One standard, several platforms

This project names no platform, forge or machine. A teaching platform adopts
the standard by **installing it, pinned by version** — and keeps its own
binding to itself: which forge holds the repositories, which teams may read
`solution`, which engine deploys a wave. Two platforms on the same version
read the same `course.toml` and render the same files; nothing of one platform
is needed by the other.

No runtime dependency. `jupytext`, if present (`COURSE_JUPYTEXT` or on `PATH`),
turns `.py` percent notebooks into `.ipynb` at build time.

## Development

```
python3 -m unittest discover -s tests      # standard library only
python3 -m pip install -e .
```

Releases: a tag `v<version>` builds and publishes to PyPI by trusted
publishing (`.github/workflows/publish.yml`). Changes: [CHANGELOG.md](CHANGELOG.md).

MIT licence — see [LICENSE](LICENSE).
