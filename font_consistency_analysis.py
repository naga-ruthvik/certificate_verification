# import fitz
# import os

# def extract_text_with_fonts_from_pdf(pdf_path):
#     """
#     extracts text with fonts
#     """
#     text=""
#     try:
#         # Open the PDF file
#         doc = fitz.open(pdf_path)
#         print("doc:")
#         for page_num in range(len(doc)):
#             page = doc.load_page(page_num)
#             print(page.get_text("dict"))