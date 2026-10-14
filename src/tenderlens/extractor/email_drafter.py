from typing import Optional, List
from pydantic import BaseModel

class EmailDraftRequest(BaseModel):
    tender_ref: str
    tender_title: str
    procuring_entity: str
    procurement_email: str
    contractor_company: str
    contractor_name: str
    contractor_phone: str
    contractor_email: str
    representative_names: Optional[List[str]] = None
    portal_name: Optional[str] = "Oracle ERP"

def draft_package_request_email(req: EmailDraftRequest) -> dict:
    """
    Generates a formal procurement tender document request email tailored to 
    Trinidad & Tobago procuring entities (e.g. WASA, UDeCOTT, NIPDEC).
    """
    reps_str = ", ".join(req.representative_names) if req.representative_names else f"{req.contractor_name} ({req.contractor_phone})"
    
    subject = f"REQUEST FOR TENDER DOCUMENTS: Ref. No. {req.tender_ref} - {req.tender_title[:60]}"
    
    body = f"""Dear Procurement Manager,

RE: REQUEST FOR TENDER DOCUMENTS & PARTICIPATION NOTICE
TENDER REF: {req.tender_ref}
TITLE: {req.tender_title}

I am writing on behalf of {req.contractor_company} to formally express our interest in submitting a proposal for the above-referenced tender.

In accordance with the published tender notice, we kindly request the issuance of the complete tender documents and instructions for submission via the {req.portal_name} portal.

Please find our official company details below for user registration and document access:
- Company Name: {req.contractor_company}
- Authorized Contact Person: {req.contractor_name}
- Email Address: {req.contractor_email}
- Telephone / WhatsApp: {req.contractor_phone}

NOTICE OF INTENTION TO ATTEND SITE VISIT / PRE-BID MEETING:
We also confirm our intention to participate in the scheduled Pre-Bid Meeting and Site Visit.
Nominated Representative(s):
- {reps_str}

Please confirm receipt of this request and provide the ERP / tender access link at your earliest convenience.

Sincerely,

{req.contractor_name}
{req.contractor_company}
Tel: {req.contractor_phone}
Email: {req.contractor_email}
"""
    return {
        "to": req.procurement_email,
        "subject": subject,
        "body": body.strip()
    }
