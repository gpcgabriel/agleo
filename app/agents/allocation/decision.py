"""The decision an allocation agent is asked to produce."""

from typing import List

from pydantic import BaseModel, Field


class AllocationDecision(BaseModel):
    """Which strategy to use for each pending application.

    This is a Pydantic model because `agno` takes the output schema in that
    form; it is the framework's contract, not a style choice. Declaring it
    makes Ollama constrain generation to this shape, so the reply never has
    to be recovered from free text.
    """

    best_fit: List[int] = Field(
        default_factory=list,
        description="IDs of the applications to place with the best_fit strategy.",
    )
    longest_duration: List[int] = Field(
        default_factory=list,
        description="IDs of the applications to place with the longest_duration strategy.",
    )


def split_without_duplicates(decision):
    """Splits a decision into two disjoint lists.

    An application must be placed once. If the model lists the same id under
    both strategies, best_fit wins and the duplicate is dropped.

    Args:
        decision (AllocationDecision): The model's reply.

    Returns:
        tuple: (best_fit ids, longest_duration ids), with no id in both.
    """
    best_fit = list(decision.best_fit)
    seen = set(best_fit)
    longest_duration = [app_id for app_id in decision.longest_duration if app_id not in seen]

    return best_fit, longest_duration
