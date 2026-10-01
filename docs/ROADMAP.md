# AGLEO Roadmap

Where the project stands and what comes next. The long-term goal is an
**agentic-defined simulation**: ground stations that decide locally, an
orchestrator above them that ties those decisions to operator intent, and a
dashboard agent that puts a network manager in the loop.

**Where it stands (30 September 2026).**

| | |
| --- | --- |
| Phases 1, 2 | done — layering, and an engine that no longer imports the LLM stack |
| **Phase 3** | **frozen**: a tick is 47% faster with the allocation outcome unchanged |
| **Phase 6** | **closed**: `llama3.1:8b` cannot pass arguments to a skill, so function calling is the capability model |
| Phase 4, 5 | designs settled, not built. The next work |
| Phases 7, 8 | supporting: one process many simulations, and an experiment harness |
| Phases 9, 10 | explored and **deliberately deferred**; both change simulation results |

**Demonstration scope, settled 26 September 2026: Phase 3 alone, done well.**
The number that tells the story is model calls per tick, before and after, with
the allocation outcome unchanged.

Two things are deliberately unfinished inside Phase 3 and are the first
candidates when it reopens: the **stability filter**, which is blocked on the
history question, and the **evaluation arm against `best_fit`**, which needs
Phase 8 and a metric that separates the strategies (threat 3).

What was learned while exploring the deferred phases is recorded in their
sections and in [Literature notes](#literature-notes), so none of it has to be
rediscovered.

---

## Phase 1 — Decoupling and structure — **done**

The application was one layer where Streamlit, the LLM agent and the simulation
engine all called into each other. It is now four, with one enforced rule:
**`streamlit` may only be imported inside `app/ui`** (`tests/test_layering.py`).
`app.py` went from 600 lines to a composition root; the layers are listed in
[PROJECT.md](PROJECT.md).

What the refactor put in place, and why each matters later:

* `SimulationSession` owns the simulator, history, viewed index and scheduled
  steps — four loose `st.session_state` keys became one object.
* `SimulationConfig` replaced six positional arguments passed hand to hand.
* `ProposedAction` — typed `ActionType` plus a validated payload — replaced a
  free dictionary with no schema. Every agent change goes through it.
* A ~140-line if/elif over action strings became six handler modules and a
  three-line dispatcher.
* `SatelliteCatalog` indexes the traces file once instead of reparsing per
  lookup: building a 15-satellite scenario went from ~7 s to ~0.4 s.

**Behaviour changes that outlived the refactor.** The selected scenario now
reaches the allocation algorithm — it was collected in the sidebar and dropped,
so every run had been `hybrid` whatever the operator picked. Step 0 shows real
connectivity instead of every user disconnected. `add_*` actions no longer
consume a tick; they refresh connectivity and record a snapshot, so a change
and a tick are no longer the same event on the timeline.

---

## The system the phases are building

Settled 29 September 2026. A network manager needs data about an
infrastructure but does not know how to run a simulation — which metrics to
collect, for how long, what to hold constant. AGLEO is what the answer is.

They choose one of two paths.

```
                            ┌─────────────────────────────┐
                            │  automatic  or  step by step │
                            └──────────────┬──────────────┘
                     ┌─────────────────────┴─────────────────────┐
                     │                                           │
              STEP BY STEP                                 AUTOMATIC
                     │                                           │
   operator gives dataset, trace, topology      operator gives the objective, and
                     │                          optionally dataset, trace, topology,
                     │                          number of runs, step budget
                     ▼                                           ▼
   simulation starts, live map beside a          the orchestrator configures and
   chat with the orchestrator agent              runs it under those directives
                     │                                           │
   operator drives the infrastructure and        it stops when it judges the
   the steps until satisfied                     objective met
                     │                                           │
                     └──────────────► metrics ◄──────────────────┘
```

### What exists today

Only part of the step-by-step path. The operator picks dataset, trace and
topology in the sidebar, the map renders live, and the dashboard agent takes
commands behind a confirmation gate. What is missing from that path is the
agent being an *orchestrator* rather than a proposer of single mutations.

The automatic path does not exist at all: there is no objective as a
first-class object, no unattended run, and no stopping criterion the agent can
evaluate. That is Phase 5.

### What the demonstration covers

**The ground station agent is the only agent inside the simulation.** The
orchestrator and the automatic path are not part of the demonstration; the
demonstration is Phase 3 — the tick made affordable, measured before and after.


---

## Threats to validity

### 1. The station's decision moves under perturbations that carry no information

Re-asking at an unchanged state returns a different answer about **39%** of the
time. Adding a line to the prompt that carries no new information moves the
answer in 5 of 6 stations. One model, one scenario, 68 decisions — it says
something about this deployment, not about LLM allocation in general.

**Why it threatens the work.** The claim under test is that a localized agent
decides something. If the answer moves under a no-op, part of what is being
measured is noise, and no prompt change can be read as causal.

**Partly acted on.** The 19% of decisions that used to vanish silently — the
model omitting applications from both strategy lists — is issue Q, fixed
30 September 2026 and now counted in the metrics. What remains is the
sensitivity itself. Before the result is quotable it needs more than one model,
more than one scenario, and the three-arm history experiment in Phase 3.

### 2. The model does not fit in the GPU

`llama3.1:8b` runs about half in VRAM and half on CPU on a GTX 1650 with 4 GB.
Every wall-clock number in Phase 3 is therefore a property of *this*
deployment. The *ratios* — 82% less prompt, 47% less wall clock — are the
transferable part; the absolute seconds are not. A model that fits entirely in
VRAM would move the floor, though not necessarily as much as expected:
`qwen3:1.7b` at 100% VRAM took **204 s per call**, because it is a reasoning
model and spends the call emitting thought. Fitting in VRAM does not determine
speed; `think: false` is set for that reason.

### 3. "Applications placed" does not measure what the agent decides

Forcing every application through `hybrid_allocation` with one fixed strategy
gives the same count either way — 18, 19, 19 over three ticks for `best_fit`
and identically 18, 19, 19 for `longest_duration` — while **7 of 20
applications land on a different process unit**. The strategies differ in
*where* an application goes, not in *whether* it goes anywhere, so counting
placements cannot tell them apart, and an agent whose job is choosing between
them cannot be evaluated by it.

A second confound sits next to it: the full `best_fit_allocation` and
`longest_duration_allocation` place 6.3 and 11.5 applications per tick, but
that gap is their own selection and deprovisioning logic, which
`hybrid_allocation` does not run at all.

**What is needed before anything can be concluded about whether the agent pays
for itself:** a metric that separates the strategies — service continuity and
migration count for `longest_duration`, unit fragmentation for `best_fit` — and
arms that differ in one thing, with the deterministic baselines applying their
strategy through the same path the agent's decision takes.

---

## Known issues carried into the next phases

| # | Issue | Addressed in |
| --- | --- | --- |
| ~~A~~ | ~~`leosim` imports `agno`~~ — resolved in Phase 2 | done |
| ~~B~~ | ~~`resource_management_algorithm` is ~250 lines with three parsing fallbacks~~ — resolved in Phase 2 | done |
| C | Agent-added satellites get a compacted trace and teleport between orbital passes | Phase 9 |
| D | `tick_duration` is computed and never read; one trace step is ~60 s of real time, recorded nowhere | Phase 9 |
| ~~E~~ | ~~Selecting the "Skills" agent mode raises `TypeError`; no skill has ever been written~~ — fixed 29 September 2026: five skills, one per action | done |
| F | `ComponentManager.model` is a global singleton; two simulations cannot coexist in one process | Phase 7 |
| G | `refresh_connectivity` reproduces the scheduler's ordering outside the engine | Phase 7 |
| H | Tick correctness is untested — tests assert the clock advances, not that allocation is right | Phase 8 |
| I | The scenario round trip is one-way: after `Simulator.initialize` every link has `topology = None`, so a second `save_scenary` raises and a running simulation cannot be checkpointed | Phase 8 |
| J | Users attach directly to ground stations, a path that does not exist in a LEO architecture | Phase 10 |
| ~~K~~ | ~~The altitude difference is divided by 1000~~ — fixed 28 September 2026. It was **five occurrences across four files**, not the two in `topology.py` this table claimed | done |
| ~~L~~ | ~~Users are created at satellite altitudes~~ — fixed 28 September 2026 | done |
| ~~M~~ | ~~`User.export()` omits `max_connection_range`~~ — fixed 28 September 2026 | done |
| N | A gateway accepts every satellite in range; real gateway earth stations serve 8 (Gen1) to 32 (Gen2) at a time | Phase 10 |
| O | An LLM tick costs one model call per ground station — 28 with the RNP topology, minutes of wall clock | Phase 3 |
| P | The slant-range formula is written five times: `Topology.within_range`, `Topology.calculate_distance`, `hybrid_allocation.distance`, `longest_duration_allocation.distance` and `state.find_reachable_satellite_ids`. This is what let issue K survive a fix | open |
| ~~Q~~ | ~~The model omits applications from both strategy lists, and `hybrid_allocation` never looks at them~~ — fixed 30 September 2026. `reconcile` matches the reply against the question; omissions and invented ids are counted, logged and carried into the metrics | done |

### The triage

Re-verified against the code on 28 September 2026 and updated as issues closed.
This is a standing list, not permission to fix anything.

**Cheap and low risk, still open:**

| # | Cost | What it changes |
| --- | --- | --- |
| P | ~30 min | one slant-range formula instead of five. This is what let K survive a fix |
| D | a field in the snapshot | records that one step is ~60 s of simulated time, which nothing does today |

**Fixable, but each carries a design decision rather than a correction:**
J (removing the user-to-ground-station link changes the network model, which is
what Phase 10 is about), N (a gateway cap needs a number — 8 for Gen1, 32 for
Gen2 — and a policy for the satellites turned away) and I (a symmetric round
trip means deciding how `Topology` is serialized).

**Blocked on a phase:** C and D on Phase 9, F and G on Phase 7, H on Phase 8.

### Why K, L and M had to move together — and what it invalidated

Fixed 28 September 2026. K was worse than the table said: it listed "two
occurrences in `topology.py`" and there were **five, across four files**, three
of them in the allocation path itself. Fixing only the engine pair would have
left the agent and the engine disagreeing about what is in range, which is
worse than both being wrong the same way. That the formula lives in five places
is now issue P.

Measured across all eight combinations, averaged over five ticks:

| K | L | M | Connected users | Provisioned |
| --- | --- | --- | --- | --- |
| — | — | — | 11.4/20 | 2.2 |
| **x** | — | — | 6.0/20 | **0.0** |
| — | — | **x** | 20.0/20 | 9.8 |
| **x** | **x** | **x** | 20.0/20 | 9.8 |

Correcting the slant-range geometry (K) without restoring the user's reach (M)
takes provisioning to **zero**: with honest geometry and a 300 km reach, no
user can see a satellite at 320-528 km. M was the fix that mattered; K and L
were free once M was in, and they make the model physically honest rather than
accidentally correct.

**This invalidates every allocation result recorded before that date**,
including the first Phase 3 baseline: they were measured on a network where
most pending applications belonged to users with no access point at all.

---

## Phase 2 — Engine purity — **done**

**Goal:** `leosim` stops depending on the LLM stack.

The engine no longer imports `agno` or knows what a model is. The allocation
strategy arrives as a plain callable with the same signature as the built-in
algorithms, and the composition root assembles it: `app/ui/sidebar.py` for the
dashboard, `main.py` for the CLI. `LLMAllocator.allocate` lives in
`app/agents/allocation/` and is injected, which is what lets the same simulator
run with `best_fit_allocation` or with a model behind it and nothing else
change.

**The cost this exposed** is Phase 3's subject: one model call per ground
station per tick, which the engine now performs faithfully instead of silently
skipping.

---

## Phase 3 — Ground station agent context

**Goal:** make an LLM tick affordable. This is the first of the three problems
the thesis is actually about.

### Frozen, 30 September 2026

Closed for the demonstration. A tick is **47% faster with the allocation
outcome unchanged**, which is the shape the demonstration asks for: cost before
and after, with provisioning held constant.

| Per tick, `llama3.1:8b`, 3 ticks per arm | Global question | Scoped | Scoped + digest |
| --- | --- | --- | --- |
| Model calls | 19.7 | 20.7 | 20.0 |
| Applications asked about | 164.7 | 101.7 | 101.7 |
| Prompt tokens per call (~) | 876 | 804 | **152** |
| Wall clock | 579.5 s | 531.0 s | **308.4 s** |
| Distinct applications placed | 13.3 | 13.0 | 13.0 |

Two things were deliberately left undone rather than rushed: the **stability
filter**, because building it forces the history question below, and the
**evaluation arm against `best_fit`**, which belongs with the harness of
Phase 8 and measures a different claim — whether the agent decides *well*, not
whether it decides *cheaply*.

**Issue Q was closed first.** A reply that omitted applications left no trace,
so 19% of decisions were invisible and every number above described a sample
with a hole in it.

### The problem, and the baseline it started from

`LLMAllocator.allocate` runs once per ground station per tick: **26 to 28 model
calls per step** on the RNP topology. Assembling the state costs 0.1-0.6 s for
all 28 stations, so the state builder was never the bottleneck.

| Users / satellites | Stations asked | Prompt tokens, median | Tokens per tick |
| --- | --- | --- | --- |
| 20 / 15 (dashboard default) | 26 of 28 | ~1 140 | ~28 000 |
| 60 / 50 | 28 of 28 | ~2 510 | ~63 000 |
| 100 / 100 | 28 of 28 | ~3 600 | ~89 000 |

A single prompt was never what breaks a small model. The cost is that the same
work happens 26 to 28 times per step, and that number barely moves with
scenario size while the prompt triples.

### Decisions that still bind

**Scope the question before caching.** The pending application list was built
once for the whole network and handed to every station: 26 of 26 received an
identical list, so a station in Porto Alegre was choosing a strategy for users
it could never serve. Caching over that is worthless — the list changes
whenever anything is placed anywhere, and the hit rate was **1.8%** once issue M
was fixed. Scoped to what a station could plausibly serve, the same key reaches
**22.3%**.

**Scoping was a negative result on cost and is kept anyway.** Measured: 8.4% of
wall clock, and the call count went *up* (19.7 → 20.7), because the "skips" in
the global arm were an accident of visit order rather than a property of the
question. It stays because **the localized decision the thesis is about did not
exist before it** — there were 26 answers to one global question.

**Batching stations into one call stays rejected.** It merges the local
decisions the thesis argues should be local.

**Summarization and policy are absorbed into Phase 4.** Under the settled
orchestrator design the station receives a digest and answers a closed
question, which is both, arrived at through the architecture.

### The digest, and what it taught

`app/agents/allocation/digest.py` renders the same decision-relevant facts as a
table instead of JSON: 2 642 characters became 473, a **−82%** reduction that
landed within a point of the estimate. The module translates and does not
decide — the moment it sorts, scores or omits a candidate, the station agent
stops deciding and starts rubber-stamping.

**The projection was wrong by a factor of three, and the reason matters.** A
linear fit of elapsed time against prompt length (`t = 1.03 s + 7.89 s per
1000 chars`, r = 0.98) predicted 99 s per tick. The measurement gave 308 s. The
fit was taken over prompts of 931 to 12 943 characters and the digest is 574:
**below the measured range a per-call floor appears that the fit had attributed
to slope.**

| Applications in the call | Calls | Median time |
| --- | --- | --- |
| 1-3 | 15 | **14.0 s** |
| 4-8 | 8 | 18.9 s |
| 9-20 | 13 | 18.7 s |

Fourteen seconds for the smallest possible question. At 20 calls per tick that
is a 280 s floor, and the digest brought the tick to 308 s — within 10% of it.
The extrapolation was labelled a projection when it was made, which is why it
was scheduled for confirmation rather than quoted as a result.

**Prompt size is no longer the lever; the number of calls is.** Two things act
on it: a stability filter, since the digest's facts repeat 19.2% of the time
between ticks where the raw JSON state repeated **0.0%**; and a smaller answer,
since time still correlates with the application count (r = 0.70) at constant
prompt length, because the reply is two lists of ids that grow with it.
Phase 4's design — one option out of a fixed set — collapses that reply to a
single token's worth of choice, which is also what makes a typed-decision model
such as Jev interesting: its published 70-500 ms attacks this floor, not prompt
size.

### The history section — **open, not decided**

The prompt carries the station's own past decisions, and that section grows
after every answer, so even at unchanged infrastructure the prompt differs
between ticks and a filter keyed on infrastructure alone would reuse a decision
the agent might have revised.

**The case for dropping it.** Re-asking at an unchanged state returns a
different answer about 39% of the time, for no reason a reader could defend.
Without the section the prompt becomes a pure function of the infrastructure,
which makes the filter's key exact rather than approximate.

**The case against.** Reading one's own past decisions and their outcomes is
close to the definition of an agent that improves — *if I chose X and it went
badly, I should try Y*. Removing it removes the mechanism the design exists to
demonstrate, on the strength of a measurement that says the mechanism is not
working *today*, with *this* model.

**The question underneath.** Adding anything to the prompt moves the answer,
even when it carries no new information. So the 39% does not distinguish

* the history section being **badly structured** — a list of ids and counts,
  with no statement of what went wrong or what to do differently; from
* the small model being **too unsteady for any prompt content to be
  attributed**, in which case the whole project rests on a base where no prompt
  change can be read as causal.

The second reading is the serious one and nothing measured so far separates
them. **What would:** three arms at a fixed infrastructure, same model, same
seed — no history, the history as written today, and a history rewritten to
state outcomes rather than list ids. If the rewritten arm wins, the section was
badly structured. If all three sit inside the no-op noise band, the model is
the problem and the thesis has to say so.

Until then the section stays as it is. The stability filter is not built, and
building it is what forces the decision.

### What it means for the thesis

If a station's answer moves under a no-op perturbation, then some of what "the
ground station decided" is measuring is noise. Two things follow:

* **The evaluation baseline stops being optional.** The arm that matters is the
  per-station model against deterministic `best_fit`.
* **It sharpens the case for a calibrated, typed-decision model.** A closed
  output set cannot silently omit an application — the exact failure issue Q
  documents — and a confidence score would distinguish a station that is
  genuinely indifferent from one that is merely unsteady.

### How to measure

Record per tick: model calls, prompt length in characters and tokens, wall
clock, and allocation outcome (provisioned / failed / omitted). Any reduction
has to be shown not to degrade allocation quality, so the outcome is recorded
alongside the cost. `app/agents/allocation/metrics.py` writes one row per
station visit and `summarize_by_step` aggregates them.

---

## Phase 4 — The multi-level orchestrator

**Goal:** the research contribution, and the second of the three core problems.

Three levels, each with a different scope:

| Level | Sees | Decides |
| --- | --- | --- |
| Ground station agent | its own neighbourhood | how to place the applications it is responsible for |
| Orchestrator | every station's decision and the operator's objectives | policy, conflicts, and what each station should optimize for |
| Dashboard agent | the operator | turning intent into a run, and results into an answer |

### What exists already

Phase 2 left the pieces in place. `LLMAllocator.allocate(model, parameters)`
has the same signature as any allocation algorithm, so the engine injects it
without knowing it talks to a model, and the composition root
(`app/ui/sidebar.py`) assembles it. A second level slots in the same way: an
orchestrator is another injected strategy, one that consults the stations
rather than replacing them.

`LLMAllocator` already keeps `decisions_by_station`, so the history an
orchestrator needs in order to reconcile is being recorded.

### Decided design: the orchestrator chews, the station chooses

Settled 26 September 2026. The orchestrator runs **before** the stations, and
its job is not to command them — it is to **prepare what they need in order to
decide**.

```
operator intent
      |
      v
  ORCHESTRATOR          global view; turns the intent into one digest of
      |                 the infrastructure and a closed question
      |  the same digest + options, to every station
      v
  GROUND STATION x N    local view; each answers with one of the options,
      |                 or says it is indifferent
      |  choices
      v
  DETERMINISTIC CODE    applies each choice to that station's pending apps
      |
      v
  ORCHESTRATOR          keeps (digest, choices) as the record of the round
```

Two properties follow, and they are what make the design worth building:

1. **The station's input shrinks by construction.** It receives a digest the
   orchestrator already reduced, not the network JSON for its neighbourhood.
   Summarization is the architecture rather than an optimization bolted on.
2. **The station's output space is closed.** One option out of an enumerated
   set — `best_fit`, `longest_duration`, or an explicit **agnostic**. Cheap to
   generate, trivial to validate, and a closed set cannot be under-filled,
   which is the failure mode issue Q and Phase 6 both found.

**Agnostic is not a failure mode.** It tells the orchestrator which decisions
the local level genuinely constrains and which it does not, which is the
thesis's central claim made falsifiable. It also doubles as conflict
prevention: a station that does not care is a station that will not fight over
a process unit.

### The constraints that make or break it

**One digest, not one per station.** The orchestrator emits a single overview
and sends the same one to every station. Emitting N tailored digests would need
the whole network state in and a long structured reply out, moving the context
problem up a level instead of removing it. A side effect worth measuring: the
28 station prompts then share a byte-identical prefix, so a server reusing a KV
cache across requests pays for it once.

**The digest must be a summary, not a serialization.** A global view written as
JSON is larger than the local neighbourhood JSON it replaces, and the cure
becomes the disease. `app/agents/allocation/digest.py`, built in Phase 3, is
the shape to reuse: 2 642 characters of JSON became 473.

**The orchestrator asks only the stations that are involved**, by the same rule
Phase 3 established — a station that cannot serve an application has no
business being asked about it.

**Ground station agents are built on function calling, not skills.** Phase 6
measured the alternative: the model that will run them cannot pass arguments to
a skill.

### Still open

1. **How do two stations claiming the same process unit resolve?** Agnostic
   answers shrink the conflict set but do not empty it. Deterministic
   arbitration is cheaper and more defensible than asking a model a second
   time. Undecided.
2. **What does the orchestrator get compared against?** Three arms:
   deterministic `best_fit`, per-station LLM *without* orchestrator, and the
   orchestrator. **The middle one is the comparison that matters** — it
   isolates the orchestrator's contribution from the contribution of merely
   using a model.

### Cost

The call *count* barely moves: one orchestrator call plus the same per-station
calls. What changes is the price of each. The station's prompt drops from a
neighbourhood digest to a question with a handful of options, and its output
from a list of ids to one token's worth of choice — which is the lever Phase 3
identified, since the remaining cost is per-call overhead and reply length, not
prompt size. The orchestrator's own call is the expensive one, and keeping it
bounded is what open question 1 is about.

Measurable only against the Phase 3 baseline, which is why Phase 3 came first.

---

## Phase 5 — Intent-driven simulation

**Goal:** the operator states a scenario and its objectives; the dashboard
agent configures, runs and reports. The third of the three core problems.

Today the operator drives the simulation one action at a time: initialize in
the sidebar, ask for steps, confirm each proposal. Every action is a single
mutation behind a confirmation gate.

### What it needs

1. **An intent as a first-class object.** A `SimulationIntent` holding what to
   simulate (scenario, constellation size, users, duration) and what to
   optimize or report. Validated the way `SimulationConfig` is.
2. **Intent to configuration.** The dashboard agent already proposes typed
   actions; it needs one that proposes a whole run rather than a single
   mutation — configuration plus a step budget plus the metrics to collect.
3. **A run that completes unattended.** `session.run_next_pending_step()`
   already consumes steps one at a time under a UI loop. An intent-driven run
   needs the same for a long horizon, with progress and an abort, and without
   a confirmation gate per step.
4. **A report at the end.** Collected metrics summarized back into the chat —
   which is `summarize_snapshot` generalized from one snapshot to a run.

### Decided: the operator picks the mode

Settled 26 September 2026. The confirmation gate exists so the agent never
mutates the engine without consent, and an intent would authorize a whole run
in one approval. Rather than choosing one, the run carries a mode the operator
sets:

| Mode | The gate | When it fits |
| --- | --- | --- |
| **Single plan** | the agent turns the intent into a concrete plan — scenario, step budget, metrics — and the operator approves that plan once; the run then executes with progress and an abort | running an experiment to completion |
| **Step by step** | unchanged: every mutation is confirmed individually in the dashboard | exploring, teaching, debugging a scenario |

What is approved in single-plan mode is the **plan, not the sentence**. The
operator consents to something specific and checkable, and a misread intent is
caught before minutes of simulation are spent rather than after.

Builds on Phase 4: an intent that mentions objectives has to reach something
that reconciles them across stations.

---
## Phase 6 — Agent capability model: Tools vs Skills — **closed**

**Goal:** make the second agent mode real, so the two ways of giving an agent
capabilities can be compared rather than assumed.

### Conclusion, 30 September 2026

**`llama3.1:8b` fails consistently at passing arguments to a skill.** It names
the skill and the script correctly and then omits the argument list, so the
script runs bare and proposes nothing. Six runs out of six, at both context
sizes, with terse skill documentation and with exhaustive skill documentation.
Function calling, given the same commands, is 6 of 6 correct.

**The scope of that claim is one model.** It says what this SLM does, not what
progressive disclosure costs in general. Repeating these runs across more
models — and at least one materially larger — is what would turn it into a
statement about the pattern. `benchmark_modes.py` takes `--model`, so the
experiment is one flag away from being repeated; that is why the skills, the
harness and this section are kept rather than deleted.

**What it means for Phase 4.** It was to be decided here whether the
orchestrator's ground station agents should be built on skills or on function
calling. They should be built on function calling: the model that will run them
cannot pass arguments to a skill.

### The evidence

Eighteen runs, three commands, two context sizes — 113 characters against
10 361, the same command in the same wording both times.

| Arm | Short context | Full context |
| --- | --- | --- |
| Tools | **3/3** | **3/3** |
| Skills, terse skill docs | 0/3 | 0/3 |
| Skills, exhaustive skill docs | 0/3 | 0/3 |

**Context load is not the explanation.** That was the hypothesis going in and
the experiment refutes it: Skills fails identically at 113 characters, where
Tools is perfect and fast (29-43 s). The two documentation variants came from
two skill trees differing only in the guidance below the call shape; only the
exhaustive one is kept, the terse tree having answered its question.

**What fails is one thing.** Three of the four parameters of `get_skill_script`
arrive correct and the fourth is absent:

```
args: {'execute': True, 'script_path': 'propose.py', 'skill_name': 'add-user'}
stderr: propose.py: error: the following arguments are required: --lat, --lon
```

`args: Optional[List[str]]` is never populated. Before the skill docs spelled
the call out, the same model passed `args` as the *string* `"['/step', '3']"`.
Making the documentation explicit moved the failure from malformed to absent;
it did not fix it.

**This is issue Q one layer up.** There, the allocation agent omitted
applications from the `best_fit` and `longest_duration` lists of a Pydantic
schema — 19% of decisions. Here it omits the `args` list entirely. Two agents,
two frameworks, one behaviour: **this model does not reliably produce
list-valued parameters.** Whether it is lists specifically or optional
parameters generally is not separable here, since agno's signature is fixed and
the parameter is both; the allocation agent's lists were *required* and were
still under-filled, which favours the first reading.

**Tokens, against the calculation this phase opened with.** Progressive
disclosure costs about 950 tokens more per command at either context size —
agno's scaffold plus six skill descriptions against six tool schemas. The
calculation predicted that (~2 543 chars per call for Tools against ~3 700-4 300
for Skills) and the measurement confirms it.

| | Short context | Full context |
| --- | --- | --- |
| Tools | 1 785-1 829 | 8 811-8 855 |
| Skills | 2 729-2 790 | 9 755-9 828 |

**Where the trade would turn.** Break-even is set by how much per-action
context each capability needs. Six actions with ~1 300 characters of
instruction each fit comfortably in a system prompt. An agent with twenty
actions, or with one that needs a page of explanation, is where loading on
demand starts to pay.

### Three defects had to be fixed before any of this measured the right thing

Each one hid the next, and the first two made Skills look like it worked.

1. **The shared prompt named the tools.** It said "call
   `propose_run_simulation`"; Skills mode has no such tool, so the model wrote
   the call out as text and `tool_call_recovery` turned it into a proposal.
   Nothing had opened a skill. Both prompts are mechanism-free now and
   `tests/test_skills.py` fails if a tool name comes back.
2. **No skill script could execute.** agno runs a script directly through its
   shebang; none had one and four had no executable bit, so every real attempt
   returned `Exec format error`. With the recovery net on this was invisible
   from the dashboard — **Skills mode had never once run a skill in the
   interface.**
3. **`#!/usr/bin/env python3` resolved to the system interpreter**, which has
   no `agno`. `runner.ensure_interpreter_on_path` puts the running
   interpreter's directory first on PATH for child processes.

### The harness

`benchmark_modes.py`, one JSON line per run in `logs/mode_benchmark.jsonl`. It
sends a fixed set of operator commands through both modes with `--arms`, holds
the context fixed with `--contexts` so load can be separated from the command,
and takes `--model`. It records whether the intended action was proposed,
whether its parameters were correct, and tokens and latency per command.

### What is still unmeasured

For a model that *can* make the call: whether it opens the right skill and how
often it acts without opening one, whether it composes the command line
correctly, wall clock per command including the extra round trip, and the
no-op perturbation test the allocation agent failed. Two things would settle
the rest: the same eighteen runs against more models, and a check of whether
the failure is lists or optional parameters, which needs a skill invocation
whose arguments are not both at once.

---

## Phase 7 — One process, many simulations

**Goal:** remove the global singleton so simulations can be built, run and
compared independently.

* `ComponentManager.model` is set in `Simulator.__init__` and read throughout
  the components as `self.model`. Component registries are class attributes
  (`cls._instances`), so two simulations share them (issue F).
* Move connectivity refresh into the engine so it stops duplicating the
  scheduler's ordering in the application layer (issue G).

**Unblocks:** the experiment harness of Phase 8; parallel runs; a clean
restart without the window in which the old session still points at the
rebuilt registries.

**Risk: high.** This touches every component. Do it with the test suite in
place and one component class at a time.

---

## Phase 8 — Experiment harness

**Goal:** run N configurations, collect metrics, compare approaches.

* A batch entry point on top of `SimulationSession`, replacing the ad-hoc
  `main.py`.
* Metrics written per run with the configuration that produced them.
* Tests that assert allocation correctness, not just that the clock advances
  (issue H).
* The Tools vs Skills comparison of Phase 6.

---

## Phase 9 — Orbital propagation: traces to SGP4 — **deferred**

**Goal:** a satellite's position comes from orbital mechanics rather than from
a recorded trace. Explored and reverted; what follows is what the exploration
established, so none of it has to be rediscovered.

### The measurement that matters most

Coverage over Brasília, 1500 km range, satellites in range per step:

| Satellites | Real TLE subset | Walker Delta (53°, 550 km) |
| --- | --- | --- |
| 15 | `[0,0,0,0,0,0]` | `[0,0,1,0,0,0]` |
| 300 | `[7,6,2,0,2,0]` — 2 gaps | `[3,3,4,4,3,3]` — **no gaps** |
| 1000 | `[13,11,7,4,9,8]` | — |
| 1584 | — | `[18,15,18,16,18,16]` |

1. **The captured dataset is survivorship-biased.** It recorded only satellites
   already above the reference point, so its first 15 look like a dense
   constellation; under unbiased propagation the same 15 give zero coverage.
   **Earlier allocation results may rest on artificially high availability.**
2. **Uniformity beats size.** A Walker constellation reaches continuous
   coverage at ~300 satellites where an arbitrary real subset needs ~1000.

### Facts that cost effort to establish

* **`linear_estimation` diverges from a real orbit by 1 000 km in 10 minutes**
  and 2 700 km in 20. It extrapolates latitude and longitude in a straight
  line, which is not an orbit. Wherever a trace runs out, the positions past
  that point are not meaningful.
* **The captured dataset is sampled at ~60 s per step**, not 56, and its epoch
  is unrecoverable — fitting a current TLE back to it does not converge.
* **98.8% of the captured constellation is still in orbit** (10 352 of 10 476),
  so a real-TLE manifest is a viable validation set.
* **Storage forces two formats.** All satellites at all steps would be 1.44 GB;
  propagation on demand plus a manifest is the workable shape.
* **The literature does not use real TLEs as the experimental base.** Hypatia
  generates TLEs from shell parameters and uses real ones to *validate*. If
  this phase resumes, the recommended shape is three datasets: the captured
  file as historical reference, a real-TLE manifest for validation, and a
  **Walker Delta shell as the experimental base**, added as a `--walker`
  mode to `trace_builder.py`.

### Decided design, if resumed

**Hybrid by default, global switch for experiments.** `Satellite.step()`
already calls a per-satellite mobility model, and the model choice plus its
parameters survive `save_scenary` → `Simulator.initialize`, verified end to
end: two models can run side by side in one tick with no structural change. A
field on `SimulationConfig` forces one model for every satellite when an
experiment needs comparability.

**Visibility becomes geometric.** A minimum elevation angle replaces the range
sphere; see Phase 10.

**Blocking dependency:** `tick_duration` has to mean something first (issue D).
SGP4 propagates to an absolute epoch, so the simulator needs a real start time
and a real seconds-per-tick. A tick is currently ~60 s of trace time while
`tick_duration` defaults to 1 s and is read by nobody.

**Risk: high for results.** Satellite dynamics change, so every metric measured
before the switch has to be re-measured after it.

---

## Phase 10 — Network model correction — **deferred**

**Goal:** make who-reaches-whom match a LEO architecture.

Kept apart from Phase 9 on purpose. Both change results, and running them
together would make any observed difference impossible to attribute to either
orbital motion or connectivity.

### What the literature says

Every LEO network simulator surveyed models the same three-stage path, and
none allows a user to reach a ground station without going through space:

```
terminal → satellite  →  satellite → satellite  →  satellite → gateway
  (uplink)                   (ISL)                    (feeder)
```

* Ground terminals and ground stations are **different roles**: terminals are
  end users, stations are the constellation's gateway to the internet.
* `starsim` states it outright: ground terminals *"cannot connect directly to
  ground stations"*.
* Terminals **are** nodes of the network graph, connected to satellites.
* Visibility is decided by a **minimum elevation angle**, usually turned into a
  maximum link distance once: Hypatia carries a `max_gsl_length_m` whose value
  derives from the elevation; `starsim` uses a ~1404 km Euclidean threshold
  taken from published Starlink figures.
* FCC filings give the reference thresholds: **Starlink 25°, Telesat 10°,
  Kuiper 35°**. In April 2026 the FCC allowed Starlink terminals down to 5° in
  some regions.

See [Literature notes](#literature-notes) for the sources and the numbers.

### What changes

1. **Remove `GroundStation.connect_users()`** (issue J). A ground station is a
   gateway, not an access point. Today a user near a station reaches a
   ground-hosted server without touching a satellite, which is the shortest
   path in the `terrestrial` scenario and should not exist.
2. **Visibility from elevation** (issue K). The altitude leg of the slant range
   is divided by 1000, so a satellite overhead reads as if it were on the
   ground — in **two** places, `within_range` and `calculate_distance`. The fix
   is that, plus deriving the threshold from a configured minimum elevation
   (default 25°) instead of an arbitrary distance.
3. **Users on the ground** (issue L). `create_users` places them at satellite
   trace coordinates, altitude included, so they orbit alongside the
   constellation.
4. **`User.export()` must keep `max_connection_range`** (issue M). It does not,
   so the scenario round trip resets 1500 km to the 300 km constructor default
   — a range smaller than any satellite's altitude, which makes a user
   geometrically unable to see one. Same defect class as the lost `name` on
   `Satellite`.
5. **Cap the satellites a gateway serves at once** (issue N). Real gateway
   earth stations handle 8 (Gen1) to 32 (Gen2) simultaneously. Every satellite
   does carry a Ka-band feeder link, so `is_gateway = True` for all of them is
   right; the scarcity is on the ground, in the ~150-200 gateway sites.

### Open decision

**Should users become nodes of the topology graph?** The literature includes
them. Today they sit outside it, so the access link has no bandwidth or delay
of its own and `has_path` starts at the access point rather than at the user.
End-to-end latency is understated as a result. Making them nodes is the
faithful option; keeping them out is cheaper and keeps the graph small.

### Measuring the change

Items 1 and 3 will cut connectivity, item 5 will cut it further. Record
connected users, link counts and allocation success before and after, per
scenario. The `terrestrial` scenario should move the most, since it is the one
relying on the path that is being removed.

**Risk: high for results.** Every comparison against earlier runs breaks.

---

## Suggested ordering

```
                    ┌──> Phase 3 (GS context) ──┐
Phase 2 (done) ─────┤                           ├──> Phase 5 (intent-driven)
                    └──> Phase 4 (orchestrator)─┘
                                                      │
        Phase 6 (tools vs skills) ───────────────┐    │
        Phase 7 (singleton) ─────────────────────┴────┴──> Phase 8 (harness)

        Phase 9 (SGP4) ──> Phase 10 (network model)      [deferred]
```

Phases 3, 4 and 5 are the thesis, and **Phase 3 is the demonstration**.

Phase 3 comes first for two reasons. An orchestrator built on top of an
unaffordable tick inherits the problem. And nothing can be claimed about
phases 4 and 5 without the instrumentation Phase 3 forces into existence —
calls per tick, prompt size, wall clock, allocation outcome.

Phase 4 then absorbs what Phase 3 deliberately left undone: the station stops
being sent the network JSON and stops emitting placements, because the
orchestrator prepares its input and closes its output. Phase 5 sits on top of
both — an intent that names objectives has to reach something that turns them
into what each station is asked.

Phase 6 is small and its answer shapes how the orchestrator's agents are built,
so it is worth doing before committing to an agent design. Phase 7 is the most
invasive and changes no results, so it waits until the harness needs it.

Phases 9 and 10 both change simulation results and must stay separate from each
other, so that an observed difference can be attributed to orbital motion or to
connectivity but not ambiguously to both. Neither is on the path to a working
demonstration.


---

## Possible future contribution: Jev for the station decision

Assessed 29 September 2026. A hosted "System One" model for typed decisions:
unstructured state in, a value from a closed set out, with a calibrated
confidence score. Published figures are **70-500 ms end to end** and 40x-200x
faster than a reasoning model — all from the vendor's announcement, none
independently verified.

**Why it fits this system unusually well.** A ground station agent reads a
digest of its neighbourhood and returns one strategy from a fixed set. That is
the shape Jev takes, and Phase 4's design narrows it further to one option out
of a known list. The attack is on the **per-call floor**, which Phase 3 measured
at 14 s and identified as the remaining cost — not on prompt size.

| | Per tick, at 20.7 calls |
| --- | --- |
| Today, `llama3.1:8b` | 308 s |
| Jev at the slow end, 500 ms | **10.3 s** |
| Jev at the fast end, 70 ms | **1.4 s** |

**The confidence score is the genuinely interesting part for the thesis.** It
replaces self-reported agnosticism with a measurement, which is exactly what
threat 1 needs: a station that is indifferent and a station that is unsteady
currently look the same. And a closed output set cannot be under-filled, which
is the failure issue Q documents and the one Phase 6 found again in the
`args` list.

**Where it does not fit.** It is a hosted API and the thesis is about small
models on ground stations; a hosted model can change under a published result;
every tick would need the network. It is future work, not a substitution.

**Phase 3's work is the input pipeline either way.** "Unstructured state in" is
the digest, and it was built for a local model.

Source: [Introducing System One Models and Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
TypeSafe AI.

---

## Literature notes

Findings gathered while grounding the Phase 3 and Phase 4 decisions. Kept here
so the numbers can be cited directly when writing up.

### Minimum elevation angle

| Operator | Minimum elevation | Source |
| --- | --- | --- |
| Starlink | 25° (original FCC filing) | FCC filings, via the ns-3 review |
| Telesat | 10° | idem |
| Kuiper | 35° | idem |

In April 2026 the FCC approved lowering the Starlink terminal minimum from 25°
to as low as 5° in some regions, applying to existing hardware. One secondary
source describes altitude-tiered thresholds (10° below 400 km, 20° between
400-500 km, 5° above 62°N); this could not be confirmed against the FCC filing
itself and should be treated as unverified.

Slant range and ground coverage radius, computed for this constellation:

| Elevation | h=350 km | h=450 km | h=550 km |
| --- | --- | --- | --- |
| 10° | 1303 / 1224 km | 1570 / 1456 km | 1815 / 1664 km |
| 25° | 747 / 643 km | 939 / 797 km | 1123 / 941 km |
| 40° | 526 / 382 km | 670 / 480 km | 812 / 573 km |

A fixed distance does not mean the same thing at different altitudes: a 1500 km
threshold implies a 7.0° minimum elevation at 350 km but 15.4° at 550 km.

### SGP4 accuracy

Measured on Starlink specifically, 24,641 TLE pairs across 501 satellites:
pooled median position error grows from **~1 km at 6 hours to ~38 km at 7
days**, following a power law with exponent between 1 and 2. SGP4 matches or
beats high-fidelity propagation over that span, because the satellites
manoeuvre and no propagator anticipates that.

The general heuristic agrees: ~1 km at epoch, degrading 1-3 km per day, with
TLEs ideally under 24 hours old and worse behaviour below 800 km altitude.

For the 14-hour dataset this project generates, interpolation puts the error at
**2-3 km** — negligible against coverage radii of hundreds of kilometres.
Windows of several days remain defensible for network simulation.

### Orbital model choice

Within the first few hours the difference between a two-body Keplerian
propagator and SGP4 is too small to affect radio conditions, and discrepancies
of tens of kilometres are considered realistic for simulation purposes. TLE
parameters are tuned for SGP4 and are not suited to classical Keplerian
propagation.

The practical consequence: orbital fidelity was never this simulator's weak
point. The missing piece was timing, not precision.

### Sources

* [A Comprehensive Review of ns-3-Based Simulation Frameworks for LEO Satellite Constellations](https://onlinelibrary.wiley.com/doi/10.1002/spe.70001)
* [Exploring the "Internet from space" with Hypatia (IMC 2020)](https://bdebopam.github.io/papers/imc2020-hypatia.pdf)
* [Hypatia — satgenpy distance tools](https://github.com/snkas/hypatia/blob/master/satgenpy/satgen/distance_tools/distance_tools.py)
* [starsim: A simulation of LEO internet satellite constellations](https://github.com/sidharthrajaram/starsim)
* [OpenSN: An Open Source Library for Emulating LEO Satellite Networks](https://conferences.sigcomm.org/events/apnet2024/papers/OpenSNAnOpenSourceLibraryforEmulatingLEOSatelliteNetworks.pdf)
* [How long can you trust a Starlink TLE? (arXiv:2605.19850)](https://arxiv.org/abs/2605.19850)
* [Mapping TLE orbital parameters to GNSS ephemeris (arXiv:2401.17767)](https://arxiv.org/abs/2401.17767)
* [Improved orbit predictions using two-line elements (arXiv:1002.2277)](https://arxiv.org/pdf/1002.2277)
* [Parametric Characterization of SGP4 Theory and TLE Positional Accuracy](https://amostech.com/TechnicalPapers/2014/Poster/OLTROGGE.pdf)
* [Celestial: Virtual Software System Testbeds for the LEO Edge (arXiv:2204.06282)](https://arxiv.org/abs/2204.06282)
* [Towards a Computing Platform for the LEO Edge (arXiv:2104.02396)](https://arxiv.org/pdf/2104.02396)
* [Gateway Station Geographical Planning for NGSO Constellations](https://ar5iv.labs.arxiv.org/html/2309.10581)
* [Connecting Communities: Inside Starlink's Community Gateway](https://openfalklands.com/connecting-communities-inside-starlinks-community-gateway/)
* [Starlink Dishes Get Wider View for Better Satellite Coverage (FCC, April 2026)](https://5gstore.com/blog/2026/04/21/starlink-dishes-wider-view-fcc-approval/)
