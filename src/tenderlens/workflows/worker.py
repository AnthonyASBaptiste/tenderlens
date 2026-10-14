import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from src.tenderlens.config import settings
from src.tenderlens.workflows.workflows import TenderFollowThroughWorkflow
from src.tenderlens.workflows.activities import (
    send_whatsapp_message_activity,
    evaluate_bid_health_activity
)

async def run_worker():
    print(f"Connecting to Temporal host at {settings.temporal_host}...")
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TenderFollowThroughWorkflow],
        activities=[send_whatsapp_message_activity, evaluate_bid_health_activity],
    )
    
    print(f"TenderLens Temporal Worker listening on task queue: {settings.temporal_task_queue}")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(run_worker())
