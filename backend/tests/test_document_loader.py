import pytest
from pathlib import Path
from app.rag.document_loader import (
    parse_markdown_with_frontmatter,
    chunk_opportunity_document,
    load_all_opportunities
)
from app.config import settings

def test_parse_markdown_with_frontmatter():
    raw_dir = Path(settings.RAW_DATA_DIRECTORY)
    test_file = raw_dir / "safaricom-industrial-attachment.md"
    assert test_file.exists(), f"Expected test file {test_file} to exist."

    doc = parse_markdown_with_frontmatter(test_file)
    assert doc.id == "opp-safaricom-attachment-2026"
    assert "Safaricom" in doc.title
    assert doc.category == "Internship"
    assert doc.verification_status == "verified"
    assert doc.official_url.startswith("https://")
    assert "Eligibility Criteria" in doc.sections
    assert "Required Documents" in doc.sections

def test_chunk_opportunity_document():
    raw_dir = Path(settings.RAW_DATA_DIRECTORY)
    test_file = raw_dir / "hef-undergraduate-scholarship.md"
    doc = parse_markdown_with_frontmatter(test_file)
    chunks = chunk_opportunity_document(doc)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.opportunity_id == "opp-hef-undergraduate-2026"
        assert chunk.official_url == "https://www.hef.co.ke"
        assert chunk.metadata["provider"] == "Universities Fund & Higher Education Loans Board (HELB)"
        assert len(chunk.content) > 50
        assert "Official Link:" in chunk.content

def test_load_all_opportunities():
    raw_dir = Path(settings.RAW_DATA_DIRECTORY)
    all_chunks = load_all_opportunities(raw_dir)
    assert len(all_chunks) >= 10, "Should have loaded at least 10 chunks from curated opportunities."
    
    categories = {c.category for c in all_chunks}
    assert "Scholarship" in categories
    assert "Internship" in categories
