import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

class OpportunityChunk(BaseModel):
    chunk_id: str
    opportunity_id: str
    title: str
    provider: str
    category: str
    section_title: str
    content: str
    official_url: str
    application_deadline: str
    status: str
    verification_status: str
    metadata: Dict[str, Any]

class RawOpportunityDocument(BaseModel):
    id: str
    title: str
    provider: str
    category: str
    target_audience: str
    field_of_study: List[str]
    degree_level: List[str]
    application_deadline: str
    status: str
    official_url: str
    verification_status: str
    verified_date: str
    source_notes: Optional[str] = None
    raw_body: str
    sections: Dict[str, str] = Field(default_factory=dict)

def parse_markdown_with_frontmatter(file_path: Path) -> RawOpportunityDocument:
    """
    Parses a markdown document with YAML frontmatter.
    Extracts structured frontmatter and splits the markdown body into semantic sections.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not frontmatter_match:
        raise ValueError(f"Document {file_path.name} does not contain valid YAML frontmatter delimiters.")

    raw_yaml, raw_body = frontmatter_match.group(1), frontmatter_match.group(2)
    meta = yaml.safe_load(raw_yaml)

    fields_of_study = meta.get("field_of_study", [])
    if isinstance(fields_of_study, str):
        fields_of_study = [fields_of_study]

    degree_levels = meta.get("degree_level", [])
    if isinstance(degree_levels, str):
        degree_levels = [degree_levels]

    section_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(section_pattern.finditer(raw_body))
    
    sections: Dict[str, str] = {}
    if not matches:
        sections["General"] = raw_body.strip()
    else:
        for i, match in enumerate(matches):
            header = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_body)
            content = raw_body[start:end].strip()
            if content:
                sections[header] = content

    return RawOpportunityDocument(
        id=str(meta.get("id", file_path.stem)),
        title=str(meta.get("title", "Untitled")),
        provider=str(meta.get("provider", "Unknown Provider")),
        category=str(meta.get("category", "General")),
        target_audience=str(meta.get("target_audience", "University Students")),
        field_of_study=fields_of_study,
        degree_level=degree_levels,
        application_deadline=str(meta.get("application_deadline", "Unspecified")),
        status=str(meta.get("status", "uncertain")),
        official_url=str(meta.get("official_url", "")),
        verification_status=str(meta.get("verification_status", "unverified")),
        verified_date=str(meta.get("verified_date", "")),
        source_notes=meta.get("source_notes"),
        raw_body=raw_body,
        sections=sections
    )

def chunk_opportunity_document(doc: RawOpportunityDocument) -> List[OpportunityChunk]:
    """
    Transforms a parsed opportunity document into semantic, topic-based chunks.
    Each chunk inherits document metadata and explicit source attribution.
    """
    chunks: List[OpportunityChunk] = []

    for section_idx, (section_title, section_text) in enumerate(doc.sections.items()):
        enriched_content = (
            f"Opportunity: {doc.title} ({doc.provider})\n"
            f"Category: {doc.category} | Deadline: {doc.application_deadline}\n"
            f"Section: {section_title}\n"
            f"Official Link: {doc.official_url}\n\n"
            f"{section_text}"
        )

        chunk_id = f"{doc.id}_sec_{section_idx}_{re.sub(r'[^a-zA-Z0-9]', '_', section_title.lower())}"

        metadata = {
            "opportunity_id": doc.id,
            "title": doc.title,
            "provider": doc.provider,
            "category": doc.category,
            "section_title": section_title,
            "official_url": doc.official_url,
            "application_deadline": doc.application_deadline,
            "status": doc.status,
            "verification_status": doc.verification_status,
            "verified_date": doc.verified_date,
            "target_audience": doc.target_audience,
            "fields_of_study": ", ".join(doc.field_of_study),
            "degree_levels": ", ".join(doc.degree_level)
        }

        chunks.append(OpportunityChunk(
            chunk_id=chunk_id,
            opportunity_id=doc.id,
            title=doc.title,
            provider=doc.provider,
            category=doc.category,
            section_title=section_title,
            content=enriched_content,
            official_url=doc.official_url,
            application_deadline=doc.application_deadline,
            status=doc.status,
            verification_status=doc.verification_status,
            metadata=metadata
        ))

    return chunks

def load_all_opportunities(directory_path: Path) -> List[OpportunityChunk]:
    """Loads and chunks all markdown opportunity files in the given directory."""
    all_chunks: List[OpportunityChunk] = []
    if not directory_path.exists():
        return all_chunks

    for file_path in sorted(directory_path.glob("*.md")):
        doc = parse_markdown_with_frontmatter(file_path)
        chunks = chunk_opportunity_document(doc)
        all_chunks.extend(chunks)

    return all_chunks
