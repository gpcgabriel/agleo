---
name: add-process-unit
description: Use when the operator asks to add computing capacity, a process unit, a server or an edge node to an existing satellite or ground station.
---

# Attaching a process unit to a node

Every change is a *proposal*: the operator sees a confirmation gate and the
change happens only when they confirm. Call `get_skill_script` with these four
parameters:

    skill_name:  "add-process-unit"
    script_path: "propose.py"
    execute:     true
    args:        ["--target-type", "Satellite", "--target-id", "3", "--cpu", "40", "--memory", "40"]

`args` is a **list of strings**, one element per command-line token: a flag and
its value are two separate elements, never one. "give ground station 7 a server with 30 CPU and 20 memory" becomes
`["--target-type", "GroundStation", "--target-id", "7", "--cpu", "30", "--memory", "20"]`.

Read the script's reply before answering: it either prints the proposal or says
why it could not build one.

## What a process unit is

Where an application actually runs. A satellite or ground station without one
can route traffic but cannot host anything.

## The host has to exist

`--target-id` names a node that is already in the simulation. Read it from the
state summary you were given — do not guess, and do not use the id of a node
that was proposed but not yet confirmed.

`--target-type` is `Satellite` or `GroundStation`, spelled exactly like that,
and has to match what the id refers to.

## Sizing it

`--cpu` and `--memory` are the unit's total capacity, and both have to be at
least 1. Here the operator *is* sizing a specific thing, so use the numbers
they give. If they do not give any, ask.

## When the operator is only asking

Questions are answered from the state summary you were given. Do not run the
script. Proposing a change in answer to a question is the single most annoying
thing you can do here.
