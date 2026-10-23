from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = "Uncategorized"
    item_type: str = "product"
    unit_cost: float = Field(default=0, ge=0)
    list_price: float = Field(default=0, ge=0)


class ProductOut(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: str = ""
    email: str = ""
    notes: str = ""


class CustomerOut(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class DealCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    customer_id: int
    product_id: int | None = None
    quantity: float = Field(default=1, gt=0)
    proposed_unit_price: float = Field(default=0, ge=0)
    status: str = "proposed"
    expected_close_date: str = ""
    notes: str = ""


class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    customer_id: int
    product_id: int | None
    quantity: float
    proposed_unit_price: float
    status: str
    expected_close_date: str
    notes: str
    created_at: datetime


class DashboardOut(BaseModel):
    products_count: int
    customers_count: int
    deals_count: int
    proposed_value: float
    won_value: float
    won_gross_profit_estimate: float
    deal_status_counts: dict[str, int]
    
class DealActivityCreate(BaseModel):
    activity_type: str = Field(min_length=1, max_length=50)
    outcome: str = Field(default="unknown", max_length=50)
    description: str = Field(default="", max_length=5000)
    next_follow_up_date: datetime | None = None


class DealActivityOut(DealActivityCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deal_id: int
    created_at: datetime



class MeetingActionItemCreate(BaseModel):
    meeting_note_id: int
    action_text: str
    source_quote: str = ""
    due_at: datetime | None = None
    confidence: float = 0.0
    needs_confirmation: bool = True


class MeetingActionItemOut(BaseModel):
    id: int
    meeting_note_id: int
    action_text: str
    source_quote: str
    due_at: datetime | None
    confidence: float
    needs_confirmation: bool
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
