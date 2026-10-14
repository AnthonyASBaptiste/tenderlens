import asyncio
import sys
from src.tenderlens.db.database import init_db
from src.tenderlens.agent.hermes_runner import HermesAgent
from src.tenderlens.workflows.activities import evaluate_bid_health_activity

def print_banner():
    print("=" * 70)
    print("       TenderLens T&T 🇹🇹 - WhatsApp Contractor Agent Simulator")
    print("  Open-Source AI Tender Readiness & Proactive Follow-Through")
    print("=" * 70)

async def run_simulation():
    await init_db()
    print_banner()
    agent = HermesAgent(contractor_phone="+18687771234")
    
    print("\n[Step 1] Contractor snaps a photo of the Sunday newspaper WASA tender ad...")
    print("Contractor -> TenderLens: 'Saw this tender ad in the paper. Can you check what I need to do?' [ATTACHMENT: fixtures/sample_real_tender_ad.png]")
    reply1 = await agent.chat("Saw this tender ad in the paper. Can you check what I need to do?", attached_file="fixtures/sample_real_tender_ad.png")
    print("\nTenderLens -> Contractor:\n" + reply1)
    
    print("\n" + "-" * 70)
    print("[Step 2] Contractor asks TenderLens to draft the package request email...")
    print("Contractor -> TenderLens: 'Yes please, my company is Caribbean Pest Solutions Ltd and my name is Anthony Baptiste'")
    reply2 = await agent.chat("Yes please, my company is Caribbean Pest Solutions Ltd and my name is Anthony Baptiste")
    print("\nTenderLens -> Contractor:\n" + reply2)

    print("\n" + "-" * 70)
    print("[Step 3] Proactive Temporal Check-in (Simulated Scheduled Trigger)...")
    health = await evaluate_bid_health_activity("tender_wtc_40_2026")
    print("TEMPORAL TIMER FIRED: Proactive Follow-Through Check-In:")
    print("TenderLens -> Contractor: 'Quick check-in on W.T.C. - 40/2026: Did you send your request email to WASA, and have you received the full RFP package on Oracle ERP yet?'")

    print("\n" + "-" * 70)
    print("[Step 4] Contractor forwards the full RFP document...")
    print("Contractor -> TenderLens: 'Yes, got access and downloaded the full tender document. Here it is.' [ATTACHMENT: fixtures/sample_tt_full_tender.txt]")
    reply3 = await agent.chat("Got access and downloaded the full tender document. Here it is.", attached_file="fixtures/sample_tt_full_tender.txt")
    print("\nTenderLens -> Contractor:\n" + reply3)

    print("\n" + "-" * 70)
    print("[Step 5] Contractor reports progress on statutory clearances...")
    print("Contractor -> TenderLens: 'Our NIS Compliance Certificate is done and ready, but still waiting on BIR Tax Clearance'")
    reply4 = await agent.chat("Our NIS Compliance Certificate is done and ready, but still waiting on BIR Tax Clearance")
    print("\nTenderLens -> Contractor:\n" + reply4)

    print("\n" + "-" * 70)
    print("[Step 6] Contractor checks overall readiness status...")
    print("Contractor -> TenderLens: 'Where am I with this tender?'")
    reply5 = await agent.chat("Where am I with this tender?")
    print("\nTenderLens -> Contractor:\n" + reply5)
    
    print("\n" + "=" * 70)
    print("🎉 Simulation completed successfully!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_simulation())
