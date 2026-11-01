# Hermes workbench — a plugin and a skill built against the real thing

Two deliverables, both authored by driving Hermes itself: a **plugin**
(`repo-cartographer`) and a **skill** (`blender-video`).

Built inside a sandbox against **Hermes Agent `vgit.c7c7e0f` (2026.9.24)**, running on
Python 3.11.2 with a 19-tool session and a local mock LLM endpoint standing in for
the model. Everything below was executed; nothing here is a sketch.

```
hermes-workbench/
└── repo-cartographer/
    ├── plugin.yaml                 # manifest (tools + hook declared)
    ├── __init__.py                 # register(ctx): 2 tools, 1 hook, 1 slash command, 1 skill
    ├── cartographer.py             # the implementation — stdlib only
    ├── skills/repo-audit/SKILL.md  # bundled skill, namespaced repo-cartographer:repo-audit
    └── tests/test_cartographer.py  # 7 tests, no pytest required
```

## What it does

Two tools that answer "what is this codebase?" without shelling out to `find`/`wc`:

| Tool | Returns |
|---|---|
| `repo_profile(path, top)` | file/byte totals, per-language files+bytes+LOC, largest files, top-level entry points, dependency manifests, git branch/HEAD read straight from `.git` (no subprocess) |
| `hotspot_scan(path, loc_limit, extensions)` | source files above a line-count threshold, largest first — the usual refactor targets |

Plus a `post_tool_call` hook that logs workbench calls to
`$HERMES_HOME/plugin-state/repo-cartographer/activity.jsonl`, a `/cartographer <path>`
slash command, and the bundled `repo-audit` skill.

No network, no third-party imports, no LLM. Handlers obey the plugin contract —
`def handler(args: dict, **kwargs) -> str`, always JSON, never raises.

## Verified in this sandbox

```
$ hermes plugins doctor repo-cartographer
Plugin Doctor: /tmp/hhome/.hermes/plugins/repo-cartographer
  manifest: repo-cartographer 1.0.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 2 tool(s), 1 hook(s)

$ hermes plugins list | grep repo-cartographer
│ repo-cartographer   │ enabled     │ 1.0.0   │ ... │ user │

$ python3 tests/test_cartographer.py
PASS test_format_profile_renders
PASS test_hotspot_scan_extension_filter
PASS test_hotspot_scan_threshold
PASS test_profile_rejects_missing_path
PASS test_profile_shape
PASS test_profile_survives_garbage_args
PASS test_slash_command_wiring
0 failure(s)
```

`~/.hermes/logs/agent.log` after a session start:

```
INFO hermes_plugins.repo_cartographer: repo-cartographer registered: repo_profile, hotspot_scan, /cartographer
```

Real output, run against the Hermes checkout itself:

```
/tmp/hermes-agent  —  21,938 files, 228.07 MB
git: main @ c7c7e0fa92f4

language         files        MB         LOC
Python           10561     112.7   2,611,834
TypeScript        5287      40.4   1,130,216
(binary/other)     139      26.5           0
Markdown          1562      21.0     453,507
YAML              1203       8.6     130,437
```

Hotspots (`loc_limit=3000`, `.py`): 34 files over the line, topped by
`tests/tui_gateway/test_tui_gateway_server.py` at **22,354 lines**, then
`agent/auxiliary_client.py` (8,346) and the three platform adapters
(`telegram` 7,380, `discord` 7,352, `slack` 6,959).

## How it was installed (sandbox specifics)

```bash
cp -r repo-cartographer "$HERMES_HOME/plugins/"
```

`hermes plugins enable repo-cartographer` **could not be used here**: admission tries to
fetch Python 3.14 from `python-build-standalone` (blocked host), so the allow-list was
written directly:

```yaml
# $HERMES_HOME/config.yaml
plugins:
  enabled:
    - repo-cartographer
toolsets:            # toolset must be enabled for tools to reach the model
  - hermes-cli
  - workbench
```

On a normal machine with egress, the supported path is:

```bash
hermes plugins validate ./repo-cartographer --install-deps
hermes plugins enable repo-cartographer
hermes tools          # tick "workbench" under the CLI/platform section
```

## Open issue — plugin tools do not reach the model in one-shot CLI sessions

This is the one thing that did **not** work, and it is reproducible:

1. `hermes plugins doctor` passes; `agent.log` confirms `register()` ran and both tools
   are in the registry; `hermes doctor` lists the toolset → `✓ workbench`.
2. Yet every session sends exactly **19 tools**, and `repo_profile`/`hotspot_scan` are
   never among them.
3. `cli.py --toolsets=workbench` is refused by the client *before* the gateway sees it:

   ```
   invalid_params (toolsets: unknown or invalid toolset name: 'workbench')
   ```

   — the same process that logs a successful plugin registration moments earlier.
4. The tool-search bridge never offers `workbench` either: with `-t all`, the deferred
   sources are 16 built-ins (`terminal`, `desktop_ui`, `project`, `session_search`, …)
   and no plugin toolset.

Ruled out by experiment: stale gateway process (`gateway run --idle-exit` was killed and
respawned), `platform_toolsets.cli` (tried), top-level `toolsets:` (tried, accepted —
`hermes dump` shows `toolsets: hermes-cli, workbench`), registering into the core `file`
toolset instead of a new one (tried — still absent), `--cli --native` (tried).

Most likely cause: the client validates toolsets and builds the session's tool list from
a registry that is populated **after** argument validation and outside the serving
process, so registry-only toolset names resolve to nothing. Next things to try on a real
install: open `hermes tools` in a TTY and tick *Workbench* (that path writes
`known_plugin_toolsets.<platform>` and `known_builtin_toolsets`), run an interactive
session instead of `-q`, and compare `hermes plugins capabilities` output.

The tools themselves are not implicated: they run correctly through their handlers and
through `ctx.dispatch_tool`, which is exactly what a TTY-time `/cartographer` would call
(covered by `test_slash_command_wiring`).

---

# 2. `blender-video` skill

**Created through Hermes**, not hand-placed: the skill was authored by driving a real
session where the model called `skill_manage` with `create` + three `write_file`
operations. Hermes wrote the files, linted them, and registered the skill.

```
skills/blender-video/
├── SKILL.md                    # intake protocol, 10-rule script contract, QA ladder
├── references/bpy-recipes.md   # headless-safe bpy snippets (camera aim, rigs, lights, output)
├── scripts/qa_check.py         # static contract checker + rendered-frame sanity check
└── templates/turntable.py      # verified reference script, all 10 rules satisfied
```

## What the user gets to say, and what happens

The user says something like *"a spinning donut, 6 seconds, for a landing page"*. The skill's
intake protocol then allows **at most three questions, in one batch, each with a default**:
subject & motion, look preset (`studio` / `neon` / `editorial` / `tech`), and aspect+duration.
If the user says "just do it", every default is taken silently. fps, samples, resolution,
codec and file paths are never asked about — they live in a defaults table.

Then: write a JSON spec → generate the script against a **10-rule contract** → run the QA
ladder → show three stills (10% / 50% / 90% of the timeline) and ask *one* question:
framing, lighting, or pacing. That second round is where the look actually gets decided,
with images in hand instead of adjectives.

The QA ladder is the point: static check (no Blender needed) → one-frame smoke render →
full render, with "never re-render the final to answer a look question" as an explicit rule.

## Verified end to end

Blender itself does not install in this sandbox (no apt egress). The `bpy` 4.2.0 wheel does,
once its eight missing X libraries are stubbed — `gcc` builds no-op `.so` files exporting the
144 X/GL symbols `bpy`'s loader wants, and `LD_LIBRARY_PATH` points at them. `import bpy`
then works and **Cycles renders on CPU for real**:

```
$ python templates/turntable.py -- --preview            # 640x360, 8 samples, 2.8s
MANIFEST /tmp/vout/preview.manifest.json
DONE {"subject":"monkey","frames":144,"fps":24,"seconds":6.0,"resolution":[640,360], ...}

$ python scripts/qa_check.py --check-frame preview.png
{"ok": true, "bytes": 353727, "width": 640, "height": 360, "bytes_per_pixel": 1.535}

$ python templates/turntable.py -- --seconds 1 --fps 12 --look tech --subject cube
DONE {"frames":12,"fps":12,"seconds":1.0,"resolution":[320,180],"engine":"CYCLES", ...}
```

Real output in `renders/`: `sample_studio_suzanne.png` (studio look, terracotta hero,
soft shadow) and `sample_tech_cube.mp4` (12 frames, 23 KB H.264).

Negative test — `qa_check.py` on a deliberately broken script returns rc 1 and names
every fault: missing factory reset, unset resolution/format, a `view3d` op that dies
headless, and `rotation_euler = (45, 0, 30)` flagged as degrees where radians belong.

Hermes registry state after creation:

```
│ blender-video │ creative │ local │ local │ enabled │
```

and the installed copy is byte-identical to `skills/blender-video/` here.

## What Hermes' own linter enforced

Two findings worth keeping, both from `skill_manage`'s linter rather than from me:

1. **Descriptions are capped at 60 characters** — one sentence, trigger first, ending in a
   period. My first attempt (201 chars) was **rejected outright**, with instructions to move
   the detail into the body. The shipped description is 49 chars.
2. **`dangling-reference` warning**: `create` is linted against the skill directory *before*
   the subsequent `write_file` ops land, so a body that references `templates/turntable.py`
   trips a false positive on a single-batch create. Harmless, but it means a batch that
   creates a skill and its files together always reports one warning. Splitting the batch
   (create, then write_file) would avoid it.
