"""LLM-driven resource allocation.

The allocator is an ordinary allocation algorithm from the engine's point of
view: a callable taking `(model, parameters)` with the ground station in
`parameters["ground_station"]`, exactly like `best_fit_allocation`. The engine
therefore knows nothing about the LLM stack.
"""

from app.agents.allocation.allocator import LLMAllocator

__all__ = ["LLMAllocator"]
