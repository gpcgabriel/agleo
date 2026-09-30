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


class ReconciledDecision:
    """What a model's reply covers of the question it was asked.

    A reply is not trusted to answer the question put to it. The station is
    asked about a specific set of pending applications, and a small model
    routinely returns fewer ids than that — or ids that were never in the
    question. Both are recorded rather than absorbed: an application the model
    left out is not placed, not counted as failed and, before this existed,
    left no trace at all, so 19% of the decisions in a measured run were
    invisible.
    """

    def __init__(self, best_fit, longest_duration, omitted, invented):
        """Args:
        best_fit (list): Applications to place with the best_fit strategy.
        longest_duration (list): Applications to place with longest_duration.
        omitted (list): Applications asked about that the reply did not cover.
        invented (list): Ids the reply named that were never asked about.
        """
        self.best_fit = best_fit
        self.longest_duration = longest_duration
        self.omitted = omitted
        self.invented = invented

    def is_complete(self):
        """Returns: bool: True if the reply answered exactly the question asked."""
        return not self.omitted and not self.invented

    def __repr__(self):
        return (
            f"ReconciledDecision(best_fit={self.best_fit}, longest_duration={self.longest_duration}, "
            f"omitted={self.omitted}, invented={self.invented})"
        )


def reconcile(decision, pending_app_ids):
    """Matches a model's reply against the applications it was asked about.

    An application must be placed once, so an id listed under both strategies
    goes to best_fit and the duplicate is dropped. An id the station was not
    asked about is dropped too: placing it would have the station act outside
    the neighbourhood it was given, and `hybrid_allocation` would happily do it.

    Args:
        decision (AllocationDecision): The model's reply.
        pending_app_ids (list): Applications the station was asked about.

    Returns:
        ReconciledDecision: The reply split into what will be acted on and
        what the model got wrong.
    """
    asked = set(pending_app_ids)

    best_fit = []
    longest_duration = []
    invented = []
    seen = set()

    for app_ids, target in ((decision.best_fit, best_fit), (decision.longest_duration, longest_duration)):
        for app_id in app_ids:
            if app_id in seen:
                continue
            seen.add(app_id)
            if app_id in asked:
                target.append(app_id)
            else:
                invented.append(app_id)

    omitted = [app_id for app_id in pending_app_ids if app_id not in seen]

    return ReconciledDecision(best_fit, longest_duration, omitted, invented)
