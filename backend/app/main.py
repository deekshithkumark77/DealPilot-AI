import json
import re
import asyncio
from contextlib import asynccontextmanager
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import Base, engine, get_db, SessionLocal
from . import models, schemas
from . import ml_service
from .meeting_ai import analyze_transcript

Base.metadata.create_all(bind=engine)


async def reminder_worker():
    """Process due in-app reminders every 30 seconds while the API is running."""
    while True:
        db = SessionLocal()
        try:
            process_due_notifications(db)
        except Exception as exc:
            db.rollback()
            print(f"Automatic reminder processing failed: {type(exc).__name__}: {exc}")
        finally:
            db.close()

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(reminder_worker())
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="DealPilot AI API",
    description="Industry-independent sales intelligence MVP API",
    version="0.3.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "DealPilot AI API",
    }


@app.get("/")
def root():
    return {
        "message": "DealPilot AI API is running",
        "docs": "/docs",
    }



# ============================================================
# MEETING INTELLIGENCE, ACTION ITEMS AND REMINDERS
# ============================================================

def schedule_action_reminders(
    db: Session,
    action_item: models.MeetingActionItem,
):
    """Create or reschedule reminders for a confirmed future deadline."""
    reminders = (
        db.query(models.Notification)
        .filter(models.Notification.action_item_id == action_item.id)
        .all()
    )

    if (
        action_item.due_at is None
        or action_item.needs_confirmation
        or action_item.status != "pending"
    ):
        # Remove unprocessed reminders if this item is no longer eligible.
        for reminder in reminders:
            if not reminder.is_sent:
                db.delete(reminder)
        return

    # The database stores datetimes as naive UTC.
    due_at = action_item.due_at
    if due_at.tzinfo is not None:
        due_at = due_at.astimezone(timezone.utc).replace(tzinfo=None)

    now = datetime.utcnow()
    offsets = {
        "24_hours": timedelta(hours=24),
        "30_minutes": timedelta(minutes=30),
    }
    existing_by_type = {row.reminder_type: row for row in reminders}

    for reminder_type, offset in offsets.items():
        scheduled_for = due_at - offset
        existing = existing_by_type.get(reminder_type)

        if scheduled_for <= now:
            # Do not leave an overdue, unprocessed reminder waiting to fire late.
            if existing is not None and not existing.is_sent:
                db.delete(existing)
            continue

        if existing is None:
            db.add(
                models.Notification(
                    action_item_id=action_item.id,
                    reminder_type=reminder_type,
                    scheduled_for=scheduled_for,
                    is_read=0,
                    is_sent=0,
                )
            )
        elif existing.scheduled_for != scheduled_for:
            # Reuse the unique row and reset it for the new deadline.
            existing.scheduled_for = scheduled_for
            existing.is_sent = 0
            existing.is_read = 0


@app.post("/meeting-notes/analyze")
def analyze_meeting_transcript(payload: dict):
    transcript = payload.get("transcript")

    if not isinstance(transcript, str) or not transcript.strip():
        raise HTTPException(
            status_code=422,
            detail="A non-empty transcript is required.",
        )

    try:
        return analyze_transcript(transcript.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        import traceback

    print(f"Meeting AI analysis failed: {type(exc).__name__}: {exc}")
    traceback.print_exc()

    raise HTTPException(
        status_code=502,
        detail="Meeting AI analysis failed. Check the backend terminal.",
    )

@app.post("/meeting-notes", status_code=201)
def save_meeting_note(
    payload: dict,
    db: Session = Depends(get_db),
):
    title = payload.get("title", "Untitled Meeting")
    transcript = payload.get("transcript", "")
    deal_id = payload.get("deal_id")
    consent_confirmed = payload.get("consent_confirmed", False)

    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=422, detail="Meeting title cannot be empty.")
    if not isinstance(transcript, str) or not transcript.strip():
        raise HTTPException(status_code=422, detail="A non-empty transcript is required.")
    if consent_confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail="Confirm permission to process and store the transcript.",
        )

    title = title.strip()
    transcript = transcript.strip()

    if len(transcript) > 30000:
        raise HTTPException(status_code=422, detail="Transcript must not exceed 30,000 characters.")

    if deal_id is not None:
        if not isinstance(deal_id, int) or isinstance(deal_id, bool):
            raise HTTPException(status_code=422, detail="deal_id must be an integer or null.")
        if not db.get(models.Deal, deal_id):
            raise HTTPException(status_code=404, detail="The specified deal was not found.")

    try:
        # Idempotency guard: the same title + exact transcript should not create
        # another meeting and another copy of every task when Save is clicked twice.
        existing_note = (
            db.query(models.MeetingNote)
            .filter(
                models.MeetingNote.title == title,
                models.MeetingNote.transcript == transcript,
            )
            .order_by(models.MeetingNote.id.desc())
            .first()
        )
        if existing_note is not None:
            existing_items = (
                db.query(models.MeetingActionItem)
                .filter(models.MeetingActionItem.meeting_note_id == existing_note.id)
                .order_by(models.MeetingActionItem.id.asc())
                .all()
            )
            try:
                saved_analysis = json.loads(existing_note.extracted_json or "{}")
            except (TypeError, json.JSONDecodeError):
                saved_analysis = {}
            return {
                "id": existing_note.id,
                "title": existing_note.title,
                "deal_id": existing_note.deal_id,
                "transcript": existing_note.transcript,
                "consent_confirmed": bool(existing_note.consent_confirmed),
                "analysis": saved_analysis,
                "action_items_created": 0,
                "already_saved": True,
                "action_items": [
                    {
                        "id": item.id,
                        "meeting_note_id": item.meeting_note_id,
                        "action_text": item.action_text,
                        "source_quote": item.source_quote,
                        "due_at": item.due_at,
                        "confidence": item.confidence,
                        "needs_confirmation": bool(item.needs_confirmation),
                        "status": item.status,
                    }
                    for item in existing_items
                ],
                "created_at": existing_note.created_at,
            }

        analysis = analyze_transcript(transcript)
        if not isinstance(analysis, dict):
            raise ValueError("The AI returned an unexpected analysis format.")

        commitments = analysis.get("commitments", [])
        if isinstance(commitments, dict):
            commitments = commitments.get("items", commitments.get("commitments", []))
        if not isinstance(commitments, list):
            raise ValueError("The AI returned commitments in an unexpected format.")

        # Remove duplicate commitments within this single AI result using
        # normalized owner + action. Keep distinct actions from the same owner.
        normalized = []
        seen = set()
        for commitment in commitments:
            if isinstance(commitment, str):
                action = commitment.strip()
                owner, quote, deadline_text = "Unknown", "", None
            elif isinstance(commitment, dict):
                action = (
                    commitment.get("action")
                    or commitment.get("commitment")
                    or commitment.get("task")
                    or commitment.get("text")
                    or ""
                )
                owner = commitment.get("owner", "Unknown")
                quote = commitment.get("source_quote") or commitment.get("source") or ""
                deadline_text = commitment.get("deadline_text")
            else:
                continue

            if not isinstance(action, str) or not action.strip():
                continue
            if not isinstance(owner, str) or not owner.strip():
                owner = "Unknown"
            if not isinstance(quote, str):
                quote = ""
            if not isinstance(deadline_text, str) or not deadline_text.strip():
                deadline_text = None

            action = action.strip()
            owner = owner.strip()
            # Normalize whitespace/case only for deduplication; preserve display text.
            dedupe_key = (
                re.sub(r"\s+", " ", owner).casefold(),
                re.sub(r"\s+", " ", action).casefold(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append({
                "owner": owner,
                "action": action,
                "source_quote": quote.strip(),
                "deadline_text": deadline_text.strip() if deadline_text else None,
            })

        # Keep the normalized commitments in saved analysis so the preview and
        # saved record refer to the same task set. Dates still require user review.
        analysis["commitments"] = [
            {
                **item,
                "needs_confirmation": True,
            }
            for item in normalized
        ]

        note = models.MeetingNote(
            title=title,
            deal_id=deal_id,
            transcript=transcript,
            extracted_json=json.dumps(analysis, ensure_ascii=False),
            consent_confirmed=1,
        )
        db.add(note)
        db.flush()

        created_items = []
        for commitment in normalized:
            owner = commitment["owner"]
            action_text = commitment["action"]
            if owner and owner.casefold() != "unknown":
                action_text = f"{owner}: {action_text}"

            item = models.MeetingActionItem(
                meeting_note_id=note.id,
                action_text=action_text,
                source_quote=commitment["source_quote"],
                # The model has no deadline_text column. Keep the phrase in
                # extracted_json; require a human-confirmed calendar datetime.
                due_at=None,
                confidence=0.0,
                needs_confirmation=1,
                status="pending",
            )
            db.add(item)
            created_items.append(item)

        db.commit()
        db.refresh(note)
        for item in created_items:
            db.refresh(item)

        return {
            "id": note.id,
            "title": note.title,
            "deal_id": note.deal_id,
            "transcript": note.transcript,
            "consent_confirmed": bool(note.consent_confirmed),
            "analysis": analysis,
            "action_items_created": len(created_items),
            "already_saved": False,
            "action_items": [
                {
                    "id": item.id,
                    "meeting_note_id": item.meeting_note_id,
                    "action_text": item.action_text,
                    "source_quote": item.source_quote,
                    "due_at": item.due_at,
                    "confidence": item.confidence,
                    "needs_confirmation": bool(item.needs_confirmation),
                    "status": item.status,
                }
                for item in created_items
            ],
            "created_at": note.created_at,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print(f"Saving meeting note failed: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Meeting analysis or saving failed. Check the backend terminal for the actual error.",
        )

@app.get("/meeting-notes")
def list_meeting_notes(db: Session = Depends(get_db)):
    notes = (
        db.query(models.MeetingNote)
        .order_by(models.MeetingNote.created_at.desc())
        .all()
    )
    return [
        {
            "id": note.id,
            "title": note.title,
            "deal_id": note.deal_id,
            "transcript": note.transcript,
            "analysis": json.loads(note.extracted_json or "{}"),
            "consent_confirmed": bool(note.consent_confirmed),
            "created_at": note.created_at,
        }
        for note in notes
    ]


@app.post("/meeting-action-items", status_code=201)
def create_meeting_action_item(
    payload: schemas.MeetingActionItemCreate,
    db: Session = Depends(get_db),
):
    if not db.get(models.MeetingNote, payload.meeting_note_id):
        raise HTTPException(status_code=404, detail="Meeting note not found.")

    if not payload.action_text.strip():
        raise HTTPException(status_code=422, detail="Action text cannot be empty.")

    if not 0 <= payload.confidence <= 1:
        raise HTTPException(status_code=422, detail="Confidence must be between 0 and 1.")

    item = models.MeetingActionItem(
        meeting_note_id=payload.meeting_note_id,
        action_text=payload.action_text.strip(),
        source_quote=payload.source_quote.strip(),
        due_at=None,
        confidence=payload.confidence,
        needs_confirmation=1,
        status="pending",
    )

    try:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    except Exception as exc:
        db.rollback()
        print(f"Creating action item failed: {type(exc).__name__}")
        raise HTTPException(status_code=500, detail="Could not save the action item.")


def _deadline_text_for_action_item(db: Session, item: models.MeetingActionItem):
    """Read the extracted deadline phrase from the meeting JSON without a DB migration."""
    note = db.get(models.MeetingNote, item.meeting_note_id)
    if note is None:
        return None

    try:
        analysis = json.loads(note.extracted_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None

    commitments = analysis.get("commitments", []) if isinstance(analysis, dict) else []
    if isinstance(commitments, dict):
        commitments = commitments.get("items", commitments.get("commitments", []))
    if not isinstance(commitments, list):
        return None

    current_action = re.sub(r"\\s+", " ", (item.action_text or "")).strip().casefold()
    for commitment in commitments:
        if not isinstance(commitment, dict):
            continue
        action = commitment.get("action") or commitment.get("commitment") or commitment.get("task") or ""
        owner = commitment.get("owner", "Unknown")
        if not isinstance(action, str):
            continue
        if not isinstance(owner, str) or not owner.strip():
            owner = "Unknown"
        expected_action = action.strip()
        if owner.strip().casefold() not in {"", "unknown"}:
            expected_action = f"{owner.strip()}: {expected_action}"
        expected_action = re.sub(r"\\s+", " ", expected_action).strip().casefold()
        if expected_action == current_action:
            deadline_text = commitment.get("deadline_text")
            return deadline_text.strip() if isinstance(deadline_text, str) and deadline_text.strip() else None
    return None


@app.get("/meeting-action-items")
def list_meeting_action_items(
    meeting_note_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.MeetingActionItem)

    if meeting_note_id is not None:
        query = query.filter(
            models.MeetingActionItem.meeting_note_id == meeting_note_id
        )

    action_items = query.order_by(models.MeetingActionItem.created_at.desc()).all()
    return [
        {
            "id": item.id,
            "meeting_note_id": item.meeting_note_id,
            "action_text": item.action_text,
            "source_quote": item.source_quote,
            "due_at": item.due_at,
            "confidence": item.confidence,
            "needs_confirmation": bool(item.needs_confirmation),
            "status": item.status,
            "created_at": item.created_at,
            "deadline_text": _deadline_text_for_action_item(db, item),
        }
        for item in action_items
    ]


@app.patch("/meeting-action-items/{action_item_id}/confirm")
def confirm_action_item_deadline(
    action_item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    item = db.get(models.MeetingActionItem, action_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found.")

    raw_due_at = payload.get("due_at")
    if not isinstance(raw_due_at, str) or not raw_due_at.strip():
        raise HTTPException(
            status_code=422,
            detail="Provide a confirmed due_at datetime in ISO 8601 format.",
        )

    try:
        due_at = datetime.fromisoformat(raw_due_at.strip().replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid ISO 8601 datetime.")

    if due_at.tzinfo is not None:
        due_at = due_at.astimezone(timezone.utc).replace(tzinfo=None)

    if due_at <= datetime.utcnow():
        raise HTTPException(status_code=422, detail="Deadline must be in the future.")

    try:
        item.due_at = due_at
        item.needs_confirmation = 0
        schedule_action_reminders(db, item)
        db.commit()
        db.refresh(item)
    except Exception as exc:
        db.rollback()
        print(f"Confirming deadline failed: {type(exc).__name__}")
        raise HTTPException(status_code=500, detail="Could not confirm the deadline.")

    return {
        "message": "Deadline confirmed and future reminders scheduled.",
        "id": item.id,
        "action_text": item.action_text,
        "due_at": item.due_at,
        "needs_confirmation": bool(item.needs_confirmation),
        "status": item.status,
    }


@app.patch("/meeting-action-items/{action_item_id}/status")
def update_action_item_status(
    action_item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    item = db.get(models.MeetingActionItem, action_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found.")

    status = payload.get("status")
    if status not in {"pending", "completed", "cancelled"}:
        raise HTTPException(
            status_code=422,
            detail="status must be pending, completed, or cancelled.",
        )

    item.status = status

    if status in {"completed", "cancelled"}:
        # Keep processed history, but remove reminders that have not fired.
        db.query(models.Notification).filter(
            models.Notification.action_item_id == item.id,
            models.Notification.is_sent == 0,
        ).delete(synchronize_session=False)
    elif status == "pending" and item.due_at is not None and not item.needs_confirmation:
        # Reopened tasks should have reminders matching the confirmed deadline.
        schedule_action_reminders(db, item)

    try:
        db.commit()
        db.refresh(item)
    except Exception as exc:
        db.rollback()
        print(f"Updating action item status failed: {type(exc).__name__}")
        raise HTTPException(status_code=500, detail="Could not update action item status.")

    return {
        "id": item.id,
        "action_text": item.action_text,
        "status": item.status,
    }


@app.get("/notifications")
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(models.Notification)

    if unread_only:
        query = query.filter(models.Notification.is_read == 0)

    notifications = query.order_by(
        models.Notification.scheduled_for.asc()
    ).all()

    return [
        {
            "id": notification.id,
            "action_item_id": notification.action_item_id,
            "reminder_type": notification.reminder_type,
            "scheduled_for": notification.scheduled_for,
            "is_read": bool(notification.is_read),
            "is_sent": bool(notification.is_sent),
            "action_text": notification.action_item.action_text,
        }
        for notification in notifications
    ]


@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
):
    notification = db.get(models.Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notification.is_read = 1
    db.commit()

    return {"id": notification.id, "is_read": True}


def process_due_notifications(db: Session) -> int:
    """Mark due reminders as available in the in-app notification feed."""
    now = datetime.utcnow()

    due_notifications = (
        db.query(models.Notification)
        .filter(
            models.Notification.is_sent == 0,
            models.Notification.scheduled_for <= now,
        )
        .all()
    )

    processed = 0

    for notification in due_notifications:
        item = db.get(models.MeetingActionItem, notification.action_item_id)

        if (
            item is None
            or item.status != "pending"
            or item.needs_confirmation
            or item.due_at is None
        ):
            notification.is_sent = 1
            continue

        notification.is_sent = 1
        processed += 1

    db.commit()
    return processed


@app.post("/notifications/process-due")
def process_due_notifications_endpoint(db: Session = Depends(get_db)):
    """Manually process due reminders; useful for testing and administration."""
    try:
        count = process_due_notifications(db)
        return {
            "processed": count,
            "message": "Due reminders processed into the in-app notification feed.",
        }
    except Exception as exc:
        db.rollback()
        print(f"Processing reminders failed: {type(exc).__name__}")
        raise HTTPException(status_code=500, detail="Could not process due reminders.")
    
# ============================================================
# PRODUCTS AND SERVICES
# ============================================================

@app.get("/products", response_model=list[schemas.ProductOut])
def list_products(db: Session = Depends(get_db)):
    return (
        db.query(models.Product)
        .order_by(models.Product.id.desc())
        .all()
    )


@app.post(
    "/products",
    response_model=schemas.ProductOut,
    status_code=201,
)
def create_product(
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
):
    if payload.item_type not in {"product", "service"}:
        raise HTTPException(
            status_code=422,
            detail="item_type must be 'product' or 'service'",
        )

    record = models.Product(**payload.model_dump())

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@app.put(
    "/products/{product_id}",
    response_model=schemas.ProductOut,
)
def update_product(
    product_id: int,
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
):
    record = db.get(models.Product, product_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Product/service not found",
        )

    if payload.item_type not in {"product", "service"}:
        raise HTTPException(
            status_code=422,
            detail="item_type must be 'product' or 'service'",
        )

    for key, value in payload.model_dump().items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)

    return record


@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    record = db.get(models.Product, product_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Product/service not found",
        )

    linked_deal = (
        db.query(models.Deal)
        .filter(models.Deal.product_id == product_id)
        .first()
    )

    if linked_deal:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete this product because deals reference it."
            ),
        )

    db.delete(record)
    db.commit()

    return {
        "message": "Product/service deleted successfully",
        "id": product_id,
    }


# ============================================================
# CUSTOMERS
# ============================================================

@app.get("/customers", response_model=list[schemas.CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return (
        db.query(models.Customer)
        .order_by(models.Customer.id.desc())
        .all()
    )


@app.post(
    "/customers",
    response_model=schemas.CustomerOut,
    status_code=201,
)
def create_customer(
    payload: schemas.CustomerCreate,
    db: Session = Depends(get_db),
):
    record = models.Customer(**payload.model_dump())

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@app.put(
    "/customers/{customer_id}",
    response_model=schemas.CustomerOut,
)
def update_customer(
    customer_id: int,
    payload: schemas.CustomerCreate,
    db: Session = Depends(get_db),
):
    record = db.get(models.Customer, customer_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    for key, value in payload.model_dump().items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)

    return record


@app.delete("/customers/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
):
    record = db.get(models.Customer, customer_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    linked_deal = (
        db.query(models.Deal)
        .filter(models.Deal.customer_id == customer_id)
        .first()
    )

    if linked_deal:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete this customer because deals reference it."
            ),
        )

    db.delete(record)
    db.commit()

    return {
        "message": "Customer deleted successfully",
        "id": customer_id,
    }


# ============================================================
# DEALS AND QUOTATIONS
# ============================================================

VALID_DEAL_STATUSES = {
    "proposed",
    "approved",
    "won",
    "lost",
}


VALID_ACTIVITY_TYPES = {
    "call",
    "meeting",
    "email",
    "proposal_sent",
    "objection",
    "follow_up",
    "commitment",
}

VALID_ACTIVITY_OUTCOMES = {
    "positive",
    "neutral",
    "negative",
    "no_response",
    "unknown",
}

@app.get("/deals", response_model=list[schemas.DealOut])
def list_deals(db: Session = Depends(get_db)):
    return (
        db.query(models.Deal)
        .order_by(models.Deal.id.desc())
        .all()
    )


@app.post(
    "/deals",
    response_model=schemas.DealOut,
    status_code=201,
)
def create_deal(
    payload: schemas.DealCreate,
    db: Session = Depends(get_db),
):
    if payload.status not in VALID_DEAL_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                "status must be proposed, approved, won, or lost"
            ),
        )

    if not db.get(models.Customer, payload.customer_id):
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if (
        payload.product_id is not None
        and not db.get(models.Product, payload.product_id)
    ):
        raise HTTPException(
            status_code=404,
            detail="Product/service not found",
        )

    record = models.Deal(**payload.model_dump())

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@app.put("/deals/{deal_id}", response_model=schemas.DealOut)
def update_deal(
    deal_id: int,
    payload: schemas.DealCreate,
    db: Session = Depends(get_db),
):
    record = db.get(models.Deal, deal_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Deal not found",
        )

    if payload.status not in VALID_DEAL_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                "status must be proposed, approved, won, or lost"
            ),
        )

    if not db.get(models.Customer, payload.customer_id):
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if (
        payload.product_id is not None
        and not db.get(models.Product, payload.product_id)
    ):
        raise HTTPException(
            status_code=404,
            detail="Product/service not found",
        )

    for key, value in payload.model_dump().items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)

    return record


@app.delete("/deals/{deal_id}")
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
):
    record = db.get(models.Deal, deal_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Deal not found",
        )

    db.delete(record)
    db.commit()

    return {
        "message": "Deal deleted successfully",
        "id": deal_id,
    }


# ============================================================
# DASHBOARD ANALYTICS
# ============================================================

@app.get(
    "/analytics/dashboard",
    response_model=schemas.DashboardOut,
)
def dashboard(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    customers = db.query(models.Customer).all()
    deals = db.query(models.Deal).all()

    status_counts = Counter(
        deal.status for deal in deals
    )

    proposed_value = sum(
        deal.quantity * deal.proposed_unit_price
        for deal in deals
        if deal.status in {"proposed", "approved"}
    )

    won_value = sum(
        deal.quantity * deal.proposed_unit_price
        for deal in deals
        if deal.status == "won"
    )

    # Estimate only; this is not verified accounting profit.
    products_by_id = {
        product.id: product
        for product in products
    }

    gross_profit_estimate = 0.0

    for deal in deals:
        product = products_by_id.get(deal.product_id)

        if deal.status == "won" and product:
            gross_profit_estimate += (
                deal.quantity
                * (
                    deal.proposed_unit_price
                    - product.unit_cost
                )
            )

    return {
        "products_count": len(products),
        "customers_count": len(customers),
        "deals_count": len(deals),
        "proposed_value": round(proposed_value, 2),
        "won_value": round(won_value, 2),
        "won_gross_profit_estimate": round(
            gross_profit_estimate, 2
        ),
        "deal_status_counts": dict(status_counts),
    }


# ============================================================
# FICTIONAL DEMO DATA
# ============================================================

@app.post("/demo/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    if (
        db.query(models.Customer).count()
        or db.query(models.Product).count()
        or db.query(models.Deal).count()
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Database already has records; "
                "seed only an empty database."
            ),
        )

    customers = [
        models.Customer(
            name="Aster Lane",
            company="Aster Lane Group",
            email="buyer@example.test",
            notes="Fictional demo customer",
        ),
        models.Customer(
            name="Northstar Works",
            company="Northstar Works",
            email="procurement@example.test",
            notes="Fictional demo customer",
        ),
        models.Customer(
            name="Mosaic & Co",
            company="Mosaic & Co",
            email="ops@example.test",
            notes="Fictional demo customer",
        ),
    ]

    products = [
        models.Product(
            name="Item Alpha",
            category="Category One",
            item_type="product",
            unit_cost=42,
            list_price=65,
        ),
        models.Product(
            name="Service Beta",
            category="Category Two",
            item_type="service",
            unit_cost=120,
            list_price=200,
        ),
        models.Product(
            name="Item Gamma",
            category="Category One",
            item_type="product",
            unit_cost=18,
            list_price=30,
        ),
    ]

    db.add_all(customers + products)
    db.commit()

    for record in customers + products:
        db.refresh(record)

    deals = [
        models.Deal(
            title="Alpha bulk enquiry",
            customer_id=customers[0].id,
            product_id=products[0].id,
            quantity=100,
            proposed_unit_price=61,
            status="proposed",
            notes="Fictional demo deal",
        ),
        models.Deal(
            title="Beta service proposal",
            customer_id=customers[1].id,
            product_id=products[1].id,
            quantity=4,
            proposed_unit_price=190,
            status="approved",
            notes="Fictional demo deal",
        ),
        models.Deal(
            title="Gamma repeat order",
            customer_id=customers[2].id,
            product_id=products[2].id,
            quantity=250,
            proposed_unit_price=29,
            status="won",
            notes="Fictional demo deal",
        ),
        models.Deal(
            title="Alpha renewal discussion",
            customer_id=customers[0].id,
            product_id=products[0].id,
            quantity=60,
            proposed_unit_price=58,
            status="lost",
            notes="Fictional demo deal",
        ),
    ]

    db.add_all(deals)
    db.commit()

    return {
        "message": "Fictional demo data created.",
        "customers": len(customers),
        "products_or_services": len(products),
        "deals": len(deals),
    }


# ============================================================
# AI DEAL RISK ANALYZER
# ============================================================

@app.get("/ai/deal-risk")
def analyze_deal_risk(
    db: Session = Depends(get_db),
):
    """
    Rule-based deal risk baseline.

    This endpoint does not use a trained ML model.
    Risk scores are heuristic indicators, not probabilities.
    """

    deals = (
        db.query(models.Deal)
        .filter(
            models.Deal.status.in_(["proposed", "approved"])
        )
        .order_by(models.Deal.id.desc())
        .all()
    )

    customers = {
        customer.id: customer
        for customer in db.query(models.Customer).all()
    }

    products = {
        product.id: product
        for product in db.query(models.Product).all()
    }

    today = date.today()
    results = []

    for deal in deals:
        score = 0
        signals = []
        recommendations = []

        customer = customers.get(deal.customer_id)
        product = products.get(deal.product_id)

        quantity = float(deal.quantity or 0)
        proposed_price = float(
            deal.proposed_unit_price or 0
        )

        deal_value = quantity * proposed_price

        # ----------------------------------------------------
        # 1. Expected close date
        # ----------------------------------------------------

        raw_date = (
            deal.expected_close_date or ""
        ).strip()

        if raw_date:
            try:
                close_date = date.fromisoformat(
                    raw_date[:10]
                )

                if close_date < today:
                    score += 35

                    signals.append(
                        "Expected close date has passed."
                    )

                    recommendations.append(
                        "Contact the customer to confirm whether "
                        "the deal is still active and update its "
                        "expected close date."
                    )

                elif close_date <= today + timedelta(days=7):
                    score += 15

                    signals.append(
                        "Expected close date is within the next 7 days."
                    )

                    recommendations.append(
                        "Confirm the decision timeline and agree "
                        "on the next step with the customer."
                    )

            except ValueError:
                score += 10

                signals.append(
                    "Expected close date is not a valid date."
                )

                recommendations.append(
                    "Correct the expected close date."
                )

        else:
            score += 10

            signals.append(
                "Expected close date is missing."
            )

            recommendations.append(
                "Set a realistic expected close date."
            )

        # ----------------------------------------------------
        # 2. Proposed price versus product/service cost
        # ----------------------------------------------------

        if product is not None:
            unit_cost = float(product.unit_cost or 0)
            list_price = float(product.list_price or 0)

            if proposed_price < unit_cost:
                score += 40

                signals.append(
                    "Proposed unit price is below the recorded unit cost."
                )

                recommendations.append(
                    "Review the quotation and confirm whether "
                    "the below-cost price is intentional and approved."
                )

            elif list_price > 0:
                discount = (
                    list_price - proposed_price
                ) / list_price

                if discount > 0.20:
                    score += 15

                    signals.append(
                        "Proposed price is more than 20% below list price."
                    )

                    recommendations.append(
                        "Review the discount and confirm the expected margin."
                    )

        # ----------------------------------------------------
        # 3. Warning phrases in deal notes
        # ----------------------------------------------------

        notes = (deal.notes or "").lower()

        risk_terms = {
            "no response": (
                "Notes mention no customer response."
            ),
            "not responding": (
                "Notes mention the customer is not responding."
            ),
            "competitor": (
                "Notes mention a competitor."
            ),
            "budget issue": (
                "Notes mention a budget issue."
            ),
            "price objection": (
                "Notes mention a price objection."
            ),
            "delayed": (
                "Notes mention a delay."
            ),
            "cancel": (
                "Notes mention cancellation."
            ),
        }

        for term, explanation in risk_terms.items():
            if term in notes:
                score += 10
                signals.append(explanation)

                recommendations.append(
                    "Follow up on this concern directly and "
                    "document the customer's response."
                )

        # Keep the score between 0 and 100.
        score = min(score, 100)

        if score >= 60:
            risk_level = "High"
        elif score >= 30:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        if not recommendations:
            recommendations.append(
                "No major warning signs were detected by the "
                "current rules. Confirm the next customer milestone."
            )

        results.append({
            "deal_id": deal.id,
            "deal_title": deal.title,
            "customer_name": (
                customer.name if customer else "Unknown"
            ),
            "company": (
                customer.company if customer else ""
            ),
            "status": deal.status,
            "deal_value": round(deal_value, 2),
            "expected_close_date": raw_date or None,
            "risk_score": score,
            "risk_level": risk_level,
            "signals": signals,
            "recommendations": list(
                dict.fromkeys(recommendations)
            ),
        })

    # Highest risk first.
    results.sort(
        key=lambda item: item["risk_score"],
        reverse=True,
    )

    high_risk_count = sum(
        item["risk_level"] == "High"
        for item in results
    )

    medium_risk_count = sum(
        item["risk_level"] == "Medium"
        for item in results
    )

    low_risk_count = sum(
        item["risk_level"] == "Low"
        for item in results
    )

    return {
        "analysis_type": "rule_based_baseline",
        "disclaimer": (
            "Risk scores are heuristic indicators, not calibrated "
            "probabilities of losing a deal."
        ),
        "total_open_deals": len(results),
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "low_risk_count": low_risk_count,
        "deals": results,
    }
# ============================================================
# PHASE 4: REAL MACHINE-LEARNING DEAL OUTCOME PREDICTION
# ============================================================

@app.get("/ai/ml/status")
def ml_model_status(db: Session = Depends(get_db)):
    """
    Show whether a trained ML model is available and
    how many genuine historical won/lost outcomes exist.
    """
    return ml_service.get_model_status(db)


@app.post("/ai/ml/train")
def train_deal_outcome_model(db: Session = Depends(get_db)):
    """
    Train a Logistic Regression model using historical
    deals marked won or lost.
    """
    result = ml_service.train_model(db)

    if not result.get("trained"):
        # Return the honest training status and data requirements.
        return result

    return result


@app.get("/ai/ml/predict/{deal_id}")
def predict_deal_outcome(
    deal_id: int,
    db: Session = Depends(get_db),
):
    """
    Predict the outcome of a deal using the saved ML model.
    This is separate from the rule-based risk analyzer.
    """
    result = ml_service.predict_deal(db, deal_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deal with ID {deal_id} was not found.",
        )

    return result

# ============================================================
# DEAL ACTIVITY HISTORY
# ============================================================

@app.post(
    "/deals/{deal_id}/activities",
    response_model=schemas.DealActivityOut,
    status_code=201,
)
def create_deal_activity(
    deal_id: int,
    payload: schemas.DealActivityCreate,
    db: Session = Depends(get_db),
):
    deal = db.get(models.Deal, deal_id)

    if not deal:
        raise HTTPException(
            status_code=404,
            detail="Deal not found",
        )

    activity_type = payload.activity_type.strip().lower()
    outcome = payload.outcome.strip().lower()

    if activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid activity_type",
                "allowed_values": sorted(VALID_ACTIVITY_TYPES),
            },
        )

    if outcome not in VALID_ACTIVITY_OUTCOMES:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid outcome",
                "allowed_values": sorted(VALID_ACTIVITY_OUTCOMES),
            },
        )

    activity = models.DealActivity(
        deal_id=deal_id,
        activity_type=activity_type,
        outcome=outcome,
        description=payload.description,
        next_follow_up_date=payload.next_follow_up_date,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity


@app.get(
    "/deals/{deal_id}/activities",
    response_model=list[schemas.DealActivityOut],
)
def list_deal_activities(
    deal_id: int,
    db: Session = Depends(get_db),
):
    deal = db.get(models.Deal, deal_id)

    if not deal:
        raise HTTPException(
            status_code=404,
            detail="Deal not found",
        )

    return (
        db.query(models.DealActivity)
        .filter(models.DealActivity.deal_id == deal_id)
        .order_by(models.DealActivity.created_at.desc())
        .all()
    )


@app.get(
    "/activities",
    response_model=list[schemas.DealActivityOut],
)
def list_all_activities(
    db: Session = Depends(get_db),
):
    return (
        db.query(models.DealActivity)
        .order_by(models.DealActivity.created_at.desc())
        .all()
    )
