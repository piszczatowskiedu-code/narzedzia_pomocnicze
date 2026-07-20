import re
import zipfile
from io import BytesIO

import streamlit as st
from PIL import Image

# ============================================
# KONFIGURACJA STRONY
# ============================================
st.set_page_config(
    page_title="Generator kopii grafik",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS (spójny z resztą narzędzi)
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #9c27b0;
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# INICJALIZACJA SESSION STATE
# ============================================
if "image_sets" not in st.session_state:
    st.session_state.image_sets = []

# ============================================
# FUNKCJE POMOCNICZE
# ============================================

def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:150] if name else "plik"


def make_unique_filenames(names, existing_names):
    used = {name: 1 for name in existing_names}
    result = []

    for name in names:
        clean = sanitize_filename(name)
        if clean not in used:
            used[clean] = 1
            result.append(f"{clean}.png")
        else:
            used[clean] += 1
            result.append(f"{clean}_{used[clean]}.png")

    return result


def image_to_png_bytes(uploaded_file):
    image = Image.open(uploaded_file).convert("RGBA")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue(), image


def create_zip(image_sets):
    zip_buffer = BytesIO()
    existing_names = set()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for image_bytes, names in image_sets:
            file_names = make_unique_filenames(names, existing_names)
            for file_name in file_names:
                zip_file.writestr(file_name, image_bytes)
                existing_names.add(file_name.replace(".png", ""))

    zip_buffer.seek(0)
    return zip_buffer


def get_total_files_count():
    return sum(len(names) for _, names in st.session_state.image_sets)


def remove_set(index):
    st.session_state.image_sets.pop(index)


# ============================================
# INTERFEJS UŻYTKOWNIKA
# ============================================

st.markdown("<div class='main-header'>🧬 Generator kopii grafik</div>", unsafe_allow_html=True)
st.markdown("---")

# Sekcja dodawania nowej pary
st.subheader("Dodaj grafikę z nazwami")

col1, col2 = st.columns(2)

with col1:
    uploaded_image = st.file_uploader(
        "Wgraj grafikę",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        key="uploader"
    )

    if uploaded_image:
        try:
            preview_image = Image.open(uploaded_image)
            st.image(preview_image, caption="Podgląd", width=200)
            st.caption(f"{preview_image.width} x {preview_image.height}px")
            uploaded_image.seek(0)
        except Exception:
            st.error("Nie udało się odczytać grafiki.")

with col2:
    names_text = st.text_area(
        "Lista nazw (jedna pod drugą)",
        height=180,
        placeholder="Jan Kowalski\nAnna Nowak\nPiotr Wiśniewski",
        key="names"
    )

    add_btn = st.button("➕ Dodaj do listy", type="secondary", width="stretch")

if add_btn:
    if not uploaded_image:
        st.error("Najpierw wgraj grafikę.")
    else:
        names = [line.strip() for line in names_text.splitlines() if line.strip()]
        if not names:
            st.error("Wpisz przynajmniej jedną nazwę.")
        else:
            try:
                image_bytes, _ = image_to_png_bytes(uploaded_image)
                st.session_state.image_sets.append((image_bytes, names))
                st.success(f"Dodano grafikę z {len(names)} nazwami.")
                st.rerun()
            except Exception:
                st.error("Nie udało się przetworzyć grafiki.")

st.markdown("---")

# Lista dodanych zestawów
st.subheader(f"Dodane zestawy ({len(st.session_state.image_sets)})")

if not st.session_state.image_sets:
    st.info("📤 Brak dodanych zestawów. Dodaj grafikę i listę nazw powyżej.")
else:
    for i, (image_bytes, names) in enumerate(st.session_state.image_sets):
        with st.container():
            col_img, col_info, col_action = st.columns([1, 3, 1])

            with col_img:
                img = Image.open(BytesIO(image_bytes))
                st.image(img, width=80)

            with col_info:
                st.write(f"**Zestaw {i + 1}** — {len(names)} plików")
                with st.expander("Nazwy"):
                    st.code("\n".join(names), language="text")

            with col_action:
                if st.button("🗑️", key=f"remove_{i}", help="Usuń zestaw"):
                    remove_set(i)
                    st.rerun()

    st.markdown("---")

    # Podsumowanie i pobieranie
    total_files = get_total_files_count()

    col_summary, col_download = st.columns(2)

    with col_summary:
        st.metric("Łącznie plików", total_files)

    with col_download:
        zip_buffer = create_zip(st.session_state.image_sets)
        st.download_button(
            label="📥 Pobierz wszystko (ZIP)",
            data=zip_buffer,
            file_name="grafiki.zip",
            mime="application/zip",
            width="stretch",
            type="primary"
        )

    # Przycisk czyszczenia
    if st.button("🗑️ Wyczyść wszystko", width="stretch"):
        st.session_state.image_sets = []
        st.rerun()

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>🧬 Generator kopii grafik</div>",
    unsafe_allow_html=True
)
