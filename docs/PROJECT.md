# LEOSim project specifics

Everything that is true of *this* codebase and nowhere else: where the layers
are, how to run it, what already cost someone a day.

General style rules live in `CLAUDE.md` at the repository root.
What the system is lives in [ARCHITECTURE.md](ARCHITECTURE.md).
What comes next lives in [ROADMAP.md](ROADMAP.md).

---

## 1. Layers

```
leosim/       simulation engine
app/core/     application domain — no streamlit
app/agents/   LLM agents — no streamlit
app/ui/       interface — the ONLY package that may import streamlit
app.py        composition root
```

Rules:

* `import streamlit` appears only under `app/ui`. Enforced by
  `tests/test_layering.py`, which checks both the import AST and that importing
  the domain does not load Streamlit even indirectly.
* `app/core` and `app/agents` never import `app/ui`.
* Only `app/ui/state.py` knows the `st.session_state` key names.
* Handlers return an `ActionResult`; they never write to the chat or raise a
  toast themselves.
* The engine never imports the LLM stack. Strategies that need it are injected
  by the composition root: `app/ui/sidebar.py` builds the `LLMAllocator` and
  passes it to `create_session`. Enforced by `tests/test_layering.py`.

---

## 2. Running it

The interpreter with `agno`, `streamlit`, `numpy` and `geopy` installed:

```
~/.pyenv/versions/3.12.9/bin/python
```

Formatting uses a different one — `black` lives on the pyenv shims:

```bash
~/.pyenv/shims/black -l 120 app leosim tests app.py dataset.py
```

Entry points:

| Command | What it does |
| --- | --- |
| `streamlit run app.py` | the dashboard |
| `python main.py` | CLI for head-to-head runs of allocation algorithms, plots through `plot.py` |
| `python -m dataset_generator` | builds satellite traces from a public API |

---

## 3. Tests

* Everything lives under `tests/`.
* There is **no pytest dependency**. Each module is executable on its own and
  ends with:

```python
if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
```

* Run one with `~/.pyenv/versions/3.12.9/bin/python tests/test_session.py`.
* A test docstring states the invariant that must hold, not the history of a
  bug: "A satellite created by the operator must take the next internal id in
  sequence", not "Regression: it used to take the NORAD id".
* No test mocks Streamlit. If a test needs to, the layering is wrong.
* Tests that need Ollama resolve the model first and skip when it is absent.
* Avoid advancing the simulation clock in tests that do not need it; a tick
  costs several seconds of topology management.

`tests/test_ui_interaction.py` is the exception to all of the above: it drives
a real browser with Playwright and needs the app already serving, so it is not
part of the sweep and reports on its own.

```bash
# In one shell
~/.pyenv/versions/3.12.9/bin/python -m streamlit run app.py --server.port 8502
# In another
~/.pyenv/versions/3.12.9/bin/python tests/test_ui_interaction.py
```

It reads `LEOSIM_URL` and defaults to port 8502, which is what
`.claude/launch.json` starts. Playwright needs its browser downloaded once:
`~/.pyenv/versions/3.12.9/bin/python -m playwright install chromium`.

`tests/test_ollama_manager.py` is the only module that mocks anything, because
the alternative is starting and stopping a daemon. It patches with `with`
blocks rather than stacked decorators, which inject one mock per decorator in
reverse order. It also spent months running nowhere — no `__main__` block, and
three of its tests patched a package deleted in Phase 1 — so when a module is
added, check that the sweep actually picks it up.

---

## 4. Traps in this codebase

Things that have already cost time:

* **Two numbering schemes for satellites.** The internal `id` is sequential and
  assigned by the class counter; the catalog `satid` comes from NORAD.
  `export()` does not keep `name`, so the catalog id survives only in the
  `catalog_id` attribute.
* **`export()` writes `None` for empty collections**, and
  `Simulator.initialize` restores that `None`. Code touching those fields must
  tolerate it.
* **The scenario round trip is one-way.** After `Simulator.initialize` every
  link has `topology = None`, because `save_scenary` excludes `Topology`. A
  second `save_scenary` raises.
* **`Simulator.initialize` resolves callables by name** through the
  `leosim.simulator` namespace. A new mobility or allocation model must be
  exported by its package `__init__` or it silently falls back to the default.
  This is why `leosim/components/__init__.py` re-exports the failure models
  although nothing in that file uses them — the import *is* the registration.
* **Mutable default arguments** were a live bug in `Simulator.__init__`. Use
  `None` and copy inside.
* **`tick_duration` is computed and never read.** One trace step is about 60
  seconds of real time (measured against a known-interval trace); nothing in
  the code records that.
* **Coordinates are `(latitude, longitude, altitude in kilometres)`.** Ground
  stations, process units and users sit at altitude 0; satellites at 320-528.
  `within_range` and `calculate_distance` use the vertical leg unscaled. If a
  `/1000` reappears there, it is the old bug coming back, not a unit
  conversion.
* **Anything a component needs after a reload must be in its `export()`.**
  `Simulator.initialize` rebuilds each object with `set_attributes(**dict)`,
  so a field missing from `export()` silently falls back to the constructor
  default. This cost half the users their connection range for months, and
  `Satellite` still loses its `name` the same way.
* **`leosim/components/mobility_models/` is the live one.** A second copy used
  to sit at `leosim/mobility_models/`, never imported and carrying bugs that
  the live copy had already fixed. It is gone; if a similar pair appears,
  `leosim/components/__init__.py` says which one wins.
* **An LLM tick costs one model call per ground station.** 26 to 28 with the
  RNP topology. Tests should not advance the clock unless that is what they are
  testing. Measured baseline in [ROADMAP.md](ROADMAP.md), Phase 3.

---

## 5. Agent behaviour

* **The agent never mutates the engine.** Every change is a typed
  `ProposedAction` behind the confirmation gate. See the action cycle in
  [ARCHITECTURE.md](ARCHITECTURE.md).
* **Informational questions must not propose actions.** A command the router
  classifies as a question reaches the agent with **no way to act at all**
  (`DispatchToAgent.allows_changes`), rather than being asked in the prompt not
  to act. The instruction that used to do that named the tools, which is what
  handed one capability model to the other in Phase 6.
* **The shared prompt names neither mode's mechanism.** Both modes read
  `app/agents/dashboard/prompts.py`. Saying "call `propose_add_node`" made the
  model in Skills mode write that call out as text instead of opening a skill;
  `tests/test_skills.py` fails if a tool name comes back.
* **A reply is not trusted to answer the question it was asked.**
  `app/agents/allocation/decision.py` reconciles the model's lists against the
  pending applications and reports two failure modes: ids left out, which used
  to be placed nowhere and counted nowhere, and ids that were never asked
  about, which `hybrid_allocation` would place on a station's behalf outside
  its neighbourhood. This model does not reliably fill list-valued parameters
  — the same behaviour sank Skills mode in Phase 6.
* **Ollama's default context is 4 096 tokens, and both agents exceed it.**
  Nothing warns you: the prompt is truncated and the model answers half a
  question. Both set `num_ctx = 8192`. `curl -s localhost:11434/api/ps` reports
  the loaded model's real `context_length`; check it before trusting any
  measurement of a prompt.
* **Never show a raw tool-call blob in the chat.** When a model emits a tool
  call as text, `app/agents/dashboard/tool_call_recovery.py` parses it; on
  failure the operator gets a sentence, not JSON.
* **A skill script is executed directly through its shebang.** It needs `#!`
  *and* the executable bit, or agno returns `Exec format error`; and
  `#!/usr/bin/env python3` resolves to the system interpreter under pyenv, so
  `runner.ensure_interpreter_on_path` puts the running one first on PATH.
* **An LLM tick costs one model call per ground station.** 26 to 28 with the
  RNP topology. Tests should not advance the clock unless that is what they are
  testing. Measured baseline in [ROADMAP.md](ROADMAP.md), Phase 3.

---

## 6. Streamlit specifics

### Reaching Streamlit's DOM from a stylesheet

* **Streamlit renames the hooks a stylesheet grabs onto.** Two generations of
  this have bitten: `element-container` became `stElementContainer`, and every
  `data-baseweb` attribute is gone. The dark theme kept looking right because
  Streamlit's own base is dark, which is how those rules stayed dead unnoticed.
  **When a widget reverts to Streamlit's colours, read the live DOM before
  editing CSS:** the rule is probably matching nothing rather than losing a
  specificity fight.
* **CSS attribute matching is case sensitive.** `[data-testid*="user"]` does
  not match `stChatMessageAvatarUser`. Every chat bubble rule in both
  stylesheets was dead for that reason alone.
* **Some Streamlit colours are out of CSS's reach.** The slider's filled track
  is an inline `linear-gradient` whose stops Streamlit computes; the radio dots
  and checkbox ticks come from the same place. They all follow `primaryColor`
  in `.streamlit/config.toml`.
* **Setting one `[theme]` option changes all of them.** With no `[theme]`
  section Streamlit follows the browser's colour scheme; the moment one option
  is set it fills the rest from its *light* base, which turned the chat input
  and the toasts white on the dark theme. `base = "dark"` is pinned there.
* **Both themes are live and both are tested.** `apply_theme(is_dark)` picks
  between `theme_dark.css` and `theme_light.css`, and `tests/test_theme.py`
  fails if one grows a selector or a variable the other lacks. Contrast was
  measured in the browser at 36 text elements per theme, all at or above 4.5:1;
  the light theme's accent is darker than the dark theme's for that reason.
  Heading order, `role="main"` and descriptive `aria-label`s are validated with
  axe-core (`tests/axe_validation.js`).

### Where elements go, and when

* **A block that appears on only some renders shifts everything below it.**
  Streamlit addresses elements by position and appends at the new position
  instead of replacing, so the previous render stays on the page with the fresh
  one drawn underneath — two maps, two conversations. Every conditional block
  in `app.py` and in `app/ui/chat/__init__.py` gets a container created before
  anything decides whether to fill it.
* **A slot that goes through one render empty keeps what the last one put
  there.** Streamlit does not trim on the way to a rerun, so ending a render
  with `st.rerun()` before drawing a slot leaves the old contents in place.
  `main_app` draws the dashboard on every pass and leaves the reload to the
  bottom of the function.
* **One widget with dynamic parameters, not two widgets in `if`/`else`.** Two
  conditional `st.chat_input` calls confused Streamlit's diff and the input was
  drawn twice. Use one call with a varying `placeholder`, `disabled` and a
  stable `key`.
* **An indented `</div>` renders as a code block.** `st.markdown` runs through
  a Markdown parser before the HTML is honoured: an f-string whose interpolated
  line can come out empty closes the HTML block there. Build raw HTML as one
  line with no blank lines in the middle.
* **The accessibility script is destroyed and rebuilt with its iframe.** Its
  listeners are attached to elements in the parent document, so they outlive
  the realm that created them and never fire again: a guard asking "is
  something attached?" leaves the slash menu permanently dead after the first
  remount. `accessibility.js` stamps a per-load realm token. Nothing
  theme-dependent is interpolated into it for the same reason — it reads the
  palette through CSS variables, so its text stays identical between renders.
* **`st.components.v1.html` is deprecated** after 2026-06-01 in favour of
  `st.iframe`, which rejects `height=0`. Use `height=1` plus a CSS collapse.

### While work is in flight

* **Any widget touched during a render stops that render**, and every control
  is held for that reason. `controls_are_locked` in `app.py` is true while the
  dashboard agent is answering or a batch of steps is running, and it reaches
  the sidebar, the theme toggle, the timeline, the confirmation gate and the
  command field. Without it a theme toggle pressed mid-inference discarded the
  answer, and a proposal confirmed mid-run landed a second snapshot on the same
  tick — which the timeline labels `Step 4 · change 1`. The prompt is handed to
  the following render (`set_prompt_for_agent`) so the controls are drawn
  disabled before the call starts.
* **Streamlit fades an element to 0.33 while it waits for its next delta**,
  through a transition — so a `getComputedStyle` taken at the wrong instant
  reads 1 and the fade looks like it does not exist. Sample across frames with
  `requestAnimationFrame` before concluding anything about it. A run of steps
  reruns the page continuously, so the whole dashboard sat at a third of its
  opacity for the length of the run; both stylesheets hold the fade off.
* **A partially drawn page is worse than a slow one.** Skipping the dashboard
  during a run left the previous render on screen: the chat input goes with it,
  so `div.stColumn:has([data-testid="stChatInput"])` stops matching and the
  orchestrator column loses its background. It is drawn on every pass now,
  locked.
* **A step costs 0.26 s; the interface costs more than the simulation.**
  Measured with `cProfile`: a tick is 0.26 s, almost all of it `geopy`
  distances inside `within_range`, and the first tick of a session is 7.4 s,
  one off. A render pass around it is another 0.5 s, of which the Folium map is
  0.18 s to build and 158 KiB to ship. Steps therefore run in batches of one
  second per render (`STEP_BATCH_SECONDS`).

---

## 7. Where to look before starting

[ROADMAP.md](ROADMAP.md) carries the phase plan, the open issues table (C
through O) and a `Literature notes` section with cited figures for elevation
angles, SGP4 accuracy and constellation modelling.

Two phases are marked **deferred**: orbital propagation (9) and the network
model correction (10). Both were explored in September 2026 and rolled back to
keep the demonstration path clear. Their sections record what was built,
measured and learned, so resuming them starts from evidence rather than from
scratch.

The current priority is phases 3, 4 and 5 — the context load on the ground
stations' models, the orchestrator, and intent-driven runs.
