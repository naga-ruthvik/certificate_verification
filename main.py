import fitz
import os

def extract_content_from_pdf(pdf_path, output_dir="extracted_content"):
    """
    Extracts all text and images from a PDF and saves them to a directory.

    Args:
        pdf_path (str): The file path to the PDF document.
        output_dir (str): The directory to save the extracted images.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    all_text = ""
    extracted_image_paths = []

    try:
        # Open the PDF file
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # --- Text Extraction ---
            all_text += page.get_text()

            # --- Image Extraction ---
            image_list = page.get_images(full=True)
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                image_filename = f"page_{page_num + 1}_image_{img_index + 1}.{image_ext}"
                image_path = os.path.join(output_dir, image_filename)
                
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                extracted_image_paths.append(image_path)
                print(f"[+] Saved image: {image_path}")
        
        doc.close()

    except FileNotFoundError:
        print(f"Error: The file at {pdf_path} was not found.")
        return None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

    return all_text, extracted_image_paths

# --- Example Usage ---

# Replace with the actual path to your PDF
pdf_document_path = "certificate.pdf"

# Call the extraction function
text_content, image_paths = extract_content_from_pdf(pdf_document_path)

if text_content:
    print("\n--- Extracted Text ---")
    print(text_content)

    print("\n--- Extracted Images Paths ---")
    for path in image_paths:
        print(path)