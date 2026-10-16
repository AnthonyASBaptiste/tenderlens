import pytest
import time
from httpx import AsyncClient, ASGITransport
from src.tenderlens.gateway.app import app
from src.tenderlens.gateway.security import generate_upload_token, verify_upload_token

def test_token_generation_and_verification():
    contractor = "+18687771234"
    tender = "tender_wtc___40_2026"
    
    token = generate_upload_token(contractor, tender, ttl_seconds=3600)
    assert token is not None
    assert "." in token
    
    # Verify valid token
    payload = verify_upload_token(token, expected_tender_id=tender)
    assert payload is not None
    assert payload["contractor_id"] == contractor
    assert payload["tender_id"] == tender

def test_token_expiration():
    contractor = "+18687771234"
    tender = "tender_wtc___40_2026"
    
    # Token that expired 10 seconds ago
    token = generate_upload_token(contractor, tender, ttl_seconds=-10)
    payload = verify_upload_token(token, expected_tender_id=tender)
    assert payload is None # Expired!

def test_token_tampering():
    contractor = "+18687771234"
    tender = "tender_wtc___40_2026"
    
    token = generate_upload_token(contractor, tender, ttl_seconds=3600)
    parts = token.split(".")
    # Tamper with the payload part
    tampered_token = f"eyJjb250cmFjdG9yX2lkIjoiKzE4Njg5OTk5OTk5In0.{parts[1]}"
    
    payload = verify_upload_token(tampered_token, expected_tender_id=tender)
    assert payload is None # Signature mismatch!

def test_cross_tender_isolation():
    contractor = "+18687771234"
    tender_a = "tender_wtc___40_2026"
    tender_b = "tender_udecott_99_2026"
    
    token_a = generate_upload_token(contractor, tender_a, ttl_seconds=3600)
    
    # Trying to use Tender A's token for Tender B must fail
    payload = verify_upload_token(token_a, expected_tender_id=tender_b)
    assert payload is None

@pytest.mark.asyncio
async def test_upload_route_with_valid_token():
    contractor = "+18687771234"
    tender = "tender_wtc___40_2026"
    token = generate_upload_token(contractor, tender, ttl_seconds=3600)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/upload/{tender}?token={token}")
        assert res.status_code == 200
        assert "Cryptographically Verified Session" in res.text
        assert contractor in res.text

@pytest.mark.asyncio
async def test_upload_route_with_invalid_token_rejects():
    tender = "tender_wtc___40_2026"
    fake_token = "invalid.token.structure"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/upload/{tender}?token={fake_token}")
        assert res.status_code == 403
        assert "invalid or has expired" in res.text
