# file: app.py
import streamlit as st
import fitz
from fuzzywuzzy import fuzz
from datetime import datetime
import os
import requests

# -------------------- Simplified verification --------------------
def simple_verify_certificate(pdf_path, student_name):
    """
    Simple certificate verification:
    - Checks if student_name exists in the PDF text.
    - Checks PDF creation date (optional, ≤5 years).
    Returns a tuple: (is_verified: bool, reason: str)
    """
    try:
        doc = fitz.open(pdf_path)
        all_text = "".join([page.get_text() for page in doc])
        doc.close()

        # Metadata date check
        creation_date = doc.metadata.get('creationDate', None)
        metadata_ok = False
        metadata_reason = ""
        if creation_date and creation_date.startswith('D:'):
            try:
                creation_date_obj = datetime.strptime(creation_date[2:10], "%Y%m%d")
                if (datetime.now() - creation_date_obj).days <= 365*5:
                    metadata_ok = True
                else:
                    metadata_reason = "Certificate is older than 5 years"
            except:
                metadata_reason = "Invalid creation date format"
        else:
            metadata_reason = "No creation date found"

        # Name check using fuzzy match
        name_score = fuzz.token_set_ratio(student_name.lower(), all_text.lower())
        name_ok = name_score >= 85
        name_reason = "" if name_ok else "Student name does not match"

        # Final decision
        if name_ok and metadata_ok:
            return True, "Name and certificate date verified"
        else:
            reasons = []
            if not name_ok:
                reasons.append(name_reason)
            if not metadata_ok:
                reasons.append(metadata_reason)
            return False, "; ".join(reasons)

    except Exception as e:
        return False, f"Error verifying certificate: {e}"

# -------------------- Streamlit frontend --------------------
st.set_page_config(page_title="EDUTRACK", layout="centered")
st.title("EDUTRACK")
st.write("Upload your certificate for verification")

# Tabs for upload or URL
tab1, tab2 = st.tabs(["Upload File", "URL Input"])
uploaded_file = None
url_input = ""

with tab1:
    uploaded_file = st.file_uploader(
        "Drop PDF Here or Click to Upload",
        type=["pdf"],
        label_visibility="hidden"
    )

with tab2:
    url_input = st.text_input(
        "Enter PDF URL",
        placeholder="https://example.com/certificate.pdf",
        label_visibility="hidden"
    )

# Input student name
student_name = st.text_input("Enter student full name")

# Buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("Clear", use_container_width=True):
        st.session_state.clear()
        st.experimental_rerun()

with col2:
    if st.button("Verify", use_container_width=True):
        file_path = None
        try:
            if uploaded_file:
                file_path = f"temp_{uploaded_file.name}"
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())
            elif url_input:
                response = requests.get(url_input)
                if response.status_code != 200:
                    st.error("Failed to fetch PDF from URL.")
                else:
                    file_path = "temp_downloaded.pdf"
                    with open(file_path, "wb") as f:
                        f.write(response.content)
            else:
                st.warning("Please upload a PDF or enter a URL.")
                file_path = None

            if file_path and student_name.strip() != "":
                verified, reason = simple_verify_certificate(file_path, student_name)
                st.subheader("Verification Result")
                st.write("✅ Verified" if verified else "❌ Not Verified")
                st.write(f"Reason: {reason}")

        except Exception as e:
            st.error(f"Error processing file: {e}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
