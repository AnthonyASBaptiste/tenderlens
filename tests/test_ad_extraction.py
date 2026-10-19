import pytest
from src.tenderlens.extractor.ad_parser import extract_from_image, parse_notice_text, TenderNoticeData
from src.tenderlens.extractor.email_drafter import draft_package_request_email, EmailDraftRequest

@pytest.mark.asyncio
async def test_extract_from_real_ad_image():
    image_path = "fixtures/sample_real_tender_ad.png"
    notice: TenderNoticeData = await extract_from_image(image_path)
    
    assert "WASA" in notice.authority or "Water and Sewerage" in notice.authority
    assert "W.T.C. - 40/2026" in notice.ref_no
    assert "Pest Control" in (notice.line_of_business or "") or "PEST" in notice.title
    assert "August 26, 2026" in (notice.closing_deadline or "")
    assert "August 4, 2026" in (notice.site_visit_date or "")
    assert notice.procurement_email == "procurement@agency.gov.tt"
    assert len(notice.immediate_actions) >= 3

def test_draft_package_request_email():
    req = EmailDraftRequest(
        tender_ref="W.T.C. - 40/2026",
        tender_title="TENDER FOR PEST CONTROL SERVICES",
        procuring_entity="Water and Sewerage Authority (WASA)",
        procurement_email="procurement@agency.gov.tt",
        contractor_company="Trinidad Clean Pro Ltd",
        contractor_name="Anthony Baptiste",
        contractor_phone="+18687771234",
        contractor_email="anthony@cleanpro.tt",
        representative_names=["Anthony Baptiste", "Kevin Charles"]
    )
    draft = draft_package_request_email(req)
    
    assert draft["to"] == "procurement@agency.gov.tt"
    assert "W.T.C. - 40/2026" in draft["subject"]
    assert "Trinidad Clean Pro Ltd" in draft["body"]
    assert "Kevin Charles" in draft["body"]
    assert "Oracle ERP" in draft["body"]
