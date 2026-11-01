"""Stdlib-only tests for repo-cartographer. Run: python3 tests/test_cartographer.py"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cartographer as c  # noqa: E402


def _fixture(root: Path) -> None:
    (root / "pkg").mkdir(parents=True, exist_ok=True)
    (root / "cli.py").write_text("print('hi')\n" * 5)
    (root / "pkg" / "core.py").write_text("x = 1\n" * 120)
    (root / "pkg" / "deep.py").write_text("y = 2\n" * 40)
    (root / "README.md").write_text("# demo\n")
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (root / "blob.bin").write_bytes(b"\x00\x01\x02" * 50)
    # Noise that must be skipped.
    (root / "node_modules").mkdir()
    (root / "node_modules" / "junk.js").write_text("junk\n" * 999)
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_bytes(b"\x00")


def test_profile_shape():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        data = json.loads(c.repo_profile({"path": tmp, "top": 5}))

        assert "error" not in data, data
        assert data["path"] == str(root)
        # 6 real files; node_modules/__pycache__ skipped
        assert data["files_total"] == 6, data["files_total"]

        langs = {row["language"]: row for row in data["languages"]}
        assert langs["Python"]["files"] == 3, langs
        assert langs["Python"]["loc"] >= 165, langs["Python"]["loc"]
        assert "(binary/other)" in langs, langs

        assert "cli.py" in data["entry_points_top_level"], data["entry_points_top_level"]
        assert "pyproject.toml" in data["manifests"], data["manifests"]
        assert data["largest_files"][0]["path"] == "pkg/core.py", data["largest_files"]
        assert data["git"]["is_repo"] is False
        assert data["scan_truncated"] is False


def test_profile_rejects_missing_path():
    data = json.loads(c.repo_profile({"path": "/nope/does/not/exist"}))
    assert "error" in data


def test_profile_survives_garbage_args():
    # Handlers must never raise: bad types fall back to defaults.
    data = json.loads(c.repo_profile({"path": ".", "top": "not-a-number"}))
    assert "error" not in data


def test_hotspot_scan_threshold():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        data = json.loads(c.hotspot_scan({"path": tmp, "loc_limit": 50}))
        paths = [h["path"] for h in data["largest"]]
        assert paths == ["pkg/core.py"], paths
        assert data["files_scanned"] == 3, data


def test_hotspot_scan_extension_filter():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        # Only the single markdown file is scanned; it is far below the floor.
        data = json.loads(c.hotspot_scan({"path": tmp, "loc_limit": 50, "extensions": "md"}))
        assert data["extensions"] == [".md"], data
        assert data["files_scanned"] == 1, data
        assert data["over_limit"] == 0, data


def test_format_profile_renders():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        rendered = c.format_profile(c.repo_profile({"path": tmp}))
        assert "Python" in rendered
        assert str(root) in rendered
        # Unparseable input falls through untouched rather than raising.
        assert c.format_profile("not json") == "not json"


def test_slash_command_wiring():
    """The /cartographer handler must dispatch repo_profile and render a table."""
    import importlib.util
    import types

    parent = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(parent))
    pkg = types.ModuleType("rc_plugin")
    pkg.__path__ = [str(parent)]
    sys.modules["rc_plugin"] = pkg
    spec = importlib.util.spec_from_file_location("rc_plugin.__init__", parent / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rc_plugin.__init__"] = mod
    spec.loader.exec_module(mod)

    calls = []

    class FakeCtx:
        def dispatch_tool(self, name, args):
            calls.append((name, args))
            return c.repo_profile({"path": ".", "top": 3})

    out = mod._handle_slash(FakeCtx(), ".")
    assert calls and calls[0][0] == "repo_profile", calls
    assert "Python" in out or "files" in out, out


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
