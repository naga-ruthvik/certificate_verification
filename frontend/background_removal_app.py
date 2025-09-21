import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os

# ✅ Import the real backend function
# Make sure verify_main.py has a function like:
# def main(file_path: str) -> dict
from verify_main import main as verify_certificate


# ---- Streamlit page configuration ----
st.set_page_config(
    page_title="EDUTRACK",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---- Custom CSS styling ----
st.markdown("""
<style>
/* Main app container */
.stApp {
    background-color: #f9f9f9;
    color: #333333;
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] button {
    font-weight: bold;
}

/* Buttons */
.stButton>button {
    font-size: 1.1em;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px 20px;
}
.clear-button {
    background-color: #444444 !important;
    color: white !important;
}
.submit-button {
    background-color: #ff6347 !important;
    color: white !important;
}

/* File uploader box */
div[data-testid="stFileUploaderDropzone"] {
    background-color: #e0e0e0;
    border: 2px dashed #999999;
    padding: 2rem;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---- Main title ----
st.title("EDUTRACK")
st.write("Upload your certificate for verification")

# ---- Tabs for input ----
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
        if uploaded_file is not None:
            # Save the uploaded file temporarily
            file_path = f"temp_{uploaded_file.name}"
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())

            # ✅ Call backend verification
            result = verify_certificate(file_path)
            st.subheader("Verification Result")
            st.json(result)

            # Show image preview if it's an image (skip PDF)
            try:
                if uploaded_file.type.startswith("image/"):
                    image = Image.open(file_path)
                    st.image(image, caption="Uploaded Certificate", use_column_width=True)
            except Exception as e:
                st.warning(f"Preview not available: {e}")

            # Clean up temp file
            os.remove(file_path)

        elif url_input:
            try:
                # Download the file from the URL
                response = requests.get(url_input)
                if response.status_code != 200:
                    st.error("Failed to fetch the file from URL.")
                else:
                    # Save temporarily
                    file_path = "temp_url_file"
                    with open(file_path, "wb") as f:
                        f.write(response.content)

                    # ✅ Call backend verification
                    result = verify_certificate(file_path)
                    st.subheader("Verification Result")
                    st.json(result)

                    # Preview if it's an image
                    try:
                        image = Image.open(BytesIO(response.content))
                        st.image(image, caption="Certificate from URL", use_column_width=True)
                    except:
                        pass

                    os.remove(file_path)

            except Exception as e:
                st.error(f"Error fetching or processing file: {e}")
        else:
            st.warning("Please upload a file or enter a URL.")

# ---- Optional Examples Section ----
st.markdown("### Examples")
# Show example images if available
example_images = []
for fname in ["examples/cert1.jpg", "examples/cert2.jpg"]:
    if os.path.exists(fname):
        example_images.append(fname)
if example_images:
    st.image(example_images, width=150)
else:
    st.info("Add example certificates in an 'examples' folder to display here.")
