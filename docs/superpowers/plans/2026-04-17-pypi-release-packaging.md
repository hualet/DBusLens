# PyPI Release Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `dbuslens` ready for PyPI publication, support `uv tool install dbuslens`, and provide bash/zsh completion setup through the CLI.

**Architecture:** Keep the existing `argparse` CLI and package layout, add a `completion` subcommand backed by `shtab`, enrich packaging metadata in `pyproject.toml`, and add a GitHub Actions release workflow that builds, tests, and publishes via PyPI Trusted Publishing.

**Tech Stack:** Python 3.12+, `argparse`, `unittest`, `uv`, GitHub Actions, PyPI Trusted Publishing, `shtab`

---

### Task 1: Add CLI completion coverage

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `dbuslens/cli.py`

- [ ] **Step 1: Write the failing tests**

```python
    def test_build_parser_defines_completion_subcommand(self) -> None:
        parser = build_parser()

        completion_args = parser.parse_args(["completion", "bash"])

        self.assertEqual(completion_args.command, "completion")
        self.assertEqual(completion_args.shell, "bash")

    def test_handle_completion_writes_shell_script(self) -> None:
        fake_shtab = types.SimpleNamespace(complete=lambda parser, shell: f"{shell}:{parser.prog}")
        with mock.patch.dict(sys.modules, {"shtab": fake_shtab}):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = _handle_completion(Namespace(shell="zsh"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "zsh:dbuslens\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tests.test_cli.CliHelpersTests -v`
Expected: FAIL because `completion` and `_handle_completion` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
    completion_parser = subparsers.add_parser("completion", help="print shell completion script")
    completion_parser.add_argument("shell", choices=["bash", "zsh"])
```

```python
def _handle_completion(args: argparse.Namespace) -> int:
    import shtab

    print(shtab.complete(build_parser(), shell=args.shell))
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m unittest tests.test_cli.CliHelpersTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py dbuslens/cli.py
git commit -m "feat(cli): add shell completion command"
```

### Task 2: Add package metadata and docs for PyPI users

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Add package metadata**

```toml
[project]
description = "Record and inspect D-Bus traffic from the terminal"
readme = "README.md"
license = { text = "GPL-3.0-only" }
authors = [{ name = "hualet" }]
keywords = ["dbus", "d-bus", "terminal", "textual", "linux"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Environment :: Console",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
  "Operating System :: POSIX :: Linux",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.12",
  "Topic :: Software Development :: Debuggers",
  "Topic :: System :: Monitoring",
]

[project.urls]
Homepage = "https://github.com/hualet/DBusLens"
Repository = "https://github.com/hualet/DBusLens"
Issues = "https://github.com/hualet/DBusLens/issues"
```

- [ ] **Step 2: Document install prerequisites and completion setup**

```markdown
Install with:

```bash
uv tool install dbuslens
```

Runtime requirements:

- Linux
- `dbus-monitor`
- `gdbus`

Enable completions:

```bash
mkdir -p ~/.local/share/bash-completion/completions
dbuslens completion bash > ~/.local/share/bash-completion/completions/dbuslens

mkdir -p ~/.local/share/zsh/site-functions
dbuslens completion zsh > ~/.local/share/zsh/site-functions/_dbuslens
```
```

- [ ] **Step 3: Run build to verify metadata renders**

Run: `uv build`
Expected: PASS and `dist/*.whl` contains summary, README, classifiers, and URLs in metadata.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml README.md
git commit -m "docs: prepare package metadata for PyPI"
```

### Task 3: Add release workflow for Trusted Publishing

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `.github/workflows/pylint.yml`

- [ ] **Step 1: Add release workflow**

```yaml
name: Release

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync
      - run: ./.venv/bin/python -m unittest discover -s tests -v
      - run: ./.venv/bin/python -m dbuslens --help
      - run: uv build

  publish:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    environment: pypi
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 2: Modernize the lint workflow to use `uv`**

```yaml
      - uses: astral-sh/setup-uv@v6
      - run: uv sync
      - run: uv run pylint $(git ls-files '*.py')
```

- [ ] **Step 3: Verify workflow syntax locally by inspection and fresh test/build run**

Run: `./.venv/bin/python -m unittest discover -s tests -v`
Expected: PASS

Run: `./.venv/bin/python -m dbuslens --help`
Expected: PASS and help lists `completion`

Run: `uv build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/pylint.yml .github/workflows/release.yml
git commit -m "ci: add trusted publishing release workflow"
```
