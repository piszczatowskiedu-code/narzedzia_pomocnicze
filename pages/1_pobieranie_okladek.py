import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import os
import base64
import json
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
SKIP_FORMATS    = {'.pdf', '.html', '.htm', '.svg', '.tiff', '.tif', '.eps', '.ai', '.psd'}
DEFAULT_FORMAT  = '.jpg'

ALLOWED_CONTENT_TYPES = {
    'image/jpeg', 'image/png', 'image/gif',
    'image/webp', 'image/bmp', 'image/x-bmp'
}
SKIP_CONTENT_TYPES = {
    'application/pdf',
    'text/html', 'text/plain', 'application/xhtml+xml',
    'image/svg+xml', 'image/tiff'
}


# ── Pomocnicze funkcje obrazu ────────────────────────────────────────────────

def has_transparency(image):
    if image.mode in ('RGBA', 'LA'):
        alpha = image.split()[-1]
        return alpha.getextrema() != (255, 255)
    elif image.mode == 'P':
        return 'transparency' in image.info
    return False


def add_white_background(image_bytes):
    """Dodaje białe tło do obrazu z przezroczystością."""
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


def convert_to_jpg(image_bytes, source_format: str) -> bytes:
    """
    Konwertuje obraz (WebP / GIF / BMP / cokolwiek) na JPEG.
    Przezroczyste piksele zastępuje białym tłem.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))

        # GIF: bierz tylko pierwszą klatkę
        if source_format == '.gif' and hasattr(image, 'n_frames') and image.n_frames > 1:
            image.seek(0)

        # Spłaszcz przezroczystość na białe tło
        if has_transparency(image) or image.mode in ('RGBA', 'LA', 'P'):
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        output = io.BytesIO()
        image.save(output, format='JPEG', quality=95, optimize=True)
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Błąd konwersji {source_format.upper()} → JPG: {e}")


def convert_webp_to_png(image_bytes, remove_transparency=False) -> bytes:
    """Konwertuje WebP na PNG."""
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
        raise Exception(f"Błąd konwersji WebP → PNG: {e}")


# ── Sieć i walidacja ─────────────────────────────────────────────────────────

def pobierz_obraz(url, timeout=TIMEOUT):
    """Pobiera obraz; zwraca cały obiekt Response (potrzebny do nagłówków)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise e


def sprawdz_format_z_url(link_str):
    """Sprawdza rozszerzenie w URL. Zwraca (ext, powod_pominiecia | None)."""
    parsed = urlparse(link_str)
    path = parsed.path.lower()
    ext = os.path.splitext(path)[1]

    for skip_ext in SKIP_FORMATS:
        if path.endswith(skip_ext):
            return ext, f"Nieobsługiwany format: {skip_ext.upper()} (z URL)"

    if ext in ALLOWED_FORMATS:
        return ext, None

    return ext or DEFAULT_FORMAT, None


def sprawdz_content_type(response):
    """Sprawdza Content-Type. Zwraca (ok, powod | None)."""
    ct = response.headers.get('Content-Type', '').split(';')[0].strip().lower()

    if ct in ALLOWED_CONTENT_TYPES:
        return True, None
    if ct in SKIP_CONTENT_TYPES:
        return False, f"Serwer zwrócił nieobsługiwany typ: {ct}"
    if ct.startswith('image/') or ct in ('', 'application/octet-stream'):
        return True, None

    return False, f"Nieobsługiwany Content-Type: {ct}"


def waliduj_pil(image_bytes):
    """Otwiera bajty przez PIL — ostateczna weryfikacja że to obraz."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        return True, None
    except Exception as e:
        return False, f"Plik nie jest prawidłowym obrazem: {e}"


# ── ZIP ──────────────────────────────────────────────────────────────────────

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


# ── Session state ────────────────────────────────────────────────────────────

if 'download_results' not in st.session_state:
    st.session_state.download_results = None

# ── Obsługa zamiany obrazków (drag & drop) ───────────────────────────────────
swap_param = st.query_params.get('swap', None)
if swap_param and st.session_state.download_results:
    try:
        swap = json.loads(swap_param)
        ean   = swap['ean']
        suf_a = swap['a']   # np. '' lub '_1'
        suf_b = swap['b']
        files = st.session_state.download_results['downloaded_files']

        # Znajdź pliki do zamiany
        key_a = next((k for k in files if k.rsplit('.', 1)[0] == f"{ean}{suf_a}"), None)
        key_b = next((k for k in files if k.rsplit('.', 1)[0] == f"{ean}{suf_b}"), None)

        if key_a and key_b:
            ext_a = '.' + key_a.rsplit('.', 1)[1]
            ext_b = '.' + key_b.rsplit('.', 1)[1]
            data_a = files.pop(key_a)
            data_b = files.pop(key_b)
            files[f"{ean}{suf_a}{ext_b}"] = data_b
            files[f"{ean}{suf_b}{ext_a}"] = data_a
        elif key_a and not key_b:
            ext_a = '.' + key_a.rsplit('.', 1)[1]
            data_a = files.pop(key_a)
            files[f"{ean}{suf_b}{ext_a}"] = data_a
        elif key_b and not key_a:
            ext_b = '.' + key_b.rsplit('.', 1)[1]
            data_b = files.pop(key_b)
            files[f"{ean}{suf_a}{ext_b}"] = data_b

        st.query_params.clear()
    except Exception as e:
        st.query_params.clear()

# ── UI ───────────────────────────────────────────────────────────────────────

st.markdown("<div class='main-header'>📥 Pobieranie okładek z Excel</div>", unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Ustawienia")

    delay_between = st.slider(
        "Opóźnienie między pobraniami (s)",
        min_value=0.2, max_value=5.0, value=1.5,
        help="Im większe opóźnienie, tym mniejsza szansa na blokadę (zalecane: 1.5s)"
    )

    st.markdown("#### 🖼️ Konwersje formatów")
    handle_transparency = st.checkbox("Dodaj białe tło do przezroczystości", value=True)
    convert_webp = st.checkbox("Konwertuj .webp → .png", value=True)
    convert_gif  = st.checkbox("Konwertuj .gif → .jpg (1. klatka)", value=True)
    convert_bmp  = st.checkbox("Konwertuj .bmp → .jpg", value=True)

    st.markdown("---")
    overwrite = st.checkbox("Nadpisuj istniejące pliki", value=False)

    if st.session_state.download_results:
        st.markdown("---")
        if st.button("🗑️ Wyczyść raport", type="secondary"):
            st.session_state.download_results = None
            st.rerun()

# ── Główna część ─────────────────────────────────────────────────────────────

uploaded_file = st.file_uploader("Wybierz plik Excel", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        with st.spinner("Wczytywanie pliku..."):
            df = pd.read_excel(uploaded_file)

        st.success(f"✅ Wczytano: **{uploaded_file.name}** | Wierszy: **{len(df)}**")

        col1, col2 = st.columns(2)
        with col1:
            ean_column = st.selectbox(
                "Kolumna EAN", options=df.columns.tolist(),
                index=df.columns.tolist().index('EAN') if 'EAN' in df.columns else 0
            )

        st.markdown("#### 🔗 Kolumny z linkami do okładek")
        st.caption("Wybierz od 1 do 5 kolumn. Pliki będą nazwane: EAN, EAN_1, EAN_2, EAN_3, EAN_4.")

        # Etykiety nazw plików: pierwsza kolumna → EAN (bez sufiksu), kolejne → EAN_1, EAN_2, EAN_3, EAN_4
        col_suffix_labels = ["EAN", "EAN_1", "EAN_2", "EAN_3", "EAN_4"]

        cols_ui = st.columns(5)
        link_columns = []
        col_options_none = ["(brak)"] + df.columns.tolist()

        for i, ui_col in enumerate(cols_ui):
            with ui_col:
                default_label = "Link do okładki" if i == 0 else f"Link do okładki {i}"
                if default_label in df.columns:
                    default_idx = col_options_none.index(default_label)
                else:
                    default_idx = 0  # "(brak)"
                chosen = st.selectbox(
                    f"→ {col_suffix_labels[i]}",
                    options=col_options_none,
                    index=default_idx,
                    key=f"link_col_{i}"
                )
                if chosen != "(brak)":
                    # suffix: None dla pierwszej kolumny (EAN), i dla kolejnych (EAN_1, EAN_2, EAN_3)
                    link_columns.append((i, chosen))

        if not link_columns:
            st.warning("⚠️ Wybierz co najmniej jedną kolumnę z linkami.")


        st.markdown("### 🔍 Filtr EAN (opcjonalne)")
        ean_filter_text = st.text_area(
            "Wklej kody EAN (jeden na linię), jeśli chcesz pobrać tylko wybrane:",
            height=100
        )

        if st.button("🚀 ROZPOCZNIJ POBIERANIE", type="primary", use_container_width=True, disabled=not link_columns):

            downloaded_files = {}
            ean_filter_set   = parse_ean_list(ean_filter_text) if ean_filter_text else None
            found_eans       = set()

            stats = {
                'sukces': 0, 'blad': 0, 'istnieje': 0,
                'pominiete': 0, 'puste_wiersze': 0, 'nieznalezione_ean': 0,
                'webp_png': 0, 'gif_jpg': 0, 'bmp_jpg': 0, 'transparency_fixed': 0,
            }
            errors_log  = []
            skipped_log = []

            progress_bar = st.progress(0)
            status_text  = st.empty()
            log_expander = st.expander("⚠️ Dziennik zdarzeń", expanded=True)

            total_rows = len(df)
            total_tasks = total_rows * len(link_columns)
            task_counter = 0

            for idx, row in df.iterrows():

                ean = row[ean_column]

                if pd.isna(ean):
                    stats['puste_wiersze'] += 1
                    task_counter += len(link_columns)
                    progress_bar.progress(min(task_counter / total_tasks, 1.0))
                    continue

                try:
                    ean = str(int(float(ean))).strip().replace(' ', '')
                except Exception:
                    ean = str(ean).strip().replace(' ', '')

                if ean_filter_set and ean not in ean_filter_set:
                    stats['nieznalezione_ean'] += 1
                    task_counter += len(link_columns)
                    progress_bar.progress(min(task_counter / total_tasks, 1.0))
                    continue

                found_eans.add(ean)

                for col_num, col_name in link_columns:
                    task_counter += 1
                    progress_bar.progress(min(task_counter / total_tasks, 1.0))

                    link = row[col_name]

                    if pd.isna(link) or str(link).strip() == '':
                        stats['puste_wiersze'] += 1
                        continue

                    link_str = str(link).strip()
                    ean_label = ean if col_num == 0 else f"{ean}_{col_num}"
                    status_text.text(f"Pobieranie: {ean_label} ({task_counter}/{total_tasks})")

                    # ── 1. Weryfikacja URL ────────────────────────────────────────
                    ext_from_url, skip_reason = sprawdz_format_z_url(link_str)
                    if skip_reason:
                        msg = f"EAN: {ean_label} | Pominięto — {skip_reason}"
                        skipped_log.append(msg)
                        log_expander.warning(msg)
                        stats['pominiete'] += 1
                        continue

                    # ── 2. Pobieranie ─────────────────────────────────────────────
                    try:
                        response = pobierz_obraz(link_str)
                    except Exception as e:
                        msg = f"EAN: {ean_label} | Błąd pobierania: {e}"
                        errors_log.append(msg)
                        log_expander.error(msg)
                        stats['blad'] += 1
                        time.sleep(delay_between)
                        continue

                    # ── 3. Weryfikacja Content-Type ───────────────────────────────
                    ct_ok, ct_reason = sprawdz_content_type(response)
                    if not ct_ok:
                        msg = f"EAN: {ean_label} | Pominięto — {ct_reason}"
                        skipped_log.append(msg)
                        log_expander.warning(msg)
                        stats['pominiete'] += 1
                        time.sleep(delay_between)
                        continue

                    image_data = response.content

                    # ── 4. Walidacja PIL ──────────────────────────────────────────
                    pil_ok, pil_reason = waliduj_pil(image_data)
                    if not pil_ok:
                        msg = f"EAN: {ean_label} | Pominięto — {pil_reason}"
                        skipped_log.append(msg)
                        log_expander.warning(msg)
                        stats['pominiete'] += 1
                        time.sleep(delay_between)
                        continue

                    # ── 5. Ustal rozszerzenie z Content-Type ─────────────────────
                    ct_header = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                    ct_ext_map = {
                        'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif',
                        'image/webp': '.webp', 'image/bmp': '.bmp'
                    }
                    extension    = ct_ext_map.get(ct_header, ext_from_url)
                    if extension not in ALLOWED_FORMATS:
                        extension = DEFAULT_FORMAT
                    original_ext = extension

                    # ── 6. Konwersje formatów ─────────────────────────────────────

                    # WebP → PNG
                    if convert_webp and original_ext == '.webp':
                        try:
                            image_data = convert_webp_to_png(image_data, remove_transparency=handle_transparency)
                            extension  = '.png'
                            stats['webp_png'] += 1
                        except Exception as e:
                            msg = f"EAN: {ean_label} | Błąd konwersji WebP→PNG: {e}"
                            errors_log.append(msg)
                            log_expander.error(msg)
                            stats['blad'] += 1
                            time.sleep(delay_between)
                            continue

                    # GIF → JPG
                    elif convert_gif and original_ext == '.gif':
                        try:
                            image_data = convert_to_jpg(image_data, source_format='.gif')
                            extension  = '.jpg'
                            stats['gif_jpg'] += 1
                        except Exception as e:
                            msg = f"EAN: {ean_label} | Błąd konwersji GIF→JPG: {e}"
                            errors_log.append(msg)
                            log_expander.error(msg)
                            stats['blad'] += 1
                            time.sleep(delay_between)
                            continue

                    # BMP → JPG
                    elif convert_bmp and original_ext == '.bmp':
                        try:
                            image_data = convert_to_jpg(image_data, source_format='.bmp')
                            extension  = '.jpg'
                            stats['bmp_jpg'] += 1
                        except Exception as e:
                            msg = f"EAN: {ean_label} | Błąd konwersji BMP→JPG: {e}"
                            errors_log.append(msg)
                            log_expander.error(msg)
                            stats['blad'] += 1
                            time.sleep(delay_between)
                            continue

                    # Białe tło dla pozostałych formatów (JPG/PNG) z przezroczystością
                    else:
                        if handle_transparency:
                            processed = add_white_background(image_data)
                            if processed != image_data:
                                image_data = processed
                                stats['transparency_fixed'] += 1

                    # ── 7. Zapis ──────────────────────────────────────────────────
                    filename = f"{ean}{extension}" if col_num == 0 else f"{ean_label}{extension}"
                    if filename in downloaded_files and not overwrite:
                        stats['istnieje'] += 1
                        time.sleep(delay_between)
                        continue

                    downloaded_files[filename] = image_data
                    stats['sukces'] += 1

                    time.sleep(delay_between)

            # ── Podsumowanie pominięć ─────────────────────────────────────────
            if skipped_log:
                with st.expander(f"📋 Pominięte pliki ({len(skipped_log)})", expanded=False):
                    for msg in skipped_log:
                        st.warning(msg)

            # Ustal raz na zawsze kolejność EAN-ów (stabilna, niezależna od kluczy słownika)
            ean_order = []
            seen_order_set = set()
            for fname in downloaded_files:
                ean_key = fname.rsplit('.', 1)[0].split('_')[0]
                if ean_key not in seen_order_set:
                    seen_order_set.add(ean_key)
                    ean_order.append(ean_key)

            st.session_state.download_results = {
                'stats': stats,
                'errors_log': errors_log,
                'skipped_log': skipped_log,
                'downloaded_files': downloaded_files,
                'missing_eans': ean_filter_set - found_eans if ean_filter_set else None,
                'ean_order': ean_order,
            }
            st.rerun()

        # ── Wyświetlanie wyników ──────────────────────────────────────────────
        if st.session_state.download_results:
            res = st.session_state.download_results
            s   = res['stats']

            st.markdown("---")
            st.markdown("## 📊 Wyniki")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("✅ Pobrane",         s['sukces'])
            c2.metric("❌ Błędy sieciowe",  s['blad'])
            c3.metric("⏭️ Pominięte",       s['pominiete'])
            c4.metric("🎨 Białe tło",       s['transparency_fixed'])

            c5, c6, c7 = st.columns(3)
            c5.metric("🔄 WebP → PNG",  s['webp_png'])
            c6.metric("🎞️ GIF → JPG",   s['gif_jpg'])
            c7.metric("🖼️ BMP → JPG",   s['bmp_jpg'])

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

                # ── Podgląd okładek z drag & drop ────────────────────────────
                st.markdown("---")
                st.markdown("## 🖼️ Podgląd pobranych okładek")
                st.caption("Przeciągnij obrazek na inną pozycję w tym samym wierszu, aby zamienić nazwy plików.")

                downloaded_files = res['downloaded_files']

                SUFFIXES      = ['', '_1', '_2', '_3', '_4']
                SUFFIX_LABELS = ['EAN', 'EAN_1', 'EAN_2', 'EAN_3', 'EAN_4']
                THUMB_SIZE    = 150

                # Użyj ustalonej raz kolejności EAN-ów (stabilna między reruns)
                seen_eans = res['ean_order']

                # Zbuduj strukturę danych dla JS: {ean: {suf: base64_png | null}}
                rows_data = []
                for ean in seen_eans:
                    cols_data = []
                    for suf, lbl in zip(SUFFIXES, SUFFIX_LABELS):
                        target_base = f"{ean}{suf}"
                        match = next((fn for fn in downloaded_files if fn.rsplit('.', 1)[0] == target_base), None)
                        if match:
                            try:
                                img = Image.open(io.BytesIO(downloaded_files[match]))
                                img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                                buf = io.BytesIO()
                                img.save(buf, format='PNG')
                                b64 = base64.b64encode(buf.getvalue()).decode()
                                cols_data.append({'suf': suf, 'label': lbl, 'img': b64, 'fname': match})
                            except Exception:
                                cols_data.append({'suf': suf, 'label': lbl, 'img': None, 'fname': None})
                        else:
                            cols_data.append({'suf': suf, 'label': lbl, 'img': None, 'fname': None})
                    rows_data.append({'ean': ean, 'cols': cols_data})

                rows_json = json.dumps(rows_data, ensure_ascii=False)
                n_cols    = len(SUFFIXES)

                html_component = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: sans-serif; font-size: 13px; background: transparent; }}

  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #f0f2f6; padding: 8px 6px; text-align: center;
        font-weight: 600; color: #333; border-bottom: 2px solid #ddd; }}
  th.ean-col {{ text-align: left; padding-left: 10px; width: 140px; }}
  td {{ padding: 6px; vertical-align: middle; border-bottom: 1px solid #f0f0f0; }}
  td.ean-cell {{ font-family: monospace; font-size: 12px; color: #555;
                 padding-left: 10px; white-space: nowrap; }}

  .slot {{
    width: {THUMB_SIZE + 16}px; height: {THUMB_SIZE + 36}px;
    border: 2px dashed #ccc; border-radius: 8px;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; background: #fafafa;
    transition: border-color .2s, background .2s;
    position: relative; cursor: default;
  }}
  .slot.has-img {{ border-style: solid; border-color: #c8d8ea; background: #fff;
                   cursor: grab; }}
  .slot.has-img:active {{ cursor: grabbing; }}
  .slot.drag-over {{ border-color: #1f77b4 !important; background: #e8f4ff !important; }}
  .slot.dragging  {{ opacity: .4; }}

  .slot img {{ max-width: {THUMB_SIZE}px; max-height: {THUMB_SIZE}px;
               border-radius: 4px; pointer-events: none; }}
  .slot .fname {{ font-size: 10px; color: #888; margin-top: 4px;
                  text-align: center; word-break: break-all;
                  max-width: {THUMB_SIZE + 8}px; }}
  .slot .empty-label {{ color: #bbb; font-size: 12px; }}

  .swap-flash {{ animation: flashGreen .6s ease; }}
  @keyframes flashGreen {{
    0%   {{ background: #d4f5d4; border-color: #4caf50; }}
    100% {{ background: #fff;    border-color: #c8d8ea; }}
  }}
</style>
</head>
<body>
<table>
  <thead><tr>
    <th class="ean-col">EAN</th>
    <th>EAN</th><th>EAN_1</th><th>EAN_2</th><th>EAN_3</th><th>EAN_4</th>
  </tr></thead>
  <tbody id="tbody"></tbody>
</table>

<script>
const rows = {rows_json};

let dragSrc = null; // {{ean, suf, el}}

function buildTable() {{
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  rows.forEach(row => {{
    const tr = document.createElement('tr');

    // EAN cell
    const td0 = document.createElement('td');
    td0.className = 'ean-cell';
    td0.textContent = row.ean;
    tr.appendChild(td0);

    row.cols.forEach(col => {{
      const td = document.createElement('td');
      td.style.textAlign = 'center';
      const slot = buildSlot(row.ean, col);
      td.appendChild(slot);
      tr.appendChild(td);
    }});

    tbody.appendChild(tr);
  }});
}}

function buildSlot(ean, col) {{
  const slot = document.createElement('div');
  slot.className = 'slot' + (col.img ? ' has-img' : '');
  slot.dataset.ean = ean;
  slot.dataset.suf = col.suf;

  if (col.img) {{
    const img = document.createElement('img');
    img.src = 'data:image/png;base64,' + col.img;
    slot.appendChild(img);
    const lbl = document.createElement('div');
    lbl.className = 'fname';
    lbl.textContent = col.fname;
    slot.appendChild(lbl);

    slot.draggable = true;

    slot.addEventListener('dragstart', e => {{
      dragSrc = {{ ean, suf: col.suf, el: slot }};
      slot.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    }});
    slot.addEventListener('dragend', () => slot.classList.remove('dragging'));
  }} else {{
    const lbl = document.createElement('div');
    lbl.className = 'empty-label';
    lbl.textContent = '—';
    slot.appendChild(lbl);
  }}

  slot.addEventListener('dragover', e => {{
    if (dragSrc && dragSrc.ean === ean && dragSrc.suf !== col.suf) {{
      e.preventDefault();
      slot.classList.add('drag-over');
    }}
  }});
  slot.addEventListener('dragleave', () => slot.classList.remove('drag-over'));

  slot.addEventListener('drop', e => {{
    e.preventDefault();
    slot.classList.remove('drag-over');
    if (!dragSrc || dragSrc.ean !== ean || dragSrc.suf === col.suf) return;

    // Zamień dane w rows[]
    const rowObj = rows.find(r => r.ean === ean);
    const colA   = rowObj.cols.find(c => c.suf === dragSrc.suf);
    const colB   = rowObj.cols.find(c => c.suf === col.suf);
    [colA.img, colB.img]     = [colB.img, colA.img];
    [colA.fname, colB.fname] = [colB.fname, colA.fname];
    buildTable();

    // Wyślij zamianę do Streamlit przez query param
    const swap = JSON.stringify({{ ean: ean, a: dragSrc.suf, b: col.suf }});
    const url  = new URL(window.parent.location.href);
    url.searchParams.set('swap', swap);
    window.parent.history.replaceState(null, '', url.toString());

    // Trigger Streamlit rerun przez symulację nawigacji
    window.parent.dispatchEvent(new Event('popstate'));
  }});

  return slot;
}}

buildTable();
</script>
</body>
</html>
"""

                table_height = 60 + len(seen_eans) * (THUMB_SIZE + 60)
                components.html(html_component, height=table_height, scrolling=True)

    except Exception as e:
        st.error(f"Wystąpił błąd krytyczny: {e}")

else:
    st.info("💡 Wgraj plik Excel, aby rozpocząć.")