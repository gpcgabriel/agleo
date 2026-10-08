from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..components.satellite import Satellite


def coordinates_history(satellite: Satellite) -> None:
    size = satellite.mobility_model_parameters.get("len")

    for i in range(size):
        satellite.coordinates_trace.append(satellite.coordinates_trace[i % size])
