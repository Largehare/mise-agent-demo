"""
Fake in-memory data replacing database queries for demo/development use.
All functions mirror the signatures in db/queries.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

# ── Static IDs (stable across calls) ──

_IDS = {
    "premise_barber": "11111111-1111-1111-1111-111111111111",
    "premise_salon":  "22222222-2222-2222-2222-222222222222",
    "premise_spa":    "33333333-3333-3333-3333-333333333333",

    "service_haircut":   "aaaa0001-0000-0000-0000-000000000000",
    "service_beard":     "aaaa0002-0000-0000-0000-000000000000",
    "service_colour":    "aaaa0003-0000-0000-0000-000000000000",
    "service_blowout":   "aaaa0004-0000-0000-0000-000000000000",
    "service_massage60": "aaaa0005-0000-0000-0000-000000000000",
    "service_massage90": "aaaa0006-0000-0000-0000-000000000000",
    "service_facial":    "aaaa0007-0000-0000-0000-000000000000",

    "staff_james":  "bbbb0001-0000-0000-0000-000000000000",
    "staff_sarah":  "bbbb0002-0000-0000-0000-000000000000",
    "staff_mike":   "bbbb0003-0000-0000-0000-000000000000",
    "staff_lisa":   "bbbb0004-0000-0000-0000-000000000000",
    "staff_carlos": "bbbb0005-0000-0000-0000-000000000000",

    "customer_demo": "cccc0001-0000-0000-0000-000000000000",
}

_PREMISES = [
    {
        "id": _IDS["premise_barber"],
        "name": "The Classic Barber Co.",
        "address": "42 King Street, NSW 2000",
        "tags": ["barber"],
        "description": "Traditional barbershop specialising in precision cuts, hot towel shaves and beard grooming.",
        "rating": 4.8,
        "contact": "(02) 9000 1111",
    },
    {
        "id": _IDS["premise_salon"],
        "name": "Lumière Hair Salon",
        "address": "18 Chapel Road, VIC 3181",
        "tags": ["salon"],
        "description": "Boutique salon offering colour, cuts and blowouts by award-winning stylists.",
        "rating": 4.6,
        "contact": "(03) 9000 2222",
    },
    {
        "id": _IDS["premise_spa"],
        "name": "Zen Retreat Spa",
        "address": "7 Harbour Walk, QLD 4000",
        "tags": ["spa", "massage"],
        "description": "Luxury day spa with signature massages, facials and holistic wellness treatments.",
        "rating": 4.9,
        "contact": "(07) 9000 3333",
    },
]

_SERVICES = [
    # Barber
    {
        "id": _IDS["service_haircut"],
        "name": "Men's Haircut",
        "price": "$45.00",
        "duration_minutes": 30,
        "description": "Classic scissor or clipper cut with wash and style.",
        "pricing_type": "fixed",
        "premise_id": _IDS["premise_barber"],
        "options": [
            {"name": "With Hot Towel Shave", "price": "$25.00", "extra_time_mins": 20},
        ],
    },
    {
        "id": _IDS["service_beard"],
        "name": "Beard Trim & Shape",
        "price": "$30.00",
        "duration_minutes": 20,
        "description": "Expert beard sculpting, trim and conditioning.",
        "pricing_type": "fixed",
        "premise_id": _IDS["premise_barber"],
        "options": [],
    },
    # Salon
    {
        "id": _IDS["service_colour"],
        "name": "Full Colour",
        "price": "$120.00",
        "duration_minutes": 90,
        "description": "Single or multi-tone colour with professional toner.",
        "pricing_type": "fixed",
        "premise_id": _IDS["premise_salon"],
        "options": [
            {"name": "Balayage Upgrade", "price": "$60.00", "extra_time_mins": 30},
        ],
    },
    {
        "id": _IDS["service_blowout"],
        "name": "Blowout & Style",
        "price": "$65.00",
        "duration_minutes": 45,
        "description": "Wash, blow-dry and professional finish.",
        "pricing_type": "fixed",
        "premise_id": _IDS["premise_salon"],
        "options": [],
    },
    # Spa
    {
        "id": _IDS["service_massage60"],
        "name": "Swedish Massage (60 min)",
        "price": "$110.00",
        "duration_minutes": 60,
        "description": "Full-body relaxation massage using long, flowing strokes.",
        "pricing_type": "fixed",
        "premise_id": _IDS["premise_spa"],
        "options": [],
    },
    {
        "id": _IDS["service_massage90"],
        "name": "Deep Tissue Massage (90 min)",
        "price": "$155.00",
        "duration_minutes": 90,
        "description": "Targets muscle tension and chronic pain with firm pressure.",
        "pricing_type": "fixed",
        "premise_id": _IDS["premise_spa"],
        "options": [],
    },
    {
        "id": _IDS["service_facial"],
        "name": "Signature Facial",
        "price": "$95.00",
        "duration_minutes": 60,
        "description": "Customised facial cleanse, exfoliation and hydration treatment.",
        "pricing_type": "fixed",
        "premise_id": _IDS["premise_spa"],
        "options": [],
    },
]

_STAFF = [
    {"id": _IDS["staff_james"],  "name": "James Carter",  "rating": 4.9, "premise_id": _IDS["premise_barber"],
     "service_ids": [_IDS["service_haircut"], _IDS["service_beard"]]},
    {"id": _IDS["staff_mike"],   "name": "Mike Nguyen",   "rating": 4.7, "premise_id": _IDS["premise_barber"],
     "service_ids": [_IDS["service_haircut"], _IDS["service_beard"]]},
    {"id": _IDS["staff_sarah"],  "name": "Sarah Bloom",   "rating": 4.8, "premise_id": _IDS["premise_salon"],
     "service_ids": [_IDS["service_colour"], _IDS["service_blowout"]]},
    {"id": _IDS["staff_lisa"],   "name": "Lisa Park",     "rating": 4.5, "premise_id": _IDS["premise_salon"],
     "service_ids": [_IDS["service_colour"], _IDS["service_blowout"]]},
    {"id": _IDS["staff_carlos"], "name": "Carlos Mendes", "rating": 5.0, "premise_id": _IDS["premise_spa"],
     "service_ids": [_IDS["service_massage60"], _IDS["service_massage90"], _IDS["service_facial"]]},
]

# Work hours per staff member (start_hour, end_hour)
_WORK_HOURS = {
    _IDS["staff_james"]:  (9, 17),
    _IDS["staff_mike"]:   (11, 19),
    _IDS["staff_sarah"]:  (10, 18),
    _IDS["staff_lisa"]:   (9, 17),
    _IDS["staff_carlos"]: (9, 20),
}

# In-memory bookings created during the demo session
_bookings: list[dict] = []


# ── Public functions matching db/queries.py signatures ──

def search_premises(
    tags: list[str] | None = None,
    keyword: str | None = None,
    limit: int = 10,
) -> list[dict]:
    results = _PREMISES[:]
    if tags:
        tags_lower = [t.lower() for t in tags]
        results = [p for p in results if any(t in p["tags"] for t in tags_lower)]
    if keyword:
        kw = keyword.lower()
        results = [p for p in results if kw in p["name"].lower()]
    return results[:limit]


def search_services(
    premise_id: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    results = _SERVICES[:]
    if premise_id:
        results = [s for s in results if s["premise_id"] == premise_id]
    if keyword:
        kw = keyword.lower()
        results = [s for s in results if kw in s["name"].lower() or kw in s["description"].lower()]
    return results


def get_staff_for_service(
    premise_id: str,
    service_id: str,
) -> list[dict]:
    return [
        {"id": s["id"], "name": s["name"], "rating": s["rating"]}
        for s in _STAFF
        if s["premise_id"] == premise_id and service_id in s["service_ids"]
    ]


def check_availability(
    premise_id: str,
    service_id: str,
    date: str,
    preferred_time: str | None = None,
) -> list[dict]:
    # Find the service duration
    service = next((s for s in _SERVICES if s["id"] == service_id), None)
    if not service:
        return [{"error": "Service not found"}]

    duration_mins = service["duration_minutes"]
    target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    # Find relevant staff
    relevant_staff = [
        s for s in _STAFF
        if s["premise_id"] == premise_id and service_id in s["service_ids"]
    ]

    results = []
    for staff in relevant_staff:
        start_h, end_h = _WORK_HOURS.get(staff["id"], (9, 17))

        # Build existing bookings for this staff on this date
        booked_blocks = [
            (b["_start"], b["_end"])
            for b in _bookings
            if b["staff_id"] == staff["id"] and b["_start"].date() == target_date.date()
        ]

        # Generate available slots (30-min increments across working hours)
        available_slots = []
        slot_start = target_date.replace(hour=start_h, minute=0)
        work_end = target_date.replace(hour=end_h, minute=0)

        while slot_start + timedelta(minutes=duration_mins) <= work_end:
            slot_end = slot_start + timedelta(minutes=duration_mins)

            # Check no overlap with existing bookings
            overlap = any(
                not (slot_end <= bs or slot_start >= be)
                for bs, be in booked_blocks
            )

            if not overlap:
                if preferred_time:
                    ph, pm = map(int, preferred_time.split(":"))
                    pref_dt = target_date.replace(hour=ph, minute=pm)
                    if slot_start == pref_dt:
                        available_slots.append({
                            "start": slot_start.strftime("%H:%M"),
                            "end": slot_end.strftime("%H:%M"),
                        })
                else:
                    available_slots.append({
                        "start": slot_start.strftime("%H:%M"),
                        "end": slot_end.strftime("%H:%M"),
                    })

            slot_start += timedelta(minutes=30)

        if available_slots:
            results.append({
                "staff_id": staff["id"],
                "staff_name": staff["name"],
                "available_slots": available_slots,
            })

    return results


def get_premise_details(premise_id: str) -> dict:
    premise = next((p for p in _PREMISES if p["id"] == premise_id), None)
    if not premise:
        return {"error": "Premise not found"}

    services = [s for s in _SERVICES if s["premise_id"] == premise_id]
    staff = [
        {"id": s["id"], "name": s["name"], "rating": s["rating"]}
        for s in _STAFF if s["premise_id"] == premise_id
    ]

    return {
        **premise,
        "services": services,
        "staff": staff,
        "recent_reviews": [
            {"score": 5.0, "comment": "Absolutely fantastic service, highly recommend!"},
            {"score": 4.5, "comment": "Great experience, will definitely come back."},
            {"score": 5.0, "comment": "Professional, friendly and skilled staff."},
        ],
    }


def create_booking(
    staff_id: str,
    service_id: str,
    premise_id: str,
    date: str,
    time: str,
) -> dict:
    service = next((s for s in _SERVICES if s["id"] == service_id), None)
    if not service:
        return {"error": "Service not found"}

    staff = next((s for s in _STAFF if s["id"] == staff_id), None)
    if not staff:
        return {"error": "Staff not found"}

    target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    h, m = map(int, time.split(":"))
    start_dt = target_date.replace(hour=h, minute=m)
    end_dt = start_dt + timedelta(minutes=service["duration_minutes"])

    booking_id = str(uuid.uuid4())
    _bookings.append({
        "booking_id": booking_id,
        "staff_id": staff_id,
        "service_id": service_id,
        "premise_id": premise_id,
        "_start": start_dt,
        "_end": end_dt,
    })

    return {
        "booking_id": booking_id,
        "staff_name": staff["name"],
        "service_name": service["name"],
        "date": date,
        "time": f"{time} - {end_dt.strftime('%H:%M')}",
        "price": service["price"],
        "status": "PENDING",
        "message": "Booking created successfully! Awaiting confirmation.",
    }
