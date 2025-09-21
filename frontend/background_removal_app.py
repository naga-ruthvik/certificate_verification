import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os

# Optional: for PDF preview
try:
    from pdf2image import convert_from_path
    pdf_preview_enabled = True
except ImportError:
    pdf_preview_enabled = False

# Backend verification
from verify_main import main as verify_certificate

# ---- Streamlit config ----
st.set_page_config(
    page_title="EDUTRACK",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---- CSS ----
st.markdown("""
<style>
.stApp { background-color: #f9f9f9; color: #333333; }
.stTabs [data-baseweb="tab-list"] button { font-weight: bold; }
.stButton>button { font-size: 1.1em; font-weight: bold; border-radius: 8px; padding: 10px 20px; }
.clear-button { background-color: #444444 !important; color: white !important; }
.submit-button { background-color: #ff6347 !important; color: white !important; }
div[data-testid="stFileUploaderDropzone"] { background-color: #e0e0e0; border: 2px dashed #999999; padding: 2rem; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ---- Title ----
st.title("EDUTRACK")
st.write("Upload your certificate for verification")

# ---- Tabs ----
tab1, tab2 = st.tabs(["Upload File", "URL Input"])
uploaded_file = None
url_input = ""

with tab1:
    uploaded_file = st.file_uploader(
        "Drop Image/PDF Here or Click to Upload",
        type=["png", "jpg", "jpeg", "pdf"],
        label_visibility="hidden"
    )

with tab2:
    url_input = st.text_input(
        "Enter Image/PDF URL",
        placeholder="https://example.com/certificate.pdf",
        label_visibility="hidden"
    )

# ---- Buttons ----
col1, col2 = st.columns(2)
with col1:
    if st.button("Clear", use_container_width=True):
        st.session_state.clear()
        st.experimental_rerun()

with col2:
    if st.button("Submit", use_container_width=True):
        file_path = None
        try:
            if uploaded_file:
                file_path = f"temp_{uploaded_file.name}"
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())
            elif url_input:
                response = requests.get(url_input)
                if response.status_code != 200:
                    st.error("Failed to fetch file from URL.")
                else:
                    ext = url_input.split(".")[-1]
                    file_path = f"temp_url_file.{ext}"
                    with open(file_path, "wb") as f:
                        f.write(response.content)

            if file_path:
                # Backend verification
                result = verify_certificate(file_path)
                st.subheader("Verification Result")
                st.json(result)

                # Preview
                if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
                    image = Image.open(file_path)
                    st.image(image, caption="Certificate Preview", use_column_width=True)
                elif file_path.lower().endswith(".pdf"):
                    st.markdown(f"**PDF Uploaded: {os.path.basename(file_path)}**")
                    with open(file_path, "rb") as f:
                        st.download_button(
                            label="Download / View PDF",
                            data=f,
                            file_name=os.path.basename(file_path),
                            mime="application/pdf"
                        )
                    if pdf_preview_enabled:
                        try:
                            pages = convert_from_path(file_path, first_page=1, last_page=1)
                            st.image(pages[0], caption="First Page Preview", use_column_width=True)
                        except:
                            st.warning("PDF preview not available.")
        except Exception as e:
            st.error(f"Error processing file: {e}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        if not uploaded_file and not url_input:
            st.warning("Please upload a file or enter a URL.")

# ---- Examples Section ----
st.markdown("### Example Certificates")

project_folder = os.path.dirname(__file__)
example_files = [
    os.path.join(project_folder, f)
    for f in os.listdir(project_folder)
    if f.lower().endswith(".pdf") and f.startswith("certificate")
]

if example_files:
    for file in example_files:
        st.markdown(f"**{os.path.basename(file)}**")
        with open(file, "rb") as f:
            st.download_button(
                label="Download / View PDF",
                data=f,
                file_name=os.path.basename(file),
                mime="application/pdf"
            )
        if pdf_preview_enabled:
            try:
                pages = convert_from_path(file, first_page=1, last_page=1)
                st.image(pages[0], caption="First Page Preview", use_column_width=True)
            except:
                pass
else:
    st.info("No example certificates available. Make sure PDFs start with 'certificate' in the project folder.")
