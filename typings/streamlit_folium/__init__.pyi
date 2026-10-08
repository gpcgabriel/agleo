# Repeating the signature streamlit-folium 0.27 annotates inline: the package ships without py.typed.
from collections.abc import Callable, Iterable
from typing import Any

import folium

def st_folium(
    fig: folium.MacroElement,
    key: str | None = None,
    height: int = 700,
    width: int | None = 500,
    returned_objects: Iterable[str] | None = None,
    zoom: int | None = None,
    center: tuple[float, float] | None = None,
    feature_group_to_add: list[folium.FeatureGroup] | folium.FeatureGroup | None = None,
    return_on_hover: bool = False,
    use_container_width: bool = False,
    layer_control: folium.LayerControl | None = None,
    pixelated: bool = False,
    debug: bool = False,
    render: bool = True,
    on_change: Callable[..., Any] | None = None,
    wrap_longitude: bool = False,
) -> dict[str, Any]: ...
