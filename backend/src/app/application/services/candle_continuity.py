"""Linear, bounded-memory continuity scanning over ordered candle timestamps."""
from collections.abc import Iterable, Iterator

from app.application.services.execution_control import check_execution


def repository_open_times(repository, **query) -> Iterable[int]:
    streaming = getattr(repository, "iter_open_time_ms", None)
    if streaming is not None:
        return streaming(**query)
    # Compatibility for existing adapters; production SQLite uses the stream.
    return sorted(repository.list_open_time_ms(**query))


def missing_open_ranges(
    actual: Iterable[int], *, start: int, end: int, step: int,
    excluded: Iterable[tuple[int, int]] = (),
) -> Iterator[tuple[int, int]]:
    if step <= 0:
        raise ValueError("Candle step must be positive")
    if end < start:
        return
    exclusions: list[tuple[int, int]] = []
    for lower, upper in sorted(excluded):
        lower = max(start, start + ((lower - start + step - 1) // step) * step)
        upper = min(end, start + ((upper - start) // step) * step)
        if lower > upper:
            continue
        if exclusions and lower <= exclusions[-1][1] + step:
            exclusions[-1] = (exclusions[-1][0], max(upper, exclusions[-1][1]))
        else:
            exclusions.append((lower, upper))
    exclusion_index = 0

    def without_exclusions(lower: int, upper: int) -> Iterator[tuple[int, int]]:
        nonlocal exclusion_index
        while exclusion_index < len(exclusions) and exclusions[exclusion_index][1] < lower:
            exclusion_index += 1
        index = exclusion_index
        while index < len(exclusions) and exclusions[index][0] <= upper:
            skip_start, skip_end = exclusions[index]
            if lower < skip_start:
                yield lower, skip_start - step
            lower = max(lower, skip_end + step)
            index += 1
        if lower <= upper:
            yield lower, upper

    cursor = start
    last = None
    for index, observed in enumerate(actual):
        if index % 2000 == 0:
            check_execution()
        if last is not None and observed < last:
            raise ValueError("Candle timestamps must be ordered")
        last = observed
        if observed < cursor or (observed - start) % step:
            continue
        if observed > end:
            break
        if observed > cursor:
            yield from without_exclusions(cursor, observed - step)
        cursor = observed + step
    if cursor <= end:
        yield from without_exclusions(cursor, start + ((end - start) // step) * step)
