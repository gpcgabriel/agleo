# AGLEO Roadmap

Where the project stands and what comes next. The long-term goal is an
**agentic-defined simulation**: ground stations that decide locally, an
orchestrator above them that ties those decisions to operator intent, and a
dashboard agent that puts a network manager in the loop.

**Current priority (September 2026).** Phases 3, 4 and 5 are the three problems
the thesis is about, and they come first:

1. **Phase 3** — the context load on the ground stations' small models
2. **Phase 4** — the orchestrator that manages the other instances
3. **Phase 5** — running whole simulations from an operator's intent

**Demonstration scope (settled 26 September 2026): Phase 3 alone, done well.**
The number that tells the story is model calls per tick, before and after, with
the allocation outcome unchanged. Phases 4 and 5 have their designs settled in
their sections, but they are built after the demonstration, not for it.

Orbital propagation (Phase 9) and the network model correction (Phase 10) were
explored and **deliberately deferred**. Both change simulation results, and
neither is on the path to an end-to-end demonstration. What was learned while
exploring them is recorded in those sections and in
[Literature notes](#literature-notes) so none of it has to be rediscovered.

---

## Phase 1 — Decoupling and structure — **done**

### What changed

The application was one layer where Streamlit, the LLM agent and the
simulation engine all called into each other. It is now four layers with one
enforced rule: **`streamlit` may only be imported inside `app/ui`**
(`tests/test_layering.py`).

| Layer | Package | Lines | Owns |
| --- | --- | --- | --- |
| Engine | `leosim/` | — | Components, topology, scheduling |
| Domain | `app/core/` | 1575 | Session, actions, handlers, catalog, routing |
| Agents | `app/agents/` | 621 | Prompts, tools, runs, recovery |
| Interface | `app/ui/` | 953 | Widgets, map, chat, theme |

`app.py` went from a 600-line module to a 144-line composition root spread
across 43 modules, the largest of which is 291 lines.

### Structural moves

* `SimulationSession` owns the simulator, history, viewed index and scheduled
  steps. Four loose `st.session_state` keys became one.
* `SimulationConfig` replaced six positional arguments passed hand to hand.
* `ProposedAction` (typed `ActionType` + validated payload) replaced a free
  dictionary with no schema.
* `execute_pending_action` (≈140 lines, if/elif over action strings) became
  six handler modules plus a three-line dispatcher.
* Command routing left the render function for `app/core/router.py`.
* `render_chat_panel` (155 lines) split into `gate`, `history` and `input`.
* `SatelliteCatalog` indexes the traces file once instead of reparsing it per
  lookup.

### Defects fixed

1. `add_process_unit` always failed — the payload was a dict while the
   executor iterated a list.
2. `connect_server` always failed on a station with no servers — `export()`
   writes `None`, `Simulator.initialize` restores it, `.append()` raised.
3. The agent ran without effective prompts — `description` and `instructions`
   were passed as function objects, and one returned a tuple annotated `str`.
4. `Simulator` mutated a shared mutable default, so two instances overwrote
   each other's `scenario`.
5. Disabling agent actions raised `ValueError` and froze the chat.
6. The "trace already taken" check compared NORAD catalog ids against
   internal sequential ids, so it never excluded anything.
7. Satellites added by the agent took the NORAD id as their internal id,
   breaking the numbering.
8. The timeline showed the history index, so a change made at step 0 read as
   step 1.
9. `st.components.v1.html` was deprecated; replaced with `st.iframe`.

### Behaviour changes to be aware of

* **The selected scenario now reaches the allocation algorithm.** It was
  always `'hybrid'` before. `longest_duration_allocation` branches on it, so
  results under `leo`/`terrestrial` with that algorithm differ from any
  previously collected data.
* Step 0 now shows real connectivity instead of every user disconnected.
* `add_*` actions no longer consume a simulation tick; they refresh
  connectivity and publish a snapshot at the same tick.

### Performance

Adding a satellite went from **38.6 s to 0.08 s**. Two independent causes: the
traces file was reparsed on every lookup, and the geodesic distance was
computed for all 286,880 indexed positions. The catalog parses once and ranks
with a vectorized haversine, refining only the 25 nearest candidates with the
exact geodesic.

### Coverage

56 tests across 12 files, none of which mock Streamlit.

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

## Known issues carried into the next phases

| # | Issue | Addressed in |
| --- | --- | --- |
| ~~A~~ | ~~`leosim` imports `agno`~~ — resolved in Phase 2 | done |
| ~~B~~ | ~~`resource_management_algorithm` is ~250 lines with three parsing fallbacks~~ — resolved in Phase 2 | done |
| C | Agent-added satellites get a compacted trace and teleport between orbital passes | Phase 9 |
| D | `tick_duration` is computed and never read; one trace step is ~60 s of real time, recorded nowhere | Phase 9 |
| E | Selecting the "Skills" agent mode raises `TypeError`; no skill has ever been written | Phase 6 |
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
| Q | The model omits applications from both strategy lists, and `hybrid_allocation` never looks at them — not placed, not counted as failed, absent from `details`. Measured at 19% of decisions under a no-op prompt change | open |

### What could be fixed now

Every issue above was re-verified against the code on 28 September 2026. This
is the standing triage; it is not permission to fix anything.

**Fixed on 28 September 2026: K, L and M, together.** They had to move as a
group.

K was worse than this table said. It listed "two occurrences in `topology.py`";
there were **five, across four files**, and the three that were nearly missed
sit in the allocation path itself — `hybrid_allocation.distance` is what
`LLMAllocator.apply_decision` runs, and `state.find_reachable_satellite_ids` is
what decides which satellites a station is told about. Fixing only the engine
pair would have left the agent and the engine disagreeing about what is in
range, which is worse than both being wrong the same way. The formula living in
five places is now issue P. Measured across all eight combinations, averaged over five ticks:

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
accidentally correct. After the three: 20/20 users connected on every tick and
11 to 13 applications provisioned, against 2.2 before.

**This invalidates every allocation result recorded before that date.** The
numbers in Phase 3's baseline were measured on a network where most pending
applications belonged to users with no access point at all.

**Cheap and low risk, still open:**

| # | Cost | What it changes |
| --- | --- | --- |
| E | two lines in `app/ui/sidebar.py` | removes a radio option that raises `TypeError: LocalSkills.__init__() missing 1 required positional argument: 'path'` the moment it is selected |
| D | a field in the snapshot | records that one step is ~60 s of simulated time, which nothing does today |

**Fixable, but each carries a design decision rather than a correction:**

| # | The decision hiding in it |
| --- | --- |
| J | removing the user-to-ground-station link changes the network model; it is what Phase 10 is about |
| N | a gateway cap needs a number — 8 (Gen1) or 32 (Gen2) — and a policy for the satellites turned away |
| I | making the round trip symmetric means deciding how `Topology` is serialized |

**Not fixable now:**

| # | Why |
| --- | --- |
| C | agent-added satellites teleport because the trace is sparse; only real propagation fixes it (Phase 9) |
| F, G | the global singleton and the duplicated scheduler ordering are invasive and change no results (Phase 7) |
| H | tick correctness can now be asserted meaningfully, since allocation actually succeeds — moved from blocked to open |
| O | this is Phase 3, in progress |

---

## Phase 2 — Engine purity — **done**

**Goal:** `leosim` stops depending on the LLM stack.

### What changed

`GroundStation` went from 424 lines to 109. It lost the `agno` imports, the
`Agent` built in its constructor, `llm_params`, `decision_history`,
`allocate_apps` and the 250-line `resource_management_algorithm`. What
remains is a network component: connectivity, links and export.

The allocation agent moved to `app/agents/allocation/`, split by
responsibility:

| Module | Lines | Responsibility |
| --- | --- | --- |
| `state.py` | 169 | Selecting the slice of network state the agent sees |
| `allocator.py` | 159 | Running the agent, applying and recording the decision |
| `prompt.py` | 58 | Building the prompt and the history section |
| `decision.py` | 43 | The output schema and splitting into disjoint lists |

`LLMAllocator.allocate(model, parameters)` has the same signature as
`best_fit_allocation`, so the engine injects it like any other algorithm and
never learns it is talking to a model.

The three parsing fallbacks (JSON → regex → `ast.literal_eval`) are gone.
`agno`'s `output_schema` constrains generation to a Pydantic model, so the
reply arrives already validated — verified against `llama3.1:8b`.

`Simulator.step` lost its dead `resource_management_algorithm is True`
branch, which no entry point ever reached.

### Composition root

`app/core` must not import `app/agents`, so `build_simulator` and
`create_session` accept an injected `allocation_algorithm`. The UI assembles
it: `app/ui/sidebar.py` builds an `LLMAllocator` when the operator selects
`llm_allocation`, and a restart preserves the injected strategy.

### Coverage

Three new layering tests (the engine never imports the LLM stack, the domain
never imports the agent package, and a runtime check that building a
simulation does not load `agno`) plus `tests/test_allocation.py` — eleven
tests without a model and one integration test against Ollama.

### Note on cost

An LLM tick asks every ground station in turn. With the RNP topology that is
28 model calls per step, minutes of wall clock. Tests exercise a single
station; batch runs should expect this cost.

---

## Phase 3 — Ground station agent context

**Goal:** make an LLM tick affordable. This is the first of the three problems
the thesis is actually about.

### The measured problem

`LLMAllocator.allocate` is called once per ground station per tick. With the
RNP topology that is **28 model calls per step**, minutes of wall clock. A
functional test that tried to run two ticks was killed after 560 s without
finishing one.

The prompt is the other half. Phase 2 already trims the state to what bears on
the pending applications, but a small local model still receives the whole
JSON of satellites, users, process units and topology for its neighbourhood.

**Baseline, measured 25 September 2026.** Built on the RNP topology, walking
every station through `collect_state` and `build_allocation_prompt` without
calling a model, at step 1 (step 0 has no pending applications, so all 28
stations skip):

| Users / satellites | Stations asked | Prompt tokens, median | Prompt tokens, max | Tokens per tick |
| --- | --- | --- | --- | --- |
| 20 / 15 (dashboard default) | 26 of 28 | ~1 140 | ~1 360 | **~28 000** |
| 60 / 50 | 28 of 28 | ~2 510 | ~2 960 | ~63 000 |
| 100 / 100 (sidebar maximum) | 28 of 28 | ~3 600 | ~4 130 | ~89 000 |

Tokens are estimated at four characters each. Assembling the state costs
0.1-0.6 s for all 28 stations, so the state builder is not the bottleneck: the
model calls are.

**What the numbers change.** A single prompt is not what breaks a small model —
1 140 tokens fits any of them comfortably, and even the largest scenario stays
near 4 000. The cost is that the *same* work happens 26 to 28 times per step,
and that number barely moves with scenario size while the prompt triples. So
the directions that cut the call count (2 and 4 below) are worth more than the
one that shortens the prompt (3), and direction 1 is worth measuring first
because it costs almost nothing.

### Directions, cheapest first

1. **Skip when nothing changed.** A station already returns early when it has
   no pending applications. Extend that: if the pending set and the reachable
   satellites are unchanged since the last decision, reuse it instead of asking
   again.
2. **Batch the stations.** One call carrying several stations' states, instead
   of one call per station. Cuts calls by the batch factor at the cost of a
   longer prompt.
3. **Summarize instead of serializing.** The state goes in as JSON today.
   A compact tabular or natural-language digest of the same facts is far
   shorter for the same information; `summarize_snapshot` already does this for
   the dashboard agent and could be adapted.
4. **Decide policy, not placements.** Ask the model for a *strategy* per
   station (or per region) and let deterministic code apply it to every
   application. One decision covers many placements. This is the direction that
   converges with Phase 4.
5. **Ask only the stations that matter.** Stations with no reachable satellite
   and no local process unit already skip. Stations whose neighbourhood is
   unchanged could skip too.

### Decided: scope the question first, then cache

Settled 26 September 2026 as "cache first", **revised 28 September 2026 after
measuring**. Phase 3 remains the demonstration scope.

**What the measurement found.** The pending application list is built once for
the whole network and handed to every station: 26 of 26 stations receive the
identical list. Each station sees its own satellites and process units, so the
*infrastructure* view is local — but the *question* is global. A station in
Porto Alegre is asked to choose a strategy for applications belonging to users
it could never serve.

That is why caching alone is worthless. The list changes whenever anything is
placed or requested anywhere, so "nothing changed since last time" almost never
holds:

| Cache key | Hit rate |
| --- | --- |
| Pending set + exact reachable satellites | 6.7% |
| Pending set + count of reachable satellites | 6.7% |
| Pending set only | 7.5% |
| Pending set, with issue M fixed | **1.8%** |

Loosening the key barely helps, which rules out satellite motion as the cause.
And the more correct the simulation becomes, the *less* the cache is worth:
once applications can actually be placed, they leave the pending set and churn
increases.

**Scoping the question changes the picture.** Asking each station only about
applications whose user it could plausibly serve — the user shares a satellite
with the station, or sits on it:

| | Calls | Applications per prompt |
| --- | --- | --- |
| Global question (today) | 228 | 9.6 |
| Scoped to the station | 224 | **4.5** |

The call count barely moves, because with satellites overhead almost every
station can reach something. But the question halves, and **the cache then
reaches 22.3% instead of 1.8%** — a scoped pending set changes far less often.
Together: roughly 174 calls where there are 228 today, with prompts half the
size.

The reason to do this first is not the number. It is that **the localized
decision the thesis is about does not exist yet**. Today there are 26 answers
to one global question. Scoping is what makes them local.

**Order:** scope, measure, then cache on top of the scoped question.

**Direction 2 stays rejected.** Batching several stations into one call merges
the local decisions the thesis argues should be local.

**Directions 3 and 4 stay absorbed into Phase 4.** Under the settled
orchestrator design the station receives a digest and answers a closed
question, which is summarization and policy arrived at through the
architecture.

### Baseline with the model, 28 September 2026

Three ticks of `LLMAllocator` on the RNP topology with `llama3.1:8b`, 20 users
and 15 satellites, measured **after** issues K, L and M were fixed. Everything
recorded before that date was measured on a network where most pending
applications belonged to users with no access point, and is not comparable.

| Tick | Calls | Skipped | Applications asked | Prompt tokens (~) | Wall clock |
| --- | --- | --- | --- | --- | --- |
| 1 | 9 | 19 | 60 | 14 296 | 474 s |
| 2 | 26 | 2 | 356 | 23 638 | 968 s |
| 3 | 24 | 4 | 78 | 13 742 | 533 s |
| **mean** | **19.7** | 8.3 | **164.7** | **17 225** | **658 s** |

**A tick costs 8 to 16 minutes.** That is the number Phase 3 has to move.

Two things the table shows that a single tick would have hidden:

* **Calls swing from 9 to 26.** Stations are visited in sequence within a tick,
  and each one's allocation empties part of the pending list, so the stations
  visited later find nothing to do and skip. One tick is not a measurement.
* **Tick 2 asks about 356 applications** in a scenario that contains 20. Every
  station is asked about nearly all of them, which is the global question
  restated as a number.

**The allocator's `provisioned` and `failed` counters cannot be used for
quality.** They are summed across stations, so with a global question the same
application is counted by every station asked about it — tick 2 reports 198
failures among 20 applications. Scoping removes that double counting by
itself, which would look like an improvement it did not make. The outcome
metric is therefore read from the simulator: how many *distinct* applications
are placed at the end of a tick.

### Result of the scoping, 28 September 2026

Three ticks per arm, `llama3.1:8b`, same seed, same scenario. The *global* arm
reproduces the pre-scoping behaviour exactly — same calls, same tokens as the
baseline above — which is what makes the two comparable.

| Per tick | Global question | Scoped to the station | |
| --- | --- | --- | --- |
| Model calls | 19.7 | 20.7 | +5% |
| Applications asked about | 164.7 | 101.7 | **−38%** |
| Prompt tokens (~) | 17 225 | 16 619 | −3.5% |
| Tokens per call (~) | 876 | 804 | −8% |
| Wall clock | 579.5 s | 531.0 s | **−8.4%** |
| Distinct applications placed | 13.3 | 13.0 | −2% |

**As a cost reduction this is a negative result.** 8.4% of wall clock, across
three ticks, is inside the noise: tick to tick the same arm varies by a factor
of two. Scoping did not make the tick affordable.

Two things went differently from the structural estimate made without the
model:

* **Calls went up, not down.** With a global question, once the first stations
  place the pending applications the list empties and every station visited
  later skips with "no pending apps". That saving was an accident of visit
  order, not locality, and scoping removes it. A station is now asked when *its*
  users have work, which is the correct criterion and costs one more call per
  tick.
* **Cutting applications barely cut tokens.** The application list is 37% of the
  prompt, so removing 42% of it removes about 15% of the prompt at best. The
  estimate had assumed applications drove prompt size.

**What the run did establish** is where the cost lives. Across 121 model calls,
elapsed time against prompt length gives **r = 0.98**; against the number of
applications, only 0.65. Time is almost exactly linear in prompt characters:

| Applications in the prompt | Calls | Median time |
| --- | --- | --- |
| 0-3 | 47 | 18.4 s |
| 4-8 | 41 | 24.7 s |
| 9-15 | 17 | 29.3 s |
| 16-30 | 16 | 42.9 s |

And the prompt is not mostly applications:

| Section of the state | Share of the prompt |
| --- | --- |
| applications | 37% |
| process_units | 25% |
| satellites | 16% |
| topology | 11% |
| ground_station | 3% |

**Keep the scoping anyway.** It is not a cost win, but it is the property the
thesis rests on: before it, 26 stations answered one network-wide question, and
no decision was local. It is also what Phase 4's orchestrator needs in order to
skip stations that have nothing to do with a request.

**The next lever is direction 3, not the cache.** With r = 0.98 against prompt
length, halving the prompt halves the tick. That means replacing the serialized
JSON of process units, satellites and topology — 52% of the prompt between them
— with a digest carrying the same facts. The cache stays after that: a scoped,
digested question is the one worth caching.

### Next: a deterministic translator, not a cache

Assessed 28 September 2026, after the scoping result pointed at prompt length.

The proposal: a module that *translates* the infrastructure state and the
applications to be provisioned into what each relevant station needs to decide,
instead of serializing the state as JSON. Measured on 24 stations at step 3:

| | Chars | Tokens (~) |
| --- | --- | --- |
| Serialized JSON prompt, today | 2 642 | 660 |
| Rendered digest, same decision-relevant facts | 473 | 118 |
| | **−82%** | |

Nothing an allocation strategy reads is dropped. What goes is JSON
punctuation, fields that are always zero (`sto` everywhere), and raw inputs the
code can turn into the number the model actually uses — a satellite's three
future positions become "visible for N steps", and `cpu_total`/`cpu_used`
become `cpu_free`.

**Projected cost.** Fitting elapsed time against prompt length over the 121
real calls of the comparison gives `t = 1.03 s + 7.89 s per 1000 chars`
(r = 0.98, measured between 931 and 12 943 chars):

| | Per call | Per tick, at 20.7 calls |
| --- | --- | --- |
| Today | 21.9 s | 453 s |
| With the digest | 4.8 s | **99 s** |

That is a projection, and 473 chars sits **below the measured range**, so the
intercept is doing more work than the data supports. It needs a confirming run
before it is quoted as a result.

**The digest is also what makes caching possible at all.** Over 12 ticks with
scoping on:

| Cache key | Hit rate |
| --- | --- |
| The full JSON state | **0.0%** |
| The facts a digest carries | **19.2%** |

The raw state never repeats — a delay written as `3.8731589318491397` changes
every tick, and so does every satellite position. Rounded, derived facts do
repeat. This settles the order: digest first, cache second, because a cache
over the raw state can never hit.

### What it changes about the orchestrator

The translation is mechanical, so it does not need a model. That splits the
orchestrator's job in two, and only one half needs language:

| Job | How often | Needs a model |
| --- | --- | --- |
| Turning operator intent into objectives | once per run, or when the intent changes | **yes** |
| Turning state into each station's question | every tick | **no** — this is the translator |
| Choosing a strategy for the question | every tick, per station | yes, and this is the thesis claim |

This is better than the settled design in two ways: the per-tick orchestrator
call disappears, and the chewing becomes reproducible and testable instead of
being a model output that has to be trusted.

**The boundary, settled 29 September 2026.** If the translator decides *which*
units to show and in what order, it has made the placement judgment and the
station agent is a rubber stamp — the contribution would live in the Python,
not in the agents. So:

> The translator **translates**. It turns the infrastructure, the context, the
> history and the pertinent parts of the state into a digest a small model can
> ingest, and it filters out the stations that cannot serve the applications at
> hand so no call is spent on them. It does not rank, score or recommend.

| Allowed | Not allowed |
| --- | --- |
| Including every process unit the station can reach | Sorting them by how well they fit |
| Computing free capacity from total and used | Dropping ones that "would not be chosen" |
| Computing remaining visibility from the future positions | Naming a best candidate |
| Skipping a station that can serve nothing this step | Skipping a station because its answer seems predictable |

The last row is the subtle one. Filtering by *capability* is translation —
the station genuinely has nothing to decide. Filtering by *expected answer* is
deciding, and it belongs to the agent.

The falsification test is the one the evaluation needs anyway: if replacing the
model with a fixed strategy produces the same allocation outcome, the agent is
not contributing and the translator has absorbed the decision.

### One gap found while prototyping

`build_network_state` pops the `pu` field from each satellite after collecting
the unit ids, so the state no longer records **which satellite a process unit
rides on**. A digest cannot then say "this unit is on a satellite visible for
N more steps", which is the column that makes `longest_duration` decidable. The
link has to be preserved before the digest can carry it.

### Measured: the digest, 29 September 2026

Three arms, three ticks each, `llama3.1:8b`, same seed and scenario. The
`unit_hosts` link was restored first, so the digest can say which satellite a
process unit rides on.

| Per tick | Global question | Scoped | Scoped + digest |
| --- | --- | --- | --- |
| Model calls | 19.7 | 20.7 | 20.0 |
| Applications asked about | 164.7 | 101.7 | 101.7 |
| Prompt tokens per tick (~) | 17 225 | 16 619 | **3 034** |
| Prompt tokens per call (~) | 876 | 804 | **152** |
| Wall clock | 579.5 s | 531.0 s | **308.4 s** |
| Distinct applications placed | 13.3 | 13.0 | 13.0 |

**A tick is 47% faster than where Phase 3 started, with the allocation outcome
unchanged.** 9.7 minutes down to 5.1.

### The projection was wrong, and the reason matters

Phase 3 projected 99 s per tick from a linear fit of elapsed time against
prompt length (`t = 1.03 s + 7.89 s per 1000 chars`, r = 0.98). The prompt
reduction landed as predicted — 82%, within a point of the estimate. The time
reduction did not: 47% against a predicted 78%.

The fit was taken over prompts of 931 to 12 943 characters, and the digest is
574. Below the measured range a per-call floor appears that the fit had
attributed to slope. Measured inside the digest arm, where prompt length is
nearly constant:

| Applications in the call | Calls | Median time |
| --- | --- | --- |
| 1-3 | 15 | **14.0 s** |
| 4-8 | 8 | 18.9 s |
| 9-20 | 13 | 18.7 s |

**Fourteen seconds for the smallest possible question.** At 20 calls per tick
that is a 280 s floor, and the digest has brought the tick to 308 s — within
10% of it.

The extrapolation was flagged as one when it was made, which is why it was
labelled a projection and scheduled for confirmation rather than quoted as a
result. It still overstated the gain by a factor of three.

### What this means for the rest of Phase 3

**Prompt size is no longer the lever; the number of calls is.** The remaining
cost is per-call overhead, not reading. Two things act on it:

* **The stability filter**, now worth building: the digest's facts repeat 19.2%
  of the time between ticks where the raw state repeated 0%. Cutting one call
  in five removes ~60 s from a tick.
* **A smaller answer.** Within the digest arm, time still correlates with the
  application count (r = 0.70) even at constant prompt length, because the
  reply is two lists of application ids that grow with it. Phase 4's design —
  one option out of a fixed set — collapses that reply to a single token's
  worth of choice.

The second is also what makes a typed-decision model such as Jev interesting:
its published 70-500 ms is an attack on exactly this floor, not on prompt size.

### The history section, and what asking about it uncovered

Raised 29 September 2026: the prompt carries the station's own past decisions,
and that section grows after every answer. So even at an unchanged
infrastructure the prompt differs between ticks, and a stability filter keyed
on infrastructure alone would be reusing a decision the agent might have
revised. The objection is correct as stated. Measured at a fixed state,
temperature 0, so the same prompt always gives the same answer:

| | Stations where the answer changed |
| --- | --- |
| Adding one history entry | **5 of 6** |

But the next question decides what to do about it. Is the answer tracking the
feedback, or moving under any perturbation at all? Two controls:

| | Stations |
| --- | --- |
| Success and failure gave *different* answers | 3 of 6 |
| A filler line carrying no information changed the answer | **5 of 6** |

The filler was `This station reports nominal operation.` It moved the decision
more often than the difference between "you placed everything" and "you placed
nothing". **The answer is not tracking feedback. It is unstable under any
change to the prompt, and the history is one more thing that perturbs it.**

### How much moves

Measured over 8 stations and 68 application decisions, comparing a prompt
against the same prompt plus the filler line:

| | Share of decisions |
| --- | --- |
| Changed strategy, `best_fit` ↔ `longest_duration` | 10% |
| **Dropped from the answer entirely** | **19%** |
| Appeared, having been absent before | 10% |

The strategy flips are the small part. The large one is the model silently
omitting applications, against an instruction that says every pending id must
appear in exactly one of the two lists.

`hybrid_allocation` iterates only the ids it is given. An application in
neither list is never looked at: not placed, not counted as failed, absent from
the `details`. About one application in five disappears under a change to the
prompt that carries no information. This is issue Q.

### What it means for the stability filter

**Build it, and drop the history section.**

Reusing a previous decision is not less principled than re-asking — it is
*more* so. Re-asking at an unchanged state currently returns a different answer
about 39% of the time for no reason a reader could defend. Reuse is at least
deterministic, and it is defensible in writing: the inputs are identical, so
the decision is.

Dropping the history costs nothing that was working. It does not transmit
feedback, it spends tokens, and it is what would otherwise force the filter's
key to include a section that grows every tick. Without it the prompt becomes a
pure function of the infrastructure, which makes the filter's key exact instead
of approximate.

There is a caveat worth stating: dropping it removes the *possibility* of
learning from outcomes, which the design intended. The measurement says that
possibility is not being realised today. If a later model does use feedback,
the section comes back — and the filter's key has to grow with it.

### What it means for the thesis

This is the uncomfortable part. If a station's answer moves under a no-op
perturbation, then some of what "the ground station decided" is measuring is
noise. Two things follow:

* **The evaluation baseline stops being optional.** The arm that matters is the
  per-station model against deterministic `best_fit`. If the agent's answers
  are substantially arbitrary, that comparison is where it shows.
* **It sharpens the case for a calibrated, typed-decision model.** A closed
  output set cannot silently omit an application, and a confidence score would
  distinguish a station that is genuinely indifferent from one that is merely
  unsteady. See the Jev assessment below.

### How to measure

Record per tick: number of model calls, prompt length in characters and
tokens, wall clock, and allocation outcome (provisioned / failed). The
baseline to beat is the current per-station call, measured above. Any
reduction has to be shown not to degrade allocation quality, so the outcome
must be recorded alongside the cost.

For the demonstration the number that tells the story is **model calls per
tick, before and after, with the provisioned/failed count unchanged**.

**Risk:** low for direction 1 — the decision reused is a decision the model
already made. The risk is staleness: reusing a choice when the neighbourhood
*did* change in a way the skip test does not capture.

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

Two properties follow, and they are what make this design worth building:

1. **The station's input shrinks by construction.** It no longer receives the
   network JSON for its neighbourhood. It receives a digest the orchestrator
   already reduced, plus the question. This is why Phase 4 subsumes directions
   3 and 4 of Phase 3 rather than competing with them — the summarization is
   the architecture, not an optimization bolted onto it.
2. **The station's output space is closed.** The reply is one option out of an
   enumerated set — plus an explicit **agnostic** answer, meaning the local
   view does not favour any of them. A closed set is cheap to generate, trivial
   to validate, and makes disagreement between stations measurable.

The agnostic answer is not a failure mode. It is information: it tells the
orchestrator which decisions the local level genuinely constrains and which it
does not, which is the thesis's central claim made falsifiable.

### Settled: one shared digest, a fixed option set, agnostic doing double duty

Settled 26 September 2026.

**One digest, not one per station.** The orchestrator produces a single
overview of the infrastructure and sends the same one to every station. Two
consequences, and the second is the interesting one:

* The orchestrator's own output stays small and bounded. Emitting N tailored
  digests would need the whole network state on the way in and a long
  structured reply on the way out, which moves the context problem up a level
  instead of removing it.
* **The 28 station prompts now share a prefix.** The digest is byte-identical
  across them, so a server that reuses a KV cache across requests pays for it
  once. Worth measuring with Ollama before counting on it, but it is free if it
  works.

**The constraint that makes or breaks this:** the digest must be a *summary*,
not a serialization. A global view written out as JSON is larger than the local
neighbourhood JSON it replaces, and the cure becomes the disease. The target is
a digest smaller than today's ~1 140-token per-station prompt, carrying the
operator's objectives and the state that bears on them.

**A fixed option set.** `best_fit`, `longest_duration`, `agnostic` — the
strategies that already exist and are already executable. Letting the
orchestrator invent options per question is more expressive, but every invented
option would need validating against something that can actually run.

**Agnostic does double duty.**

1. *As a default.* The orchestrator ran before, so it is not around afterwards
   to break ties without paying for a second pass. The policy it emitted
   carries a default; agnostic means "apply it here", at zero extra cost.
2. *As a tie-breaker.* When stations disagree, the agnostic ones are not
   counted on either side. They shrink the conflict set instead of padding it,
   which is what makes the disagreement that remains worth looking at.

**The orchestrator asks only the stations that are involved.** The same rule
Phase 3 applies to applications applies one level up: a station with nothing to
do with the request at the current step is not consulted at all. Two filters,
and they compose:

* *Relevance.* The station cannot serve any application in the request — skip
  it. This is Phase 3's scoping, read from the orchestrator's side.
* *Stability.* Nothing significant changed in that station's neighbourhood
  since it last answered — reuse its answer instead of asking again.

"Significant" needs a definition that is written down and measured, not
guessed. The candidates are the ones Phase 3 measures: the scoped application
set, the reachable satellites, and whether any reachable process unit still has
capacity. Whatever is chosen, the orchestrator must be able to say *why* it
skipped a station, because that is the record the thesis argues from.

**The digest and the answers are kept together.** After the round, the
orchestrator holds the pair `(digest, {station: choice})`. That pair is the
unit of history: it records what the network looked like, what each station
concluded, and what followed. `LLMAllocator.decisions_by_station` already keeps
per-station decisions; this widens it to a per-tick record that later rounds can
be grounded in.

Storing it is cheap. *Feeding it back* into a later prompt is not — it is the
context problem again, one level up, and it needs its own measurement before
being switched on.

### What this changes in the code

`AllocationDecision` today splits pending application ids into `best_fit` and
`longest_duration` lists. Under this design it becomes a single choice:

```python
class StationChoice(BaseModel):
    option: str      # "best_fit", "longest_duration" or "agnostic"
    reason: str      # one sentence, for the run report
```

`LLMAllocator` keeps its signature — it stays an allocation algorithm the
engine injects — but `allocate` grows an orchestrator pass before the
per-station loop, and a record of `(digest, choices)` after it.

### Still open

1. **How do two stations claiming the same process unit resolve?** Agnostic
   answers shrink the conflict set but do not empty it. Deterministic
   arbitration is cheaper and more defensible than asking a model a second
   time. Undecided.
2. **What does the orchestrator get compared against?** Without a baseline
   there is no result. Three arms: deterministic `best_fit`, per-station LLM
   *without* orchestrator, and the orchestrator. The middle one is the
   comparison that matters — it isolates the orchestrator's contribution from
   the contribution of merely using a model.

### Cost

The call *count* barely moves: one orchestrator call plus the same per-station
calls. What changes is the price of each. The station's prompt drops from a
neighbourhood digest of roughly 1 140 tokens to a question with a handful of
options, and its output drops from a list of application ids to one token's
worth of choice. The orchestrator's own call is the expensive one, and keeping
it bounded is what open question 1 is about.

This is measurable only against the Phase 3 baseline, which is why Phase 3 is
sequenced first.

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
## Phase 6 — Agent capability model: Tools vs Skills

**Goal:** make the second agent mode real, so the two ways of giving an agent
capabilities can be compared rather than assumed.

### Current state

The sidebar offers "Tools" and "Skills" as agent modes, but only Tools works.
Selecting Skills raises `TypeError` the moment the operator sends a message,
and it has done so since before the Phase 1 refactor. Two API mismatches
against the installed `agno`:

* `LocalSkills()` is called with no arguments, but `path` is a required
  positional argument.
* `Skills(local_skills=...)` does not match the signature, which is
  `Skills(loaders: List[SkillLoader])`.

No skill has ever been written. The `Skills/` folder held only an empty
`__init__.py` and was removed with the rest of the old agent package.

### What it takes

1. **Fix the construction:** `Skills(loaders=[LocalSkills(path=SKILLS_DIR)])`.
2. **Write the skills.** A skill is a folder containing `SKILL.md`: YAML
   frontmatter (`name`, `description`, optionally `license`, `metadata`,
   `compatibility`) followed by instructions in the body. One skill per
   capability the agent has today as a tool — advancing the simulation,
   restarting it, adding nodes, users and applications.
3. **Decide how a skill produces a proposal.** Tools write into the
   `ProposalBuffer` because they are Python callables. A skill is
   instructions, not a callable, so the confirmation gate needs a path from
   skill output to `ProposedAction` — most likely a structured reply parsed
   into a payload, reusing the validation already in `app/core/actions.py`.
4. **Keep the modes symmetric.** Both must end at the same gate, so the
   comparison measures the capability model and not two different pipelines.

### The comparison

This is what the second mode exists for. Once the harness of Phase 8 is in
place, run the same operator commands through both modes and measure:

* whether the intended action was proposed at all;
* whether its parameters were correct;
* how often the reply had to be recovered from text instead of arriving as a
  proper call — `app/agents/tool_call_recovery.py` already detects this and
  only needs a counter;
* tokens consumed and latency per command.

**Why here in the order:** the answer informs Phase 4. If skills steer a small
local model more reliably than function calling, the ground station agents of
the orchestrator should be built that way from the start.

**Risk:** low for the existing system — Tools mode is untouched. The open
question is design, not stability: step 3 above has no obvious answer yet.

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

> **Explored in September 2026, then rolled back.** A working implementation
> existed and was reverted to keep the demonstration path clear. Nothing below
> is speculation: it was built, measured and verified. The code is gone; the
> findings are not. Re-implementing should start from this section rather than
> from scratch.

### What was built and verified

* `dataset_generator/trace_builder.py` — fetches TLEs from Celestrak
  (`--group`, `--satellites`, `--match-dataset`, `--limit`,
  `--format manifest|trace`, `--min-altitude`) and propagates locally.
* `leosim/orbit_models/sgp4_propagation.py` — TEME to geodetic conversion and
  an `sgp4_mobility` model sharing `linear_estimation`'s signature.
* `dataset_generator/load_satellites.py` — reads both dataset shapes and three
  orbit modes.
* `SimulationConfig.orbit_model` with `trace` / `sgp4` / `hybrid`, wired
  through `bootstrap` and `dataset.load_topology`.

All four combinations ran end to end, with `tick_duration` taken from the
dataset (60 s) instead of the unread default of 1 s.

### Facts that cost effort to establish

* **The bulk fetch works.** `GROUP=starlink` returns ~10,700 TLEs in one
  request. The per-satellite `CATNR` query is what is slow. Celestrak throttles
  repeated bulk requests for about two hours, per address — not permanently.
  An earlier report that this phase was "blocked on data" was wrong for this
  reason.
* **98.8% of the captured constellation is still in orbit**: 10,352 of 10,476
  satellites still have a current TLE; 34 more sit below 300 km and are
  reentering (one at 90 km).
* **The captured dataset's epoch is unrecoverable.** Fitting a current TLE back
  to its recorded positions gives a 630 km sequence error, because the
  satellite decayed 29 km in between. The captured file carries no timestamps,
  so trace and SGP4 live in different, unknowable time frames.
* **The captured dataset is sampled at ~60 s per step**, not 56. Measured
  against a trace of known interval; 840 steps therefore cover 14 hours.
* **Storage forces two formats.** All satellites at all steps would be 1.44 GB.
  A manifest (TLEs plus timing, no positions) covers 10,318 satellites in
  2.1 MB; a trace of 100 satellites over 840 steps is 6.5 MB.

### The measurement that matters most

Coverage over Brasília, 1500 km range, satellites in range per step:

| Satellites | Real TLE subset | Walker Delta (53°, 550 km) |
| --- | --- | --- |
| 15 | `[0,0,0,0,0,0]` | `[0,0,1,0,0,0]` |
| 100 | `[0,1,1,0,2,0]` | — |
| 300 | `[7,6,2,0,2,0]` — 2 gaps | `[3,3,4,4,3,3]` — **no gaps** |
| 1000 | `[13,11,7,4,9,8]` | — |
| 1584 | — | `[18,15,18,16,18,16]` |

Two conclusions:

1. **The captured dataset is survivorship-biased.** It recorded only satellites
   already above the reference point, so its first 15 satellites look like a
   dense constellation. Under unbiased propagation the same 15 give zero
   coverage. Earlier allocation results may therefore rest on artificially high
   satellite availability.
2. **Uniformity beats size.** A Walker constellation reaches continuous
   coverage at ~300 satellites where an arbitrary real subset needs ~1000.

### What the literature does instead

Simulators do not use real TLEs as the experimental base. Hypatia takes shell
parameters — altitude, inclination, satellites per plane, number of planes —
and **generates** TLEs from them. Real TLEs are used to *validate* the
synthetic constellation, not to drive it.

If this phase is resumed, the recommended shape is three datasets with
distinct roles: the captured file as historical reference, a real-TLE manifest
for validation, and a **Walker Delta shell as the experimental base**. Adding a
`--walker P/S/i/h` mode to `trace_builder.py` would reuse the propagation and
output format already written.

### Also discovered, still open

`linear_estimation` diverges from a real orbit by **1000 km in 10 minutes**
and 2700 km in 20 — it extrapolates latitude and longitude in a straight line,
which is not an orbit. Wherever a trace runs out, positions past that point are
not meaningful.

---

**Goal:** a satellite's position comes from orbital mechanics, not from a
recorded observation table.

### Why

The traces file is the orbit model today. That has three consequences:

* A satellite can only exist where the file has data. Creating one means
  searching the catalog for a real satellite that passes nearby and borrowing
  its ground track.
* A satellite appears in the file only while it is above the reference point.
  Only 680 of 10,476 satellites have contiguous appearances; the median is 26
  appearances out of 840 steps. The scenario loader pads the gaps with `None`
  (the satellite goes inactive, correctly), but `get_coordinates_trace` — the
  path used when the agent adds a satellite — compacts them, so the satellite
  teleports between orbital passes (issue C).
* `linear_estimation`, the fallback when the trace runs out, extrapolates
  latitude and longitude linearly. A LEO ground track is a sinusoid drifting
  west as the Earth rotates beneath it, so the estimate diverges quickly.

### What it takes

1. **Add the `sgp4` dependency** (not currently installed).
2. **Acquire TLE data.** The current file has none — `satid` and
   `intDesignator` identify the satellite in a catalog, but the positions are
   already propagated server-side by N2YO. TLEs come from Celestrak or
   Space-Track by NORAD id.
3. **Write `leosim/orbit_models/sgp4_propagation.py`**, a mobility model with
   the same signature as `linear_estimation`: takes the satellite, returns
   `(lat, lon, alt)`.
4. **Store the TLE in `mobility_model_parameters`.** That field is already
   serialized by `Satellite.export()` and restored by `Simulator.initialize`,
   so orbital elements survive the scenario round trip with no format change.
5. **Give `tick_duration` meaning.** SGP4 propagates to an absolute epoch, so
   the simulator needs a real start time and a real seconds-per-tick (issue
   D). A tick is currently ~56 s of trace time while `tick_duration` defaults
   to 1 s and is read by nobody.
6. **Retire the catalog lookup.** Creating a satellite becomes: pick orbital
   elements, propagate. `SatelliteCatalog`, `get_closest_satellite` and the
   haversine ranking all become unnecessary.

### Decided design: hybrid by default, global switch for experiments

The two models coexist rather than one replacing the other. This was verified
end to end: a per-satellite model choice and its parameters survive
`save_scenary` → `Simulator.initialize`, and two models run side by side in
the same tick.

Three properties of the existing code make this work with no structural
change:

* `mobility_model` is an instance attribute, so each satellite carries its own.
* `Satellite.export()` stores `mobility_model.__name__` and
  `Simulator.initialize` resolves it through the `leosim.simulator` namespace,
  so the choice survives the scenario round trip. A new model must therefore
  be exported by `leosim/orbit_models/__init__.py`, which today exports only
  `coordinates_history`.
* `mobility_model_parameters` round-trips as plain data — that is where the
  TLE lives, with no scenario format change.

**Default mode — fallback hybrid.** `Satellite.step()` already calls the
mobility model only where the trace has no value:

```python
needs_calculation = (len(self.coordinates_trace) <= steps) or (self.coordinates_trace[steps] is None)
if needs_calculation:
    new_position = self.mobility_model(self)
```

A scenario satellite holds 179 positions of which roughly 176 are `None` —
precisely the gaps between orbital passes. With SGP4 as the model, a satellite
follows **real observations during a pass and propagated physics through the
gaps**, which is exactly where the teleport of issue C occurs.

**Experiment switch — global choice.** A field on `SimulationConfig` and a
sidebar selector pick the orbit model for the whole constellation, so
`traces only`, `SGP4 only` and `hybrid` become three comparable
configurations.

### Decided: visibility becomes geometric

Today a satellite with no recorded position goes `active = False`. The code
uses **absence of data as a proxy for "not overhead"**.

Once propagation fills the gaps a satellite always has a position, so
visibility must be decided **geometrically** — distance against
`max_connection_range` — whenever the trace file is not the source of the
position. This is physically correct and it changes what coverage means, so
it is a deliberate decision rather than a side effect.

Trace-driven satellites keep the current behaviour, so the two modes stay
comparable only through the experiment switch, never by accident.

### Blocking dependency

There is no TLE data. `satid` and `intDesignator` identify a satellite in a
catalog, but the file carries positions already propagated server-side by
N2YO. TLEs must be fetched from Celestrak or Space-Track by NORAD id before
any of this can run.

**Risk: high for results.** Satellite dynamics change, so every metric
changes. Do this **before** collecting data for publication, not after.

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

Assessed 29 September 2026, **not scheduled**. Recorded so the question does
not have to be reopened from scratch.

### What it is

Jev is TypeSafe AI's first "System One Model": *unstructured state in, typed
probabilistic decisions out*. It is not a text generator. The vendor describes
a separate architecture with a parallel sampler that emits all outputs in a
single query rather than one token at a time, trained with Reinforcement
Learning for Calibrated Decisions rather than RLHF — the stated target being
epistemically honest probabilities instead of human preference.

Published figures: end-to-end **70 ms to 500 ms**, claimed **40x-200x faster**
than an LLM at equivalent intelligence, input at **$0.042/MTok with output
tokens free**. Outputs are type-safe values drawn from a declared set, each
carrying a confidence score. The use cases named are "smart if-statements",
map-reduce over large data, real-time applications and verification.

*All of these come from the vendor's own announcement; none is independently
verified here.*

### Why it fits this system unusually well

The ground station agent is close to the archetype that model is built for.

| What the station agent does | What Jev takes |
| --- | --- |
| Reads a digest of its neighbourhood | unstructured state in |
| Answers `best_fit`, `longest_duration` or `agnostic` | a declared, closed output set |
| Is called 20.7 times per tick, 28 stations in parallel | parallel sampling, per-call latency in milliseconds |
| Needs no prose — its answer is consumed by code | typed value, not text |

The settled Phase 4 design already narrows the station's reply to one option
out of a fixed set with a one-sentence reason. Drop the sentence and that is
exactly a typed decision.

**Projected tick cost**, at 20.7 calls per tick:

| | Per tick |
| --- | --- |
| `llama3.1:8b` today | 453 s |
| `llama3.1:8b` with the digest (projected) | 99 s |
| Jev at the slow end, 500 ms | **10.3 s** |
| Jev at the fast end, 70 ms | **1.4 s** |

At the digest's ~118 tokens per call, a 180-step run sends about 440k input
tokens: **$0.018 per run**, or roughly $18 for a thousand runs. Cost is not
what would decide this.

### The part that is genuinely interesting for the thesis

**The confidence score replaces self-reported agnosticism with a measurement.**

The current design asks the station to *declare* itself indifferent. A station
that says "agnostic" might be indifferent, or might be a small model failing to
commit. Those are not the same thing, and nothing in the reply distinguishes
them.

A calibrated probability does distinguish them: 51%/49% between two options is
indifference expressed numerically, and 95% is a station whose local view
genuinely determines the answer. That turns the thesis's central claim — that
localized decisions carry information — from something argued into something
plotted.

### Where it does not fit

**The dashboard agent.** It converses with the operator, explains what
happened, and writes the report at the end of an automatic run. That is prose,
and a typed-decision model does not produce prose.

**The orchestrator's intent translation.** Turning "simulate a scenario where a
region loses two gateways and tell me what happens to latency" into objectives
and a configuration is a language task.

So the shape would be **hybrid**, which also matches the System One / System
Two framing the vendor uses: an LLM at the two language-facing boundaries, a
typed-decision model for the high-volume decision inside the simulation loop.

### What would have to be settled first

* **It is a hosted API, and the thesis is about small models on ground
  stations.** Whether that contradicts the premise depends on what "localized"
  means in the claim: locality of *decision scope in the network topology*, or
  locality of *where inference runs*. The dissertation has to say which, and
  the answer changes whether this is a contribution or a contradiction.
* **Reproducibility.** A hosted model can change under a result. Measurements
  taken against a pinned local model in Ollama can be rerun in two years; ones
  taken against a managed endpoint may not be. For the dissertation's headline
  numbers this matters more than speed.
* **The claims are the vendor's.** 40x-200x and "cannot hallucinate" need
  independent measurement on this workload before being repeated.
* **Offline operation disappears.** Every tick needs the network.

### What it does not change

**Phase 3's work is the input pipeline either way.** "Unstructured state in"
still has to be produced, and a smaller, cleaner state is better for a typed
decision model too — cheaper per call, and more stable between ticks, which is
what makes the skip filter work. The translator is not wasted if this happens;
it is the prerequisite.

### When to revisit

After the demonstration, and after Phase 8 exists to measure it against the
local-model baseline. The number to beat is the one Phase 3 is establishing.

### Source

* [Introducing System One Models and Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev), TypeSafe AI

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
