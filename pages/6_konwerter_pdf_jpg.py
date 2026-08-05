import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import zipfile
from datetime import datetime

DPI = 72
QUALITY = 95

# ============================================
# FUNKCJE
# ============================================

def convert_pdf_to_jpg(pdf_bytes: bytes) -> tuple[dict, int]:
    """Konwertuje PDF na JPG używając PyMuPDF."""
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    if pdf_document.is_encrypted:
        pdf_document.close()
        raise ValueError("PDF jest zaszyfrowany hasłem.")

    jpg_files = {}
    zoom = DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for i in range(pdf_document.page_count):
        page = pdf_document.load_page(i)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        pil_image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

        buf = io.BytesIO()
        pil_image.save(buf, format="JPEG", quality=QUALITY, optimize=True)
        buf.seek(0)

        jpg_files[f"page_{i + 1:03d}.jpg"] = buf.getvalue()

    page_count = pdf_document.page_count
    pdf_document.close()
    return jpg_files, page_count


def create_zip(files_dict: dict) -> io.BytesIO:
    """Tworzy archiwum ZIP."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files_dict.items():
            zf.writestr(name, data)
    zip_buffer.seek(0)
    return zip_buffer


# ============================================
# INTERFEJS
# ============================================

st.markdown("## 📄 Konwerter PDF → JPG")
st.markdown("---")

uploaded_file = st.file_uploader("Wybierz plik PDF", type=["pdf"])

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    st.info(f"📁 **{uploaded_file.name}** — {len(pdf_bytes) / 1024:.1f} KB")

    if st.button("🚀 KONWERTUJ", type="primary"):
        try:
            with st.spinner("Konwertuję..."):
                jpg_files, page_count = convert_pdf_to_jpg(pdf_bytes)

            st.success(f"✅ Skonwertowano {page_count} stron")

            base_name = uploaded_file.name.rsplit(".", 1)[0]

            if page_count == 1:
                data = list(jpg_files.values())[0]
                st.download_button(
                    f"⬇️ Pobierz {base_name}.jpg",
                    data=data,
                    file_name=f"{base_name}.jpg",
                    mime="image/jpeg",
                    type="primary"
                )
            else:
                zip_buf = create_zip(jpg_files)
                zip_name = f"{base_name}_JPG_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                st.download_button(
                    f"⬇️ Pobierz ZIP ({page_count} stron)",
                    data=zip_buf,
                    file_name=zip_name,
                    mime="application/zip",
                    type="primary"
                )

            # Podgląd wszystkich stron w gridzie 5-kolumnowym
            st.markdown("---")
            st.markdown("### 👁️ Podgląd stron")

            pages_list = list(jpg_files.items())
            cols_per_row = 5

            for row_start in range(0, len(pages_list), cols_per_row):
                row_pages = pages_list[row_start:row_start + cols_per_row]
                cols = st.columns(cols_per_row)

                for col, (fname, fdata) in zip(cols, row_pages):
                    img = Image.open(io.BytesIO(fdata))
                    col.image(img, caption=fname, use_container_width=True)

        except Exception as e:
            st.error(f"❌ {e}")
