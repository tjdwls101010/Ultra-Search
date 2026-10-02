"""The skill's tree, and the rules that keep it navigable.

The skill is read by its tree before any file: `scripts/` holds `cli.py`, the one entry point, and `ultra_search/`, the one package. Each unit directly in the package is of one kind -- a feature (a reason the skill exists), a system (a format or program someone else owns), a store (a kind of state on disk) or a helper (shared by every kind) -- and imports run one way, features to systems and stores to helpers, so a feature can change or go without touching the rest. Nothing outside a unit reaches past what its interface exports, tests included, so the inside can change without touching callers.

State does not live in the skill's `data/`, as the skill layout would have it: runs, saved pages, maps and crawls go to `./.ultra-search/` in the working directory. The skill is loaded globally and several projects' sessions run at once, a per-project registry is what keeps a bare `status` or `result` to that project's most recent run, and what the skill saves has to be readable with Read, which refuses files inside an installed skill folder.

Each checker is a function of source text, so it is shown failing on a short source that breaks its rule before it is trusted on the real tree. They read the usual ways of spelling an import or an edit, not every way Python allows: they catch a slip, and a deliberate workaround is a change to these rules to raise in review.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".claude" / "skills" / "ultra-search"
SCRIPTS = SKILL / "scripts"
PACKAGE_NAME = "ultra_search"
PACKAGE = SCRIPTS / PACKAGE_NAME
TESTS = REPO / "tests"

#: Every unit directly in the package, by kind. A new unit fails the tree check until it is named here.
KINDS = {
    "research": "feature",
    "fetch": "feature",
    "site": "feature",
    "doctor": "feature",
    "aside": "system",
    "converter": "system",
    "runs": "store",
    "saved": "store",
    "outcome": "helper",
    "ids": "helper",
    "workspace": "helper",
}

#: Which units each unit may import. A feature built from another feature is an edge named here, never implied.
ALLOWED = {
    "research": {"aside", "runs", "outcome", "ids"},
    "fetch": {"aside", "converter", "saved", "outcome", "ids"},
    "site": {"fetch", "aside", "saved", "outcome"},
    "doctor": {"aside", "converter", "runs", "outcome"},
    "aside": {"outcome", "ids"},
    "converter": {"outcome", "ids"},
    "runs": {"outcome", "ids", "workspace"},
    "saved": {"outcome", "ids", "workspace"},
    "outcome": set(),
    "ids": set(),
    "workspace": set(),
}


# --- reading the tree ------------------------------------------------------------------------


def unit_of(module: str) -> str | None:
    """The unit a dotted module name belongs to: `ultra_search.research.evidence` -> `research`."""
    parts = module.split(".")
    if parts[0] != PACKAGE_NAME or len(parts) < 2:
        return None
    return parts[1]


def module_name(path: Path) -> str:
    rel = path.relative_to(SCRIPTS).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def is_package(unit: str) -> bool:
    return (PACKAGE / unit / "__init__.py").exists()


def exported(unit: str) -> set[str]:
    """What a unit's interface offers: a package's `__all__`, or a single module's public names."""
    if is_package(unit):
        tree = ast.parse((PACKAGE / unit / "__init__.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                return set(ast.literal_eval(node.value))
        return set()
    tree = ast.parse((PACKAGE / f"{unit}.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
    return {n for n in names if not n.startswith("_")}


def imports(source: str, module: str) -> list[tuple[str, list[str], int]]:
    """Every import as (absolute module, names taken from it, line), relative ones resolved against ``module``."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append((a.name, [], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = module.split(".")
                # A module's own package is one level up; a package's __init__ is its own package.
                base = base[: len(base) - node.level + (1 if module_is_package(module) else 0)]
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            out.append((target, [a.name for a in node.names], node.lineno))
    return out


def module_is_package(module: str) -> bool:
    path = SCRIPTS.joinpath(*module.split("."))
    return (path / "__init__.py").exists()


# --- the checkers --------------------------------------------------------------------------------


def direction_violations(source: str, module: str) -> list[str]:
    """Imports from this unit to a unit it may not depend on. A name taken from the package
    itself (`from ultra_search import site`) is an import of that unit."""
    mine = unit_of(module)
    out = []
    for target, names, line in imports(source, module):
        targets = [target] + [f"{target}.{n}" for n in names if target == PACKAGE_NAME]
        for t in targets:
            theirs = unit_of(t)
            if theirs is None or theirs == mine:
                continue
            if mine is not None and theirs not in ALLOWED[mine]:
                out.append(f"{module}:{line} imports {theirs} ({KINDS.get(mine)} -> {KINDS.get(theirs)})")
    return out


def _rebound(tree: ast.AST) -> set[str]:
    """Names given another value somewhere in the file -- a parameter, an assignment -- whose
    attributes then say nothing about a unit."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            out.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            out.add(node.id)
    return out


def reach_violations(source: str, module: str) -> list[str]:
    """Uses of another unit beyond what its interface exports, under whatever name it was imported as."""
    mine = unit_of(module)
    out = []
    units: dict[str, str] = {}  # local name -> unit
    packages: set[str] = set()  # local names bound to the package itself
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == PACKAGE_NAME:
                    packages.add(a.asname or a.name)
                    continue
                theirs = unit_of(a.name)
                if theirs in (None, mine):
                    continue
                if len(a.name.split(".")) > 2:
                    out.append(f"{module}:{node.lineno} reaches into {a.name}")
                elif a.asname:
                    units[a.asname] = theirs
                else:
                    packages.add(PACKAGE_NAME)
        elif isinstance(node, ast.ImportFrom):
            target = imports(ast.unparse(node), module)[0][0] if node.level else (node.module or "")
            parts = target.split(".")
            if target == PACKAGE_NAME:
                for a in node.names:
                    if a.name in KINDS and a.name != mine:
                        units[a.asname or a.name] = a.name
                continue
            theirs = unit_of(target) if parts[0] == PACKAGE_NAME else None
            if theirs in (None, mine):
                continue
            if len(parts) > 2:
                out.append(f"{module}:{node.lineno} reaches into {target}")
                continue
            public = exported(theirs)
            out += [f"{module}:{node.lineno} takes {theirs}.{a.name}, which {theirs} does not export"
                    for a in node.names if a.name not in public]
    rebound = _rebound(tree)
    units = {k: v for k, v in units.items() if k not in rebound}
    packages -= rebound
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        unit = None
        if isinstance(node.value, ast.Name) and node.value.id in units:
            unit = units[node.value.id]
        elif isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name) \
                and node.value.value.id in packages and node.value.attr in KINDS:
            unit = node.value.attr
        if unit and unit != mine and node.attr not in exported(unit):
            out.append(f"{module}:{node.lineno} uses {unit}.{node.attr}, which {unit} does not export")
    return out


#: Calls that change a list in place, when the list is `sys.path`.
_PATH_MUTATORS = ("insert", "append", "extend", "remove", "pop", "clear")
#: Ways an environment is given a key.
_ENV_SETTERS = ("setenv", "putenv", "setdefault")


def path_edits(source: str, where: str) -> list[str]:
    """`sys.path` changed -- under any name `sys` or `path` was imported as -- in code, or in code
    handed to a child process as a string, or PYTHONPATH set in an environment."""
    tree = ast.parse(source)
    paths = {"sys.path"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            paths |= {f"{a.asname}.path" for a in node.names if a.name == "sys" and a.asname}
        if isinstance(node, ast.ImportFrom) and node.module == "sys":
            paths |= {a.asname or a.name for a in node.names if a.name == "path"}

    def is_path(expr: ast.AST) -> bool:
        return ast.unparse(expr) in paths

    out = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in _PATH_MUTATORS and is_path(node.func.value):
            out.append(f"{where}:{line} changes sys.path")
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            for t in targets:
                if (isinstance(t, ast.Attribute) and ast.unparse(t) in paths) \
                        or (isinstance(t, ast.Subscript) and ast.unparse(t.value) in paths):
                    out.append(f"{where}:{line} changes sys.path")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "sys" in node.value:
            try:
                inner = path_edits(node.value, where)
            except SyntaxError:
                inner = []
            if inner:
                out.append(f"{where}:{line} changes sys.path in code it hands on")
        if isinstance(node, ast.keyword) and node.arg == "PYTHONPATH":
            out.append(f"{where}:{node.value.lineno} sets PYTHONPATH")
        if isinstance(node, ast.keyword) and node.arg == "env" and isinstance(node.value, ast.Dict) \
                and any(isinstance(k, ast.Constant) and k.value == "PYTHONPATH" for k in node.value.keys):
            out.append(f"{where}:{line} sets PYTHONPATH")
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) \
                and isinstance(node.slice, ast.Constant) and node.slice.value == "PYTHONPATH":
            out.append(f"{where}:{line} sets PYTHONPATH")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _ENV_SETTERS \
                and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "PYTHONPATH":
            out.append(f"{where}:{line} sets PYTHONPATH")
    return out


#: Spellings only Aside's own records, programs and output use. Outside `aside/` they mean its format leaked.
ASIDE_NAMES = ("stopReason", "toolUse", "taskId", "task_id", "cacheRead", "cacheWrite", "publishDate", "toolResult",
               "turn-lifecycle", "system-message", "<citation", "<quote", "runningSessionCount", "semaphore",
               "webfetch", "websearch", "read_file", "openTab", "closeTab", "\\x1b[")
#: The same for the Node converter, outside `converter/`.
CONVERTER_NAMES = ("node_modules", "anydoc", "to_markdown.mjs", "npm")
#: An event's stored record and a tool result's own detail are handed out whole, never read: the
#: raw log level prints the one, `show --item` returns the other.
OPAQUE_READS = {("ultra_search.research.render", "raw"), ("ultra_search.research.commands", "details")}
#: The units that hold transcript events.
EVENT_READERS = ("research", "runs")


def opaque_reads(source: str, module: str) -> list[str]:
    """Reads of an event's stored record or detail, except handing one out whole where that is its job."""
    if unit_of(module) not in EVENT_READERS:
        return []
    tree = ast.parse(source)
    looked_into = set()  # `.raw[...]`, `.details.get(...)`: something read out of it
    for node in ast.walk(tree):
        if isinstance(node, (ast.Subscript, ast.Attribute)) and isinstance(node.value, ast.Attribute):
            looked_into.add(id(node.value))
    return [f"{module}:{node.lineno} reads .{node.attr}" for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr in ("raw", "details")
            and ((module, node.attr) not in OPAQUE_READS or id(node) in looked_into)]


def foreign_names(source: str, where: str, names: tuple[str, ...]) -> list[str]:
    return [f"{where}: {name}" for name in names if name in source]


def main_guard(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) \
                and node.test.left.id == "__name__":
            return True
    return False


def package_paths_in_tests(source: str, where: str) -> list[str]:
    """A test that reads a file inside the package by path reaches past every interface."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and (
                node.value == PACKAGE_NAME or f"{PACKAGE_NAME}/" in node.value or f"/{PACKAGE_NAME}" in node.value):
            out.append(f"{where}:{node.lineno} names {node.value!r}")
    return out


# --- the checkers, shown failing ------------------------------------------------------------------


def test_the_direction_checker_catches_a_feature_importing_a_feature() -> None:
    assert direction_violations("from ultra_search import research\n", "ultra_search.fetch.acquire")
    assert direction_violations("from ultra_search.research import supervise\n", "ultra_search.doctor")
    assert direction_violations("from .. import site\n", "ultra_search.fetch.acquire")
    assert direction_violations("import ultra_search.runs\n", "ultra_search.aside.sessions")
    assert not direction_violations("from ultra_search import fetch\n", "ultra_search.site.commands")
    assert not direction_violations("from . import evidence\n", "ultra_search.research.commands")


def test_the_reach_checker_catches_a_module_past_an_interface() -> None:
    for source in ("from ultra_search.runs.registry import Run\n", "import ultra_search.aside.sessions\n",
                   "from ultra_search import runs\nruns.registry.Run\n",
                   "from ultra_search import runs as storage\nstorage.registry.Run\n",
                   "import ultra_search.runs as storage\nstorage.registry.Run\n",
                   "import ultra_search.runs\nultra_search.runs.registry.Run\n",
                   "import ultra_search as us\nus.runs.registry.Run\n"):
        assert reach_violations(source, "tests.test_x"), source
    assert reach_violations("from ultra_search.runs import registry\n", "ultra_search.research.commands")
    for source in ("from ultra_search import runs\nruns.Run\n",
                   "from ultra_search import runs as storage\nruns = []\nruns.clear()\n",
                   "from ultra_search import runs\ndef count(runs):\n    return runs.count(1)\n"):
        assert not reach_violations(source, "tests.test_x"), source


def test_the_path_checker_catches_every_way_of_editing_the_import_path() -> None:
    for source in ("import sys\nsys.path.insert(0, 'x')\n", "import sys\nsys.path.append('x')\n",
                   "import sys\nsys.path = ['x']\n", "import sys\nsys.path += ['x']\n",
                   "import sys\nsys.path[:] = ['x']\n", "import sys\ndel sys.path[0]\n",
                   "from sys import path\npath.insert(0, 'x')\n", "from sys import path as p\np.append('x')\n",
                   "import sys as runtime\nruntime.path.insert(0, 'x')\n",
                   "code = 'import sys; sys.path.insert(0, \"x\")'\n",
                   "env = dict(os.environ, PYTHONPATH='x')\n", "subprocess.run(argv, env={'PYTHONPATH': 'x'})\n",
                   "os.environ['PYTHONPATH'] = 'x'\n", "monkeypatch.setenv('PYTHONPATH', 'x')\n",
                   "os.environ.setdefault('PYTHONPATH', 'x')\n"):
        assert path_edits(source, "x"), source
    for source in ("import sys\nprint(sys.path)\n", "message = 'Do not set PYTHONPATH'\n", "path = []\npath.append(1)\n",
                   "code = 'import sys; print(sys.path[0])'\n", "expected = {'PYTHONPATH': None}\n",
                   "from sys import path\npath = []\n"):
        assert not path_edits(source, "x"), source


def test_the_entry_point_checker_and_the_test_path_checker_catch_their_cases() -> None:
    assert main_guard('if __name__ == "__main__":\n    main()\n')
    assert not main_guard("def main():\n    pass\n")
    assert package_paths_in_tests('SNIPPETS = SCRIPTS / "ultra_search" / "aside"\n', "t")
    assert package_paths_in_tests('p = SCRIPTS / "ultra_search/aside/snippets"\n', "t")
    assert not package_paths_in_tests("from ultra_search import aside\n", "t")
    assert not package_paths_in_tests('assert row["started_by_ultra_search"]\n', "t")


def test_the_format_checkers_catch_a_leak() -> None:
    assert opaque_reads("x = event.details['sources']\n", "ultra_search.research.evidence")
    assert opaque_reads("x = event.raw\n", "ultra_search.research.follow")
    assert not opaque_reads("x = json.dumps(event.raw)\n", "ultra_search.research.render")
    assert not opaque_reads('payload = {"details": e.details}\n', "ultra_search.research.commands")
    assert opaque_reads('x = event.raw["content"]\n', "ultra_search.research.render")
    assert opaque_reads('x = e.details.get("sources")\n', "ultra_search.research.commands")
    assert not opaque_reads("x = doc.raw\n", "ultra_search.fetch.acquire")
    assert foreign_names('if e.stop_reason != "toolUse":\n', "x", ASIDE_NAMES)
    assert foreign_names('help="Runs `npm ci`"\n', "x", CONVERTER_NAMES)


# --- the tree ---------------------------------------------------------------------------------------


def package_modules() -> list[Path]:
    return sorted(p for p in PACKAGE.rglob("*.py") if "node_modules" not in p.parts)


def test_scripts_holds_one_entry_point_and_one_package() -> None:
    top = {p.name for p in SCRIPTS.iterdir() if p.name != "__pycache__"}
    assert top == {"cli.py", PACKAGE_NAME}
    assert PACKAGE_NAME not in sys.stdlib_module_names


def test_every_unit_is_of_a_named_kind() -> None:
    units = {p.stem for p in PACKAGE.glob("*.py") if p.stem != "__init__"} | {
        p.name for p in PACKAGE.iterdir() if p.is_dir() and (p / "__init__.py").exists()
    }
    assert units == set(KINDS)


def test_imports_run_from_features_to_systems_and_stores_to_helpers() -> None:
    violations = []
    for path in package_modules():
        violations += direction_violations(path.read_text(encoding="utf-8"), module_name(path))
    assert violations == []


def test_nothing_outside_a_unit_reaches_past_its_interface() -> None:
    violations = []
    for path in [*package_modules(), SCRIPTS / "cli.py", *TESTS.rglob("*.py")]:
        module = module_name(path) if path.is_relative_to(SCRIPTS) else f"tests.{path.stem}"
        violations += reach_violations(path.read_text(encoding="utf-8"), module)
    assert violations == []


def test_tests_read_the_package_only_through_its_interfaces() -> None:
    violations = []
    for path in TESTS.rglob("*.py"):
        if path.name != "test_structure.py":
            violations += package_paths_in_tests(path.read_text(encoding="utf-8"), str(path.relative_to(REPO)))
    assert violations == []


def test_nothing_edits_the_import_path() -> None:
    violations = []
    for path in [*package_modules(), SCRIPTS / "cli.py", *TESTS.rglob("*.py"), TESTS / "fake_aside" / "aside"]:
        if path.name != "test_structure.py":
            violations += path_edits(path.read_text(encoding="utf-8"), str(path.relative_to(REPO)))
    assert violations == []


def test_cli_py_is_the_only_entry_point() -> None:
    assert [str(p.relative_to(SCRIPTS)) for p in package_modules() if main_guard(p.read_text(encoding="utf-8"))] == []


def test_state_lives_in_the_working_directory_not_the_skill_folder() -> None:
    assert not (SKILL / "data").exists()


def test_only_the_aside_unit_reads_asides_records() -> None:
    violations = []
    for path in package_modules():
        violations += opaque_reads(path.read_text(encoding="utf-8"), module_name(path))
    assert violations == []


def test_asides_and_the_converters_names_stay_in_their_units() -> None:
    """The primary guard is the reads above; this catches a name copied into feature code, help
    text included, which a change to the other program would then silently break."""
    violations = []
    for path in [*package_modules(), SCRIPTS / "cli.py"]:
        text = path.read_text(encoding="utf-8")
        where = str(path.relative_to(SCRIPTS))
        if not path.is_relative_to(PACKAGE / "aside"):
            violations += foreign_names(text, where, ASIDE_NAMES)
        if not path.is_relative_to(PACKAGE / "converter"):
            violations += foreign_names(text, where, CONVERTER_NAMES)
    assert violations == []
