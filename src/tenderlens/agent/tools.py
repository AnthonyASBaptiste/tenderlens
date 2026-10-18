import os
import json
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from src.tenderlens.db.database import AsyncSessionLocal
from src.tenderlens.db.models import Contractor, Tender, BidTask, MessageLog
from src.tenderlens.extractor.ad_parser import extract_from_image, TenderNoticeData
from src.tenderlens.extractor.email_drafter import draft_package_request_email, EmailDraftRequest
from src.tenderlens.extractor.pdf_parser import load_text_or_pdf
from src.tenderlens.extractor.compliance_analyzer import analyze_compliance_requirements, TenderBidPlan
from src.tenderlens.config import settings

TENDERLENS_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "ingest_tender_ad_image",
            "description": "Processes an image of a newspaper tender notice or EOI ad, extracts critical dates and contact instructions, and creates a tracked tender record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Local path or URL to the tender notice image."},
                    "contractor_phone": {"type": "string", "description": "Contractor's WhatsApp phone number (e.g. +18687771234)."}
                },
                "required": ["image_path", "contractor_phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draft_tender_request_email",
            "description": "Generates a formal procurement package request email addressed to the procuring entity for Oracle ERP / portal access.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tender_id": {"type": "string", "description": "The unique ID or ref number of the tender."},
                    "contractor_company": {"type": "string", "description": "Contractor's company name."},
                    "contractor_name": {"type": "string", "description": "Authorized contact person name."},
                    "contractor_email": {"type": "string", "description": "Email address for ERP access."}
                },
                "required": ["tender_id", "contractor_company", "contractor_name", "contractor_email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ingest_full_tender_pdf",
            "description": "Parses a full tender RFP PDF document, extracts all statutory and technical compliance requirements with page citations, and initializes the bid checklist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tender_id": {"type": "string", "description": "The tender ID to attach the bid plan to."},
                    "file_path": {"type": "string", "description": "Path to the full tender PDF or document."}
                },
                "required": ["tender_id", "file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_tender_status",
            "description": "Retrieves the current progress, completed checklist items, and next recommended action for an active tender.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tender_id": {"type": "string", "description": "The tender ID or reference number."}
                },
                "required": ["tender_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_bid_task_status",
            "description": "Updates the progress of a specific task (e.g. marking BIR clearance as done or in progress).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tender_id": {"type": "string", "description": "The tender ID."},
                    "task_id": {"type": "string", "description": "Task identifier or keyword (e.g. bir, nis, vat, bond)."},
                    "new_status": {"type": "string", "enum": ["done", "in_progress", "missing", "flagged_uncertain"], "description": "New task status."},
                    "contractor_notes": {"type": "string", "description": "Optional notes from the contractor."}
                },
                "required": ["tender_id", "task_id", "new_status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_requirement",
            "description": "Provides guidance on Trinidad & Tobago statutory requirements, explaining what office issues the document and typical processing time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requirement_type": {"type": "string", "description": "Requirement to explain: BIR, NIS, VAT, TENDER_BOND, or OSH."}
                },
                "required": ["requirement_type"]
            }
        }
    }
]
HERMES_TOOLS_SCHEMA = TENDERLENS_TOOLS_SCHEMA

async def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches tool execution to the appropriate backend handler."""
    if name == "ingest_tender_ad_image":
        return await handle_ingest_ad_image(args["image_path"], args["contractor_phone"])
    elif name == "draft_tender_request_email":
        return await handle_draft_email(args["tender_id"], args["contractor_company"], args["contractor_name"], args["contractor_email"])
    elif name == "ingest_full_tender_pdf":
        return await handle_ingest_full_pdf(args["tender_id"], args["file_path"])
    elif name == "get_tender_status":
        return await handle_get_status(args["tender_id"])
    elif name == "update_bid_task_status":
        return await handle_update_task(args["tender_id"], args["task_id"], args["new_status"], args.get("contractor_notes"))
    elif name == "explain_requirement":
        return handle_explain_requirement(args["requirement_type"])
    else:
        return {"error": f"Unknown tool: {name}"}

async def handle_ingest_ad_image(image_path: str, contractor_phone: str) -> Dict[str, Any]:
    notice: TenderNoticeData = await extract_from_image(image_path)
    tender_id = f"tender_{notice.ref_no.lower().replace(' ', '_').replace('.', '').replace('-', '_').replace('/', '_')}"
    
    async with AsyncSessionLocal() as session:
        # 1. Upsert contractor
        c_res = await session.execute(select(Contractor).where(Contractor.id == contractor_phone))
        contractor = c_res.scalar_one_or_none()
        if not contractor:
            contractor = Contractor(id=contractor_phone)
            session.add(contractor)
            
        # 2. Upsert tender
        t_res = await session.execute(select(Tender).where(Tender.id == tender_id))
        tender = t_res.scalar_one_or_none()
        if not tender:
            tender = Tender(
                id=tender_id,
                contractor_id=contractor_phone,
                ref_no=notice.ref_no,
                authority=notice.authority,
                title=notice.title,
                line_of_business=notice.line_of_business,
                stage="notice_only",
                publication_date=notice.publication_date,
                site_visit_date=notice.site_visit_date,
                site_visit_registration_deadline=notice.site_visit_registration_deadline,
                queries_deadline=notice.queries_deadline,
                closing_deadline=notice.closing_deadline,
                procurement_contact_email=notice.procurement_email,
                procurement_phone=notice.procurement_phone,
                source_file_path=image_path
            )
            session.add(tender)
        await session.commit()
        
    return {
        "status": "success",
        "tender_id": tender_id,
        "ref_no": notice.ref_no,
        "authority": notice.authority,
        "title": notice.title,
        "closing_deadline": notice.closing_deadline,
        "site_visit_date": notice.site_visit_date,
        "site_visit_registration_deadline": notice.site_visit_registration_deadline,
        "procurement_email": notice.procurement_email,
        "immediate_actions": notice.immediate_actions,
        "message": f"Successfully ingested tender notice for {notice.authority} ({notice.ref_no})."
    }

async def handle_draft_email(tender_id: str, company: str, name: str, email: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Tender).where((Tender.id == tender_id) | (Tender.ref_no == tender_id)))
        tender = res.scalar_one_or_none()
        if not tender:
            return {"error": f"Tender {tender_id} not found."}
            
        draft = draft_package_request_email(EmailDraftRequest(
            tender_ref=tender.ref_no,
            tender_title=tender.title,
            procuring_entity=tender.authority,
            procurement_email=tender.procurement_contact_email or "purchasingandstores@wasa.gov.tt",
            contractor_company=company,
            contractor_name=name,
            contractor_phone=tender.contractor_id,
            contractor_email=email
        ))
        
        tender.stage = "package_requested"
        await session.commit()
        
    return {
        "status": "success",
        "to": draft["to"],
        "subject": draft["subject"],
        "body": draft["body"],
        "instructions": "Copy and email this to the procurement email to register for ERP tender access."
    }

async def handle_ingest_full_pdf(tender_id: str, file_path: str) -> Dict[str, Any]:
    pages = load_text_or_pdf(file_path)
    
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Tender).where((Tender.id == tender_id) | (Tender.ref_no == tender_id)))
        tender = res.scalar_one_or_none()
        if not tender:
            return {"error": f"Tender {tender_id} not found."}
            
        plan: TenderBidPlan = analyze_compliance_requirements(pages, tender.ref_no, tender.closing_deadline or "TBD")
        
        # Save tasks to DB
        for item in plan.tasks:
            # Check if task already exists
            task_uid = f"{tender.id}_{item.task_id}"
            task_res = await session.execute(select(BidTask).where(BidTask.id == task_uid))
            task_obj = task_res.scalar_one_or_none()
            if not task_obj:
                task_obj = BidTask(
                    id=task_uid,
                    tender_id=tender.id,
                    category=item.category,
                    title=item.title,
                    description=item.description,
                    citation_page=item.citation_page,
                    status=item.status,
                    notes=f"Lead time: {item.lead_time_days} days. {item.action_prompt}"
                )
                session.add(task_obj)
                
        tender.stage = "full_rfp"
        await session.commit()
        
    return {
        "status": "success",
        "tender_id": tender_id,
        "total_requirements": plan.total_requirements_count,
        "statutory_warning": plan.statutory_warning,
        "sample_tasks": [{"id": t.task_id, "title": t.title, "page": t.citation_page} for t in plan.tasks[:4]]
    }

async def handle_get_status(tender_id: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        t_res = await session.execute(select(Tender).where((Tender.id == tender_id) | (Tender.ref_no == tender_id)))
        tender = t_res.scalar_one_or_none()
        if not tender:
            return {"error": f"Tender {tender_id} not found."}
            
        tasks_res = await session.execute(select(BidTask).where(BidTask.tender_id == tender.id))
        tasks = tasks_res.scalars().all()
        
        total = len(tasks)
        completed = [t for t in tasks if t.status == "done"]
        missing = [t for t in tasks if t.status != "done"]
        
        pct = round((len(completed) / total * 100), 1) if total > 0 else 0.0
        
        next_action = "Request tender package from authority."
        if tender.stage == "full_rfp":
            stat_missing = [t for t in missing if t.category == "Statutory"]
            if stat_missing:
                next_action = f"Apply immediately for {stat_missing[0].title} (High lead-time bottleneck!)."
            elif missing:
                next_action = f"Prepare {missing[0].title}."
            else:
                next_action = "Review final package and upload to portal!"
                
        return {
            "tender_id": tender.id,
            "ref_no": tender.ref_no,
            "authority": tender.authority,
            "stage": tender.stage,
            "closing_deadline": tender.closing_deadline,
            "total_items": total,
            "completed_count": len(completed),
            "missing_count": len(missing),
            "readiness_percentage": pct,
            "completed_items": [t.title for t in completed],
            "outstanding_items": [f"{t.title} ({t.citation_page})" for t in missing[:5]],
            "next_recommended_action": next_action
        }

async def handle_update_task(tender_id: str, task_key: str, status: str, notes: Optional[str] = None) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        t_res = await session.execute(select(Tender).where((Tender.id == tender_id) | (Tender.ref_no == tender_id)))
        tender = t_res.scalar_one_or_none()
        if not tender:
            return {"error": f"Tender {tender_id} not found."}
            
        tasks_res = await session.execute(select(BidTask).where(BidTask.tender_id == tender.id))
        tasks = tasks_res.scalars().all()
        
        matched_task = None
        for t in tasks:
            if task_key.lower() in t.id.lower() or task_key.lower() in t.title.lower():
                matched_task = t
                break
                
        if not matched_task:
            return {"error": f"Could not find matching task for keyword '{task_key}'."}
            
        matched_task.status = status
        if notes:
            matched_task.notes = f"{matched_task.notes or ''} | Contractor note: {notes}"
        await session.commit()
        
        return {
            "status": "success",
            "task_title": matched_task.title,
            "new_status": matched_task.status,
            "tender_ref": tender.ref_no,
            "message": f"Updated '{matched_task.title}' to {status}."
        }

def handle_explain_requirement(req_type: str) -> Dict[str, Any]:
    req = req_type.upper()
    if "BIR" in req or "TAX" in req:
        return {
            "requirement": "Board of Inland Revenue (BIR) Tax Clearance",
            "issuing_agency": "Inland Revenue Division (IRD), Ministry of Finance, Trinidad and Tobago",
            "typical_turnaround": "5 to 10 business days",
            "validity": "Usually valid for 6 months",
            "why_mandatory": "Required under Section 58 of the Public Procurement and Disposal of Public Property Act. Tenders without valid tax compliance are rejected on administrative grounds.",
            "pro_tip": "If expired, submit your renewal application immediately at the IRD office in Port of Spain or San Fernando."
        }
    elif "VAT" in req:
        return {
            "requirement": "Value Added Tax (VAT) Clearance Certificate",
            "issuing_agency": "Inland Revenue Division (IRD), Ministry of Finance, Trinidad and Tobago",
            "typical_turnaround": "5 to 10 business days",
            "validity": "Usually valid for 6 months",
            "why_mandatory": "Mandatory under Section 58 of the Public Procurement and Disposal of Public Property Act to verify that VAT returns and payments are in good standing.",
            "pro_tip": "If you already obtained a VAT clearance for another public tender in the past 6 months, verify if the expiry date extends past this bid's closing deadline."
        }
    elif "NIS" in req or "NIB" in req:
        return {
            "requirement": "National Insurance Board (NIS) Compliance Certificate",
            "issuing_agency": "National Insurance Board of Trinidad and Tobago (NIBTT)",
            "typical_turnaround": "3 to 5 business days",
            "validity": "Valid for 3 months to 1 year",
            "why_mandatory": "Certifies that your company's employee and employer contributions are up to date.",
            "pro_tip": "Bring your proof of contribution payments to your local NIB service center."
        }
    elif "BOND" in req or "SECURITY" in req:
        return {
            "requirement": "Bid Security / Tender Bond",
            "issuing_agency": "Commercial Banks (Republic, RBC, Scotiabank, First Citizens) or Insurance Companies",
            "typical_turnaround": "3 to 5 business days",
            "validity": "90 to 120 days (as specified in RFP)",
            "why_mandatory": "Protects the procuring entity if a winning bidder withdraws or refuses to sign the contract.",
            "pro_tip": "Ensure the bond wording exactly matches the specimen in the tender document, including the validity period (often 90 to 120 days)."
        }
    elif "INCORPORATION" in req or "DIRECTOR" in req or "FORM 4" in req or "FORM 28" in req or "COMPANY" in req:
        return {
            "requirement": "Certificate of Incorporation & Notice of Directors (Form 4 / Form 28)",
            "issuing_agency": "Registrar General's Department, Ministry of the Attorney General and Legal Affairs (TTBizLink / Companies Registry)",
            "typical_turnaround": "Immediate (if copies on file) or 1 to 3 business days for certified copies",
            "validity": "Valid indefinitely unless company directorship or articles change",
            "why_mandatory": "Verifies legal personality and confirms authorized signatories on tender submissions.",
            "pro_tip": "Keep certified true copies of your company documents in your compliance folder."
        }
    else:
        return {
            "requirement": req_type,
            "guidance": "Consult the instructions to tenderers in the procurement package for specific formatting requirements."
        }
