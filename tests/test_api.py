import pytest
from httpx import AsyncClient, ASGITransport
from src.tenderlens.gateway.app import app
from src.tenderlens.db.database import init_db

@pytest.mark.asyncio
async def test_health_and_webhook():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test /health
        res = await ac.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "TenderLens" in data["app"]
        
        # Test /webhook verification
        v_res = await ac.get("/webhook", params={
            "hub.mode": "subscribe",
            "hub.challenge": "123456",
            "hub.verify_token": "tenderlens_dev_token"
        })
        assert v_res.status_code == 200
        assert v_res.text == "123456"
        
        # Test /upload page
        u_res = await ac.get("/upload/tender_test_123")
        assert u_res.status_code == 200
        assert "Upload Tender Package" in u_res.text
