import pytest
from httpx import AsyncClient, ASGITransport
from src.tenderlens.gateway.app import app
from src.tenderlens.agent.tools import execute_tool, handle_explain_requirement
from src.tenderlens.extractor.pdf_parser import load_text_or_pdf
from src.tenderlens.extractor.ad_parser import parse_notice_text

@pytest.mark.asyncio
async def test_webhook_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/webhook", params={
            "hub.mode": "subscribe",
            "hub.challenge": "123456",
            "hub.verify_token": "wrong_token_here"
        })
        assert res.status_code == 403
        assert "Verification failed" in res.text

@pytest.mark.asyncio
async def test_webhook_empty_payload():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/webhook", json={})
        assert res.status_code == 200
        assert res.json() == {"status": "ignored"}

@pytest.mark.asyncio
async def test_get_nonexistent_tender():
    res = await execute_tool("get_tender_status", {"tender_id": "nonexistent_tender_999"})
    assert "error" in res
    assert "not found" in res["error"].lower()

@pytest.mark.asyncio
async def test_update_nonexistent_task():
    res = await execute_tool("update_bid_task_status", {
        "tender_id": "tender_wtc___40_2026",
        "task_id": "totally_fabricated_nonexistent_task_xyz",
        "new_status": "done"
    })
    assert "error" in res
    assert "could not find matching task" in res["error"].lower()

def test_explain_all_statutory_requirements():
    for req in ["BIR", "NIS", "VAT", "BOND", "SECURITY", "UNKNOWN_REQ"]:
        exp = handle_explain_requirement(req)
        assert "requirement" in exp
        if req == "BIR":
            assert "Inland Revenue" in exp["issuing_agency"]
            assert "5 to 10" in exp["typical_turnaround"]
        elif req == "NIS":
            assert "NIBTT" in exp["issuing_agency"]
            assert "3 to 5" in exp["typical_turnaround"]
        elif req == "VAT":
            assert "Inland Revenue" in exp["issuing_agency"]
            assert "5 to 10" in exp["typical_turnaround"]
            assert "6 months" in exp["validity"]

def test_pdf_missing_file_raises_error():
    with pytest.raises(FileNotFoundError):
        load_text_or_pdf("fixtures/definitely_non_existent_file.pdf")

def test_ad_parser_robust_fallback():
    sparse_text = "TENDER FOR PAINTING OF WATER TANKS. Closing date: September 15, 2026. Ref: WASA-2026-PNT"
    parsed = parse_notice_text(sparse_text)
    assert parsed.ref_no == "WASA-2026-PNT"
    assert "PAINTING" in parsed.title

@pytest.mark.asyncio
async def test_tender_agent_magic_upload_link_intent():
    from src.tenderlens.agent.tender_agent import TenderAgent, HermesAgent
    agent = TenderAgent(contractor_phone="+18687771234")
    reply = await agent.chat("Send me the upload link to drop my tender package")
    assert "/upload/" in reply
    assert "token=" in reply
    
    # Verify backwards compatibility alias
    alias_agent = HermesAgent(contractor_phone="+18687771234")
    assert isinstance(alias_agent, TenderAgent)

@pytest.mark.asyncio
async def test_webhook_unsupported_media_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "18687771234",
                            "type": "audio",
                            "audio": {"id": "audio_123"}
                        }]
                    }
                }]
            }]
        }
        res = await ac.post("/webhook", json=payload)
        assert res.status_code == 200
        assert res.json() == {"status": "processed"}
