"""
Port of mise-api scheduling logic for availability calculation.
Based on StaffPremise.naive_build_timeframes() and get_free_timeframes()
from mise-api/src/api/schedule/models.py
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Booking,
    Schedule,
    ScheduleApprovalStatus,
    StaffPremise,
    BLOCKING_STATUSES,
)


@dataclass
class Timeframe:
    start: datetime
    end: datetime
    schedule_id: uuid.UUID
    booking_id: Optional[uuid.UUID] = None


def get_schedule_rows(
    session: Session,
    staff_premise_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> list[Schedule]:
    """Query approved schedules within a date range for a staff-premise."""
    # Replicate Schedule.within() logic:
    # Non-recurring: start <= end AND end >= start
    # Recurring: start <= end AND repeat_until >= start
    from sqlalchemy import or_, and_

    return (
        session.query(Schedule)
        .filter(
            or_(
                and_(
                    Schedule._week == 0,
                    Schedule.start <= end,
                    Schedule.end >= start,
                ),
                and_(
                    Schedule._week != 0,
                    Schedule.start <= end,
                    Schedule.repeat_until >= start,
                ),
            ),
            Schedule.staff_premise_id == staff_premise_id,
            Schedule._approval_status == ScheduleApprovalStatus.APPROVED.value,
        )
        .all()
    )


def remove_unavailable(
    timeframe: Timeframe, booking: Booking
) -> list[Optional[Timeframe]]:
    """Split a timeframe around a booking, accounting for processing_time."""
    results = []

    booking_effective_end = booking.end - timedelta(
        hours=booking.processing_time or 0
    )

    # Left fragment: before the booking
    if booking.start > timeframe.start:
        results.append(Timeframe(timeframe.start, booking.start, timeframe.schedule_id))
    else:
        results.append(None)

    # Right fragment: after the booking (minus processing time)
    if booking_effective_end < timeframe.end:
        results.append(Timeframe(booking_effective_end, timeframe.end, timeframe.schedule_id))
    else:
        results.append(None)

    return results


def get_free_timeframes(
    session: Session,
    staff_id: uuid.UUID,
    premise_id: uuid.UUID,
    timeframe: Timeframe,
) -> list[Timeframe]:
    """
    Queue-based algorithm to find free time slots by splitting around existing bookings.
    Replicates StaffPremise.get_free_timeframes() from mise-api.
    """
    from sqlalchemy import func, text

    unchecked_queue = [timeframe]
    free_timeframes: list[Timeframe] = []

    while unchecked_queue:
        current = unchecked_queue.pop()

        # Find overlapping booking using Booking.overlaps logic:
        # effective_end = end - processing_time_hours
        # (effective_end > start) & (booking.start < end)
        effective_end = Booking.end - (
            text("interval '1 hour'") * func.coalesce(Booking.processing_time, 0)
        )

        overlapping = session.scalars(
            select(Booking).where(
                Booking.staff_id == staff_id,
                Booking.premise_id == premise_id,
                effective_end > current.start,
                Booking.start < current.end,
                Booking._status.in_(BLOCKING_STATUSES),
            )
        ).first()

        if overlapping:
            fragments = remove_unavailable(current, overlapping)
            for frag in fragments:
                if frag is not None:
                    unchecked_queue.append(frag)
        else:
            free_timeframes.append(current)

    return free_timeframes


def build_timeframes(
    session: Session,
    staff_premise_id: uuid.UUID,
    staff_id: uuid.UUID,
    premise_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> list[Timeframe]:
    """
    Build list of free time slots for a staff member at a premise within a date range.
    Replicates StaffPremise.naive_build_timeframes() from mise-api.
    Complexity: O(m*n) where m = schedules, n = days in range.
    """
    schedules = get_schedule_rows(session, staff_premise_id, start, end)

    start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)

    timeframes: list[Timeframe] = []

    for schedule in schedules:
        if schedule.is_repeating:
            # Walk day by day through the range
            cursor = schedule.start
            while cursor <= end_utc and (schedule.repeat_until is None or cursor <= schedule.repeat_until):
                if cursor >= start_utc and cursor.weekday() in schedule.week_days:
                    tf = Timeframe(
                        start=cursor,
                        end=cursor + schedule.duration,
                        schedule_id=schedule._id,
                    )
                    free = get_free_timeframes(session, staff_id, premise_id, tf)
                    timeframes.extend(free)
                cursor += timedelta(days=1)
        else:
            # Non-recurring: use schedule start/end directly
            tf = Timeframe(
                start=schedule.start,
                end=schedule.end,
                schedule_id=schedule._id,
            )
            free = get_free_timeframes(session, staff_id, premise_id, tf)
            timeframes.extend(free)

    # Deduplicate by (start, end)
    seen = set()
    unique = []
    for tf in timeframes:
        key = (tf.start, tf.end)
        if key not in seen:
            seen.add(key)
            unique.append(tf)

    return sorted(unique, key=lambda t: t.start)
