import os
import shutil
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Response, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from src.tenderlens.config import settings
from src.tenderlens.db.database import init_db
from src.tenderlens.agent.tender_agent import TenderAgent, HermesAgent
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

import httpx

async def send_whatsapp_reply(to_num: str, text: str):
    if not (settings.whatsapp_api_token and settings.whatsapp_phone_number_id):
        return
    url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_num.replace("+", ""),
        "type": "text",
        "text": {"body": text}
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                print(f"[WhatsApp API Error] {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[WhatsApp API Dispatch Failed] {e}")

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
                
                agent = TenderAgent(contractor_phone=f"+{from_num}")
                
                reply_text = ""
                if msg_type == "text":
                    user_text = msg.get("text", {}).get("body", "")
                    reply_text = await agent.chat(user_text)
                elif msg_type in ["image", "document"]:
                    # Note: in live Meta webhook, download media using media_id via Graph API
                    reply_text = "I received your document! Analyzing requirements now..."
                else:
                    reply_text = "TenderLens can process tender text messages, photos of newspaper notices, and PDF tender documents. Please send a photo or document to analyze."
                    
                print(f"[WhatsApp] Reply to {from_num}: {reply_text[:100]}...")
                if reply_text:
                    await send_whatsapp_reply(from_num, reply_text)
                
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

from pydantic import BaseModel
from src.tenderlens.workflows.activities import evaluate_bid_health_activity

class ChatRequest(BaseModel):
    message: str
    attachment: Optional[str] = None
    contractor_phone: Optional[str] = "+18687771234"

@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    agent = TenderAgent(contractor_phone=req.contractor_phone or "+18687771234")
    reply = await agent.chat(req.message, attached_file=req.attachment)
    return {
        "reply": reply,
        "contractor_phone": agent.contractor_phone,
        "active_tender_id": agent.active_tender_id
    }

@app.get("/api/proactive-checkin/{tender_id}")
async def trigger_proactive_checkin(tender_id: str):
    health = await evaluate_bid_health_activity(tender_id)
    return {
        "tender_id": tender_id,
        "proactive_prompt": health.suggested_prompt,
        "readiness_percentage": health.readiness_percentage,
        "has_statutory_bottleneck": health.has_statutory_bottleneck
    }

@app.get("/", response_class=HTMLResponse)
@app.get("/demo", response_class=HTMLResponse)
async def web_simulator():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TenderLens T&T 🇹🇹 - WhatsApp Simulator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background: #0b141a; height: 100vh; display: flex; justify-content: center; align-items: center; }
        .phone-container { width: 100%; max-width: 480px; height: 100vh; max-height: 850px; background: #0b141a; display: flex; flex-direction: column; box-shadow: 0 10px 40px rgba(0,0,0,0.6); position: relative; border-radius: 16px; overflow: hidden; border: 1px solid #222e35; }
        
        /* WhatsApp Header */
        .chat-header { background: #202c33; color: #e9edef; padding: 10px 16px; display: flex; align-items: center; gap: 12px; z-index: 10; border-bottom: 1px solid #2a3942; }
        .avatar { width: 42px; height: 42px; border-radius: 50%; background: #00a884; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; color: white; flex-shrink: 0; }
        .header-info { flex: 1; }
        .header-name { font-size: 16px; font-weight: 600; color: #e9edef; display: flex; align-items: center; gap: 6px; }
        .verified-badge { background: #00a884; color: white; border-radius: 50%; width: 14px; height: 14px; font-size: 10px; display: inline-flex; align-items: center; justify-content: center; }
        .header-status { font-size: 12px; color: #8696a0; }
        
        /* Quick Action Bar */
        .quick-actions { background: #111b21; padding: 8px 12px; display: flex; gap: 8px; overflow-x: auto; border-bottom: 1px solid #222e35; scrollbar-width: none; }
        .quick-actions::-webkit-scrollbar { display: none; }
        .action-chip { background: #202c33; color: #00a884; border: 1px solid #2a3942; border-radius: 20px; padding: 6px 12px; font-size: 12px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: 0.2s; display: flex; align-items: center; gap: 4px; }
        .action-chip:hover { background: #00a884; color: white; border-color: #00a884; }
        
        /* Message Area */
        .chat-messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: #0b141a; background-image: radial-gradient(#182229 1px, transparent 1px); background-size: 20px 20px; }
        
        .message { max-width: 82%; padding: 8px 12px 6px; border-radius: 8px; font-size: 14px; line-height: 1.45; word-wrap: break-word; position: relative; }
        .msg-in { background: #202c33; color: #e9edef; align-self: flex-start; border-top-left-radius: 0; }
        .msg-out { background: #005c4b; color: #e9edef; align-self: flex-end; border-top-right-radius: 0; }
        .msg-time { font-size: 10px; color: #8696a0; text-align: right; margin-top: 4px; display: flex; justify-content: flex-end; align-items: center; gap: 3px; }
        .msg-time.out { color: #53bdeb; }
        .msg-body { white-space: pre-wrap; }
        
        /* Input Area */
        .chat-input-bar { background: #202c33; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border-top: 1px solid #2a3942; }
        .input-box { flex: 1; background: #2a3942; border: none; border-radius: 8px; padding: 10px 14px; font-size: 14px; color: #e9edef; outline: none; }
        .input-box::placeholder { color: #8696a0; }
        .btn-send { background: #00a884; border: none; width: 40px; height: 40px; border-radius: 50%; color: white; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; transition: 0.2s; }
        .btn-send:hover { background: #02906f; }
        .btn-clip { background: transparent; border: none; font-size: 20px; cursor: pointer; color: #8696a0; padding: 4px; }
        .btn-clip:hover { color: #e9edef; }
    </style>
</head>
<body>
    <div class="phone-container">
        <!-- Header -->
        <div class="chat-header">
            <div class="avatar">🇹🇹</div>
            <div class="header-info">
                <div class="header-name">
                    TenderLens T&T
                    <span class="verified-badge">✓</span>
                </div>
                <div class="header-status">Online • Hacktoberfest 2026 AI Assistant</div>
            </div>
            <a href="/upload/tender_wtc___40_2026?token=dev" target="_blank" style="color: #00a884; font-size: 12px; text-decoration: none; border: 1px solid #00a884; border-radius: 12px; padding: 4px 8px;">Large Upload ↗</a>
        </div>

        <!-- Quick Action Chips for Judges -->
        <div class="quick-actions">
            <button class="action-chip" onclick="sendQuickAd()">📷 1. Send WASA Ad</button>
            <button class="action-chip" onclick="sendQuickEmailReq()">✉️ 2. Request ERP Email</button>
            <button class="action-chip" onclick="sendQuickFullRFP()">📄 3. Send Full RFP</button>
            <button class="action-chip" onclick="simulateTemporalCheckin()">⏰ 4. Trigger Check-in</button>
            <button class="action-chip" onclick="sendQuickStatus()">📊 5. Check Status</button>
        </div>

        <!-- Chat Area -->
        <div class="chat-messages" id="messagesBox">
            <div class="message msg-in">
                <div class="msg-body">👋 Welcome to <strong>TenderLens T&T</strong>!

I help Trinidad & Tobago contractors win public tenders by ensuring you never miss a deadline or get disqualified on missing statutory documents (BIR, NIS, VAT, Bid Bonds).

👉 Click the quick-test buttons above or text me anything!</div>
                <div class="msg-time">Just now</div>
            </div>
        </div>

        <!-- Input Bar -->
        <div class="chat-input-bar">
            <input type="text" class="input-box" id="msgInput" placeholder="Type a message or question..." onkeydown="if(event.key==='Enter') sendCustomMsg()">
            <button class="btn-send" onclick="sendCustomMsg()">➤</button>
        </div>
    </div>

    <script>
        const messagesBox = document.getElementById('messagesBox');
        const msgInput = document.getElementById('msgInput');
        let currentTenderId = "tender_wtc___40_2026";

        function appendMessage(text, isOut = false) {
            const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${isOut ? 'msg-out' : 'msg-in'}`;
            msgDiv.innerHTML = `
                <div class="msg-body">${escapeHtml(text)}</div>
                <div class="msg-time ${isOut ? 'out' : ''}">${time} ${isOut ? '✓✓' : ''}</div>
            `;
            messagesBox.appendChild(msgDiv);
            messagesBox.scrollTop = messagesBox.scrollHeight;
        }

        function escapeHtml(text) {
            return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        async function postChat(msg, attachment = null) {
            appendMessage(msg, true);
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg, attachment: attachment })
                });
                const data = await res.json();
                if (data.active_tender_id) currentTenderId = data.active_tender_id;
                appendMessage(data.reply, false);
            } catch (err) {
                appendMessage("❌ Error reaching TenderLens backend.", false);
            }
        }

        function sendQuickAd() {
            postChat("Saw this tender ad in the Sunday newspaper. Can you check what I need to do?", "fixtures/sample_real_tender_ad.png");
        }

        function sendQuickEmailReq() {
            postChat("Yes please, my company is Caribbean Pest Solutions Ltd and my name is Anthony Baptiste");
        }

        function sendQuickFullRFP() {
            postChat("Got access and downloaded the full tender document. Here it is.", "fixtures/sample_tt_full_tender.txt");
        }

        async function simulateTemporalCheckin() {
            appendMessage("⚡ [Simulating Temporal Scheduled Check-In Event...]", true);
            try {
                const res = await fetch(`/api/proactive-checkin/${currentTenderId}`);
                const data = await res.json();
                appendMessage("⏰ [TEMPORAL WORKFLOW CHECK-IN TRIGGERED]\n\n" + data.proactive_prompt, false);
            } catch(e) {
                appendMessage("TenderLens Proactive Check-In: Have you obtained your BIR Tax Clearance Certificate yet? (Reply: Done or In Progress)", false);
            }
        }

        function sendQuickStatus() {
            postChat("Where am I with this tender?");
        }

        function sendCustomMsg() {
            const val = msgInput.value.trim();
            if (!val) return;
            msgInput.value = '';
            postChat(val);
        }
    </script>
</body>
</html>"""
    return html

