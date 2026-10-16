import hmac
import hashlib
import time
import base64
import json
import os
from typing import Optional, Dict, Any

# In production on Render, set SECRET_KEY in environment variables
SECRET_KEY = os.getenv("MAGIC_LINK_SECRET", "tenderlens_default_secure_secret_key_2026")

def generate_upload_token(contractor_id: str, tender_id: str, ttl_seconds: int = 3600) -> str:
    """
    Creates a cryptographically signed HMAC-SHA256 token encoding the contractor identity,
    tender ID, and an expiration timestamp (default 1 hour).
    """
    payload = {
        "contractor_id": contractor_id,
        "tender_id": tender_id,
        "exp": int(time.time()) + ttl_seconds
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')
    
    sig = hmac.new(
        SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode('utf-8').rstrip('=')
    
    return f"{payload_b64}.{sig_b64}"

def verify_upload_token(token: str, expected_tender_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Verifies that the magic token:
    1. Has a valid cryptographic HMAC signature against SECRET_KEY.
    2. Has not expired.
    3. Matches the expected tender_id (prevents using a token for Tender A on Tender B).
    """
    if not token or "." not in token:
        return None
        
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
            
        payload_b64, sig_b64 = parts[0], parts[1]
        
        # Verify signature
        expected_sig = hmac.new(
            SECRET_KEY.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Pad base64 for decoding
        rem = len(sig_b64) % 4
        padded_sig = sig_b64 + ("=" * ((4 - rem) % 4))
        actual_sig = base64.urlsafe_b64decode(padded_sig.encode('utf-8'))
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None # Tampered signature!
            
        # Decode payload
        rem_p = len(payload_b64) % 4
        padded_payload = payload_b64 + ("=" * ((4 - rem_p) % 4))
        payload_data = json.loads(base64.urlsafe_b64decode(padded_payload.encode('utf-8')).decode('utf-8'))
        
        # Check expiry
        if time.time() > payload_data.get("exp", 0):
            return None # Expired token!
            
        # Check tender match
        if expected_tender_id and payload_data.get("tender_id") != expected_tender_id:
            return None # Wrong tender!
            
        return payload_data
    except Exception:
        return None
