"""
Parameterized query functions for the mise-ai agent.
These wrap SQL queries behind typed Python interfaces - the LLM never sees raw SQL.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import (
    Booking,
    BookingStatus,
    Customer,
    Premise,
    PremiseTag,
    PremisesReview,
    Schedule,
    Service,
    ServiceOption,
    Staff,
    StaffPremise,
    StaffReview,
    StaffService,
    decode_tags,
    encode_tags,
    BLOCKING_STATUSES,
)
from utils.scheduling import build_timeframes


def search_premises(
    session: Session,
    tags: list[str] | None = None,
    keyword: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search premises by category tags and/or keyword."""
    query = session.query(Premise)

    if tags:
        bitmask = encode_tags(tags)
        query = query.filter(Premise._tags.op("&")(bitmask) > 0)

    if keyword:
        query = query.filter(Premise.name.ilike(f"%{keyword}%"))

    premises = query.limit(limit).all()

    results = []
    for p in premises:
        results.append({
            "id": str(p._id),
            "name": p.name,
            "address": f"{p.address_line}, {p.state} {p.post_code}",
            "tags": p.tag_names,
            "description": p.description or "",
            "rating": round(p.rating, 1) if p.rating else "No reviews yet",
            "contact": p.contact_number or p.contact_email or "",
        })

    return results


def search_services(
    session: Session,
    premise_id: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    """Search services, optionally filtered by premise and/or keyword."""
    query = session.query(Service)

    if premise_id:
        query = query.filter(Service.premise_id == uuid.UUID(premise_id))

    if keyword:
        query = query.filter(Service.name.ilike(f"%{keyword}%"))

    services = query.all()

    results = []
    for s in services:
        options = []
        for opt in s.service_options:
            options.append({
                "name": opt.name,
                "price": f"${opt.price:.2f}",
                "extra_time_mins": int((opt.extra_time or 0) * 60),
            })

        results.append({
            "id": str(s._id),
            "name": s.name,
            "price": f"${s.price:.2f}",
            "duration_minutes": s.duration_minutes,
            "description": s.description or "",
            "pricing_type": s.unit_name,
            "premise_id": str(s.premise_id),
            "options": options,
        })

    return results


def get_staff_for_service(
    session: Session,
    premise_id: str,
    service_id: str,
) -> list[dict]:
    """Find staff members at a premise who offer a specific service."""
    staff_list = (
        session.query(Staff)
        .join(StaffPremise, StaffPremise.staff_id == Staff._id)
        .join(StaffService, StaffService.staff_id == Staff._id)
        .filter(
            StaffPremise.premise_id == uuid.UUID(premise_id),
            StaffService.service_id == uuid.UUID(service_id),
        )
        .all()
    )

    results = []
    for s in staff_list:
        avg_score = session.query(func.avg(StaffReview.score)).filter(
            StaffReview.staff_id == s._id,
            StaffReview.score.isnot(None),
        ).scalar()

        results.append({
            "id": str(s._id),
            "name": s.display_name,
            "rating": round(float(avg_score), 1) if avg_score else "No reviews yet",
        })

    return results


def check_availability(
    session: Session,
    premise_id: str,
    service_id: str,
    date: str,
    preferred_time: str | None = None,
) -> list[dict]:
    """
    Check staff availability for a service at a premise on a given date.
    This is the core RAG function: intent -> SQL -> schedule extraction -> context injection.

    Args:
        premise_id: UUID of the premise
        service_id: UUID of the service
        date: ISO date string (YYYY-MM-DD)
        preferred_time: Optional preferred time (HH:MM)
    """
    # Parse date range for the full day
    target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    day_start = target_date
    day_end = target_date + timedelta(days=1)

    # Get the service to know duration
    service = session.query(Service).filter(Service._id == uuid.UUID(service_id)).first()
    if not service:
        return [{"error": "Service not found"}]

    service_duration = timedelta(hours=service.default_time + (service.processing_time or 0))

    # Find staff who offer this service at this premise
    staff_premises = (
        session.query(StaffPremise)
        .join(StaffService, StaffService.staff_id == StaffPremise.staff_id)
        .filter(
            StaffPremise.premise_id == uuid.UUID(premise_id),
            StaffService.service_id == uuid.UUID(service_id),
        )
        .all()
    )

    results = []
    for sp in staff_premises:
        staff = session.query(Staff).filter(Staff._id == sp.staff_id).first()
        if not staff:
            continue

        # Build free timeframes using ported scheduling logic
        free_slots = build_timeframes(
            session=session,
            staff_premise_id=sp._id,
            staff_id=sp.staff_id,
            premise_id=sp.premise_id,
            start=day_start,
            end=day_end,
        )

        # Filter slots that can fit the service duration
        available_slots = []
        for slot in free_slots:
            slot_duration = slot.end - slot.start
            if slot_duration >= service_duration:
                # If preferred time specified, check if it falls within this slot
                if preferred_time:
                    h, m = map(int, preferred_time.split(":"))
                    pref_start = target_date.replace(hour=h, minute=m)
                    pref_end = pref_start + service_duration
                    if pref_start >= slot.start and pref_end <= slot.end:
                        available_slots.append({
                            "start": pref_start.strftime("%H:%M"),
                            "end": pref_end.strftime("%H:%M"),
                        })
                else:
                    available_slots.append({
                        "start": slot.start.strftime("%H:%M"),
                        "end": slot.end.strftime("%H:%M"),
                    })

        if available_slots:
            results.append({
                "staff_id": str(sp.staff_id),
                "staff_name": staff.display_name,
                "available_slots": available_slots,
            })

    return results


def get_premise_details(
    session: Session,
    premise_id: str,
) -> dict:
    """Get full details for a premise including services, staff, and reviews."""
    premise = session.query(Premise).filter(Premise._id == uuid.UUID(premise_id)).first()
    if not premise:
        return {"error": "Premise not found"}

    # Services
    services = []
    for s in premise.services:
        services.append({
            "id": str(s._id),
            "name": s.name,
            "price": f"${s.price:.2f}",
            "duration_minutes": s.duration_minutes,
            "description": s.description or "",
        })

    # Staff
    staff_list = []
    for sp in premise.staff_premises:
        staff = session.query(Staff).filter(Staff._id == sp.staff_id).first()
        if staff:
            staff_list.append({
                "id": str(staff._id),
                "name": staff.display_name,
            })

    # Reviews (latest 5)
    reviews = (
        session.query(PremisesReview)
        .filter(PremisesReview.premise_id == premise._id)
        .order_by(PremisesReview.date_created.desc())
        .limit(5)
        .all()
    )
    review_list = []
    for r in reviews:
        review_list.append({
            "score": r.score,
            "comment": r.comment,
        })

    return {
        "id": str(premise._id),
        "name": premise.name,
        "address": f"{premise.address_line}, {premise.state} {premise.post_code}",
        "tags": premise.tag_names,
        "description": premise.description or "",
        "rating": round(premise.rating, 1) if premise.rating else "No reviews yet",
        "contact": premise.contact_number or premise.contact_email or "",
        "services": services,
        "staff": staff_list,
        "recent_reviews": review_list,
    }


def create_booking(
    session: Session,
    staff_id: str,
    service_id: str,
    premise_id: str,
    customer_id: str,
    date: str,
    time: str,
) -> dict:
    """
    Create a new booking with PENDING status.
    Returns booking details for confirmation.
    """
    # Get service for price and duration
    service = session.query(Service).filter(Service._id == uuid.UUID(service_id)).first()
    if not service:
        return {"error": "Service not found"}

    staff = session.query(Staff).filter(Staff._id == uuid.UUID(staff_id)).first()
    if not staff:
        return {"error": "Staff not found"}

    # Parse start time
    target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    h, m = map(int, time.split(":"))
    start = target_date.replace(hour=h, minute=m)
    end = start + timedelta(hours=service.default_time)

    booking = Booking(
        _id=uuid.uuid4(),
        staff_id=uuid.UUID(staff_id),
        service_id=uuid.UUID(service_id),
        premise_id=uuid.UUID(premise_id),
        customer_id=uuid.UUID(customer_id),
        start=start,
        end=end,
        price=service.price,
        duration=service.default_time,
        processing_time=service.processing_time,
        _status=BookingStatus.PENDING.value,
        date_created=datetime.now(timezone.utc),
    )

    session.add(booking)
    session.commit()

    return {
        "booking_id": str(booking._id),
        "staff_name": staff.display_name,
        "service_name": service.name,
        "date": date,
        "time": f"{time} - {end.strftime('%H:%M')}",
        "price": f"${service.price:.2f}",
        "status": "PENDING",
        "message": "Booking created successfully! Awaiting confirmation.",
    }
