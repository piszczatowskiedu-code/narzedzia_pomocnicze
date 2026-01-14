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

# Custom CSS
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #00cc00;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    textarea::placeholder {
        color: #e0e0e0 !important;
        opacity: 0.4 !important;
    }
</style>
""", unsafe_allow_html=True)

# STAŁE KONFIGURACYJNE
TIMEOUT = 30
ALLOWED_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
DEFAULT_FORMAT = '.jpg'

def has_transparency(image):
    """Sprawdza czy obraz ma przezroczystość"""
    if image.mode in ('RGBA', 'LA'):
        if image.mode == 'RGBA':
            alpha = image.split()[-1]
            if alpha.getextrema() != (255, 255):
                return True
        elif image.mode == 'LA':
            alpha = image.split()[-1]
            if alpha.getextrema() != (255, 255):
                return True
    elif image.mode == 'P':
        if 'transparency' in image.info:
            return True
    return False

def add_white_background(image_bytes):
    """Dodaje białe tło do obrazu z przezroczystością"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if not has_transparency(image):
            return image_bytes
        
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        background = Image.new('RGBA', image.size, (255, 255, 255, 255))
        background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
        final_image = background.convert('RGB')
        
        output = io.BytesIO()
        format_to_save = 'JPEG' if image.format in ['JPEG', 'JPG'] else 'PNG'
        final_image.save(output, format=format_to_save, quality=95, optimize=True)
        return output.getvalue()
    except Exception:
        return image_bytes

def convert_webp_to_png(image_bytes, remove_transparency=False):
    """Konwertuje obraz WebP na PNG"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if remove_transparency and has_transparency(image):
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode in ('RGBA', 'LA'):
            pass
        else:
            if image.mode != 'RGB':
                image = image.convert('RGB')
        
        output = io.BytesIO()
        image.save(output, format='PNG', optimize=True)
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Błąd konwersji WebP: {e}")

def pobierz_obraz(url, timeout=TIMEOUT):
    """Pobiera obraz z ulepszonymi nagłówkami i systemem prób (retries)"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }
    
    # Próbujemy pobrać plik maksymalnie 3 razy w razie błędu sieciowego
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            return response.content
        except (requests.exceptions.RequestException) as e:
            if attempt < max_retries:
                time.sleep(2) # Czekaj przed ponowieniem
                continue
            raise e

def create_zip_from_memory(files_dict):
    """Tworzy archiwum ZIP w pamięci RAM"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, file_data in files_dict.items():
            zip_file.writestr(filename, file_data)
    zip_buffer.seek(0)
    return zip_buffer

def parse_ean_list(ean_text):
    """Parsuje kody EAN z pola tekstowego"""
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

# Inicjalizacja session_state
if 'download_results' not in st.session_state:
    st.session_state.download_results = None

st.markdown("<div class='main-header'>📥 Pobieranie okładek z Excel</div>", unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Ustawienia")
    
    # NOWOŚĆ: Kontrola opóźnienia
    delay_between = st.slider(
        "Opóźnienie między pobraniami (s)",
        min_value=0.2,
        max_value=5.0,
        value=1.5,
        help="Im większe opóźnienie, tym mniejsza szansa na blokadę przez serwer (zalecane: 1.5s)"
    )

    handle_transparency = st.checkbox("Dodaj białe tło do przezroczystości", value=True)
    convert_webp = st.checkbox("Konwertuj .webp na .png", value=True)
    overwrite = st.checkbox("Nadpisuj istniejące pliki", value=False)
    
    st.markdown("---")
    if st.session_state.download_results:
        if st.button("🗑️ Wyczyść raport", type="secondary"):
            st.session_state.download_results = None
            st.rerun()

# Główna część aplikacji
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
            
            stats = {'sukces': 0, 'blad': 0, 'istnieje': 0, 'konwersje': 0, 'transparency_fixed': 0, 
                     'nieznalezione_ean': 0, 'pdf_pominięte': 0, 'puste_wiersze': 0}
            
            errors_log = []
            pdf_eans = []
            transparency_processed = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_expander = st.expander("⚠️ Dziennik zdarzeń", expanded=True)
            
            total_rows = len(df)
            
            for idx, row in df.iterrows():
                progress = (idx + 1) / total_rows
                progress_bar.progress(progress)
                
                link = row[link_column]
                ean = row[ean_column]
                
                if pd.isna(link) or pd.isna(ean):
                    stats['puste_wiersze'] += 1
                    continue
                
                try:
                    ean = str(int(float(ean))).strip().replace(' ', '')
                except:
                    ean = str(ean).strip().replace(' ', '')
                
                if ean_filter_set and ean not in ean_filter_set:
                    stats['nieznalezione_ean'] += 1
                    continue
                
                found_eans.add(ean)
                status_text.text(f"Pobieranie: {ean} ({idx + 1}/{total_rows})")

                try:
                    parsed_url = urlparse(str(link))
                    extension = os.path.splitext(parsed_url.path)[1].lower()
                    
                    if extension == '.pdf' or '.pdf' in str(link).lower():
                        stats['pdf_pominięte'] += 1
                        pdf_eans.append(ean)
                        continue
                    
                    if not extension or extension not in ALLOWED_FORMATS:
                        extension = DEFAULT_FORMAT
                    
                    original_ext = extension
                    image_data = pobierz_obraz(str(link))
                    
                    # Obróbka obrazu
                    if handle_transparency and extension != '.webp':
                        processed = add_white_background(image_data)
                        if processed != image_data:
                            image_data = processed
                            stats['transparency_fixed'] += 1
                            transparency_processed.append(ean)
                    
                    if convert_webp and original_ext == '.webp':
                        image_data = convert_webp_to_png(image_data, remove_transparency=handle_transparency)
                        extension = '.png'
                        stats['konwersje'] += 1
                    
                    filename = f"{ean}{extension}"
                    if filename in downloaded_files and not overwrite:
                        stats['istnieje'] += 1
                        continue
                    
                    downloaded_files[filename] = image_data
                    stats['sukces'] += 1
                    
                except Exception as e:
                    err = f"EAN: {ean} | Błąd: {str(e)}"
                    errors_log.append(err)
                    log_expander.error(err)
                    stats['blad'] += 1
                
                # Zawsze czekaj, aby nie przeciążyć serwera
                time.sleep(delay_between)
            
            st.session_state.download_results = {
                'stats': stats, 'errors_log': errors_log, 'pdf_eans': pdf_eans,
                'downloaded_files': downloaded_files, 'missing_eans': ean_filter_set - found_eans if ean_filter_set else None,
                'transparency_processed': transparency_processed
            }
            st.rerun()

        # Wyświetlanie wyników
        if st.session_state.download_results:
            res = st.session_state.download_results
            s = res['stats']
            
            st.markdown("---")
            st.markdown("## 📊 Wyniki")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pobrane", s['sukces'])
            c2.metric("Błędy", s['blad'])
            c3.metric("Białe tło", s['transparency_fixed'])
            c4.metric("Pominięte PDF", s['pdf_pominięte'])
            
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
    st.info("💡 Wgraj plik Excel, aby rozpocząć. Pamiętaj, aby ustawić odpowiednie opóźnienie w panelu bocznym.")