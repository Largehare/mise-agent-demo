"""
MCP (Model Context Protocol) server for the Mise booking agent.
Exposes database query tools via MCP so any MCP-compatible client
(Claude Desktop, Claude Code, etc.) can search services and book appointments.

Run:
  python mcp_server.py              # stdio (for Claude Desktop)
  python mcp_server.py --http       # streamable HTTP (for networked clients)
"""

import json
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from db.connection import SessionLocal
from db.queries import (
    check_availability as _check_availability,
    create_booking as _create_booking,
    get_premise_details as _get_premise_details,
    search_premises as _search_premises,
    search_services as _search_services,
)

mcp = FastMCP(
    "Mise Booking Agent",
    instructions=(
        "You are Mise Assistant, a booking concierge for the Mise service marketplace. "
        "Use the provided tools to search for service venues, find available appointments, "
        "and create bookings. ONLY state facts from tool results - never invent data."
    ),
)


# ── Tools ──


@mcp.tool()
def search_premises(
    tags: Optional[list[str]] = None,
    keyword: Optional[str] = None,
) -> str:
    """Search for service venues (premises) by category and/or name.

    Args:
        tags: Filter by category. Valid values: tattoo, barber, massage, salon, dental, spa.
        keyword: Optional keyword to search in premise names.

    Returns:
        JSON list of matching premises with id, name, address, tags, rating.
    """
    session = SessionLocal()
    try:
        results = _search_premises(session, tags=tags, keyword=keyword)
        if not results:
            return "No premises found matching your criteria."
        return json.dumps(results, indent=2)
    finally:
        session.close()


@mcp.tool()
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
    session = SessionLocal()
    try:
        results = _search_services(session, premise_id=premise_id, keyword=keyword)
        if not results:
            return "No services found matching your criteria."
        return json.dumps(results, indent=2)
    finally:
        session.close()


@mcp.tool()
def check_availability(
    premise_id: str,
    service_id: str,
    date: str,
    preferred_time: Optional[str] = None,
) -> str:
    """Check staff availability for a service at a premise on a specific date.

    Queries real employee schedules and existing bookings to determine
    actual available time slots. Always call this before confirming any booking.

    Args:
        premise_id: UUID of the premise.
        service_id: UUID of the service.
        date: Target date in YYYY-MM-DD format.
        preferred_time: Optional preferred time in HH:MM format (24-hour).

    Returns:
        JSON list of available staff with their open time slots.
    """
    session = SessionLocal()
    try:
        results = _check_availability(
            session,
            premise_id=premise_id,
            service_id=service_id,
            date=date,
            preferred_time=preferred_time,
        )
        if not results:
            return "No availability found for this service on the requested date."
        return json.dumps(results, indent=2)
    finally:
        session.close()


@mcp.tool()
def get_premise_details(premise_id: str) -> str:
    """Get detailed information about a specific premise including services, staff, and reviews.

    Args:
        premise_id: UUID of the premise.

    Returns:
        JSON object with full premise details, services list, staff list, and recent reviews.
    """
    session = SessionLocal()
    try:
        result = _get_premise_details(session, premise_id=premise_id)
        return json.dumps(result, indent=2)
    finally:
        session.close()


@mcp.tool()
def create_booking(
    staff_id: str,
    service_id: str,
    premise_id: str,
    date: str,
    time: str,
) -> str:
    """Create a new booking appointment.

    Args:
        staff_id: UUID of the staff member.
        service_id: UUID of the service.
        premise_id: UUID of the premise.
        date: Booking date in YYYY-MM-DD format.
        time: Booking start time in HH:MM format (24-hour).

    Returns:
        JSON object with booking confirmation including booking_id, price, and status.
    """
    session = SessionLocal()
    try:
        from db.models import Customer
        customer = session.query(Customer).first()
        if not customer:
            return json.dumps({"error": "No customer found in database. Please seed test data."})

        result = _create_booking(
            session,
            staff_id=staff_id,
            service_id=service_id,
            premise_id=premise_id,
            customer_id=str(customer._id),
            date=date,
            time=time,
        )
        return json.dumps(result, indent=2)
    finally:
        session.close()


# ── Resources (read-only data for context) ──


@mcp.resource("mise://categories")
def get_categories() -> str:
    """List all available service categories on the Mise platform."""
    categories = [
        {"name": "tattoo", "description": "Tattoo studios and artists"},
        {"name": "barber", "description": "Barbershops and men's grooming"},
        {"name": "massage", "description": "Massage therapy and bodywork"},
        {"name": "salon", "description": "Hair salons and beauty services"},
        {"name": "dental", "description": "Dental clinics and oral care"},
        {"name": "spa", "description": "Spa and wellness centers"},
    ]
    return json.dumps(categories, indent=2)


@mcp.resource("mise://premises")
def get_all_premises() -> str:
    """List all premises currently registered on the platform."""
    session = SessionLocal()
    try:
        results = _search_premises(session, limit=50)
        return json.dumps(results, indent=2)
    finally:
        session.close()


# ── Prompts (reusable templates) ──


@mcp.prompt()
def booking_assistant() -> str:
    """System prompt for the Mise booking assistant with anti-hallucination rules."""
    return (
        "You are Mise Assistant, a booking concierge for the Mise service marketplace. "
        "Help users find services and book appointments.\n\n"
        "STRICT RULES:\n"
        "1. ONLY state facts from tool results. Never invent data.\n"
        "2. Always call check_availability before confirming a time slot.\n"
        "3. Prices and durations must exactly match tool results.\n"
        "4. Available categories: tattoo, barber, massage, salon, dental, spa.\n\n"
        "FLOW: Search premises -> Search services -> Check availability -> Confirm -> Book"
    )


@mcp.prompt()
def search_and_book(service_type: str, date: str) -> str:
    """Pre-built prompt for searching and booking a specific service type on a date."""
    return (
        f"I'd like to find a {service_type} appointment on {date}. "
        f"Please search for available {service_type} venues, show me their services "
        f"and pricing, check availability for {date}, and help me book."
    )


if __name__ == "__main__":
    transport = "streamable-http" if "--http" in sys.argv else "stdio"
    mcp.run(transport=transport)
