from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(120), default="Uncategorized")
    item_type: Mapped[str] = mapped_column(String(40), default="product")  # product or service
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    list_price: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Deal(Base):
    __tablename__ = "deals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=1)
    proposed_unit_price: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="proposed")
    # proposed, approved, won, lost
    expected_close_date: Mapped[str] = mapped_column(String(30), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer] = relationship()
    product: Mapped[Product | None] = relationship()



class MeetingNote(Base):
    __tablename__ = "meeting_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    deal_id: Mapped[int | None] = mapped_column(
        ForeignKey("deals.id"),
        nullable=True,
        index=True,
    )
    transcript: Mapped[str] = mapped_column(Text, default="")
    extracted_json: Mapped[str] = mapped_column(Text, default="{}")
    consent_confirmed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    deal: Mapped["Deal | None"] = relationship()

class DealActivity(Base):
    __tablename__ = "deal_activities"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id"),
        index=True
    )

    activity_type: Mapped[str] = mapped_column(
        String(50),
        index=True
    )

    outcome: Mapped[str] = mapped_column(
        String(50),
        default="unknown"
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    next_follow_up_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    deal: Mapped["Deal"] = relationship()

    __table_args__ = (
        Index(
            "ix_deal_activities_deal_created",
            "deal_id",
            "created_at"
        ),
    )

class MeetingActionItem(Base):
    __tablename__ = "meeting_action_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    meeting_note_id: Mapped[int] = mapped_column(
        ForeignKey("meeting_notes.id"),
        index=True,
    )

    action_text: Mapped[str] = mapped_column(Text)
    source_quote: Mapped[str] = mapped_column(Text, default="")

    due_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_confirmation: Mapped[int] = mapped_column(Integer, default=1)

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        index=True,
    )  # pending, completed, cancelled

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    meeting_note: Mapped["MeetingNote"] = relationship()

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    action_item_id: Mapped[int] = mapped_column(
        ForeignKey("meeting_action_items.id"),
        index=True,
    )

    reminder_type: Mapped[str] = mapped_column(
        String(30),
    )  # 24_hours or 30_minutes

    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime,
        index=True,
    )

    is_read: Mapped[int] = mapped_column(Integer, default=0)
    is_sent: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    action_item: Mapped["MeetingActionItem"] = relationship()

    __table_args__ = (
        Index(
            "ix_notifications_due",
            "is_sent",
            "scheduled_for",
        ),
        Index(
            "ix_notifications_action_reminder",
            "action_item_id",
            "reminder_type",
            unique=True,
        ),
    )
