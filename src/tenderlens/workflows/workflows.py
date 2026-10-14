import datetime
from datetime import timedelta
from typing import Optional, Dict, Any, List
from temporalio import workflow
from pydantic import BaseModel

# Import activities using string names for workflow isolation
with workflow.unsafe.imports_passed_through():
    from src.tenderlens.workflows.activities import (
        SendWhatsAppInput,
        send_whatsapp_message_activity,
        evaluate_bid_health_activity,
        BidHealthResult
    )

class WorkflowInitParams(BaseModel):
    tender_id: str
    contractor_id: str
    ref_no: str
    stage: str = "notice_only" # notice_only or full_rfp
    check_in_interval_seconds: int = 86400 # default 24h, lower during tests

class UpdateTaskSignal(BaseModel):
    task_id: str
    status: str
    notes: Optional[str] = None

@workflow.defn
class TenderFollowThroughWorkflow:
    """
    Durable workflow that maintains continuous follow-through with a contractor 
    from initial tender notice/ad through final bid submission.
    """
    def __init__(self) -> None:
        self.tender_id: str = ""
        self.contractor_id: str = ""
        self.ref_no: str = ""
        self.stage: str = "notice_only"
        self.is_active: bool = True
        self.check_in_count: int = 0
        self.last_message_sent: str = ""
        self.task_updates: List[Dict[str, Any]] = []
        self.interval_seconds: int = 86400

    @workflow.run
    async def run(self, params: WorkflowInitParams) -> str:
        self.tender_id = params.tender_id
        self.contractor_id = params.contractor_id
        self.ref_no = params.ref_no
        self.stage = params.stage
        self.interval_seconds = params.check_in_interval_seconds
        
        workflow.logger.info(f"Started TenderFollowThroughWorkflow for {self.ref_no} ({self.tender_id})")

        while self.is_active:
            # 1. Evaluate current bid readiness state
            health: BidHealthResult = await workflow.execute_activity(
                evaluate_bid_health_activity,
                self.tender_id,
                start_to_close_timeout=timedelta(seconds=20)
            )

            # 2. Check if all requirements are finished
            if health.total_tasks > 0 and health.completed_tasks == health.total_tasks:
                completion_msg = f"🎉 Great work! All compliance items for {self.ref_no} are completed. Ready for submission!"
                await workflow.execute_activity(
                    send_whatsapp_message_activity,
                    SendWhatsAppInput(contractor_id=self.contractor_id, tender_id=self.tender_id, message=completion_msg),
                    start_to_close_timeout=timedelta(seconds=20)
                )
                self.last_message_sent = completion_msg
                self.is_active = False
                break

            # 3. If in notice stage, check early milestone alerts
            if self.stage == "notice_only":
                prompt = (
                    f"TenderLens Check-in for {self.ref_no}:\n"
                    f"Have you submitted your email to request the tender package from WASA Oracle ERP?\n"
                    f"Remember: Site Visit registration requires 2 business days advance notice.\n"
                    f"Reply 'Sent email', 'Got package', or 'Need help'."
                )
            else:
                prompt = health.suggested_prompt

            # 4. Dispatch proactive check-in
            self.check_in_count += 1
            self.last_message_sent = prompt
            
            await workflow.execute_activity(
                send_whatsapp_message_activity,
                SendWhatsAppInput(contractor_id=self.contractor_id, tender_id=self.tender_id, message=prompt),
                start_to_close_timeout=timedelta(seconds=20)
            )

            # 5. Sleep until next check-in or wake up upon receiving a signal
            await workflow.wait_condition(
                lambda: not self.is_active,
                timeout=timedelta(seconds=self.interval_seconds)
            )

        return f"Workflow concluded for {self.ref_no} with {self.check_in_count} check-ins."

    @workflow.signal
    def signal_update_task(self, signal: UpdateTaskSignal) -> None:
        """Signal received when contractor updates task via WhatsApp message."""
        self.task_updates.append(signal.model_dump())
        workflow.logger.info(f"Received task update: {signal.task_id} -> {signal.status}")

    @workflow.signal
    def signal_full_package_received(self) -> None:
        """Signal received when contractor forwards the full tender PDF."""
        self.stage = "full_rfp"
        workflow.logger.info(f"Transitioned {self.ref_no} to full RFP stage.")

    @workflow.signal
    def signal_complete(self) -> None:
        """Signal to gracefully end workflow (e.g., bid submitted or cancelled)."""
        self.is_active = False

    @workflow.query
    def query_status(self) -> Dict[str, Any]:
        """Returns live workflow state."""
        return {
            "tender_id": self.tender_id,
            "ref_no": self.ref_no,
            "stage": self.stage,
            "is_active": self.is_active,
            "check_in_count": self.check_in_count,
            "last_message_sent": self.last_message_sent,
            "recorded_updates_count": len(self.task_updates)
        }
