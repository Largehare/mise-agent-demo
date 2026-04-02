"""LangChain tool definitions wrapping fake data query functions."""

import json
from typing import Optional

from langchain_core.tools import tool

from db.fake_data import (
    check_availability as _check_availability,
    create_booking as _create_booking,
    get_premise_details as _get_premise_details,
    search_premises as _search_premises,
    search_services as _search_services,
)


@tool
def search_premises(
    tags: Optional[list[str]] = None,
    keyword: Optional[str] = None,
) -> str:
    """Search for service venues (premises) by category and/or name.

    Args:
        tags: Filter by category tags. Valid values: tattoo, barber, massage, salon, dental, spa.
        keyword: Optional keyword to search in premise names.

    Returns:
        JSON list of matching premises with id, name, address, tags, rating.
    """
    results = _search_premises(tags=tags, keyword=keyword)
    if not results:
        return "No premises found matching your criteria."
    return json.dumps(results, indent=2)


@tool
def search_services(
    premise_id: Optional[str] = None,
    keyword: Optional[str] = None,
) -> str:
    """Search for services offered at a specific premise or across all premises.

    Args:
        premise_id: UUID of a specific premise to search within.
        keyword: Optional keyword to search in service names (e.g., "haircut", "massage").

    Returns:
        JSON list of services with id, name, price, duration, and options.
    """
    results = _search_services(premise_id=premise_id, keyword=keyword)
    if not results:
        return "No services found matching your criteria."
    return json.dumps(results, indent=2)


@tool
def check_availability(
    premise_id: str,
    service_id: str,
    date: str,
    preferred_time: Optional[str] = None,
) -> str:
    """Check staff availability for a service at a premise on a specific date.

    This tool queries employee schedules and existing bookings to determine
    actual available time slots. Always call this before confirming any booking.

    Args:
        premise_id: UUID of the premise.
        service_id: UUID of the service.
        date: Target date in YYYY-MM-DD format.
        preferred_time: Optional preferred time in HH:MM format (24-hour).

    Returns:
        JSON list of available staff with their open time slots.
    """
    results = _check_availability(
        premise_id=premise_id,
        service_id=service_id,
        date=date,
        preferred_time=preferred_time,
    )
    if not results:
        return "No availability found for this service on the requested date."
    return json.dumps(results, indent=2)


@tool
def get_premise_details(premise_id: str) -> str:
    """Get detailed information about a specific premise including services, staff, and reviews.

    Args:
        premise_id: UUID of the premise.

    Returns:
        JSON object with full premise details.
    """
    result = _get_premise_details(premise_id=premise_id)
    return json.dumps(result, indent=2)


@tool
def create_booking(
    staff_id: str,
    service_id: str,
    premise_id: str,
    date: str,
    time: str,
) -> str:
    """Create a new booking appointment. Only call this after confirming all details with the user.

    Args:
        staff_id: UUID of the staff member.
        service_id: UUID of the service.
        premise_id: UUID of the premise.
        date: Booking date in YYYY-MM-DD format.
        time: Booking start time in HH:MM format (24-hour).

    Returns:
        JSON object with booking confirmation details.
    """
    result = _create_booking(
        staff_id=staff_id,
        service_id=service_id,
        premise_id=premise_id,
        date=date,
        time=time,
    )
    return json.dumps(result, indent=2)


# All tools exported for agent registration
all_tools = [
    search_premises,
    search_services,
    check_availability,
    get_premise_details,
    create_booking,
]
