# Changelog

## 1.0.0 — unreleased

The first release as a project of its own. Born as `maqi-package`, then
`maqi-course` (one file, then a package, in a private platform repository),
then `course_manager` inside the bulkhours repository; now one neutral
project that every platform installs, pinned by version, and none owns.

- One grammar: `course.toml` as COURSE.md writes it. The earlier forms
  (`package.toml`, `[package]`, `[subpackage]`, `id` / `lab` / `labs` in a
  wave, the `renderer` key) are no longer read; `coursemanager migrate`
  rewrites a file that still uses them.
- The same markers in C++ and CUDA (`//`), chosen by the file's suffix or
  the notebook's kernel (`C++14`, `C++17`, `c`); `int x = f();  // SOLUTION`
  keeps type, name and `;`; `#if 0 // BEGIN PROMPT … #endif // END PROMPT`.
- The hole is `...` in every language.
- Leak check: a line marked SOLUTION is a secret whatever its length;
  whitespace cannot hide a copy; trivial lines (`pass`, `}`) are not secrets.
- Compound assignments keep their operator: `x += f()  # SOLUTION` → `x += ...`.
- Errors name the block and the line it opened on.
- `coursemanager --version` prints version and a fingerprint of the files.
