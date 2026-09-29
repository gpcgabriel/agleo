"""Rendering of the network state as a digest a small model can read.

The state arrives as nested dictionaries built for a program. Serializing it
costs about 2 600 characters per station, and elapsed time is almost exactly
linear in prompt length, so most of a tick is spent reading JSON punctuation
and fields that are always zero.

This renders the same decision-relevant facts as plain lines: about 470
characters, an 82% reduction.

**This module translates. It does not decide.** Every process unit the station
can reach appears, in the order the state lists them. Free capacity and host
are derived because the model would otherwise have to work them out from
`cpu_total`/`cpu_used` and a satellite id. Nothing is sorted by how well it
fits, nothing is left out for being a poor candidate, and no option is marked
as preferable. Those are the agent's job, and moving them here would make the
agent a rubber stamp.
"""

UNKNOWN = "-"


def component_id(key):
    """Returns: int or None: The numeric part of a key such as "PU_17"."""
    try:
        return int(key.split("_")[1])
    except (IndexError, ValueError):
        return None


def build_delay_by_satellite(topology):
    """Maps each satellite to the delay of its link with this station.

    `build_network_state` already filters `gs_sat` down to the asking station,
    so every link here belongs to it.

    Args:
        topology (dict): The exported topology, trimmed to this station.

    Returns:
        dict: Satellite id to delay in milliseconds, rounded to one decimal.
    """
    return {link["sat"]: round(link.get("delay", 0), 1) for link in topology.get("gs_sat", [])}


def render_applications(applications, pending_app_ids):
    """Renders the applications this station is being asked to place.

    Args:
        applications (dict): Exported applications, keyed "App_<id>".
        pending_app_ids (list): The ones this station could serve.

    Returns:
        list: One line per application.
    """
    pending = set(pending_app_ids)
    lines = []

    for key, application in applications.items():
        application_id = component_id(key)
        if application_id not in pending:
            continue

        placed_on = application.get("provisioned_on")
        lines.append(
            f"  {application_id} "
            f"{application.get('cpu', 0)} "
            f"{application.get('mem', 0)} "
            f"{application.get('remaining_time', 0)} "
            f"{placed_on if placed_on is not None else UNKNOWN}"
        )

    return lines


def render_process_units(process_units, unit_hosts, delay_by_satellite):
    """Renders the process units the station can reach.

    Args:
        process_units (dict): Exported units, keyed "PU_<id>".
        unit_hosts (dict): Unit key to the satellite or station it sits on.
        delay_by_satellite (dict): Satellite id to link delay.

    Returns:
        list: One line per available unit.
    """
    lines = []

    for key, unit in process_units.items():
        if not unit.get("available", True):
            continue

        host = unit_hosts.get(key, UNKNOWN)
        if host.startswith("Sat_"):
            delay = delay_by_satellite.get(component_id(host), UNKNOWN)
        elif host.startswith("GS_"):
            # A unit on the station itself is reached without a radio hop.
            delay = 0
        else:
            delay = UNKNOWN

        lines.append(
            f"  {component_id(key)} "
            f"{unit.get('cpu_total', 0) - unit.get('cpu_used', 0)} "
            f"{unit.get('mem_total', 0) - unit.get('mem_used', 0)} "
            f"{host} "
            f"{delay}"
        )

    return lines


def render_digest(state, pending_app_ids):
    """Renders one station's view of the network as a digest.

    Args:
        state (dict): The state built by `build_network_state`.
        pending_app_ids (list): Applications this station could place.

    Returns:
        str: The digest to put in the prompt.
    """
    station = state.get("ground_station", {})
    topology = state.get("topology", {})
    delay_by_satellite = build_delay_by_satellite(topology)

    lines = [
        f"STEP {state.get('step', 0)} | station at {station.get('pos')} "
        f"| reach {station.get('range')} km | scenario {state.get('scenario')}",
        "",
        "PLACE THESE APPLICATIONS  id cpu mem runs_for on_unit",
    ]
    lines += render_applications(state.get("applications", {}), pending_app_ids)

    lines += ["", "PROCESS UNITS IN REACH  id cpu_free mem_free host delay_ms"]
    lines += render_process_units(state.get("process_units", {}), state.get("unit_hosts", {}), delay_by_satellite)

    lines += [
        "",
        f"SATELLITES IN REACH {len(state.get('satellites', {}))} "
        f"| LINKS {topology.get('link_count', 0)} "
        f"| FLOWS active {topology.get('flows_active', 0)} waiting {topology.get('flows_waiting', 0)}",
    ]

    return "\n".join(lines)
