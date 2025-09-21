import os
import json
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional
from pprint import pprint

from scraper_test.scraping import (
    extract_from_website,
    build_prompt,
    call_llm_extract,
)
from main import extract_content_from_pdf


@dataclass
class LLMExtractionSpec:
    """
    Specification for the LLM to extract information.
    """
    instruction: str
    schema: Dict[str, str]


def verify_certificate(
    pdf_document_path: str,
    target_url: Optional[str] = None,
    max_pdfs: int = 3
) -> Dict:
    """
    Verify a certificate by extracting text/images from a PDF,
    scraping the related website, and calling the LLM extractor.

    Args:
        pdf_document_path: Local path to the certificate PDF.
        target_url: (Optional) Website URL for cross-verification.
        max_pdfs: Max number of PDFs to fetch from the website.

    Returns:
        dict: Extraction and verification result.
    """
    # ---- 1. Extract text & images from the uploaded PDF ----
    text_content, image_paths = extract_content_from_pdf(pdf_document_path)

    # ---- 2. Build the extraction schema ----
    spec = LLMExtractionSpec(
        instruction=(
            "You are a precise information extractor. "
            "Fill the schema fields using the provided documents. "
            "If a field is not present, use null."
        ),
        schema={
            "title": "Main title or document/course/article heading",
            "issuer": "Publishing or issuing organization (e.g., Meta, IEEE, Govt.)",
            "author_or_name": "Person or entity name if available",
            "date": "Completion or publication date in ISO if possible",
            "duration_or_pages": "Hours for courses or page count for PDFs",
            "description": "1-3 sentence summary",
            "skills_or_topics": "Array of key skills/topics mentioned",
            "source_urls": "Array of source URLs from which the data was extracted",
        },
    )

    # ---- 3. Optional: scrape website for comparison ----
    docs = []
    if target_url:
        try:
            docs = extract_from_website(target_url, include_pdfs=True, max_pdfs=max_pdfs)
        except Exception as e:
            return {"error": f"Website scraping failed: {e}"}

    # ---- 4. Build the LLM prompt ----
    try:
        prompt = build_prompt(docs, spec, text_content)
    except Exception as e:
        return {"error": f"Prompt building failed: {e}"}

    # ---- 5. Call the LLM for structured extraction ----
    try:
        extracted = call_llm_extract(prompt)
    except Exception as e:
        # Fallback if LLM fails
        fallback = {}
        if docs:
            meta = getattr(docs[0], "metadata", {})
            fallback = {
                "title": meta.get("title", ""),
                "source": getattr(docs[0], "source_url", ""),
            }
        extracted = {"error": str(e), "fallback": fallback}

    # ---- 6. Package final result ----
    result = {
        "parsed_pdf_data": text_content,   # or a structured summary if available
        "image_paths": image_paths,
        "website_docs_count": len(docs),
        "llm_extraction": extracted,
    }

    return result


# ✅ Wrapper for Streamlit frontend
def main(file_path: str) -> Dict:
    """
    Entry point for frontend.
    The Streamlit app calls this function with the uploaded file path.
    """
    return verify_certificate(file_path)


# Stand-alone test
if __name__ == "__main__":
    # Example usage (replace with your own file/URL)
    target_url = (
        "https://archive.nptel.ac.in/content/noc/NOC24/SEM2/Ecertificates/106/"
        "noc24-cs78/Course/NPTEL24CS78S43680188002689171.pdf"
    )
    pdf_path = "certificate_3.pdf"
    output = verify_certificate(pdf_path, target_url)
    pprint(output)
