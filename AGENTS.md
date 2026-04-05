# Repository Guidelines

## Project Structure & Module Organization

This repository is a small Python CLI scanner with top-level modules:

- `main.py`: interactive entrypoint and scan orchestration
- `crawler.py`: in-scope URL discovery
- `scanner.py`: request-based vulnerability checks
- `reporter.py`: JSON report generation
- `utils.py`: shared helpers
- `README.md`: minimal project overview

There is no `tests/` directory yet. When adding tests, place them under `tests/` and mirror module names, for example `tests/test_crawler.py`.

## Build, Test, and Development Commands

- `python3 main.py`: run the scanner locally
- `python3 -m py_compile main.py crawler.py scanner.py reporter.py utils.py`: quick syntax validation
- `python3 -m pytest`: run the test suite once `tests/` exists

Keep commands runnable from the repository root. Avoid adding workflow steps that require editing files outside this repo.

## Coding Style & Naming Conventions

Use Python with 4-space indentation and standard library-first imports. Prefer small functions, explicit helper names, and module-level constants for scan limits and defaults.

- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Files: lowercase, single-purpose modules such as `crawler.py`

Follow the existing direct style. Add short comments only where the logic is non-obvious. Prefer ASCII unless a file already uses other characters.

## Testing Guidelines

There is no formal test coverage baseline yet; new behavior should include targeted tests where practical. Focus first on deterministic logic such as URL normalization, scope filtering, and result formatting.

Name tests `test_<behavior>.py` and test functions `test_<expected_outcome>()`.

## Commit & Pull Request Guidelines

Current history uses short, imperative commit messages such as `Create crawler.py`. Keep commits concise and descriptive, for example `Improve crawler scope handling`.

Pull requests should include:

- a short summary of the change
- affected files or modules
- how the change was verified
- any security impact or scan-behavior change

## Security & Configuration Tips

This project issues live HTTP requests. Keep scans scoped to authorized targets, preserve same-origin restrictions in crawler changes, and avoid adding high-risk checks without explicit safeguards and clear reporting.
