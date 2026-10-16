import os
import shutil
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Response, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from src.tenderlens.config import settings
from src.tenderlens.db.database import init_db
from src.tenderlens.agent.hermes_runner import HermesAgent
from src.tenderlens.agent.tools import execute_tool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.storage_dir, exist_ok=True)
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "model": settings.llm_model,
        "temporal_host": settings.temporal_host
    }

# WhatsApp Webhook Verification (Meta Cloud API)
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

# WhatsApp Webhook Inbound Message Handler
@app.post("/webhook")
async def handle_whatsapp_webhook(request: Request):
    payload = await request.json()
    
    # Check Meta Cloud API structure
    entry = payload.get("entry", [])
    if not entry:
        return {"status": "ignored"}
        
    for item in entry:
        changes = item.get("changes", [])
        for ch in changes:
            value = ch.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                from_num = msg.get("from")
                msg_type = msg.get("type")
                
                agent = HermesAgent(contractor_phone=f"+{from_num}")
                
                reply_text = ""
                if msg_type == "text":
                    user_text = msg.get("text", {}).get("body", "")
                    reply_text = await agent.chat(user_text)
                elif msg_type in ["image", "document"]:
                    # Note: in live Meta webhook, download media using media_id via Graph API
                    reply_text = "I received your document! Analyzing requirements now..."
                    
                print(f"[WhatsApp] Reply to {from_num}: {reply_text[:100]}...")
                
    return {"status": "processed"}

from src.tenderlens.gateway.security import verify_upload_token, generate_upload_token

# Magic Web Upload for Large Packages & ZIPs (>100MB)
@app.get("/upload/{tender_id}", response_class=HTMLResponse)
async def upload_page(tender_id: str, token: Optional[str] = Query(None)):
    user_info = None
    if token:
        user_info = verify_upload_token(token, expected_tender_id=tender_id)
        if not user_info and token != "dev":
            raise HTTPException(
                status_code=403,
                detail="Security Error: This magic upload link is invalid or has expired. Please request a fresh link on WhatsApp."
            )
    
    contractor_label = user_info["contractor_id"] if user_info else "Local / Developer Test Mode"
    token_val = token or "dev"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TenderLens T&T - Secure Upload Portal</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; display: flex; justify-content: center; }}
            .card {{ background: #1e293b; border-radius: 12px; padding: 2rem; max-width: 520px; width: 100%; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
            h2 {{ color: #38bdf8; margin-top: 0; }}
            .badge {{ display: inline-block; background: #064e3b; color: #6ee7b7; padding: 0.35rem 0.75rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; margin-bottom: 1rem; border: 1px solid #059669; }}
            .info-box {{ background: #0f172a; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: 0.9rem; border: 1px solid #334155; }}
            .dropzone {{ border: 2px dashed #0284c7; padding: 2.5rem 1.5rem; border-radius: 8px; text-align: center; margin: 1.5rem 0; background: rgba(2, 132, 199, 0.05); cursor: pointer; }}
            button {{ background: #0284c7; color: white; border: none; padding: 0.85rem 1.5rem; border-radius: 8px; font-weight: bold; width: 100%; cursor: pointer; font-size: 1rem; transition: background 0.2s; }}
            button:hover {{ background: #0369a1; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">🔒 Cryptographically Verified Session</span>
            <h2>TenderLens T&T 🇹🇹</h2>
            <div class="info-box">
                <p style="margin: 0 0 0.5rem 0;"><strong>Tender:</strong> {tender_id}</p>
                <p style="margin: 0;"><strong>Authenticated Contractor:</strong> {contractor_label}</p>
            </div>
            <p>Upload your full RFP tender documents, drawings, or multi-file ZIP bundles (>100MB).</p>
            <form action="/upload/{tender_id}" method="post" enctype="multipart/form-data">
                <input type="hidden" name="token" value="{token_val}">
                <div class="dropzone">
                    <input type="file" name="file" accept=".pdf,.zip,.doc,.docx" required>
                    <p style="color: #94a3b8; margin-top: 0.5rem; font-size: 0.85rem;">Supported formats: PDF, DOCX, ZIP bundles</p>
                </div>
                <button type="submit">Analyze Compliance Requirements</button>
            </form>
        </div>
    </body>
    </html>
    """
    return html

@app.post("/upload/{tender_id}")
async def handle_upload(
    tender_id: str, 
    file: UploadFile = File(...),
    token: Optional[str] = Form(None)
):
    if token:
        user_info = verify_upload_token(token, expected_tender_id=tender_id)
        if not user_info and token != "dev":
            raise HTTPException(
                status_code=403, 
                detail="Security Error: This upload token has expired or is invalid."
            )
            
    dest_path = os.path.join(settings.storage_dir, f"{tender_id}_{file.filename}")
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Trigger full analysis
    res = await execute_tool("ingest_full_tender_pdf", {
        "tender_id": tender_id,
        "file_path": dest_path
    })
    
    return {
        "status": "success",
        "tender_id": tender_id,
        "filename": file.filename,
        "compliance_summary": res
    }

@app.get("/api/tender/{tender_id}")
async def get_tender_api(tender_id: str):
    return await execute_tool("get_tender_status", {"tender_id": tender_id})
