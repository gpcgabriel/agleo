# Importing the simulator components.
from ..component_manager import ComponentManager
from .network_link import NetworkLink
from .satellite import Satellite
from .user import User
from typing import List, Tuple, Optional, Dict, Any


class GroundStation(ComponentManager):
    _instances = []
    _object_count = 0

    def __init__(
        self,
        id: int = 0,
        coordinates: Optional[Tuple[float, float, float]] = None,
        wireless_delay: int = 0,
        max_connection_range: int = 2000,
    ) -> None:
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        if id == 0:
            id = self.__class__._object_count
        self.id = id

        self.coordinates = coordinates
        self.wireless_delay = wireless_delay
        self.max_connection_range = max_connection_range

        self.users: List[User] = []
        self.process_unit = []

    def export(self) -> Dict[str, Any]:
        component = {
            "id": self.id,
            "coordinates": self.coordinates,
            "wireless_delay": self.wireless_delay,
            "max_connection_range": self.max_connection_range,
            "relationships": {
                "users": [{"id": user.id, "class": type(user).__name__} for user in self.users],
                "process_unit": (
                    [{"id": unit.id, "class": type(unit).__name__} for unit in self.process_unit]
                    if self.process_unit
                    else None
                ),
            },
        }
        return component

    def connect_server(self, server) -> None:
        # `export()` writes None when the station has no servers, and
        # `Simulator.initialize` restores that None. Without this guard,
        # attaching the first server to an empty station raises AttributeError.
        if self.process_unit is None:
            self.process_unit = []

        self.process_unit.append(server)
        server.coordinates = self.coordinates

    def step(self) -> None:
        self.connection_to_satellites()
        self.connect_users()

    def connect_users(self) -> None:
        """Connects every user currently within range to this ground station.

        Kept separate from `step()` so that connectivity can also be
        recomputed outside a simulation tick, when the operator changes the
        infrastructure and expects to see the effect right away.
        """
        topology = self.model.topology
        self.users = []

        for user in User.all():
            if topology.within_range(self, user):
                user.connect_to_access_point(self)

    def connection_to_satellites(self) -> None:
        topology = self.model.topology
        for satellite in Satellite.all():
            if satellite.coordinates is None:
                continue
            if topology.within_range(self, satellite) and satellite.is_gateway:
                if self.model.topology.has_edge(self, satellite):
                    continue
                link = NetworkLink()
                link["topology"] = topology
                link["nodes"] = [satellite, self]
                link["bandwidth"] = NetworkLink.default_bandwidth
                link["delay"] = link.get_delay()
                link["type"] = "dynamic"
                topology.add_edge(satellite, self)
                topology._adj[satellite][self] = link
                topology._adj[self][satellite] = link

    @staticmethod
    def export_groundstations() -> Dict:
        gs_data = {}
        for gs in GroundStation._instances:
            gpos = gs.coordinates
            gs_data[f"GS_{gs.id}"] = {
                "pos": (round(gpos[0], 1), round(gpos[1], 1)) if gpos else None,
                "range": gs.max_connection_range,
                "delay": gs.wireless_delay,
                "pus": [unit.id for unit in (gs.process_unit or [])],
                "users": [user.id for user in gs.users],
            }
        return gs_data
