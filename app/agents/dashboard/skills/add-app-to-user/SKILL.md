---
name: add-app-to-user
description: Use when the operator asks to add an application, a workload or a service to an existing user, or to give a user something to run.
---

# Giving an application to a user

Every change is a *proposal*: the operator sees a confirmation gate and the
change happens only when they confirm. Call `get_skill_script` with these four
parameters:

    skill_name:  "add-app-to-user"
    script_path: "propose.py"
    execute:     true
    args:        ["--user-id", "2", "--cpu", "20", "--memory", "30"]

`args` is a **list of strings**, one element per command-line token: a flag and
its value are two separate elements, never one. "give user 5 an app needing 10 CPU and 15 memory" becomes
`["--user-id", "5", "--cpu", "10", "--memory", "15"]`.

Read the script's reply before answering: it either prints the proposal or says
why it could not build one.

## The user has to exist

`--user-id` names a user already in the simulation. Read it from the state
summary — do not guess, and do not use the id of a user that was proposed but
not yet confirmed.

## Demand, not capacity

`--cpu` and `--memory` are what the application *asks for*, not what a machine
provides. A process unit has to have that much free for the application to be
placed. Both have to be at least 1.

## What happens next

The application starts unplaced. It is the allocation algorithm, on the next
tick, that decides which process unit hosts it — or leaves it pending because
nothing in reach has room.

## When the operator is only asking

Questions are answered from the state summary you were given. Do not run the
script. Proposing a change in answer to a question is the single most annoying
thing you can do here.
