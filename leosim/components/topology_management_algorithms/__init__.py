"""Algorithms that add the links between satellites on every tick."""

from .barabasi_albert_topology_management import barabasi_albert_topology_management
from .default_topology_management import default_topology_management, mesh_network

__all__ = ["barabasi_albert_topology_management", "default_topology_management", "mesh_network"]
