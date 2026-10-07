---
name: run-full-simulation
description: Use when the operator wants a whole simulation carried out for them and the results reported — "run a simulation for me", "simulate 50 steps with 40 users", "/simulate 20". This builds a new simulation, runs it from start to finish and answers with its metrics.
---

# Carrying out a whole simulation

Every change is a *proposal*: the operator sees a confirmation gate and the run
starts only when they confirm. Call `get_skill_script` with these four
parameters:

    skill_name:  "run-full-simulation"
    script_path: "propose.py"
    execute:     true
    args:        ["--steps", "20"]

`args` is a **list of strings**, one element per command-line token: a flag and
its value are two separate elements, never one. "simulate 50 steps with 40
users" becomes `["--steps", "50", "--num-users", "40"]`.

Read the script's reply before answering: it either prints the proposal or says
why it could not build one.

## What it does

Builds a new simulation, runs it from step zero to the end of the budget
without pausing in between, and reports what it measured: how many
applications were placed, how many users stayed connected, how large the
network was and what its mean delay came to.

`--steps` is the only required flag and must be at least 1. If the operator
says "run a simulation" without a number, ask them how long it should be
instead of guessing — the run goes to completion once approved.

Everything else keeps whatever the simulation is configured with:

    --num-users        how many users to create
    --num-satellites   maximum number of satellites
    --scenario         hybrid, leo or terrestrial
    --algorithm        allocation algorithm

Name only the settings the operator asked to change.

## What it does not do

It does not advance the simulation on screen — it replaces it. Moving the
current simulation forward and keeping everything in it is a different skill,
and so is restarting without running anything.
