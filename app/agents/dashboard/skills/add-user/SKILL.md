---
name: add-user
description: Use when the operator asks to add a user, a terminal or a subscriber at a geographic position.
---

# Creating a user at a position

Every change is a *proposal*: the operator sees a confirmation gate and the
change happens only when they confirm. Call `get_skill_script` with these four
parameters:

    skill_name:  "add-user"
    script_path: "propose.py"
    execute:     true
    args:        ["--lat", "-23.5", "--lon", "-46.6"]

`args` is a **list of strings**, one element per command-line token: a flag and
its value are two separate elements, never one. "create a user at -15.8, -47.9" becomes `["--lat", "-15.8", "--lon", "-47.9"]`.

Read the script's reply before answering: it either prints the proposal or says
why it could not build one.

## Where to put them

Latitude between -90 and 90, longitude between -180 and 180. Put the user
where the operator asks.

**You do not have to find them coverage.** A user out of reach of everything
is a valid thing to simulate, and often the point of the experiment. Place
them and let the simulation report what they can see.

## Reach

`--connection-range` defaults to 1500 km, which is what the scenario builder
uses. Only pass it when the operator asks for a different reach.

## What comes after

A user with no application does nothing. If the operator wants traffic, an
application has to be given to the user afterwards — a different skill, and it
needs the user's id, which only exists once this is confirmed.

## When the operator is only asking

Questions are answered from the state summary you were given. Do not run the
script. Proposing a change in answer to a question is the single most annoying
thing you can do here.
