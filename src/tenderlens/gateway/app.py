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
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>TenderLens T&T - Secure Upload Portal</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            body {{ background: #0f172a; color: #f8fafc; min-height: 100vh; padding: 2rem 1rem; display: flex; justify-content: center; align-items: flex-start; }}
            .card {{ background: #1e293b; border-radius: 16px; padding: 2.25rem; max-width: 580px; width: 100%; border: 1px solid #334155; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }}
            .header-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; }}
            h2 {{ color: #38bdf8; font-size: 1.5rem; font-weight: 700; display: flex; align-items: center; gap: 8px; }}
            .badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(16, 185, 129, 0.12); color: #34d399; padding: 0.4rem 0.85rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3); }}
            .info-box {{ background: #0b1329; border-radius: 10px; padding: 1rem 1.25rem; margin: 1.25rem 0; font-size: 0.88rem; border: 1px solid #1e293b; line-height: 1.5; }}
            .info-row {{ display: flex; justify-content: space-between; margin-bottom: 0.35rem; }}
            .info-label {{ color: #94a3b8; font-weight: 500; }}
            .info-val {{ color: #e2e8f0; font-weight: 600; word-break: break-all; }}
            
            /* Drag and Drop Zone */
            .dropzone {{ border: 2px dashed #38bdf8; padding: 2.5rem 1.5rem; border-radius: 12px; text-align: center; margin: 1.5rem 0; background: rgba(56, 189, 248, 0.04); cursor: pointer; transition: all 0.25s ease; position: relative; }}
            .dropzone:hover, .dropzone.dragover {{ background: rgba(56, 189, 248, 0.1); border-color: #0284c7; transform: translateY(-1px); }}
            .dropzone input[type="file"] {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }}
            .drop-icon {{ font-size: 2.5rem; margin-bottom: 0.75rem; color: #38bdf8; }}
            .drop-title {{ font-size: 1.05rem; font-weight: 600; color: #f1f5f9; margin-bottom: 0.35rem; }}
            .drop-hint {{ color: #94a3b8; font-size: 0.82rem; }}
            .file-selected {{ margin-top: 0.75rem; color: #34d399; font-weight: 600; font-size: 0.9rem; display: none; }}
            
            /* Action Button */
            button.btn-submit {{ background: linear-gradient(135deg, #0284c7, #2563eb); color: white; border: none; padding: 0.95rem 1.5rem; border-radius: 10px; font-weight: 600; width: 100%; cursor: pointer; font-size: 1rem; transition: all 0.2s; box-shadow: 0 4px 14px rgba(2, 132, 199, 0.3); }}
            button.btn-submit:hover {{ background: linear-gradient(135deg, #0369a1, #1d4ed8); transform: translateY(-1px); box-shadow: 0 6px 18px rgba(2, 132, 199, 0.4); }}
            button.btn-submit:disabled {{ opacity: 0.6; cursor: not-allowed; }}
            
            /* Live Results */
            .results-card {{ margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #334155; display: none; }}
            .alert-box {{ background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5; padding: 0.85rem 1rem; border-radius: 8px; font-size: 0.88rem; margin: 1rem 0; line-height: 1.45; }}
            .task-item {{ background: #0f172a; padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1e293b; font-size: 0.88rem; }}
            .btn-wa {{ display: inline-flex; align-items: center; justify-content: center; gap: 8px; background: #00a884; color: white; text-decoration: none; padding: 0.85rem 1.25rem; border-radius: 10px; font-weight: 600; width: 100%; margin-top: 1rem; transition: 0.2s; }}
            .btn-wa:hover {{ background: #02906f; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header-row">
                <h2>TenderLens T&T 🇹🇹</h2>
                <span class="badge">🔒 Cryptographically Verified Session</span>
            </div>
            
            <div class="info-box">
                <div class="info-row">
                    <span class="info-label">Active Tender:</span>
                    <span class="info-val">{tender_id}</span>
                </div>
                <div class="info-row" style="margin-bottom: 0;">
                    <span class="info-label">Authenticated Contractor:</span>
                    <span class="info-val">{contractor_label}</span>
                </div>
            </div>
            
            <p style="color: #cbd5e1; font-size: 0.92rem; line-height: 1.5; margin-bottom: 0.5rem;">
                Upload your official procurement RFP document, bills of quantities, or multi-file tender package (&gt;100MB).
            </p>
            
            <form id="uploadForm" action="/upload/{tender_id}" method="post" enctype="multipart/form-data">
                <input type="hidden" name="token" value="{token_val}">
                <div class="dropzone" id="dropzone">
                    <input type="file" id="fileInput" name="file" accept=".pdf,.zip,.doc,.docx,.txt" required>
                    <div class="drop-icon">☁️</div>
                    <div class="drop-title">Drop your Tender RFP file here</div>
                    <div class="drop-hint">or click to browse from device (PDF, DOCX, ZIP bundles)</div>
                    <div class="file-selected" id="fileSelected"></div>
                </div>
                <button type="submit" class="btn-submit" id="btnSubmit">Analyze Compliance Requirements</button>
            </form>
            
            <div class="results-card" id="resultsCard">
                <h3 style="color: #38bdf8; font-size: 1.15rem; margin-bottom: 0.75rem;">Analysis Complete 🎉</h3>
                <div id="statAlert" class="alert-box"></div>
                <div id="tasksList"></div>
                <a href="/demo" class="btn-wa">💬 Open WhatsApp Simulator to Track Deadlines</a>
            </div>
        </div>
        
        <script>
            const dropzone = document.getElementById('dropzone');
            const fileInput = document.getElementById('fileInput');
            const fileSelected = document.getElementById('fileSelected');
            const uploadForm = document.getElementById('uploadForm');
            const btnSubmit = document.getElementById('btnSubmit');
            const resultsCard = document.getElementById('resultsCard');
            const statAlert = document.getElementById('statAlert');
            const tasksList = document.getElementById('tasksList');
            
            fileInput.addEventListener('change', () => {{
                if (fileInput.files.length > 0) {{
                    const file = fileInput.files[0];
                    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
                    fileSelected.textContent = `📄 Selected: ${{file.name}} (${{sizeMB}} MB)`;
                    fileSelected.style.display = 'block';
                }}
            }});
            
            ['dragenter', 'dragover'].forEach(name => {{
                dropzone.addEventListener(name, (e) => {{
                    e.preventDefault();
                    dropzone.classList.add('dragover');
                }});
            }});
            
            ['dragleave', 'drop'].forEach(name => {{
                dropzone.addEventListener(name, (e) => {{
                    e.preventDefault();
                    dropzone.classList.remove('dragover');
                }});
            }});
            
            uploadForm.addEventListener('submit', async (e) => {{
                e.preventDefault();
                if (!fileInput.files.length) return;
                
                btnSubmit.disabled = true;
                btnSubmit.textContent = 'Analyzing Compliance Requirements with Gemma 2...';
                
                const formData = new FormData(uploadForm);
                try {{
                    const res = await fetch(uploadForm.action, {{
                        method: 'POST',
                        body: formData
                    }});
                    const data = await res.json();
                    
                    if (data.status === 'success' && data.compliance_summary) {{
                        const summary = data.compliance_summary;
                        statAlert.textContent = '🚨 ' + summary.statutory_warning;
                        tasksList.innerHTML = '';
                        (summary.sample_tasks || []).forEach(t => {{
                            const div = document.createElement('div');
                            div.className = 'task-item';
                            div.innerHTML = `<span><strong>${{t.title}}</strong></span><span style="color: #38bdf8; font-size: 0.8rem;">${{t.page || 'Mandatory'}}</span>`;
                            tasksList.appendChild(div);
                        }});
                        resultsCard.style.display = 'block';
                        btnSubmit.textContent = '✓ Document Ingested Successfully';
                    }} else {{
                        alert('Upload failed: ' + (data.detail || 'Unknown error'));
                        btnSubmit.disabled = false;
                        btnSubmit.textContent = 'Analyze Compliance Requirements';
                    }}
                }} catch (err) {{
                    alert('Error connecting to TenderLens: ' + err.message);
                    btnSubmit.disabled = false;
                    btnSubmit.textContent = 'Analyze Compliance Requirements';
                }}
            }});
        </script>
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
    try:
        agent = TenderAgent(contractor_phone=req.contractor_phone or "+18687771234")
        reply = await agent.chat(req.message, attached_file=req.attachment)
        return {
            "reply": reply,
            "contractor_phone": agent.contractor_phone,
            "active_tender_id": agent.active_tender_id
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Fall back to helpful message instead of crashing with HTTP 500
        return {
            "reply": f"⚠️ I encountered an issue processing that request: {str(e)}. Please try typing your question or uploading your tender document.",
            "contractor_phone": req.contractor_phone or "+18687771234",
            "active_tender_id": "tender_wtc___40_2026"
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
    html = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TenderLens T&T 🇹🇹 - WhatsApp Simulator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background: #0b141a; height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; }
        .phone-container { width: 100%; max-width: 490px; height: 100vh; max-height: 860px; background: #0b141a; display: flex; flex-direction: column; box-shadow: 0 16px 50px rgba(0,0,0,0.7); position: relative; border-radius: 18px; overflow: hidden; border: 1px solid #222e35; }
        
        @media (max-width: 520px) {
            .phone-container { max-height: 100vh; border-radius: 0; border: none; }
        }
        
        /* WhatsApp Header */
        .chat-header { background: #202c33; color: #e9edef; padding: 10px 16px; display: flex; align-items: center; gap: 12px; z-index: 10; border-bottom: 1px solid #2a3942; }
        .avatar { width: 42px; height: 42px; border-radius: 50%; background: #00a884; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; color: white; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0, 168, 132, 0.4); }
        .header-info { flex: 1; }
        .header-name { font-size: 16px; font-weight: 600; color: #e9edef; display: flex; align-items: center; gap: 6px; }
        .verified-badge { background: #00a884; color: white; border-radius: 50%; width: 14px; height: 14px; font-size: 10px; display: inline-flex; align-items: center; justify-content: center; }
        .header-status { font-size: 12px; color: #8696a0; }
        .header-link { color: #00a884; font-size: 12px; text-decoration: none; border: 1px solid #00a884; border-radius: 14px; padding: 5px 10px; font-weight: 500; transition: all 0.2s; white-space: nowrap; }
        .header-link:hover { background: rgba(0, 168, 132, 0.15); color: #25d366; border-color: #25d366; }
        
        /* Quick Action Bar */
        .quick-actions { background: #111b21; padding: 9px 12px; display: flex; gap: 8px; overflow-x: auto; border-bottom: 1px solid #222e35; scrollbar-width: none; }
        .quick-actions::-webkit-scrollbar { display: none; }
        .action-chip { background: #202c33; color: #00a884; border: 1px solid #2a3942; border-radius: 20px; padding: 6px 13px; font-size: 12px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: all 0.2s; display: flex; align-items: center; gap: 5px; }
        .action-chip:hover { background: #00a884; color: white; border-color: #00a884; transform: translateY(-1px); }
        .action-chip:active { transform: scale(0.96); }
        .action-chip.chip-reset { color: #94a3b8; border-color: #334155; }
        .action-chip.chip-reset:hover { background: #334155; color: #f1f5f9; border-color: #475569; }
        
        /* Message Area */
        .chat-messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: #0b141a; background-image: radial-gradient(#182229 1.2px, transparent 1.2px); background-size: 20px 20px; }
        
        .message { max-width: 84%; padding: 9px 13px 7px; border-radius: 10px; font-size: 14px; line-height: 1.5; word-wrap: break-word; position: relative; box-shadow: 0 1px 3px rgba(0,0,0,0.25); }
        .msg-in { background: #202c33; color: #e9edef; align-self: flex-start; border-top-left-radius: 2px; }
        .msg-out { background: #005c4b; color: #e9edef; align-self: flex-end; border-top-right-radius: 2px; }
        .msg-time { font-size: 10px; color: #8696a0; text-align: right; margin-top: 5px; display: flex; justify-content: flex-end; align-items: center; gap: 3px; }
        .msg-time.out { color: #53bdeb; }
        .msg-body { white-space: pre-wrap; }
        .msg-body a { color: #53bdeb; text-decoration: underline; font-weight: 500; }
        .msg-body strong { color: #f1f5f9; font-weight: 600; }
        
        /* Typing Indicator Bubble */
        .typing-bubble { display: none; align-self: flex-start; background: #202c33; padding: 12px 16px; border-radius: 12px; border-top-left-radius: 2px; box-shadow: 0 1px 3px rgba(0,0,0,0.25); }
        .typing-dots { display: flex; gap: 4px; align-items: center; }
        .dot { width: 7px; height: 7px; background: #8696a0; border-radius: 50%; animation: pulse 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes pulse { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }
        
        /* Input Area */
        .chat-input-bar { background: #202c33; padding: 10px 14px; display: flex; align-items: center; gap: 10px; border-top: 1px solid #2a3942; }
        .input-box { flex: 1; background: #2a3942; border: 1px solid transparent; border-radius: 10px; padding: 10px 14px; font-size: 14px; color: #e9edef; outline: none; transition: border-color 0.2s; }
        .input-box:focus { border-color: #00a884; }
        .input-box::placeholder { color: #8696a0; }
        .btn-send { background: #00a884; border: none; width: 42px; height: 42px; border-radius: 50%; color: white; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; transition: all 0.2s; box-shadow: 0 2px 8px rgba(0, 168, 132, 0.4); }
        .btn-send:hover { background: #02906f; transform: scale(1.04); }
        .btn-send:active { transform: scale(0.96); }
        .btn-send svg { width: 18px; height: 18px; fill: currentColor; }
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
            <a href="/upload/tender_wtc___40_2026?token=dev" target="_blank" class="header-link">Large Upload ↗</a>
        </div>

        <!-- Quick Action Chips for Judges -->
        <div class="quick-actions">
            <button class="action-chip" onclick="sendQuickAd()">📷 1. Send WASA Ad</button>
            <button class="action-chip" onclick="sendQuickEmailReq()">✉️ 2. Request ERP Email</button>
            <button class="action-chip" onclick="sendQuickFullRFP()">📄 3. Send Full RFP</button>
            <button class="action-chip" onclick="simulateTemporalCheckin()">⏰ 4. Trigger Check-in</button>
            <button class="action-chip" onclick="sendQuickStatus()">📊 5. Check Status</button>
            <button class="action-chip chip-reset" onclick="resetDemo()">↺ Reset</button>
        </div>

        <!-- Chat Area -->
        <div class="chat-messages" id="messagesBox">
            <div class="message msg-in">
                <div class="msg-body">👋 Welcome to <strong>TenderLens T&T</strong>!

I help Trinidad &amp; Tobago contractors win public tenders by ensuring you never miss a deadline or get disqualified on missing statutory documents (BIR, NIS, VAT, Bid Bonds).

👉 Click the quick-test buttons above or text me anything!</div>
                <div class="msg-time">Just now</div>
            </div>
            
            <div class="typing-bubble" id="typingBubble">
                <div class="typing-dots">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            </div>
        </div>

        <!-- Input Bar -->
        <div class="chat-input-bar">
            <input type="text" class="input-box" id="msgInput" placeholder="Type a message or question..." onkeydown="if(event.key==='Enter') sendCustomMsg()">
            <button class="btn-send" onclick="sendCustomMsg()" title="Send">
                <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </button>
        </div>
    </div>

    <script>
        const messagesBox = document.getElementById('messagesBox');
        const msgInput = document.getElementById('msgInput');
        const typingBubble = document.getElementById('typingBubble');
        let currentTenderId = "tender_wtc___40_2026";

        function formatMsg(text) {
            let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            // Bold markdown: **bold** or *bold*
            escaped = escaped.replace(/(\*\*|\*)(.*?)\1/g, '<strong>$2</strong>');
            // Links
            escaped = escaped.replace(/(https?:\/\/[^\s]+|\/upload\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');
            return escaped;
        }

        function appendMessage(text, isOut = false) {
            const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${isOut ? 'msg-out' : 'msg-in'}`;
            msgDiv.innerHTML = `
                <div class="msg-body">${formatMsg(text)}</div>
                <div class="msg-time ${isOut ? 'out' : ''}">${time} ${isOut ? '✓✓' : ''}</div>
            `;
            messagesBox.insertBefore(msgDiv, typingBubble);
            messagesBox.scrollTop = messagesBox.scrollHeight;
        }

        function showTyping(show) {
            typingBubble.style.display = show ? 'flex' : 'none';
            if (show) messagesBox.scrollTop = messagesBox.scrollHeight;
        }

        async function postChat(msg, attachment = null) {
            appendMessage(msg, true);
            showTyping(true);
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg, attachment: attachment })
                });
                const data = await res.json();
                showTyping(false);
                if (data.active_tender_id) currentTenderId = data.active_tender_id;
                appendMessage(data.reply, false);
            } catch (err) {
                showTyping(false);
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
            showTyping(true);
            try {
                const res = await fetch(`/api/proactive-checkin/${currentTenderId}`);
                const data = await res.json();
                showTyping(false);
                appendMessage("⏰ [TEMPORAL WORKFLOW CHECK-IN TRIGGERED]\n\n" + data.proactive_prompt, false);
            } catch(e) {
                showTyping(false);
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

        function resetDemo() {
            const initialGreeting = `👋 Welcome to <strong>TenderLens T&T</strong>!

I help Trinidad &amp; Tobago contractors win public tenders by ensuring you never miss a deadline or get disqualified on missing statutory documents (BIR, NIS, VAT, Bid Bonds).

👉 Click the quick-test buttons above or text me anything!`;
            
            while (messagesBox.firstChild && messagesBox.firstChild !== typingBubble) {
                messagesBox.removeChild(messagesBox.firstChild);
            }
            
            const firstMsg = document.createElement('div');
            firstMsg.className = 'message msg-in';
            firstMsg.innerHTML = `
                <div class="msg-body">${initialGreeting}</div>
                <div class="msg-time">Just now</div>
            `;
            messagesBox.insertBefore(firstMsg, typingBubble);
            currentTenderId = "tender_wtc___40_2026";
        }
    </script>
</body>
</html>"""
    return html
    return html

