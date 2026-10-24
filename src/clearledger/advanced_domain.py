"""Bounded meet-in-the-middle exact subset search; never allocates financial records."""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Literal
from uuid import UUID

from clearledger.matching_domain import integer

Outcome = Literal["UNIQUE", "AMBIGUOUS", "UNRESOLVED", "SEARCH_INCOMPLETE"]


@dataclass(frozen=True)
class Limits:
    max_candidates: int = 32
    max_combination_size: int = 8
    max_work: int = 100_000
    max_time_ms: int = 100
    top_k: int = 20

    def __post_init__(self) -> None:
        for value in (
            self.max_candidates,
            self.max_combination_size,
            self.max_work,
            self.max_time_ms,
            self.top_k,
        ):
            integer(value, minimum=1)
        # Hard ceilings also protect callers outside the HTTP/configuration layer.
        if (
            self.max_candidates > 40
            or self.max_combination_size > 40
            or self.max_work > 1_000_000
            or self.max_time_ms > 2000
            or self.top_k > 100
        ):
            raise ValueError("Search limits exceed hard safety ceilings")


@dataclass(frozen=True)
class SearchResult:
    outcome: Outcome
    reason: str
    candidates: tuple[tuple[UUID, ...], ...]
    search_exhaustive: bool
    work: int
    elapsed_ns: int
    ambiguity_proven: bool


class Exhausted(Exception):
    pass


DEFAULT_LIMITS = Limits()


def subsets(
    invoices: tuple[tuple[UUID, int], ...],
    target: int,
    limits: Limits = DEFAULT_LIMITS,
    *,
    clock: Callable[[], int] = perf_counter_ns,
) -> SearchResult:
    """O(2**(n/2) + matching joins), bounded in memory/work/time.

    All amounts are positive paise; invoice identities, not amounts, distinguish
    solutions. Size pruning is conservative: unexplored feasible prefixes make
    the result incomplete even if none would ultimately reach the target.
    """
    integer(target)
    if len({item[0] for item in invoices}) != len(invoices):
        raise ValueError("Duplicate invoice identity")
    for _, amount in invoices:
        integer(amount, minimum=1)
    start = clock()
    work = 0
    candidates: list[tuple[UUID, ...]] = []
    incomplete = False
    reason = "COMPLETE"

    def tick() -> None:
        nonlocal work
        if work >= limits.max_work:
            raise Exhausted("WORK_LIMIT")
        if clock() - start >= limits.max_time_ms * 1_000_000:
            raise Exhausted("TIME_LIMIT")
        work += 1

    def half(rows: tuple[tuple[UUID, int], ...]) -> list[tuple[int, tuple[UUID, ...]]]:
        nonlocal incomplete
        states: list[tuple[int, tuple[UUID, ...]]] = [(0, ())]
        for invoice_id, amount in rows:
            additions = []
            for total, ids in states:
                tick()
                if total + amount > target:
                    continue
                if len(ids) >= limits.max_combination_size:
                    incomplete = True
                    continue
                additions.append((total + amount, (*ids, invoice_id)))
            states.extend(additions)
        return states

    if len(invoices) > limits.max_candidates:
        reason, incomplete = "CANDIDATE_LIMIT", True
    elif target == 0:
        reason = "NO_AVAILABLE_CASH"
    else:
        # Ignore individually oversized invoices; positive amounts cannot join an exact subset.
        rows = tuple(sorted((row for row in invoices if row[1] <= target), key=lambda x: x[0]))
        try:
            left = half(rows[: len(rows) // 2])
            right = half(rows[len(rows) // 2 :])
            by_total: dict[int, list[tuple[UUID, ...]]] = {}
            for total, ids in right:
                tick()
                by_total.setdefault(total, []).append(ids)
            for total, ids in left:
                tick()
                for other in by_total.get(target - total, []):
                    tick()
                    if len(ids) + len(other) > limits.max_combination_size:
                        incomplete = True
                        continue
                    if len(candidates) >= limits.top_k:
                        raise Exhausted("TOP_K_LIMIT")
                    candidates.append(tuple(sorted((*ids, *other))))
            if incomplete:
                reason = "COMBINATION_SIZE_LIMIT"
        except Exhausted as error:
            incomplete, reason = True, str(error)
    outcome: Outcome = (
        "SEARCH_INCOMPLETE"
        if incomplete
        else "UNIQUE"
        if len(candidates) == 1
        else "AMBIGUOUS"
        if candidates
        else "UNRESOLVED"
    )
    return SearchResult(
        outcome,
        reason,
        tuple(sorted(candidates)),
        not incomplete,
        work,
        clock() - start,
        len(candidates) > 1 or reason == "TOP_K_LIMIT",
    )
