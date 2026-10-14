import pytest
import os
from sqlalchemy import delete
from src.tenderlens.db.database import init_db, AsyncSessionLocal
from src.tenderlens.db.models import BidTask, Tender, Contractor, MessageLog
from src.tenderlens.agent.tools import execute_tool
from src.tenderlens.workflows.activities import evaluate_bid_health_activity, send_whatsapp_message_activity, SendWhatsAppInput

@pytest.mark.asyncio
async def test_end_to_end_flow():
    # 1. Initialize database and clear test tables
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(BidTask))
        await session.execute(delete(Tender))
        await session.execute(delete(Contractor))
        await session.execute(delete(MessageLog))
        await session.commit()
    
    # 2. Ingest ad image
    ad_res = await execute_tool("ingest_tender_ad_image", {
        "image_path": "fixtures/sample_real_tender_ad.png",
        "contractor_phone": "+18687771234"
    })
    assert ad_res["status"] == "success"
    tender_id = ad_res["tender_id"]
    
    # 3. Draft package request email
    draft_res = await execute_tool("draft_tender_request_email", {
        "tender_id": tender_id,
        "contractor_company": "Apex Facility Management Ltd",
        "contractor_name": "Anthony Baptiste",
        "contractor_email": "anthony@apex.tt"
    })
    assert draft_res["status"] == "success"
    assert "purchasingandstores@wasa.gov.tt" in draft_res["to"]
    
    # 4. Ingest full tender document
    full_res = await execute_tool("ingest_full_tender_pdf", {
        "tender_id": tender_id,
        "file_path": "fixtures/sample_tt_full_tender.txt"
    })
    assert full_res["status"] == "success"
    assert full_res["total_requirements"] >= 8
    
    # 5. Check health activity
    health = await evaluate_bid_health_activity(tender_id)
    assert health.total_tasks >= 8
    assert health.completed_tasks == 0
    assert health.has_statutory_bottleneck is True
    assert "BIR Tax Clearance" in health.suggested_prompt
    
    # 6. Update BIR task to done
    update_res = await execute_tool("update_bid_task_status", {
        "tender_id": tender_id,
        "task_id": "bir",
        "new_status": "done",
        "contractor_notes": "Certificate obtained from IRD Port of Spain"
    })
    assert update_res["status"] == "success"
    assert update_res["new_status"] == "done"
    
    # 7. Re-check health after update
    updated_health = await evaluate_bid_health_activity(tender_id)
    assert updated_health.completed_tasks == 1
    assert updated_health.readiness_percentage > 0.0
    
    # 8. Test sending message activity
    msg_res = await send_whatsapp_message_activity(SendWhatsAppInput(
        contractor_id="+18687771234",
        tender_id=tender_id,
        message="Test reminder from TenderLens"
    ))
    assert msg_res is True
