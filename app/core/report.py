"""Metrics of a completed run, and the report the operator reads.

A plan is approved once and then runs unattended, so what comes back has to
stand on its own: nobody was watching the ticks go by. Everything here is
derived from the snapshot history, which is already the record of what
happened — there is no second instrumentation path to keep in step, and the
numbers can be recomputed from a saved history alone.

What this does *not* measure is what the model cost. That belongs to the
allocator and is kept in `app/agents/allocation/metrics.py`, because a run
with no agent in it still has a report.
"""

PERCENT = 100.0


def share(part, whole):
    """Expresses a count as a percentage of its total.

    Args:
        part (int): The count.
        whole (int): What it is out of.

    Returns:
        float: The percentage, or zero when there was nothing to count. A
        scenario with no applications provisions none of them, and reporting
        that as 100% would read as a perfect run.
    """
    if not whole:
        return 0.0

    return round(part * PERCENT / whole, 1)


def measure_snapshot(snapshot):
    """Reduces one snapshot to the numbers a run is judged by.

    Args:
        snapshot (dict): A snapshot from `app/core/snapshot.py`.

    Returns:
        dict: The tick, how many users held a connection and how many
        applications were placed, the totals each is out of, and the size and
        mean delay of the network at that moment.
    """
    users = snapshot.get("users") or []
    applications = [app for user in users for app in user.get("applications") or []]
    links = snapshot.get("links") or []
    delays = [link.get("delay") or 0 for link in links]

    return {
        "step": snapshot.get("step", 0),
        "users_total": len(users),
        "users_connected": sum(1 for user in users if user.get("connected_aps")),
        "applications_total": len(applications),
        "applications_allocated": sum(1 for app in applications if app.get("allocated_to") is not None),
        "ground_stations": len(snapshot.get("ground_stations") or []),
        "satellites_active": sum(1 for satellite in snapshot.get("satellites") or [] if satellite.get("active")),
        "links": len(links),
        "mean_delay": round(sum(delays) / len(delays), 2) if delays else 0.0,
    }


def collect_run_metrics(history):
    """Measures every snapshot of a run and summarizes the series.

    Args:
        history (list): The session's snapshots, oldest first.

    Returns:
        dict: "series" with one measurement per snapshot and "final" with the
        last of them, plus the run's step count and the provisioning and
        connectivity shares as an average, as a final value, and at their
        worst tick. An empty history gives an empty series and nothing else,
        so the caller decides what to say about a run that produced nothing.
    """
    series = [measure_snapshot(snapshot) for snapshot in history or []]
    if not series:
        return {"series": [], "final": None, "steps_run": 0}

    provisioning = [share(row["applications_allocated"], row["applications_total"]) for row in series]
    connectivity = [share(row["users_connected"], row["users_total"]) for row in series]
    worst = min(range(len(series)), key=lambda index: provisioning[index])

    return {
        "series": series,
        "final": series[-1],
        # Counting ticks rather than snapshots: an infrastructure change
        # records a snapshot without advancing the clock, so the two differ
        # the moment a run is not purely automatic.
        "steps_run": series[-1]["step"] - series[0]["step"],
        "provisioning_mean": round(sum(provisioning) / len(provisioning), 1),
        "provisioning_final": provisioning[-1],
        "provisioning_worst": provisioning[worst],
        "provisioning_worst_step": series[worst]["step"],
        "connectivity_mean": round(sum(connectivity) / len(connectivity), 1),
        "connectivity_final": connectivity[-1],
        "links_mean": round(sum(row["links"] for row in series) / len(series), 1),
        "delay_mean": round(sum(row["mean_delay"] for row in series) / len(series), 2),
    }


def summarize_run(plan, metrics):
    """Writes the report the operator reads when a run ends.

    Args:
        plan (SimulationPlan): What was approved.
        metrics (dict): What `collect_run_metrics` measured.

    Returns:
        str: Markdown for the conversation.
    """
    if not metrics["series"]:
        return "The run produced no snapshots, so there is nothing to report."

    final = metrics["final"]
    config = plan.config
    stopped_early = metrics["steps_run"] < plan.steps

    lines = [f"### Simulation report — {metrics['steps_run']} of {plan.steps} steps"]
    if stopped_early:
        lines.append("\nThe run was stopped before the plan was spent; everything below covers what did run.")

    lines.append("\n| Measure | Result |")
    lines.append("| --- | --- |")
    lines.append(f"| Scenario | {config.scenario}, allocated by `{config.algorithm}` |")
    lines.append(
        f"| Network | {final['users_total']} users, {final['satellites_active']} active satellites, "
        f"{final['ground_stations']} ground stations |"
    )
    lines.append(
        f"| Applications placed | {metrics['provisioning_mean']}% on average, "
        f"{metrics['provisioning_final']}% at the last step |"
    )
    lines.append(
        f"| Worst tick | {metrics['provisioning_worst']}% placed, at step {metrics['provisioning_worst_step']} |"
    )
    lines.append(
        f"| Users connected | {metrics['connectivity_mean']}% on average, "
        f"{metrics['connectivity_final']}% at the last step |"
    )
    lines.append(f"| Network size | {metrics['links_mean']} links on average, {metrics['delay_mean']} ms mean delay |")
    lines.append(
        f"\nEvery tick is on the timeline: drag the slider to inspect any of them "
        f"({final['applications_allocated']} of {final['applications_total']} applications "
        f"are placed at the end)."
    )

    return "\n".join(lines)
