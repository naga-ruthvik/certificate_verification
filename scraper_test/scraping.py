# file: extractor_llm_pipeline.py
import os
import re
import json
import time
import pathlib
import mimetypes
import tempfile
import urllib.parse
import requests
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from pprint import pprint
from tenacity import retry, stop_after_attempt, wait_exponential

# HTML rendering
from playwright.sync_api import sync_playwright

# PDF parsing
from pypdf import PdfReader  # fast text extraction for text-based PDFs
# For scanned PDFs, consider: pip install pytesseract pdf2image; then OCR fallback.

# Load API key from env
from dotenv import load_dotenv
load_dotenv()

# -------------------------------
# Config
# -------------------------------
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36"
}
DOWNLOAD_DIR = pathlib.Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# -------------------------------
# Data models
# -------------------------------
@dataclass
class ExtractedDocument:
    source_url: str
    content_type: str  # "html" or "pdf"
    text: str
    metadata: Dict[str, str]

@dataclass
class LLMExtractionSpec:
    # Customize fields expected from the LLM
    instruction: str
    schema: Dict[str, str]  # key -> description

# -------------------------------
# Utilities
# -------------------------------
def normalize_url(base_url: str, href: str) -> Optional[str]:
    if not href:
        return None
    return urllib.parse.urljoin(base_url, href)

def is_pdf_link(url: str) -> bool:
    if not url:
        return False
    # extension or explicit PDF content type later
    return ".pdf" in urllib.parse.urlparse(url).path.lower()

def save_binary(content: bytes, filename: str) -> pathlib.Path:
    path = DOWNLOAD_DIR / filename
    path.write_bytes(content)
    return path

# -------------------------------
# HTML rendering & extraction
# -------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def render_and_get_html(url: str, timeout_ms: int = 20000) -> Tuple[str, Dict[str, str]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=DEFAULT_HEADERS["User-Agent"],
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.goto(url, wait_until="networkidle")
        # Some sites need a tiny wait for late JS
        time.sleep(1.0)
        html = page.content()
        # Capture metadata
        meta = {
            "title": page.title(),
            "final_url": page.url,
        }
        context.close()
        browser.close()
        return html, meta

def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Remove script/style/nav/footer
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    # Prefer main if present
    main = soup.find("main")
    text = (main.get_text(separator="\n") if main else soup.get_text(separator="\n"))
    # Clean
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)

def find_pdf_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        candidate = normalize_url(base_url, a["href"])
        if candidate and is_pdf_link(candidate):
            links.append(candidate)
    # de-duplicate
    return sorted(list(set(links)))

# -------------------------------
# PDF download & text extraction
# -------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def fetch_url(url: str) -> requests.Response:
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp

def ensure_pdf(url: str) -> pathlib.Path:
    resp = fetch_url(url)
    ctype = resp.headers.get("Content-Type", "")
    filename = pathlib.Path(urllib.parse.urlparse(url).path).name or f"file_{int(time.time())}.pdf"
    if not filename.lower().endswith(".pdf"):
        # Try to infer
        ext = mimetypes.guess_extension(ctype.split(";")[0].strip()) or ".pdf"
        filename = filename + ext
    return save_binary(resp.content, filename)

def pdf_to_text(pdf_path: pathlib.Path) -> str:
    text_parts = []
    try:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
    except Exception as e:
        text_parts.append(f"[PDF parse error: {e}]")
    text = "\n".join(text_parts).strip()
    # If empty (scanned PDFs), consider OCR fallback (pytesseract + pdf2image)
    return text or "[Empty or scanned PDF without text layer]"

# -------------------------------
# Orchestrator: extract from URL (HTML + PDFs)
# -------------------------------
def extract_from_website(url: str, include_pdfs: bool = True, max_pdfs: int = 5) -> List[ExtractedDocument]:
    docs: List[ExtractedDocument] = []
    # Try rendering dynamic page
    try:
        html, meta = render_and_get_html(url)
        text = html_to_text(html)
        docs.append(ExtractedDocument(
            source_url=meta.get("final_url", url),
            content_type="html",
            text=text,
            metadata=meta
        ))
        if include_pdfs:
            pdf_links = find_pdf_links(html, meta.get("final_url", url))
            for i, pdf_url in enumerate(pdf_links[:max_pdfs]):
                pdf_path = ensure_pdf(pdf_url)
                pdf_text = pdf_to_text(pdf_path)
                docs.append(ExtractedDocument(
                    source_url=pdf_url,
                    content_type="pdf",
                    text=pdf_text,
                    metadata={"filename": str(pdf_path.name)}
                ))
    except Exception as e:
        # Fallback: static GET and parse
        resp = fetch_url(url)
        ctype = resp.headers.get("Content-Type", "")
        if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
            pdf_name = pathlib.Path(urllib.parse.urlparse(url).path).name or "download.pdf"
            path = save_binary(resp.content, pdf_name)
            pdf_text = pdf_to_text(path)
            docs.append(ExtractedDocument(
                source_url=url,
                content_type="pdf",
                text=pdf_text,
                metadata={"filename": str(path.name)}
            ))
        else:
            soup = BeautifulSoup(resp.text, "html.parser")
            text = html_to_text(str(soup))
            docs.append(ExtractedDocument(
                source_url=url,
                content_type="html",
                text=text,
                metadata={"final_url": url, "title": soup.title.string if soup.title else ""}
            ))
    return docs

# -------------------------------
# Send to LLM for structured parsing
# -------------------------------
from typing import List,Any
# KEEP THIS CORRECT VERSION
@dataclass
class ExtractedDocument:
    source_url: str
    content_type: str  # "html" or "pdf"
    text: str
    metadata: Dict[str, str]

@dataclass
class LLMExtractionSpec:
    # Customize fields expected from the LLM
    instruction: str
    schema: Dict[str, str]  # key -> description

def build_prompt(
    docs: List[Any],      # Now correctly handles a list of objects like ExtractedDocument
    spec: Any,            # Handles the LLMExtractionSpec object
    pdf_data: str         # JSON string of reference data for verification
) -> str:
    """
    Build a unified prompt for extraction and per-field verification from multiple 
    sources, including source URLs in the output.
    
    Args:
        docs: List of ExtractedDocument objects.
        spec: An LLMExtractionSpec object containing the schema.
        pdf_data: A JSON string containing reference data for verification.
    
    Returns:
        str: A full prompt for the LLM.
    """
    # Concatenate document content with source information and separators
    blocks = []
    source_urls = []
    for d in docs:
        # Using dot notation to access object attributes
        content_preview = d.text[:20000]
        blocks.append(f"=== SOURCE: {d.source_url} ({d.content_type}) ===\n{content_preview}\n\n")
        source_urls.append(d.source_url)
    
    # [FIX 1] Access the .schema attribute of the spec object before calling .items()
    schema_desc = "\n".join([f"- {k}: {v}" for k, v in spec.schema.items()])

    # Dynamically build the JSON structure for the 'extracted_data' field
    field_verification_examples = []
    for key in spec.schema.keys():
        field_example = f"""            "{key}": {{
                "value": "<extracted value for {key} or null>",
                "is_verified": <boolean>,
                "reasoning": "<Explain why this specific field matches or mismatches the reference data.>"
            }}"""
        field_verification_examples.append(field_example)
    
    extracted_data_format = ",\n".join(field_verification_examples)

    # Assemble the final prompt
    prompt = prompt = rf"""
You are a strict certificate verification system that detects certificate forgery. 
You will be given two pieces of text:
1. Data extracted from an uploaded certificate (PDF).
2. Data scraped from the official verification URL.

Your job:
- Parse both texts into structured fields: {{ "name", "course", "issuer", "date", "certificate_id" }} if present.
- Compare fields strictly.
- If a field is missing in either source, mark it as "null".
- Do not assume or hallucinate values.

Rules for verification:
- If certificate_id exists in both sources, it must match exactly.
- Issuer must match exactly (case-insensitive).
- Course title must match with at least 90% similarity.
- Name must match with at least 80% similarity (to allow for small variations like initials).
- Date must match exactly if present.
- If majority of critical fields (issuer + course + certificate_id + name) match, then "verified" = true. Otherwise false.

Output must be ONLY in the following JSON format:

{{
    "parsed_pdf_data": {{ ... }},
    "parsed_site_data": {{ ... }},
    "verified": true/false,
    "score": 0.0-1.0,
    "reason": "Short explanation of why it was verified or rejected"
}}

Example:
{{
    "parsed_pdf_data": {{
        "name": "Ruthvik Naga",
        "course": "Cloud Computing",
        "issuer": "NPTEL",
        "date": "July 2024",
        "certificate_id": "ABC123"
    }},
    "parsed_site_data": {{
        "name": "Ruthvik N.",
        "course": "Cloud Computing",
        "issuer": "NPTEL",
        "date": "July 2024",
        "certificate_id": "ABC123"
    }},
    "verified": true,
    "score": 0.9,
    "reason": "All fields match with minor name variation"
}}

Now compare the following:

PDF Extracted Text:
<<<{pdf_data}>>>

Scraped Website Text:
<<<{docs}>>>
"""


    return prompt


def call_llm_extract(prompt: str) -> Dict:
    """
    Example with OpenAI-compatible clients. Replace with preferred LLM provider.
    """
    """
    Sends a prompt to the Gemini API and gets a JSON response.
    """
    import google.generativeai as genai
    genai.configure(api_key="AIzaSyCQ8bdN_qjuGjAnm9ADHSm4kq9WWgXb_qo")

    model = genai.GenerativeModel(
        # Use a model that supports JSON mode, like Gemini 1.5 Flash.
        model_name="gemini-2.5-flash-lite",
        system_instruction="Return only valid JSON. No prose."
        )

    # 2. `temperature` and `response_format` are set in `generation_config`.
    generation_config = {
        "temperature": 0,
        "response_mime_type": "application/json",
        "temperature": 0.0,
        "top_p": 0.9,
        "top_k": 5,           
        "max_output_tokens": 500,
        "candidate_count": 1

    }

    # 3. The API call is `generate_content`.
    response = model.generate_content(
        prompt,
        generation_config=generation_config
    )

    # 4. The raw JSON string is in `response.text`.
    raw_json_text = response.text
    return json.loads(raw_json_text)

import json
from pprint import pprint

# if __name__ == "__main__":
#     # --- 1. Define Inputs ---
    
#     # The URL of a certificate or course page to verify.
#     # Using a Coursera certificate page as a good, complex example.
#     TEST_URL = "https://archive.nptel.ac.in/content/noc/NOC24/SEM2/Ecertificates/106/noc24-cs78/Course/NPTEL24CS78S43680188002689171.pdf"

#     # This is the reference text, as if it were extracted from a PDF the user uploaded.
#     # We will check if the TEST_URL contains matching information.
#     REFERENCE_PDF_TEXT = """
#     No. of credits recommended: 2 or 3
#     To verify the certificate
#     Roll No:
#     Jul-Sep 2024
#     (8 week course)
#     Programming, Data Structures and Algorithms using Python
#     NAGA RUTHVIK
#     17.71/25
#     39.38/75
#     57
#     2068
#     NPTEL24CS78S436801880
#     """

#     # Define the schema of what we want the LLM to find and verify.
#     EXTRACTION_SPEC = LLMExtractionSpec(
#         instruction="Extract certificate details and verify them against the reference text.",
#         schema={
#             "student_name": "The full name of the student who completed the course.",
#             "issuing_organization": "The name of the company that created the course (e.g., Google, IBM).",
#             "completion_date": "The month and year the course was completed.",
#             "score": "The final score or percentage achieved, if available."
#         }
#     )

#     # --- 2. Run the Extraction Pipeline ---
#     print(f"[*] Starting extraction from URL: {TEST_URL}")
    
#     # Fetches the website content (and any linked PDFs, though this example URL has none).
#     documents = extract_from_website(TEST_URL, include_pdfs=False) # Set to False for this test
    
#     if not documents:
#         print("[!] No documents were extracted. Exiting.")
#     else:
#         print(f"[*] Extracted {len(documents)} document(s) successfully.")
#         print(f"documents: {documents}")
        
#         # --- 3. Build the Prompt ---
#         print("[*] Building prompt for the LLM...")
#         prompt = build_prompt(
#             docs=documents,
#             spec=EXTRACTION_SPEC,
#             pdf_data=REFERENCE_PDF_TEXT
#         )

#         # Optional: Uncomment the line below to see the full prompt sent to the LLM.
#         # print(prompt)

#         # --- 4. Call the LLM and Print Results ---
#         print("[*] Calling Gemini API for structured extraction and verification...")
#         try:
#             structured_data = call_llm_extract(prompt)
#             print("\n✅ LLM Extraction Complete. Result:")
#             pprint(structured_data)
#         except Exception as e:
#             print(f"\n❌ An error occurred while calling the LLM: {e}")
