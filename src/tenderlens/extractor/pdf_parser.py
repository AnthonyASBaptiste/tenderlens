import os
from typing import List, Dict, Any
from pypdf import PdfReader

class ExtractedPage(Dict[str, Any]):
    page_number: int
    text: str

def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses a PDF tender document page by page, preserving page numbering for citations.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")
        
    reader = PdfReader(file_path)
    pages = []
    
    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        # Clean up excessive repeating linebreaks and whitespace
        clean_text = "\n".join([line.strip() for line in page_text.splitlines() if line.strip()])
        pages.append({
            "page_number": idx + 1,
            "text": clean_text
        })
        
    return pages

def load_text_or_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Utility that loads either a PDF or a text fixture with [PAGE X] delimiters.
    """
    if file_path.endswith(".pdf"):
        return parse_pdf(file_path)
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check for [PAGE X] markers
    import re
    page_splits = re.split(r"\[PAGE\s+(\d+)\]", content)
    if len(page_splits) > 1:
        pages = []
        for i in range(1, len(page_splits), 2):
            p_num = int(page_splits[i])
            p_text = page_splits[i+1].strip()
            pages.append({"page_number": p_num, "text": p_text})
        return pages
        
    return [{"page_number": 1, "text": content}]
