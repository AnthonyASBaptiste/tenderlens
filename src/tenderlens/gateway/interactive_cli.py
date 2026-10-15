import asyncio
import sys
import os
from src.tenderlens.db.database import init_db
from src.tenderlens.agent.hermes_runner import HermesAgent
from src.tenderlens.workflows.activities import evaluate_bid_health_activity

def print_banner():
    print("=" * 70)
    print("       TenderLens T&T 🇹🇹 - WhatsApp Contractor Terminal Simulator")
    print("  Open-Source AI Tender Readiness & Proactive Follow-Through")
    print("=" * 70)
    print("Commands:")
    print("  /ad [path]     - Send a tender ad / newspaper clipping photo")
    print("  /tender [path] - Send full tender RFP document (txt/pdf)")
    print("  /checkin       - Simulate a proactive Temporal follow-up reminder")
    print("  /status        - Ask 'Where am I with this tender?'")
    print("  /auto          - Run the automated 6-step demo script")
    print("  /exit          - Quit simulator")
    print("  or simply type any message to chat like you would on WhatsApp!")
    print("=" * 70)

async def run_simulation():
    await init_db()
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
    health = await evaluate_bid_health_activity(agent.active_tender_id)
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

async def run_interactive():
    await init_db()
    print_banner()
    agent = HermesAgent(contractor_phone="+18687771234")
    
    while True:
        try:
            user_input = input("\nYou (WhatsApp): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting TenderLens simulator. Goodbye!")
            break
            
        if not user_input:
            continue
            
        if user_input in ["/exit", "exit", "quit", ":q"]:
            print("Exiting TenderLens simulator. Goodbye!")
            break
            
        if user_input == "/auto":
            await run_simulation()
            continue
            
        if user_input.startswith("/ad"):
            parts = user_input.split(maxsplit=1)
            file_path = parts[1].strip() if len(parts) > 1 else "fixtures/sample_real_tender_ad.png"
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                continue
            print(f"📎 Sending photo of tender ad: {file_path}...")
            reply = await agent.chat("Here is a photo of a tender notice from the newspaper.", attached_file=file_path)
            print(f"\nTenderLens:\n{reply}")
            continue

        if user_input.startswith("/tender") or user_input.startswith("/doc"):
            parts = user_input.split(maxsplit=1)
            file_path = parts[1].strip() if len(parts) > 1 else "fixtures/sample_tt_full_tender.txt"
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                continue
            print(f"📎 Sending full tender RFP document: {file_path}...")
            reply = await agent.chat("Here is the full tender RFP document.", attached_file=file_path)
            print(f"\nTenderLens:\n{reply}")
            continue

        if user_input in ["/checkin", "checkin"]:
            health = await evaluate_bid_health_activity(agent.active_tender_id)
            print("\n[⏰ TEMPORAL WORKFLOW TIMER FIRED]")
            print(f"TenderLens (Proactive Check-In):\n{health.suggested_prompt}")
            continue

        if user_input in ["/status", "status"]:
            reply = await agent.chat("Where am I with this tender?")
            print(f"\nTenderLens:\n{reply}")
            continue

        # Regular WhatsApp message
        reply = await agent.chat(user_input)
        print(f"\nTenderLens:\n{reply}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ["--demo", "--auto"]:
        asyncio.run(run_simulation())
    else:
        asyncio.run(run_interactive())

if __name__ == "__main__":
    main()
