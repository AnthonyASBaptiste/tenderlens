import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Contractor(Base):
    __tablename__ = "contractors"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True) # E.164 phone number e.g. +18681234567
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    tenders: Mapped[List["Tender"]] = relationship("Tender", back_populates="contractor")

class Tender(Base):
    __tablename__ = "tenders"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True) # e.g. tender_wtc_40_2026
    contractor_id: Mapped[str] = mapped_column(String(50), ForeignKey("contractors.id"))
    ref_no: Mapped[str] = mapped_column(String(100)) # e.g. W.T.C. - 40/2026
    authority: Mapped[str] = mapped_column(String(255)) # e.g. WASA
    title: Mapped[str] = mapped_column(Text)
    line_of_business: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stage: Mapped[str] = mapped_column(String(50), default="notice_only") # notice_only, package_requested, full_rfp, submitted
    
    publication_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    site_visit_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    site_visit_registration_deadline: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    queries_deadline: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    closing_deadline: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    procurement_contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    procurement_phone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    contractor: Mapped["Contractor"] = relationship("Contractor", back_populates="tenders")
    tasks: Mapped[List["BidTask"]] = relationship("BidTask", back_populates="tender", cascade="all, delete-orphan")

class BidTask(Base):
    __tablename__ = "bid_tasks"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tender_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenders.id"))
    category: Mapped[str] = mapped_column(String(50)) # Statutory, Technical, Financial_Bond, Logistics
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="missing") # missing, in_progress, done, flagged_uncertain
    due_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    citation_page: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    tender: Mapped["Tender"] = relationship("Tender", back_populates="tasks")

class MessageLog(Base):
    __tablename__ = "message_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contractor_id: Mapped[str] = mapped_column(String(50))
    tender_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    direction: Mapped[str] = mapped_column(String(20)) # inbound, outbound
    content: Mapped[Text] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
