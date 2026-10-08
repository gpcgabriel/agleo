from collections.abc import Iterator, Sequence

class Point:
    latitude: float
    longitude: float
    altitude: float
    def __new__(
        cls,
        latitude: float | str | Sequence[float] | Point | None = None,
        longitude: float | None = None,
        altitude: float | None = None,
    ) -> Point: ...
    def __getitem__(self, index: int) -> float: ...
    def __iter__(self) -> Iterator[float]: ...
