import pytest
from src.tenderlens.extractor.pdf_parser import load_text_or_pdf
from src.tenderlens.extractor.compliance_analyzer import analyze_compliance_requirements, TenderBidPlan

def test_full_tender_compliance_extraction():
    fixture_path = "fixtures/sample_tt_full_tender.txt"
    pages = load_text_or_pdf(fixture_path)
    
    assert len(pages) == 5
    assert pages[0]["page_number"] == 1
    assert pages[4]["page_number"] == 5
    
    plan: TenderBidPlan = analyze_compliance_requirements(pages, "W.T.C. - 40/2026", "August 26, 2026")
    
    assert plan.tender_ref == "W.T.C. - 40/2026"
    assert plan.total_requirements_count >= 8
    
    task_map = {t.task_id: t for t in plan.tasks}
    
    # Check BIR citation
    bir_task = task_map.get("stat_bir_clearance")
    assert bir_task is not None
    assert "Page 3" in bir_task.citation_page
    assert bir_task.lead_time_days >= 5
    
    # Check NIS citation
    nis_task = task_map.get("stat_nis_clearance")
    assert nis_task is not None
    assert "Page 3" in nis_task.citation_page
    
    # Check Tender Bond citation
    bond_task = task_map.get("fin_tender_bond")
    assert bond_task is not None
    assert "Page 4" in bond_task.citation_page
    
    # Check Site Visit citation
    site_task = task_map.get("log_site_visit")
    assert site_task is not None
    assert "Page 2" in site_task.citation_page
