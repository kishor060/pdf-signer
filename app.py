import io
import zipfile
import streamlit as st
import pdfplumber
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image

st.set_page_config(page_title="PDF Batch Signer", layout="centered")
st.title("Batch PDF Auto-Signer")

search_text = st.text_input("Target Search Phrase:", value="Sanjiv Bansal")
uploaded_files = st.file_uploader("Upload PDF file(s):", type=["pdf"], accept_multiple_files=True)


def make_transparent_png(image_path: str) -> io.BytesIO:
    img = Image.open(image_path).convert("RGBA")
    data = img.getdata()
    new_data = [
        (255, 255, 255, 0) if (d[0] > 220 and d[1] > 220 and d[2] > 220) else d
        for d in data
    ]
    img.putdata(new_data)
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out


def find_text_coordinates(pdf_stream, search_phrase):
    try:
        with pdfplumber.open(pdf_stream) as pdf:
            for page_idx in range(len(pdf.pages) - 1, -1, -1):
                page = pdf.pages[page_idx]
                words = page.extract_words()
                text_content = " ".join([w["text"] for w in words])

                if search_phrase in text_content:
                    for i in range(len(words) - 1, -1, -1):
                        if words[i]["text"] == "Sanjiv":
                            if i + 1 < len(words) and "Bansal" in words[i + 1]["text"]:
                                return page_idx, words[i]["x0"], words[i]["top"], page.height
    except Exception:
        pass
    return None, None, None, None


def sign_pdf(file_bytes, phrase, sig_stream):
    page_idx, pdf_x, pdf_top, page_height = find_text_coordinates(io.BytesIO(file_bytes), phrase)
    if page_idx is None:
        return file_bytes

    # Exact placement coordinates from your working local script
    x_offset, y_offset = 0, 3
    converted_y = page_height - pdf_top + y_offset
    converted_x = pdf_x + x_offset

    packet = io.BytesIO()
    c = canvas.Canvas(packet)
    sig_stream.seek(0)
    c.drawImage(ImageReader(sig_stream), converted_x, converted_y, width=75, height=30, mask="auto")
    c.save()
    packet.seek(0)

    reader = PdfReader(io.BytesIO(file_bytes))
    writer = PdfWriter()
    stamp_page = PdfReader(packet).pages[0]

    for idx, page in enumerate(reader.pages):
        if idx == page_idx:
            page.merge_page(stamp_page)
        writer.add_page(page)

    output_stream = io.BytesIO()
    writer.write(output_stream)
    return output_stream.getvalue()


if uploaded_files and st.button("Sign and Process PDFs"):
    sig_stream = make_transparent_png("Dr.Sign.jpeg")

    if len(uploaded_files) == 1:
        file = uploaded_files[0]
        signed_bytes = sign_pdf(file.read(), search_text, sig_stream)
        st.success(f"Processed: {file.name}")
        st.download_button(
            label="Download Signed PDF",
            data=signed_bytes,
            file_name=f"signed_{file.name}",
            mime="application/pdf",
        )
    else:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file in uploaded_files:
                signed_bytes = sign_pdf(file.read(), search_text, sig_stream)
                zip_file.writestr(f"signed_{file.name}", signed_bytes)
        zip_buffer.seek(0)

        st.success(f"Processed all {len(uploaded_files)} files!")
        st.download_button(
            label="Download All as ZIP",
            data=zip_buffer.getvalue(),
            file_name="signed_documents.zip",
            mime="application/zip",
        )
