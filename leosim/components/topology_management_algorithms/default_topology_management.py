from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..network_link import NetworkLink
from ..satellite import Satellite

if TYPE_CHECKING:
    from ..topology import Topology


def mesh_network(topology: Topology) -> None:
    satellites = [sat for sat in Satellite.all() if sat.coordinates is not None]

    for satellite in satellites:
        targets = [
            neighbor
            for neighbor in satellites
            if neighbor != satellite
            and neighbor not in topology[satellite]
            and topology.within_range(satellite, neighbor)
        ]

        for target in targets:
            link = NetworkLink()

            link["nodes"] = [satellite, target]
            link["bandwidth"] = NetworkLink.default_bandwidth
            link["delay"] = link.get_delay()
            link["type"] = "dynamic"

            topology.attach_link(link)


def default_topology_management(topology: Topology, **parameters: Any) -> None:
    mesh_network(topology=topology)
