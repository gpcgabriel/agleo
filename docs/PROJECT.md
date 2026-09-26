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

Two gaps to be aware of:

* `tests/test_ollama_manager.py` is written for pytest fixtures and has no
  `__main__` block, so its 9 tests **never run**. Either port them to
  `run_module_tests` or delete them; silently dead tests are worse than none.
* `tests/test_ui_interaction.py` needs `playwright`, which is not installed, so
  no interface test runs today.

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
* **Streamlit's `data-testid` values changed.** Rules written against
  `element-container` match nothing; the current testid is `stElementContainer`
  and `element-container` is now a class.
* **`within_range` and `calculate_distance` divide altitudes by 1000.**
  Altitudes are already in kilometres, so the vertical leg of the slant range
  collapses and a satellite overhead reads as if it were on the ground. Two
  occurrences in `leosim/components/topology.py`.
* **Users are created at satellite altitudes.** `dataset.create_users` samples
  positions from `Satellite.coordinates_trace`, altitude included, so users
  orbit instead of standing on the ground.
* **`User.export()` omits `max_connection_range`.** The scenario round trip
  resets 1500 km to the 300 km constructor default — smaller than any
  satellite's altitude, so with correct geometry a user could never see one.
  Same defect class as the lost `name` on `Satellite`.
* **`leosim/components/mobility_models/` is the live one.** A second copy used
  to sit at `leosim/mobility_models/`, never imported and carrying bugs that
  the live copy had already fixed. It is gone; if a similar pair appears,
  `leosim/components/__init__.py` says which one wins.
* **An LLM tick costs one model call per ground station.** 26 to 28 with the
  RNP topology. Tests should not advance the clock unless that is what they are
  testing. Measured baseline in [ROADMAP.md](ROADMAP.md), Phase 3.

---

## 5. Agent behaviour

* **Informational questions must not propose actions.** When the operator asks
  "how many applications are allocated?" or "did GS 28 allocate anything?", the
  dashboard agent answers from the state summary. It does not reach for
  `propose_*` tools. Encoded in `app/agents/prompts.py`; it was a real
  complaint, not a hypothetical.
* **The agent never mutates the engine.** Every change is a typed
  `ProposedAction` behind the confirmation gate. See the action cycle in
  [ARCHITECTURE.md](ARCHITECTURE.md).
* **Never show a raw tool-call blob in the chat.** When a model emits a tool
  call as text, `app/agents/tool_call_recovery.py` parses it; on failure the
  operator gets a sentence, not JSON.

---

## 6. Streamlit specifics

* **One widget, dynamic parameters — not two widgets in `if`/`else`.** Two
  conditional `st.chat_input` calls confused Streamlit's diff and the input was
  drawn twice in the DOM. Use a single call with a varying `placeholder`,
  `disabled` and a stable `key`.
* **Check contrast on both themes.** Dark mode produced dark text on dark
  backgrounds in buttons and number inputs. Heading order (`<h1>`…`<h6>` with
  no skipped level), `role="main"` and descriptive `aria-label`s are validated
  with axe-core (`tests/axe_validation.js`).
* **`st.components.v1.html` is deprecated** after 2026-06-01 in favour of
  `st.iframe`, which rejects `height=0`. Use `height=1` plus a CSS collapse.

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
