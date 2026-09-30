---
name: add-nodes
description: Use when the operator asks to add satellites or ground stations to the network. Handles one node or many in a single proposal.
---

# Adding satellites or ground stations

Every change is a *proposal*: the operator sees a confirmation gate and the
change happens only when they confirm. Call `get_skill_script` with these four
parameters:

    skill_name:  "add-nodes"
    script_path: "propose.py"
    execute:     true
    args:        ["--node-types", "Satellite", "--latitudes", "-7.2", "--longitudes", "-35.8"]

`args` is a **list of strings**, one element per command-line token: a flag and
its value are two separate elements, never one. "add a satellite at -8.1, -34.9" becomes
`["--node-types", "Satellite", "--latitudes", "-8.1", "--longitudes", "-34.9"]`.

Read the script's reply before answering: it either prints the proposal or says
why it could not build one.

## The lists are parallel

Entry *i* of each list describes the same node, so all three must be the same
length. `--node-types` takes `Satellite` or `GroundStation`, spelled exactly
like that.

**Never ask the operator for an altitude.** It follows from the node type —
550 km for a satellite, 0 for a ground station — and is filled in for you. The
proposal says so, and the operator sees it at the gate.

**When the operator names an existing node** — "near ground station 24" —
read that node's coordinates from the context state you were given and pass
them. They are already in front of you; asking for them wastes the operator's
turn.

Send one call with the full lists rather than one call per node: the operator
then confirms once instead of five times.

## Things that will trip you up

**Do not invent spacing.** If the operator gives one position for several
nodes, repeat that position — the code spreads them out itself.

**Do not ask about capacity.** Each node's CPU and memory are drawn
automatically. A node is a place, not a size.

## What comes after

A node is empty when created. If the operator wants it to host applications,
a process unit has to be attached to it afterwards — that is a different
skill, and it needs the node's id, which only exists once this is confirmed.

## When the operator is only asking

Questions are answered from the state summary you were given. Do not run the
script. Proposing a change in answer to a question is the single most annoying
thing you can do here.
