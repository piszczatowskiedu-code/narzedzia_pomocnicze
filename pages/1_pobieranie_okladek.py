import streamlit as st
import pandas as pd
import requests
import os
from pathlib import Path
from urllib.parse import urlparse
import time
from PIL import Image
import io
import zipfile
from datetime import datetime

st.set_page_config(
    page_title="Pobieranie okładek PRO",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stProgress > div > div > div > div { background-color: #00cc00; }
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 1rem; }
    textarea::placeholder { color: #e0e0e0 !important; opacity: 0.4 !important; }
</style>
""", unsafe_allow_html=True)

TIMEOUT = 30
ALLOWED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
# Formaty które rozpoznajemy ale pomijamy z informacją
SKIP_FORMATS = {'.pdf', '.html', '.htm', '.svg', '.tiff', '.tif', '.eps', '.ai', '.psd'}
DEFAULT_FORMAT = '.jpg'

ALLOWED_CONTENT_TYPES = {
    'image/jpeg', 'image/png', 'image/gif',
    'image/webp', 'image/bmp', 'image/x-bmp'
}
SKIP_CONTENT_TYPES = {
    'application/pdf',
    'text/html', 'text/plain', 'application/xhtml+xml',
    'image/svg+xml', 'image/tiff'
}

def has_transparency(image):
    if image.mode in ('RGBA', 'LA'):
        alpha = image.split()[-1]
        return alpha.getextrema() != (255, 255)
    elif image.mode == 'P':
        return 'transparency' in image.info
    return False

def add_white_background(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if not has_transparency(image):
            return image_bytes
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        background = Image.new('RGBA', image.size, (255, 255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        final_image = background.convert('RGB')
        output = io.BytesIO()
        fmt = 'JPEG' if getattr(image, 'format', '') in ['JPEG', 'JPG'] else 'PNG'
        final_image.save(output, format=fmt, quality=95, optimize=True)
        return output.getvalue()
    except Exception:
        return image_bytes

def convert_webp_to_png(image_bytes, remove_transparency=False):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if remove_transparency and has_transparency(image):
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode not in ('RGBA', 'LA') and image.mode != 'RGB':
            image = image.convert('RGB')
        output = io.BytesIO()
        image.save(output, format='PNG', optimize=True)
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Błąd konwersji WebP: {e}")

def pobierz_obraz(url, timeout=TIMEOUT):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                time.sleep(2)
                continue
            raise e

def sprawdz_format_z_url(link_str):
    """
    Zwraca (rozszerzenie, powod_pominiecia_lub_None).
    Sprawdza wyłącznie URL — bez pobierania.
    """
    parsed = urlparse(link_str)
    path = parsed.path.lower()
    ext = os.path.splitext(path)[1]

    # Zabezpieczenie przed PDF i HTML na poziomie URL
    for skip_ext in SKIP_FORMATS:
        if path.endswith(skip_ext):
            return ext, f"Nieobsługiwany format pliku: {skip_ext.upper()} (z URL)"

    if ext in ALLOWED_FORMATS:
        return ext, None

    # Nieznane rozszerzenie — spróbujemy pobrać i sprawdzimy Content-Type
    return ext or DEFAULT_FORMAT, None

def sprawdz_content_type(response):
    """
    Sprawdza Content-Type z nagłówków odpowiedzi HTTP.
    Zwraca (ok: bool, powod: str | None)
    """
    ct = response.headers.get('Content-Type', '').split(';')[0].strip().lower()

    if ct in ALLOWED_CONTENT_TYPES:
        return True, None

    if ct in SKIP_CONTENT_TYPES:
        return False, f"Serwer zwrócił: {ct}"

    if ct.startswith('image/'):
        # Nieznany podtyp image — próbujemy, PIL zdecyduje
        return True, None

    if ct in ('', 'application/octet-stream'):
        # Brak info — próbujemy otworzyć PIL-em
        return True, None

    return False, f"Nieobsługiwany Content-Type: {ct}"

def waliduj_pil(image_bytes):
    """
    Otwiera bajty przez PIL — jeśli to nie jest obraz, PIL wyrzuci wyjątek.
    Zwraca (ok: bool, powod: str | None)
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()  # sprawdza integralność bez dekodowania całości
        return True, None
    except Exception as e:
        return False, f"Plik nie jest prawidłowym obrazem: {e}"

def create_zip_from_memory(files_dict):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, file_data in files_dict.items():
            zip_file.writestr(filename, file_data)
    zip_buffer.seek(0)
    return zip_buffer

def parse_ean_list(ean_text):
    if not ean_text:
        return set()
    ean_list = []
    for line in ean_text.strip().split('\n'):
        ean = line.strip()
        if ean:
            try:
                ean = str(int(float(ean))).strip()
            except (ValueError, OverflowError):
                ean = str(ean).strip()
            ean_list.append(ean)
    return set(ean_list)

if 'download_results' not in st.session_state:
    st.session_state.download_results = None

st.markdown("<div class='main-header'>📥 Pobieranie okładek z Excel</div>", unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    delay_between = st.slider("Opóźnienie między pobraniami (s)", 0.2, 5.0, 1.5,
                              help="Im większe opóźnienie, tym mniejsza szansa na blokadę (zalecane: 1.5s)")
    handle_transparency = st.checkbox("Dodaj białe tło do przezroczystości", value=True)
    convert_webp = st.checkbox("Konwertuj .webp na .png", value=True)
    overwrite = st.checkbox("Nadpisuj istniejące pliki", value=False)
    st.markdown("---")
    if st.session_state.download_results:
        if st.button("🗑️ Wyczyść raport", type="secondary"):
            st.session_state.download_results = None
            st.rerun()

uploaded_file = st.file_uploader("Wybierz plik Excel", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        with st.spinner("Wczytywanie pliku..."):
            df = pd.read_excel(uploaded_file)

        st.success(f"✅ Wczytano: **{uploaded_file.name}** | Wierszy: **{len(df)}**")

        col1, col2 = st.columns(2)
        with col1:
            ean_column = st.selectbox("Kolumna EAN", options=df.columns.tolist(),
                                      index=df.columns.tolist().index('EAN') if 'EAN' in df.columns else 0)
        with col2:
            link_column = st.selectbox("Kolumna z linkami", options=df.columns.tolist(),
                                       index=df.columns.tolist().index('Link do okładki') if 'Link do okładki' in df.columns else 0)

        st.markdown("### 🔍 Filtr EAN (opcjonalne)")
        ean_filter_text = st.text_area("Wklej kody EAN (jeden na linię), jeśli chcesz pobrać tylko wybrane:", height=100)

        if st.button("🚀 ROZPOCZNIJ POBIERANIE", type="primary", use_container_width=True):
            downloaded_files = {}
            ean_filter_set = parse_ean_list(ean_filter_text) if ean_filter_text else None
            found_eans = set()

            stats = {
                'sukces': 0, 'blad': 0, 'istnieje': 0,
                'konwersje': 0, 'transparency_fixed': 0,
                'nieznalezione_ean': 0, 'pominiete': 0, 'puste_wiersze': 0
            }
            errors_log = []
            skipped_log = []      # pominięte niebędące błędem sieci

            progress_bar = st.progress(0)
            status_text = st.empty()
            log_expander = st.expander("⚠️ Dziennik zdarzeń", expanded=True)

            total_rows = len(df)

            for idx, row in df.iterrows():
                progress_bar.progress((idx + 1) / total_rows)

                link = row[link_column]
                ean  = row[ean_column]

                if pd.isna(link) or pd.isna(ean):
                    stats['puste_wiersze'] += 1
                    continue

                try:
                    ean = str(int(float(ean))).strip().replace(' ', '')
                except Exception:
                    ean = str(ean).strip().replace(' ', '')

                if ean_filter_set and ean not in ean_filter_set:
                    stats['nieznalezione_ean'] += 1
                    continue

                found_eans.add(ean)
                status_text.text(f"Pobieranie: {ean} ({idx + 1}/{total_rows})")
                link_str = str(link).strip()

                # ── 1. Weryfikacja rozszerzenia z URL (bez pobierania) ──────────
                ext_from_url, skip_reason = sprawdz_format_z_url(link_str)
                if skip_reason:
                    msg = f"EAN: {ean} | Pominięto — {skip_reason}"
                    skipped_log.append(msg)
                    log_expander.warning(msg)
                    stats['pominiete'] += 1
                    continue

                # ── 2. Pobieranie ───────────────────────────────────────────────
                try:
                    response = pobierz_obraz(link_str)
                except Exception as e:
                    msg = f"EAN: {ean} | Błąd pobierania: {e}"
                    errors_log.append(msg)
                    log_expander.error(msg)
                    stats['blad'] += 1
                    time.sleep(delay_between)
                    continue

                # ── 3. Weryfikacja Content-Type ─────────────────────────────────
                ct_ok, ct_reason = sprawdz_content_type(response)
                if not ct_ok:
                    msg = f"EAN: {ean} | Pominięto — {ct_reason}"
                    skipped_log.append(msg)
                    log_expander.warning(msg)
                    stats['pominiete'] += 1
                    time.sleep(delay_between)
                    continue

                image_data = response.content

                # ── 4. Weryfikacja PIL (czy to naprawdę obraz) ──────────────────
                pil_ok, pil_reason = waliduj_pil(image_data)
                if not pil_ok:
                    msg = f"EAN: {ean} | Pominięto — {pil_reason}"
                    skipped_log.append(msg)
                    log_expander.warning(msg)
                    stats['pominiete'] += 1
                    time.sleep(delay_between)
                    continue

                # ── 5. Ustal ostateczne rozszerzenie ────────────────────────────
                ct_header = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                ct_ext_map = {
                    'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif',
                    'image/webp': '.webp', 'image/bmp': '.bmp'
                }
                extension = ct_ext_map.get(ct_header, ext_from_url)
                if extension not in ALLOWED_FORMATS:
                    extension = DEFAULT_FORMAT
                original_ext = extension

                # ── 6. Obróbka obrazu ───────────────────────────────────────────
                if handle_transparency and original_ext != '.webp':
                    processed = add_white_background(image_data)
                    if processed != image_data:
                        image_data = processed
                        stats['transparency_fixed'] += 1

                if convert_webp and original_ext == '.webp':
                    try:
                        image_data = convert_webp_to_png(image_data, remove_transparency=handle_transparency)
                        extension = '.png'
                        stats['konwersje'] += 1
                    except Exception as e:
                        msg = f"EAN: {ean} | Błąd konwersji WebP: {e}"
                        errors_log.append(msg)
                        log_expander.error(msg)
                        stats['blad'] += 1
                        time.sleep(delay_between)
                        continue

                # ── 7. Zapis ────────────────────────────────────────────────────
                filename = f"{ean}{extension}"
                if filename in downloaded_files and not overwrite:
                    stats['istnieje'] += 1
                    time.sleep(delay_between)
                    continue

                downloaded_files[filename] = image_data
                stats['sukces'] += 1

                time.sleep(delay_between)

            # ── Raport końcowy ──────────────────────────────────────────────────
            if skipped_log:
                with st.expander(f"📋 Pominięte pliki ({len(skipped_log)})", expanded=False):
                    for msg in skipped_log:
                        st.warning(msg)

            st.session_state.download_results = {
                'stats': stats,
                'errors_log': errors_log,
                'skipped_log': skipped_log,
                'downloaded_files': downloaded_files,
                'missing_eans': ean_filter_set - found_eans if ean_filter_set else None,
            }
            st.rerun()

        # ── Wyświetlanie wyników ────────────────────────────────────────────────
        if st.session_state.download_results:
            res = st.session_state.download_results
            s   = res['stats']

            st.markdown("---")
            st.markdown("## 📊 Wyniki")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("✅ Pobrane",      s['sukces'])
            c2.metric("❌ Błędy sieciowe", s['blad'])
            c3.metric("⏭️ Pominięte",    s['pominiete'])
            c4.metric("🎨 Białe tło",    s['transparency_fixed'])
            c5.metric("🔄 Konwersje WebP", s['konwersje'])

            if s['sukces'] > 0:
                zip_data = create_zip_from_memory(res['downloaded_files'])
                st.download_button(
                    label=f"⬇️ POBIERZ PACZKĘ ZIP ({s['sukces']} plików)",
                    data=zip_data,
                    file_name=f"okladki_{datetime.now().strftime('%H%M%S')}.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"Wystąpił błąd krytyczny: {e}")

else:
    st.info("💡 Wgraj plik Excel, aby rozpocząć.")