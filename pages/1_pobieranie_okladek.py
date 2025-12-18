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
    page_title="Pobieranie okładek",
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
DELAY_BETWEEN_DOWNLOADS = 1.0
TIMEOUT = 30
ALLOWED_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
DEFAULT_FORMAT = '.jpg'

def has_transparency(image):
    """Sprawdza czy obraz ma przezroczystość"""
    if image.mode in ('RGBA', 'LA'):
        # Sprawdź czy faktycznie używa przezroczystości
        if image.mode == 'RGBA':
            alpha = image.split()[-1]
            if alpha.getextrema() != (255, 255):
                return True
        elif image.mode == 'LA':
            alpha = image.split()[-1]
            if alpha.getextrema() != (255, 255):
                return True
    elif image.mode == 'P':
        # Sprawdź czy paleta ma przezroczystość
        if 'transparency' in image.info:
            return True
    return False

def add_white_background(image_bytes):
    """Dodaje białe tło do obrazu z przezroczystością"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Sprawdź czy obraz ma przezroczystość
        if not has_transparency(image):
            # Obraz nie ma przezroczystości, zwróć oryginalny
            return image_bytes
        
        # Konwertuj do RGBA jeśli potrzeba
        if image.mode != 'RGBA':
            if image.mode == 'P':
                image = image.convert('RGBA')
            elif image.mode == 'LA':
                image = image.convert('RGBA')
        
        # Utwórz białe tło
        background = Image.new('RGBA', image.size, (255, 255, 255, 255))
        
        # Złącz obraz z tłem
        background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
        
        # Konwertuj do RGB (usuń kanał alpha)
        final_image = background.convert('RGB')
        
        # Zapisz do bytes
        output = io.BytesIO()
        # Zachowaj format oryginalny jeśli to możliwe
        format_to_save = 'JPEG' if image.format in ['JPEG', 'JPG'] else 'PNG'
        final_image.save(output, format=format_to_save, quality=95, optimize=True)
        return output.getvalue()
        
    except Exception as e:
        # W razie błędu zwróć oryginalny obraz
        return image_bytes

def convert_webp_to_png(image_bytes, remove_transparency=False):
    """Konwertuje obraz WebP na PNG z opcjonalnym usunięciem przezroczystości"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Jeśli ma usunąć przezroczystość i obraz ją ma
        if remove_transparency and has_transparency(image):
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode in ('RGBA', 'LA'):
            # Zachowaj przezroczystość ale konwertuj format
            pass
        else:
            # Konwertuj do RGB jeśli nie ma przezroczystości
            if image.mode != 'RGB':
                image = image.convert('RGB')
        
        output = io.BytesIO()
        image.save(output, format='PNG', optimize=True)
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Błąd konwersji WebP: {e}")

def pobierz_obraz(url, timeout=TIMEOUT):
    """Pobiera obraz z URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers, timeout=timeout, stream=True)
    response.raise_for_status()
    return response.content

def create_zip_from_memory(files_dict):
    """Tworzy archiwum ZIP z plików w pamięci"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, file_data in files_dict.items():
            zip_file.writestr(filename, file_data)
    zip_buffer.seek(0)
    return zip_buffer

def parse_ean_list(ean_text):
    """Parsuje listę kodów EAN z tekstu"""
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

# Nagłówek
st.markdown("<div class='main-header'>📥 Pobieranie okładek z Excel</div>", unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Ustawienia")
    
    # Sekcja przezroczystości - uproszczona
    handle_transparency = st.checkbox(
        "Dodaj białe tło do przezroczystych obrazów",
        value=True,
        help="Automatycznie wykrywa obrazy z przezroczystym tłem i dodaje białe tło"
    )
    
    # Sekcja konwersji WebP
    convert_webp = st.checkbox(
        "Konwertuj .webp na .png",
        value=True,
        help="Automatycznie konwertuje obrazy WebP do formatu PNG"
    )
    
    # Sekcja plików
    overwrite = st.checkbox(
        "Nadpisuj istniejące pliki",
        value=False,
        help="Pobierz ponownie pliki, które już istnieją"
    )
    
    st.markdown("---")
    st.markdown("### 📋 Instrukcja")
    st.markdown("""
    1. Wgraj plik Excel
    2. Wybierz kolumny z danymi
    3. Opcjonalnie: wklej listę EAN
    4. Kliknij 'Pobierz okładki'
    5. Pobierz archiwum ZIP
    """)
    
    st.markdown("---")
    st.markdown("### ℹ️ Informacje")
    st.info("Aplikacja automatycznie pomija puste wiersze, pliki PDF i nieprawidłowe linki.")
    
    if st.session_state.download_results:
        st.markdown("---")
        if st.button("🗑️ Wyczyść raport", type="secondary"):
            st.session_state.download_results = None
            st.rerun()

# Główna część aplikacji
uploaded_file = st.file_uploader(
    "Wybierz plik Excel",
    type=['xlsx', 'xls'],
    help="Obsługiwane formaty: .xlsx, .xls"
)

if uploaded_file is not None:
    try:
        with st.spinner("Wczytywanie pliku..."):
            df = pd.read_excel(uploaded_file)
        
        st.success(f"✅ Wczytano: **{uploaded_file.name}** | Wierszy: **{len(df)}** | Kolumn: **{len(df.columns)}**")
        
        # Konfiguracja - wybór kolumn
        st.markdown("### 🎯 Wybór kolumn")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ean_column = st.selectbox(
                "Kolumna z kodami EAN",
                options=df.columns.tolist(),
                index=df.columns.tolist().index('EAN') if 'EAN' in df.columns else 0,
                help="Wybierz kolumnę zawierającą unikalne kody EAN"
            )
            
            st.markdown("**Przykładowa wartość:**")
            sample_ean = df[ean_column].dropna().head(1).tolist()
            if sample_ean:
                ean_value = sample_ean[0]
                try:
                    ean_value = str(int(float(ean_value)))
                except (ValueError, OverflowError):
                    ean_value = str(ean_value)
                st.code(ean_value, language=None)
        
        with col2:
            link_column = st.selectbox(
                "Kolumna z linkami do okładek",
                options=df.columns.tolist(),
                index=df.columns.tolist().index('Link do okładki') if 'Link do okładki' in df.columns else 0,
                help="Wybierz kolumnę zawierającą URL do obrazów"
            )
            
            st.markdown("**Przykładowa wartość:**")
            sample_links = df[link_column].dropna().head(1).tolist()
            if sample_links:
                st.code(str(sample_links[0])[:70] + "...", language=None)
        
        # Sekcja filtrowania EAN
        st.markdown("---")
        st.markdown("### 🔍 Filtrowanie po kodach EAN (opcjonalne)")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            ean_filter_text = st.text_area(
                "Wklej kody EAN do pobrania (jeden kod na linię)",
                height=150,
                placeholder="5901234567890\n5907654321098\n9788374959216",
                help="Jeśli wpiszesz kody EAN, tylko te produkty zostaną pobrane. Zostaw puste aby pobrać wszystkie."
            )
        
        with col2:
            if ean_filter_text:
                ean_filter_set = parse_ean_list(ean_filter_text)
                st.info(f"📝 Wprowadzono kodów: **{len(ean_filter_set)}**")
                
                df_eans = df[ean_column].dropna().apply(lambda x: str(int(float(x))) if pd.notna(x) else '')
                matching = sum(1 for ean in df_eans if ean in ean_filter_set)
                st.success(f"✅ Znaleziono w pliku: **{matching}**")
                
                if matching == 0:
                    st.warning("⚠️ Żaden z podanych kodów nie został znaleziony!")
            else:
                st.info("🔓 Filtr nieaktywny\n\nPobrane zostaną wszystkie produkty")
        
        # Przycisk pobierania
        st.markdown("---")
        st.markdown("### 🚀 Rozpocznij pobieranie")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            start_download = st.button(
                "📥 POBIERZ OKŁADKI",
                type="primary",
                width="stretch"
            )
        
        if start_download:
            downloaded_files = {}
            ean_filter_set = parse_ean_list(ean_filter_text) if ean_filter_text else None
            found_eans = set()
            
            # Statystyki
            stats = {
                'sukces': 0,
                'blad': 0,
                'istnieje': 0,  
                'konwersje': 0,
                'transparency_fixed': 0,  # Licznik obrazów z dodanym tłem
                'nieznalezione_ean': 0,
                'pdf_pominięte': 0,
                'puste_wiersze': 0
            }
            
            errors_log = []
            pdf_eans = []
            transparency_processed = []  # Lista EAN z usuniętą przezroczystością
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            log_expander = st.expander("⚠️ Błędy i ostrzeżenia", expanded=False)
            log_container = log_expander.container()
            
            total_rows = len(df)
            
            for idx, row in df.iterrows():
                progress = (idx + 1) / total_rows
                progress_bar.progress(progress)
                status_text.text(f"Przetwarzanie: {idx + 1}/{total_rows} ({progress*100:.1f}%)")
                
                link = row[link_column]
                ean = row[ean_column]
                
                if pd.isna(link) or pd.isna(ean):
                    stats['puste_wiersze'] += 1
                    continue
                
                try:
                    ean = str(int(float(ean))).strip().replace(' ', '')
                except (ValueError, OverflowError):
                    ean = str(ean).strip().replace(' ', '')
                
                if ean_filter_set:
                    if ean not in ean_filter_set:
                        stats['nieznalezione_ean'] += 1
                        continue
                    else:
                        found_eans.add(ean)
                
                link_lower = str(link).lower()
                if '.pdf' in link_lower:
                    with log_container:
                        st.warning(f"EAN {ean}: Pominięto - link prowadzi do pliku PDF")
                    stats['pdf_pominięte'] += 1
                    pdf_eans.append(ean)
                    continue
                
                try:
                    parsed_url = urlparse(str(link))
                    extension = os.path.splitext(parsed_url.path)[1].lower()
                    
                    if extension == '.pdf':
                        with log_container:
                            st.warning(f"EAN {ean}: Pominięto - link prowadzi do pliku PDF")
                        stats['pdf_pominięte'] += 1
                        pdf_eans.append(ean)
                        continue
                    
                    if not extension or extension not in ALLOWED_FORMATS:
                        extension = DEFAULT_FORMAT
                    
                    original_extension = extension
                    
                    # Pobierz obraz
                    image_data = pobierz_obraz(link)
                    
                    # Obsługa przezroczystości (przed konwersją WebP)
                    if handle_transparency and extension != '.webp':
                        original_size = len(image_data)
                        processed_data = add_white_background(image_data)
                        
                        # Sprawdź czy obraz został przetworzony
                        if len(processed_data) != original_size or processed_data != image_data:
                            image_data = processed_data
                            stats['transparency_fixed'] += 1
                            transparency_processed.append(ean)
                    
                    # Konwersja WebP
                    if convert_webp and original_extension == '.webp':
                        # Sprawdź czy WebP ma przezroczystość przed konwersją
                        if handle_transparency:
                            temp_img = Image.open(io.BytesIO(image_data))
                            had_transparency = has_transparency(temp_img)
                        
                        image_data = convert_webp_to_png(
                            image_data, 
                            remove_transparency=handle_transparency
                        )
                        extension = '.png'
                        stats['konwersje'] += 1
                        
                        # Jeśli WebP miał przezroczystość i została usunięta
                        if handle_transparency and had_transparency:
                            stats['transparency_fixed'] += 1
                            transparency_processed.append(ean)
                    
                    filename = f"{ean}{extension}"
                    
                    if filename in downloaded_files and not overwrite:
                        stats['istnieje'] += 1  
                        continue
                    
                    downloaded_files[filename] = image_data
                    stats['sukces'] += 1
                    time.sleep(DELAY_BETWEEN_DOWNLOADS)
                    
                except Exception as e:
                    error_msg = f"EAN: {ean} | Błąd: {str(e)}"
                    errors_log.append(error_msg)
                    with log_container:
                        st.error(error_msg)
                    stats['blad'] += 1
            
            progress_bar.progress(1.0)
            status_text.text("✅ Pobieranie zakończone!")
            
            missing_eans = None
            if ean_filter_set:
                missing_eans = ean_filter_set - found_eans
            
            st.session_state.download_results = {
                'stats': stats,
                'errors_log': errors_log,
                'pdf_eans': pdf_eans,
                'downloaded_files': downloaded_files,
                'missing_eans': missing_eans,
                'ean_filter_set': ean_filter_set,
                'transparency_processed': transparency_processed
            }
        
        # Wyświetl wyniki
        if st.session_state.download_results:
            results = st.session_state.download_results
            stats = results['stats']
            errors_log = results['errors_log']
            pdf_eans = results['pdf_eans']
            downloaded_files = results['downloaded_files']
            missing_eans = results['missing_eans']
            ean_filter_set = results['ean_filter_set']
            transparency_processed = results.get('transparency_processed', [])
            
            st.markdown("---")
            st.markdown("## 📊 Raport końcowy")
            
            # Statystyki
            cols_data = []
            if stats['sukces'] > 0:
                cols_data.append(("✅ Pobrane", stats['sukces']))
            if stats.get('transparency_fixed', 0) > 0:
                cols_data.append(("🎨 Dodano białe tło", stats['transparency_fixed']))
            if stats['konwersje'] > 0:
                cols_data.append(("🔄 Konwersje WebP", stats['konwersje']))
            if stats['blad'] > 0:
                cols_data.append(("❌ Błędy", stats['blad']))
            if stats['istnieje'] > 0:
                cols_data.append(("📁 Już istnieje", stats['istnieje']))
            if ean_filter_set and stats['nieznalezione_ean'] > 0:
                cols_data.append(("🔍 Poza filtrem", stats['nieznalezione_ean']))
            if stats['pdf_pominięte'] > 0:
                cols_data.append(("📄 Pliki PDF", stats['pdf_pominięte']))
            
            if cols_data:
                cols = st.columns(len(cols_data))
                for i, (label, value) in enumerate(cols_data):
                    cols[i].metric(label, value)
            
            # Lista obrazów z dodanym tłem
            if transparency_processed and handle_transparency:
                with st.expander(f"🎨 Obrazy z dodanym białym tłem ({len(transparency_processed)})"):
                    st.info("Wykryto i usunięto przezroczystość w poniższych obrazach")
                    trans_text = '\n'.join(transparency_processed[:100])
                    st.text_area(
                        "Lista kodów EAN:",
                        value=trans_text,
                        height=min(150, len(transparency_processed) * 20),
                        help="Obrazy tych produktów miały przezroczyste tło"
                    )
                    if len(transparency_processed) > 100:
                        st.text(f"... i {len(transparency_processed) - 100} więcej")
            
            # Błędy
            if errors_log:
                with st.expander(f"❌ Lista błędów ({len(errors_log)})"):
                    for error in errors_log:
                        st.text(error)
            
            # Lista pominiętych PDF
            if pdf_eans:
                with st.expander(f"📄 Pominięte pliki PDF ({len(pdf_eans)})"):
                    st.info("Następujące produkty mają linki do plików PDF zamiast obrazów:")
                    pdf_text = '\n'.join(pdf_eans)
                    st.text_area(
                        "Lista kodów EAN z linkami PDF:",
                        value=pdf_text,
                        height=150,
                        help="Te produkty wymagają ręcznego pozyskania obrazów okładek"
                    )
            
            # Brakujące EAN
            if missing_eans:
                st.markdown("---")
                st.markdown("### ⚠️ Kody EAN nieznalezione w pliku Excel")
                st.warning(f"Następujące kody EAN nie zostały znalezione ({len(missing_eans)} kodów):")
                
                missing_eans_text = '\n'.join(sorted(list(missing_eans)))
                st.text_area(
                    "Lista brakujących kodów EAN:",
                    value=missing_eans_text,
                    height=200,
                    help="Możesz skopiować tę listę i przekazać do uzupełnienia"
                )
            
            # Download ZIP
            if stats['sukces'] > 0:
                st.markdown("### 💾 Pobierz archiwum")
                
                with st.spinner("Tworzenie archiwum ZIP..."):
                    zip_buffer = create_zip_from_memory(downloaded_files)
                
                zip_filename = f"okladki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                
                st.download_button(
                    label=f"⬇️ Pobierz {stats['sukces']} plików (ZIP)",
                    data=zip_buffer,
                    file_name=zip_filename,
                    mime="application/zip",
                    width="stretch",
                    type="primary"
                )
                
                with st.expander(f"📋 Lista pobranych plików ({stats['sukces']})"):
                    for i, filename in enumerate(sorted(downloaded_files.keys()), 1):
                        st.text(f"{i}. {filename}")
            else:
                st.warning("Nie pobrano żadnych plików")
    
    except Exception as e:
        st.error(f"❌ Błąd: {str(e)}")
        st.exception(e)

else:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.info("📤 Wgraj plik Excel, aby rozpocząć")
        
        with st.expander("📋 Wymagana struktura pliku Excel"):
            example_df = pd.DataFrame({
                'EAN': ['5901234567890', '5907654321098', '9788374959216'],
                'Link do okładki': [
                    'https://example.com/image1.jpg',
                    'https://example.com/image2.png',
                    'https://example.com/image3.webp'
                ]
            })
            st.dataframe(example_df, width="stretch")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>📥 Moduł pobierania okładek</div>",
    unsafe_allow_html=True
)