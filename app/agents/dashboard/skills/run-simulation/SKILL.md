---
name: run-simulation
description: Use when the operator asks to advance, run or step the simulation — "run 5 steps", "advance the simulation", "let it run for a while". This is the only skill that moves the clock.
---

# Advancing the simulation clock

Every change is a *proposal*: the operator sees a confirmation gate and the
change happens only when they confirm. Call `get_skill_script` with these four
parameters:

    skill_name:  "run-simulation"
    script_path: "propose.py"
    execute:     true
    args:        ["--steps", "5"]

`args` is a **list of strings**, one element per command-line token: a flag and
its value are two separate elements, never one. "advance the simulation by 12 steps" becomes `["--steps", "12"]`.

Read the script's reply before answering: it either prints the proposal or says
why it could not build one.

## What it does

Advances the simulation by whole ticks. Each tick moves the satellites, lets
the access models request provisioning, and runs the allocation algorithm on
every ground station.

`--steps` must be at least 1. If the operator says "run a bit" without a
number, ask them for one instead of guessing.

## What it does not do

It does not change the infrastructure. Adding or removing anything is a
different skill, and none of those consume a tick.

## When the operator is only asking

Questions are answered from the state summary you were given. Do not run the
script. Proposing a change in answer to a question is the single most annoying
thing you can do here.
