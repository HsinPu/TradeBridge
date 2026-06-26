from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class CronSchedule:
    minutes: set[int]
    hours: set[int]
    days: set[int]
    months: set[int]
    days_of_week: set[int]


def parse_cron_expression(expression: str) -> CronSchedule:
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError("cron_expression must contain 5 fields: minute hour day month day_of_week.")

    return CronSchedule(
        minutes=_parse_field(fields[0], minimum=0, maximum=59, field_name="minute"),
        hours=_parse_field(fields[1], minimum=0, maximum=23, field_name="hour"),
        days=_parse_field(fields[2], minimum=1, maximum=31, field_name="day"),
        months=_parse_field(fields[3], minimum=1, maximum=12, field_name="month"),
        days_of_week=_parse_day_of_week(fields[4]),
    )


def validate_cron_expression(expression: str) -> None:
    parse_cron_expression(expression)


def cron_matches(expression: str, value: datetime) -> bool:
    schedule = parse_cron_expression(expression)
    value = _to_utc_minute(value)
    day_of_week = (value.weekday() + 1) % 7
    return (
        value.minute in schedule.minutes
        and value.hour in schedule.hours
        and value.day in schedule.days
        and value.month in schedule.months
        and day_of_week in schedule.days_of_week
    )


def next_cron_run(expression: str, *, after: datetime) -> datetime:
    parse_cron_expression(expression)
    cursor = _to_utc_minute(after) + timedelta(minutes=1)
    deadline = cursor + timedelta(days=366)
    while cursor <= deadline:
        if cron_matches(expression, cursor):
            return cursor
        cursor += timedelta(minutes=1)
    raise ValueError("cron_expression has no run time within the next 366 days.")


def _parse_day_of_week(value: str) -> set[int]:
    parsed = _parse_field(value, minimum=0, maximum=7, field_name="day_of_week")
    return {0 if item == 7 else item for item in parsed}


def _parse_field(value: str, *, minimum: int, maximum: int, field_name: str) -> set[int]:
    values: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"cron_expression has an empty {field_name} field item.")
        values.update(_parse_part(part, minimum=minimum, maximum=maximum, field_name=field_name))
    return values


def _parse_part(value: str, *, minimum: int, maximum: int, field_name: str) -> set[int]:
    range_part, step = _split_step(value, field_name=field_name)
    if range_part == "*":
        start = minimum
        end = maximum
    elif "-" in range_part:
        start_text, end_text = range_part.split("-", 1)
        start = _parse_int(start_text, minimum=minimum, maximum=maximum, field_name=field_name)
        end = _parse_int(end_text, minimum=minimum, maximum=maximum, field_name=field_name)
        if start > end:
            raise ValueError(f"cron_expression {field_name} range must start before it ends.")
    else:
        parsed = _parse_int(range_part, minimum=minimum, maximum=maximum, field_name=field_name)
        return {parsed}

    return set(range(start, end + 1, step))


def _split_step(value: str, *, field_name: str) -> tuple[str, int]:
    if "/" not in value:
        return value, 1
    range_part, step_text = value.split("/", 1)
    if not range_part:
        raise ValueError(f"cron_expression {field_name} step is missing a range.")
    step = _parse_int(step_text, minimum=1, maximum=10_000, field_name=f"{field_name} step")
    return range_part, step


def _parse_int(value: str, *, minimum: int, maximum: int, field_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"cron_expression {field_name} value must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"cron_expression {field_name} value must be between {minimum} and {maximum}.")
    return parsed


def _to_utc_minute(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)
