"""
Standalone SQLAlchemy ORM models mapping to the mise-api database.
No Flask dependency - uses plain SQLAlchemy DeclarativeBase.
"""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, Float, Integer, Numeric, String, Date
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Enums (replicated from mise-api/src/api/enums.py) ──


class PremiseTag(Enum):
    TATTOO = 0
    BARBER = 1
    MASSAGE = 2
    SALON = 3
    DENTAL = 4
    SPA = 5


class BookingStatus(Enum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2
    PAID = 3
    CANCELLED = 4
    PAYMENT_FAILED = 5
    COMPLETED = 6
    REVIEWED = 7
    REFUND_PENDING = 8
    REFUND_PROCESSING = 9
    REFUNDED = 10
    REFUND_REJECTED = 11
    DISPUTED = 12
    DISPUTE_WON = 13
    DISPUTE_LOST = 14
    AWAITING_PAYMENT = 15
    EXPIRED = 16


BLOCKING_STATUSES = [
    BookingStatus.PENDING.value,
    BookingStatus.APPROVED.value,
    BookingStatus.PAID.value,
    BookingStatus.AWAITING_PAYMENT.value,
]


class ScheduleApprovalStatus(Enum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2


class ServicePriceUnit(Enum):
    FIXED = 0
    HOURLY = 1


class Day(Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


def decode_tags(value: int) -> list[str]:
    """Decode _tags bitmask into list of tag names."""
    return [tag.name.lower() for tag in PremiseTag if (value & (1 << tag.value)) != 0]


def encode_tags(tag_names: list[str]) -> int:
    """Encode list of tag names into bitmask."""
    value = 0
    for name in tag_names:
        tag = PremiseTag[name.upper()]
        value |= 1 << tag.value
    return value


def decode_week(value: int) -> list[str]:
    """Decode _week bitmask into list of day names."""
    return [day.name.lower() for day in Day if (value & (1 << day.value)) != 0]


# ── Models ──


class Premise(Base):
    __tablename__ = "premise"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(256), nullable=False)
    address_line = Column(String(256), nullable=False)
    state = Column(String(128), nullable=False)
    post_code = Column(String(128), nullable=False)
    _tags = Column(Integer, nullable=False)
    description = Column(String(512), nullable=True)
    contact_number = Column(String(256))
    contact_email = Column(String(256), nullable=True)
    business_id = Column(UUID(as_uuid=True))
    banner_image = Column(String(256), nullable=True)
    date_created = Column(DateTime, nullable=True)
    # Skip PostGIS location column - not needed for MVP queries

    services = relationship("Service", back_populates="premise")
    staff_premises = relationship("StaffPremise", back_populates="premise")
    premises_reviews = relationship("PremisesReview", back_populates="premise")
    bookings = relationship("Booking", back_populates="premise")

    @property
    def tag_names(self) -> list[str]:
        return decode_tags(self._tags) if self._tags else []

    @property
    def rating(self) -> float | None:
        valid = [r for r in self.premises_reviews if r.score is not None]
        if not valid:
            return None
        return sum(r.score for r in valid) / len(valid)


class Service(Base):
    __tablename__ = "service"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    description = Column(String(512), nullable=True)
    default_time = Column(Float, nullable=False)  # duration in hours
    processing_time = Column(Float, nullable=True)
    minimum_age = Column(Integer, nullable=True)
    _unit = Column(Integer, nullable=False)
    premise_id = Column(UUID(as_uuid=True))
    service_image = Column(String(256), nullable=True)

    premise = relationship("Premise", back_populates="services", foreign_keys=[premise_id],
                           primaryjoin="Service.premise_id == Premise._id")
    service_options = relationship("ServiceOption", back_populates="service")
    staff_services = relationship("StaffService", back_populates="service")

    @property
    def unit_name(self) -> str:
        return ServicePriceUnit(self._unit).name.lower()

    @property
    def duration_minutes(self) -> int:
        return int(self.default_time * 60)


class ServiceOption(Base):
    __tablename__ = "service_option"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    extra_time = Column(Float, nullable=True)
    processing_time = Column(Float, nullable=True)
    service_id = Column(UUID(as_uuid=True))

    service = relationship("Service", back_populates="service_options", foreign_keys=[service_id],
                           primaryjoin="ServiceOption.service_id == Service._id")


class Staff(Base):
    __tablename__ = "staff"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(128), nullable=False, unique=True)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=True)
    contact_number = Column(String(256))
    profile_picture = Column(String(256), nullable=True)

    staff_premises = relationship("StaffPremise", back_populates="staff")
    staff_services = relationship("StaffService", back_populates="staff")
    staff_reviews = relationship("StaffReview", back_populates="staff")

    @property
    def display_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name


class Customer(Base):
    __tablename__ = "customer"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(128), nullable=False, unique=True)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=True)
    contact_number = Column(String(256), nullable=True)
    profile_picture = Column(String(256), nullable=True)

    bookings = relationship("Booking", back_populates="customer")


class StaffPremise(Base):
    __tablename__ = "staff_premise"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True))
    premise_id = Column(UUID(as_uuid=True))

    staff = relationship("Staff", back_populates="staff_premises", foreign_keys=[staff_id],
                         primaryjoin="StaffPremise.staff_id == Staff._id")
    premise = relationship("Premise", back_populates="staff_premises", foreign_keys=[premise_id],
                           primaryjoin="StaffPremise.premise_id == Premise._id")
    schedules = relationship("Schedule", back_populates="staff_premise")


class StaffService(Base):
    __tablename__ = "staff_service"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True))
    service_id = Column(UUID(as_uuid=True))

    staff = relationship("Staff", back_populates="staff_services", foreign_keys=[staff_id],
                         primaryjoin="StaffService.staff_id == Staff._id")
    service = relationship("Service", back_populates="staff_services", foreign_keys=[service_id],
                           primaryjoin="StaffService.service_id == Service._id")


class Schedule(Base):
    __tablename__ = "schedule"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_premise_id = Column(UUID(as_uuid=True))
    start = Column(DateTime(timezone=True), nullable=False)
    end = Column(DateTime(timezone=True), nullable=False)
    repeat_until = Column(DateTime(timezone=True), nullable=True)
    _week = Column(Integer, nullable=False, default=0)
    _approval_status = Column(Integer, nullable=False)

    staff_premise = relationship("StaffPremise", back_populates="schedules", foreign_keys=[staff_premise_id],
                                 primaryjoin="Schedule.staff_premise_id == StaffPremise._id")

    @property
    def is_repeating(self) -> bool:
        return self._week != 0

    @property
    def week_days(self) -> list[int]:
        """Returns list of weekday integers (0=Monday..6=Sunday) this schedule applies to."""
        return [day.value for day in Day if (self._week & (1 << day.value)) != 0]

    @property
    def duration(self):
        return self.end - self.start


class Booking(Base):
    __tablename__ = "booking"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True))
    service_id = Column(UUID(as_uuid=True))
    premise_id = Column(UUID(as_uuid=True))
    customer_id = Column(UUID(as_uuid=True))
    service_option_ids = Column(ARRAY(UUID(as_uuid=True)))
    start = Column(DateTime(timezone=True), nullable=False)
    end = Column(DateTime(timezone=True), nullable=False)
    description = Column(String(512), nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    duration = Column(Float, nullable=False)
    processing_time = Column(Float, nullable=True)
    customer_notes = Column(String(255))
    staff_notes = Column(String(255), nullable=True)
    reference_image = Column(String(256), nullable=True)
    _status = Column(Integer, nullable=False, default=BookingStatus.PENDING.value)
    payment_intent_id = Column(String(255), nullable=True)
    transfer_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    date_created = Column(DateTime(timezone=True), nullable=True)

    staff = relationship("Staff", foreign_keys=[staff_id],
                         primaryjoin="Booking.staff_id == Staff._id")
    service = relationship("Service", foreign_keys=[service_id],
                           primaryjoin="Booking.service_id == Service._id")
    premise = relationship("Premise", back_populates="bookings", foreign_keys=[premise_id],
                           primaryjoin="Booking.premise_id == Premise._id")
    customer = relationship("Customer", back_populates="bookings", foreign_keys=[customer_id],
                            primaryjoin="Booking.customer_id == Customer._id")

    @property
    def status(self) -> BookingStatus:
        return BookingStatus(self._status)


class PremisesReview(Base):
    __tablename__ = "premises_review"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    premise_id = Column(UUID(as_uuid=True))
    service_id = Column(UUID(as_uuid=True), nullable=True)
    booking_id = Column(UUID(as_uuid=True), nullable=True)
    customer_id = Column(UUID(as_uuid=True), nullable=False)
    date_created = Column(DateTime(timezone=True), nullable=True)
    comment = Column(String(512), nullable=False, default="")
    media = Column(String(256), nullable=True)
    score = Column(Float, nullable=True)

    premise = relationship("Premise", back_populates="premises_reviews", foreign_keys=[premise_id],
                           primaryjoin="PremisesReview.premise_id == Premise._id")


class StaffReview(Base):
    __tablename__ = "staff_review"

    _id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True))
    customer_id = Column(UUID(as_uuid=True), nullable=False)
    service_id = Column(UUID(as_uuid=True), nullable=True)
    booking_id = Column(UUID(as_uuid=True), nullable=False)
    date_created = Column(DateTime(timezone=True), nullable=True)
    comment = Column(String(512), nullable=False, default="")
    score = Column(Float, nullable=True)

    staff = relationship("Staff", back_populates="staff_reviews", foreign_keys=[staff_id],
                         primaryjoin="StaffReview.staff_id == Staff._id")
