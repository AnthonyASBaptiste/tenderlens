import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ExtractedTask(BaseModel):
    task_id: str
    category: str # Statutory, Corporate, Financial_Bond, Technical, Logistics
    title: str
    description: str
    citation_page: str
    lead_time_days: int # Days needed to obtain/prepare
    status: str = "missing" # missing, in_progress, done, flagged_uncertain
    suggested_due_date: Optional[str] = None
    action_prompt: str # Question to prompt contractor on WhatsApp

class TenderBidPlan(BaseModel):
    tender_ref: str
    tender_title: str
    closing_deadline: str
    tasks: List[ExtractedTask]
    statutory_warning: str
    total_requirements_count: int

def analyze_compliance_requirements(pages: List[Dict[str, Any]], tender_ref: str, closing_date: str = "August 26, 2026") -> TenderBidPlan:
    """
    Scans tender pages for T&T public procurement mandatory requirements,
    extracting page citations and generating an actionable bid readiness checklist.
    """
    full_text = " ".join([p["text"] for p in pages])
    
    def find_citation(keywords: List[str]) -> str:
        for p in pages:
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", p["text"], re.IGNORECASE):
                    return f"Page {p['page_number']}"
        return "Page 1 (General Conditions)"

    tasks: List[ExtractedTask] = []
    
    # 1. Statutory Clearances
    # BIR Tax Clearance
    bir_cite = find_citation(["Board of Inland Revenue", "BIR Tax", "Tax Clearance", "BIR Clearance"])
    tasks.append(ExtractedTask(
        task_id="stat_bir_clearance",
        category="Statutory",
        title="Valid BIR Tax Clearance Certificate",
        description="Original or certified copy of valid Tax Clearance Certificate issued by the Board of Inland Revenue (IRD) in the company's name.",
        citation_page=bir_cite,
        lead_time_days=8,
        action_prompt="Do you have a current BIR Tax Clearance Certificate? (Takes 5-10 business days to obtain if expired)"
    ))
    
    # NIS Clearance
    nis_cite = find_citation(["National Insurance", "NIB", "NIS Compliance", "National Insurance Board"])
    tasks.append(ExtractedTask(
        task_id="stat_nis_clearance",
        category="Statutory",
        title="Valid NIS Compliance Certificate",
        description="Original or certified copy of valid Certificate of Compliance issued by the National Insurance Board of Trinidad and Tobago (NIBTT).",
        citation_page=nis_cite,
        lead_time_days=5,
        action_prompt="Do you have a valid NIS Compliance Certificate from NIBTT?"
    ))
    
    # VAT Clearance
    vat_cite = find_citation(["Value Added Tax", "VAT Clearance", "VAT Certificate"])
    tasks.append(ExtractedTask(
        task_id="stat_vat_clearance",
        category="Statutory",
        title="Valid VAT Clearance Certificate",
        description="Valid VAT Clearance Certificate from the Inland Revenue Division (or letter of exemption if annual turnover is below TT$500k threshold).",
        citation_page=vat_cite,
        lead_time_days=8,
        action_prompt="Do you have your valid VAT Clearance Certificate (or VAT exemption letter)?"
    ))

    # 2. Corporate Governance
    incorp_cite = find_citation(["Certificate of Incorporation", "Notice of Directors", "Form 4", "Form 28", "Companies Act"])
    tasks.append(ExtractedTask(
        task_id="corp_registration",
        category="Corporate",
        title="Certificate of Incorporation & Notice of Directors",
        description="Certified copies of Certificate of Incorporation/Continuance and most recent Notice of Directors (Form 4/Form 28) or Annual Return.",
        citation_page=incorp_cite,
        lead_time_days=2,
        action_prompt="Do you have certified copies of your Certificate of Incorporation and current Notice of Directors?"
    ))

    # OSH Policy
    osh_cite = find_citation(["Occupational Safety", "OSH", "HSE", "Health and Safety", "Safety Policy"])
    tasks.append(ExtractedTask(
        task_id="corp_osh_policy",
        category="Corporate",
        title="Company HSE / OSH Policy Statement",
        description="Signed company Occupational Safety and Health (OSH) Policy statement and drug/alcohol policy.",
        citation_page=osh_cite,
        lead_time_days=2,
        action_prompt="Do you have a signed company HSE / OSH policy statement ready?"
    ))

    # 3. Financial & Bonding
    bond_cite = find_citation(["Tender Bond", "Bid Security", "Bid-Securing", "Bank Guarantee", "Performance Bond"])
    tasks.append(ExtractedTask(
        task_id="fin_tender_bond",
        category="Financial_Bond",
        title="Bid Security / Tender Bond (or Declaration)",
        description="Tender Bond from an authorized commercial bank or insurance company, or signed Bid-Securing Declaration as stipulated.",
        citation_page=bond_cite,
        lead_time_days=5,
        action_prompt="Have you contacted your bank or insurance broker to issue the required Tender Bond?"
    ))

    fin_cite = find_citation(["Audited Financial Statements", "Financial Statements", "Audited Accounts", "Balance Sheet"])
    tasks.append(ExtractedTask(
        task_id="fin_audited_statements",
        category="Financial_Bond",
        title="Audited Financial Statements (Last 3 Years)",
        description="Audited financial statements or signed accountant's reports for the last three (3) consecutive financial years.",
        citation_page=fin_cite,
        lead_time_days=4,
        action_prompt="Are your audited financial statements for the past 3 years signed and ready?"
    ))

    # 4. Technical & Experience
    exp_cite = find_citation(["Past Performance", "Experience", "References", "Similar Contracts", "Work Experience"])
    tasks.append(ExtractedTask(
        task_id="tech_past_experience",
        category="Technical",
        title="Past Project Experience & Client References (3+)",
        description="Details of at least three (3) successfully executed contracts of similar scope and value within the last 5 years with client contact details.",
        citation_page=exp_cite,
        lead_time_days=3,
        action_prompt="Do you have 3 client reference letters / completion certificates for similar works?"
    ))

    cv_cite = find_citation(["Curriculum Vitae", "Key Personnel", "Personnel", "CVs", "Qualifications"])
    tasks.append(ExtractedTask(
        task_id="tech_key_personnel",
        category="Technical",
        title="Key Personnel Resumes & Certifications",
        description="CVs, professional certificates, and evidence of experience for proposed Project Lead, Supervisors, and Safety Officers.",
        citation_page=cv_cite,
        lead_time_days=2,
        action_prompt="Have you compiled the CVs and certifications for your proposed team?"
    ))

    # 5. Logistics & Submission
    site_cite = find_citation(["Site Visit", "Pre-Bid", "Site Inspection", "Certificate of Site Visit"])
    tasks.append(ExtractedTask(
        task_id="log_site_visit",
        category="Logistics",
        title="Site Visit Attendance & Certificate",
        description="Attendance at the mandatory Pre-Bid Meeting & Site Visit, and obtaining the signed Site Visit Attendance Certificate.",
        citation_page=site_cite,
        lead_time_days=1,
        action_prompt="Have you registered your representatives for the mandatory Site Visit?"
    ))

    warning = "CRITICAL PATH ALERT: In Trinidad & Tobago, BIR and VAT Tax Clearance certificates typically take 5-10 business days from the Inland Revenue Division. Start these immediately."

    return TenderBidPlan(
        tender_ref=tender_ref,
        tender_title=pages[0]["text"][:100] if pages else "Tender RFP",
        closing_deadline=closing_date,
        tasks=tasks,
        statutory_warning=warning,
        total_requirements_count=len(tasks)
    )
