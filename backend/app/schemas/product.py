from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.security import sanitize_text
from app.models.product import (
    CallToAction,
    CaseStudy,
    FAQ,
    Feature,
    IdealCustomerProfile,
    Integration,
    Objection,
    Pricing,
)


def _text(limit: int):
    def _v(value):
        return sanitize_text(value, max_length=limit)

    return _v


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tagline: str = ""
    description: str = ""
    category: str = ""
    target_customers: str = ""
    main_problem: str = ""
    main_benefits: list[str] = Field(default_factory=list)
    features: list[Feature] = Field(default_factory=list)
    pricing: Pricing = Field(default_factory=Pricing)
    integrations: list[Integration] = Field(default_factory=list)
    security_info: str = ""
    faqs: list[FAQ] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    case_studies: list[CaseStudy] = Field(default_factory=list)
    icp: IdealCustomerProfile = Field(default_factory=IdealCustomerProfile)
    cta: CallToAction = Field(default_factory=CallToAction)
    welcome_message: str = ""

    @field_validator("name", "tagline", "category", mode="before")
    @classmethod
    def _short(cls, v):
        return sanitize_text(v, max_length=200)

    @field_validator(
        "description", "target_customers", "main_problem", "security_info",
        "welcome_message", mode="before",
    )
    @classmethod
    def _long(cls, v):
        return sanitize_text(v, max_length=6000)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    """Partial update — only the provided fields are written."""

    name: str | None = Field(default=None, max_length=120)
    tagline: str | None = None
    description: str | None = None
    category: str | None = None
    target_customers: str | None = None
    main_problem: str | None = None
    main_benefits: list[str] | None = None
    features: list[Feature] | None = None
    pricing: Pricing | None = None
    integrations: list[Integration] | None = None
    security_info: str | None = None
    faqs: list[FAQ] | None = None
    objections: list[Objection] | None = None
    case_studies: list[CaseStudy] | None = None
    icp: IdealCustomerProfile | None = None
    cta: CallToAction | None = None
    welcome_message: str | None = None
    is_published: bool | None = None


class ProductOut(ProductBase):
    id: str
    founder_id: str
    slug: str
    is_published: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    demo_url: str = ""


class ProductSummary(BaseModel):
    id: str
    name: str
    slug: str
    tagline: str = ""
    is_published: bool = False
    section_count: int = 0
    document_count: int = 0
    chunk_count: int = 0
    session_count: int = 0
    updated_at: str | None = None
    demo_url: str = ""


class KnowledgeStatus(BaseModel):
    product_id: str
    documents_total: int = 0
    documents_indexed: int = 0
    documents_failed: int = 0
    documents_processing: int = 0
    chunks_total: int = 0
    profile_chunks: int = 0
    vectors_indexed: int = 0
    embedding_model: str = ""
    vector_backend: str = ""
    ready: bool = False


# --- Demo sections ---------------------------------------------------------


class SectionHighlight(BaseModel):
    id: str = ""
    label: str = ""
    detail: str = ""


class DemoSectionBase(BaseModel):
    section_key: str = Field(min_length=1, max_length=48)
    title: str = Field(min_length=1, max_length=120)
    description: str = ""
    feature_explanation: str = ""
    visual_placeholder: str = ""
    highlights: list[SectionHighlight] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order_index: int = 0

    @field_validator("section_key", mode="before")
    @classmethod
    def _key(cls, v):
        from app.core.security import slugify

        return slugify(str(v or ""), fallback="section")

    @field_validator("title", "description", "visual_placeholder", mode="before")
    @classmethod
    def _short(cls, v):
        return sanitize_text(v, max_length=500)

    @field_validator("feature_explanation", mode="before")
    @classmethod
    def _long(cls, v):
        return sanitize_text(v, max_length=4000)

    @field_validator("keywords", mode="before")
    @classmethod
    def _kw(cls, v):
        if not v:
            return []
        if isinstance(v, str):
            v = [k for k in v.split(",")]
        return [sanitize_text(k, max_length=40) for k in v if sanitize_text(k)][:20]


class DemoSectionCreate(DemoSectionBase):
    pass


class DemoSectionUpdate(BaseModel):
    section_key: str | None = None
    title: str | None = None
    description: str | None = None
    feature_explanation: str | None = None
    visual_placeholder: str | None = None
    highlights: list[SectionHighlight] | None = None
    keywords: list[str] | None = None
    order_index: int | None = None


class DemoSectionOut(DemoSectionBase):
    id: str
    product_id: str


class SectionReorder(BaseModel):
    ordered_ids: list[str]


# --- Documents -------------------------------------------------------------


class DocumentOut(BaseModel):
    id: str
    product_id: str
    filename: str
    content_type: str = ""
    size_bytes: int = 0
    status: str = "pending"
    chunk_count: int = 0
    char_count: int = 0
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
