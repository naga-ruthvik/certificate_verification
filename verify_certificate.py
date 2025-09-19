import fitz
import os
import cv2
import numpy as np
from fuzzywuzzy import fuzz
from datetime import datetime
import tempfile
import shutil
import pytesseract
from PIL import Image

# --- Configuration and Reference Data ---
# In a full app, these come from a DB or config
AUTHENTIC_LOGOS = {
    'university_of_example': 'path/to/your/authentic_logo.png'
}

# --- Verification Parameters ---
WEIGHTS = {
    'name_match': 0.4,
    'logo_match': 0.4,
    'metadata_check': 0.2
}

THRESHOLDS = {
    'name_score': 85,       # Lowered threshold for fuzzy matching
    'logo_score': 50,       # Matches count threshold
    'metadata_score': 100   # Binary pass/fail
}

def ocr_extract_text(image_path):
    """Fallback OCR extraction from images for scanned certificates."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text

def verify_certificate(pdf_path, student_name, authentic_logos):
    results = {
        'is_verified': False,
        'final_score': 0.0,
        'name_match_score': 0,
        'logo_match_score': 0,
        'metadata_check_score': 0,
        'analysis_log': []
    }
    extracted_image_paths = []

    # Create temp directory for extracted images
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            doc = fitz.open(pdf_path)
            # Extract text from all pages
            all_text = "".join([page.get_text() for page in doc])
            
            # If extracted text is too short, fallback to OCR on images
            if len(all_text.strip()) < 20:
                results['analysis_log'].append("Low text extracted from PDF, switching to OCR on images.")
            else:
                results['analysis_log'].append(f"Extracted {len(all_text)} characters from PDF text.")
            
            # Extract images
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                for img_index, img_info in enumerate(page.get_images(full=True)):
                    xref = img_info[0]
                    img_data = doc.extract_image(xref)
                    img_path = os.path.join(temp_dir, f'img_p{page_num}_i{img_index}.{img_data["ext"]}')
                    with open(img_path, "wb") as f:
                        f.write(img_data["image"])
                    extracted_image_paths.append(img_path)
            
            # OCR fallback if needed
            if len(all_text.strip()) < 20 and extracted_image_paths:
                ocr_text_concat = ""
                for img_path in extracted_image_paths:
                    ocr_text_concat += ocr_extract_text(img_path) + " "
                all_text = ocr_text_concat
                results['analysis_log'].append(f"Extracted {len(all_text)} characters from OCR on images.")
            
            # Step 1: Metadata check
            metadata_check = 0
            doc_info = doc.metadata
            if 'creationDate' in doc_info and doc_info['creationDate']:
                creation_date_str = doc_info['creationDate']
                if creation_date_str.startswith('D:'):
                    creation_date_str = creation_date_str[2:10]
                try:
                    creation_date = datetime.strptime(creation_date_str, '%Y%m%d')
                    if (datetime.now() - creation_date).days <= 365 * 5:
                        metadata_check = 100
                    else:
                        results['analysis_log'].append("Warning: Certificate is older than 5 years.")
                except ValueError:
                    results['analysis_log'].append("Error: Creation date format invalid.")
            else:
                results['analysis_log'].append("Warning: No creation date found in metadata.")
            results['metadata_check_score'] = metadata_check
            
            # Step 2: Name matching using fuzzy matching
            name_match_score = fuzz.token_set_ratio(student_name.lower().strip(), all_text.lower())
            results['name_match_score'] = name_match_score
            
            # Step 3: Logo verification using SIFT
            logo_match_score = 0
            if not extracted_image_paths:
                results['analysis_log'].append("Warning: No images found for logo verification.")
            else:
                sift = cv2.SIFT_create()
                for logo_name, ref_path in authentic_logos.items():
                    ref_logo = cv2.imread(ref_path, cv2.IMREAD_GRAYSCALE)
                    if ref_logo is None:
                        results['analysis_log'].append(f"Error: Reference logo {ref_path} not found.")
                        continue
                    kp_ref, des_ref = sift.detectAndCompute(ref_logo, None)
                    if des_ref is None:
                        results['analysis_log'].append(f"Warning: No descriptors found in logo {logo_name}.")
                        continue
                    bf = cv2.BFMatcher()
                    for img_path in extracted_image_paths:
                        extracted_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        if extracted_img is None:
                            continue
                        kp_ext, des_ext = sift.detectAndCompute(extracted_img, None)
                        if des_ext is None:
                            continue
                        matches = bf.knnMatch(des_ref, des_ext, k=2)
                        good_matches = [m for m, n in matches if m.distance < 0.75 * n.distance]
                        if len(good_matches) > logo_match_score:
                            logo_match_score = len(good_matches)
            results['logo_match_score'] = logo_match_score
            
            doc.close()
        
        except Exception as e:
            results['analysis_log'].append(f"Error during verification: {e}")
        
        # Calculate weighted final score
        final_score = (
            (results['name_match_score'] / 100) * WEIGHTS['name_match'] +
            (min(results['logo_match_score'], THRESHOLDS['logo_score']) / THRESHOLDS['logo_score']) * WEIGHTS['logo_match'] +
            (results['metadata_check_score'] / 100) * WEIGHTS['metadata_check']
        )
        results['final_score'] = final_score * 100
        
        # Final decision logic - metadata check requires full score to pass
        if (results['name_match_score'] >= THRESHOLDS['name_score'] and
            results['logo_match_score'] >= THRESHOLDS['logo_score'] and
            results['metadata_check_score'] == THRESHOLDS['metadata_score']):
            results['is_verified'] = True
        else:
            results['is_verified'] = False

    return results

# --- Example Usage ---
pdf_path = "certificate.pdf"
student_name = "BHARATH SAI YADA"
authentic_logos = {'university_logo': 'authentic_logo.png'}

verification_results = verify_certificate(pdf_path, student_name, authentic_logos)

print("\n--- Final Verification Report ---")
for key, value in verification_results.items():
    if key == 'analysis_log':
        print(f"{key.replace('_', ' ').title()}:")
        for log in value:
            print(f"  - {log}")
    else:
        print(f"{key.replace('_', ' ').title()}: {value}")
