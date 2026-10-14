import datetime
from temporalio import activity
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from src.tenderlens.db.database import AsyncSessionLocal
from src.tenderlens.db.models import Tender, BidTask, MessageLog, Contractor
import httpx
from src.tenderlens.config import settings

class SendWhatsAppInput(BaseModel):
    contractor_id: str
    tender_id: Optional[str] = None
    message: str

class BidHealthResult(BaseModel):
    tender_id: str
    total_tasks: int
    completed_tasks: int
    missing_tasks: int
    readiness_percentage: float
    has_statutory_bottleneck: bool
    critical_missing: List[str]
    suggested_prompt: str

@activity.defn
async def send_whatsapp_message_activity(params: SendWhatsAppInput) -> bool:
    """
    Sends an outbound proactive message to the contractor over WhatsApp
    and logs the message in the audit table.
    """
    activity.logger.info(f"Dispatched proactive WhatsApp to {params.contractor_id}: {params.message[:50]}...")
    
    # 1. Log to DB
    async with AsyncSessionLocal() as session:
        log_entry = MessageLog(
            contractor_id=params.contractor_id,
            tender_id=params.tender_id,
            direction="outbound",
            content=params.message
        )
        session.add(log_entry)
        await session.commit()
        
    # 2. If WhatsApp Cloud API credentials are provided, send HTTP POST
    if settings.whatsapp_api_token and settings.whatsapp_phone_number_id:
        try:
            url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {settings.whatsapp_api_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": params.contractor_id.replace("+", ""),
                "type": "text",
                "text": {"body": params.message}
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code >= 400:
                    activity.logger.warning(f"WhatsApp API warning: {resp.text}")
        except Exception as e:
            activity.logger.error(f"Failed to post to WhatsApp API: {e}")
            
    return True

@activity.defn
async def evaluate_bid_health_activity(tender_id: str) -> BidHealthResult:
    """
    Evaluates current progress against deadlines, checking for high-lead-time blockers
    like BIR/NIS tax clearances.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BidTask).where(BidTask.tender_id == tender_id))
        tasks = result.scalars().all()
        
        if not tasks:
            return BidHealthResult(
                tender_id=tender_id,
                total_tasks=0,
                completed_tasks=0,
                missing_tasks=0,
                readiness_percentage=0.0,
                has_statutory_bottleneck=False,
                critical_missing=[],
                suggested_prompt="No tasks recorded for this tender yet."
            )
            
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "done")
        missing_tasks = [t for t in tasks if t.status != "done"]
        
        # Check statutory bottlenecks
        stat_blockers = [t.title for t in missing_tasks if t.category == "Statutory"]
        pct = round((completed / total) * 100, 1)
        
        critical_missing = [t.title for t in missing_tasks[:3]]
        
        if stat_blockers:
            prompt = f"Reminder: Your {stat_blockers[0]} is still marked outstanding. Have you obtained or requested it? Reply 'Done', 'In Progress', or 'Need Help'."
        elif missing_tasks:
            prompt = f"TenderLens Check-in: You have completed {completed}/{total} items ({pct}%). Next priority: {missing_tasks[0].title}. Is this ready?"
        else:
            prompt = "All bid checklist requirements are complete! Ready for final submission assembly."
            
        return BidHealthResult(
            tender_id=tender_id,
            total_tasks=total,
            completed_tasks=completed,
            missing_tasks=len(missing_tasks),
            readiness_percentage=pct,
            has_statutory_bottleneck=len(stat_blockers) > 0,
            critical_missing=critical_missing,
            suggested_prompt=prompt
        )
