---
name: restart-simulation
description: Use when the operator asks to restart, reset or rebuild the simulation from the beginning, or to change how it is built — a different number of users or satellites, another scenario or another allocation algorithm.
---

# Restarting the simulation at step zero

Every change is a *proposal*: the operator sees a confirmation gate and the
change happens only when they confirm. Call `get_skill_script` with these four
parameters:

    skill_name:  "restart-simulation"
    script_path: "propose.py"
    execute:     true
    args:        ["--num-users", "40", "--scenario", "leo"]

`args` is a **list of strings**, one element per command-line token: a flag and
its value are two separate elements, never one. "restart with 40 users" becomes `["--num-users", "40"]`; a plain
"restart the simulation" becomes `[]`.

Read the script's reply before answering: it either prints the proposal or says
why it could not build one.

## Settings

* `--num-users` — how many users to create, 1 or more.
* `--num-satellites` — the maximum number of satellites, 1 or more.
* `--scenario` — `hybrid`, `leo` or `terrestrial`.
* `--algorithm` — the allocation algorithm to run.
* `--gml-path` — the terrestrial topology file.
* `--satellites-path` — the satellite traces file.

The values are checked against the configuration currently loaded, which lives
in the dashboard rather than here, so an invalid one is refused at the gate
instead of by this script.
