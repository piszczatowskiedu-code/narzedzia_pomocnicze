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
    page_title="Pobieranie okładek z Excel",
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
</style>
""", unsafe_allow_html=True)

# STAŁE KONFIGURACYJNE
DELAY_BETWEEN_DOWNLOADS = 1.0  # sekund między pobraniami
TIMEOUT = 30  # timeout dla requestów w sekundach
ALLOWED_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
DEFAULT_FORMAT = '.jpg'  # domyślny format gdy nieznany

def convert_webp_to_png(image_bytes):
    """Konwertuje obraz WebP na PNG"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Konwersja RGBA na RGB jeśli potrzeba
        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        
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

def create_zip(folder_path):
    """Tworzy archiwum ZIP z pobranych plików"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zip_file.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

# Nagłówek
st.markdown("<div class='main-header'>📥 Pobieranie okładek z Excel</div>", unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Ustawienia")
    
    # Sekcja konwersji
    convert_webp = st.checkbox(
        "🔄 Konwertuj .webp na .png",
        value=True,
        help="Automatycznie konwertuje obrazy WebP do formatu PNG"
    )
    
    # Sekcja plików
    overwrite = st.checkbox(
        "📁 Nadpisuj istniejące pliki",
        value=False,
        help="Pobierz ponownie pliki, które już istnieją"
    )
    
    st.markdown("---")
    st.markdown("### 📖 Instrukcja")
    st.markdown("""
    1. 📤 Wgraj plik Excel
    2. 🎯 Wybierz kolumny z danymi
    3. 🚀 Kliknij 'Pobierz okładki'
    4. ⬇️ Pobierz archiwum ZIP
    """)
    
    st.markdown("---")
    st.markdown("### ℹ️ Informacje")
    st.info("Aplikacja automatycznie pomija puste wiersze i nieprawidłowe linki.")

# Główna część aplikacji
uploaded_file = st.file_uploader(
    "📤 Wybierz plik Excel",
    type=['xlsx', 'xls'],
    help="Obsługiwane formaty: .xlsx, .xls"
)

if uploaded_file is not None:
    try:
        # Wczytanie pliku
        with st.spinner("Wczytywanie pliku..."):
            df = pd.read_excel(uploaded_file)
        
        st.success(f"✅ Wczytano: **{uploaded_file.name}** | Wierszy: **{len(df)}** | Kolumn: **{len(df.columns)}**")
        
        # Konfiguracja - wybór kolumn
        st.markdown("### 🎯 Wybór kolumn")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ean_column = st.selectbox(
                "📌 Kolumna z kodami EAN",
                options=df.columns.tolist(),
                index=df.columns.tolist().index('EAN') if 'EAN' in df.columns else 0,
                help="Wybierz kolumnę zawierającą unikalne kody EAN"
            )
            
            # Preview EAN
            st.markdown("**Przykładowe wartości:**")
            sample_ean = df[ean_column].dropna().head(3).tolist()
            for ean in sample_ean:
                st.code(str(ean), language=None)
        
        with col2:
            link_column = st.selectbox(
                "🔗 Kolumna z linkami do okładek",
                options=df.columns.tolist(),
                index=df.columns.tolist().index('Link do okładki') if 'Link do okładki' in df.columns else 0,
                help="Wybierz kolumnę zawierającą URL do obrazów"
            )
            
            # Preview links
            st.markdown("**Przykładowe wartości:**")
            sample_links = df[link_column].dropna().head(3).tolist()
            for link in sample_links:
                st.code(str(link)[:50] + "...", language=None)
        
        # Przycisk pobierania
        st.markdown("---")
        st.markdown("### 🚀 Rozpocznij pobieranie")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            start_download = st.button(
                "📥 POBIERZ OKŁADKI",
                type="primary",
                use_container_width=True
            )
        
        if start_download:
            # Utworzenie folderu
            output_folder = f"okladki_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(output_folder, exist_ok=True)
            
            # Statystyki
            stats = {
                'sukces': 0,
                'blad': 0,
                'pominięto': 0,
                'konwersje': 0
            }
            
            errors_log = []
            
            # Progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Logi - tylko błędy
            log_expander = st.expander("⚠️ Błędy i ostrzeżenia", expanded=False)
            log_container = log_expander.container()
            
            total_rows = len(df)
            
            for idx, row in df.iterrows():
                progress = (idx + 1) / total_rows
                progress_bar.progress(progress)
                status_text.text(f"⏳ Przetwarzanie: {idx + 1}/{total_rows} ({progress*100:.1f}%)")
                
                link = row[link_column]
                ean = row[ean_column]
                
                if pd.isna(link) or pd.isna(ean):
                    with log_container:
                        st.warning(f"⚠️ Wiersz {idx + 2}: Brak danych")
                    stats['pominięto'] += 1
                    continue
                
                try:
                    ean = str(int(float(ean))).strip().replace(' ', '')
                except (ValueError, OverflowError):
                    ean = str(ean).strip().replace(' ', '')
                
                try:
                    parsed_url = urlparse(str(link))
                    extension = os.path.splitext(parsed_url.path)[1].lower()
                    
                    if not extension or extension not in ALLOWED_FORMATS:
                        extension = DEFAULT_FORMAT
                    
                    original_extension = extension
                    if convert_webp and extension == '.webp':
                        extension = '.png'
                    
                    filename = f"{ean}{extension}"
                    filepath = os.path.join(output_folder, filename)
                    
                    if os.path.exists(filepath) and not overwrite:
                        stats['pominięto'] += 1
                        continue
                    
                    image_data = pobierz_obraz(link)
                    
                    if convert_webp and original_extension == '.webp':
                        image_data = convert_webp_to_png(image_data)
                        stats['konwersje'] += 1
                    
                    with open(filepath, 'wb') as f:
                        f.write(image_data)
                    
                    stats['sukces'] += 1
                    time.sleep(DELAY_BETWEEN_DOWNLOADS)
                    
                except Exception as e:
                    error_msg = f"EAN: {ean} | Błąd: {str(e)}"
                    errors_log.append(error_msg)
                    with log_container:
                        st.error(f"❌ {error_msg}")
                    stats['blad'] += 1
            
            # Zakończenie
            progress_bar.progress(1.0)
            status_text.text("✅ Pobieranie zakończone!")
            
            # Finalne podsumowanie
            st.markdown("---")
            st.markdown("## 📊 Raport końcowy")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("✅ Pobrane", stats['sukces'], delta=None)
            col2.metric("❌ Błędy", stats['blad'], delta=None)
            col3.metric("⏭️ Pominięte", stats['pominięto'], delta=None)
            col4.metric("🔄 Konwersje WebP", stats['konwersje'], delta=None)
            
            # Błędy
            if errors_log:
                with st.expander(f"❌ Lista błędów ({len(errors_log)})"):
                    for error in errors_log:
                        st.text(error)
            
            # Download ZIP
            if stats['sukces'] > 0:
                st.markdown("### 📦 Pobierz archiwum")
                
                with st.spinner("📦 Tworzenie archiwum ZIP..."):
                    zip_buffer = create_zip(output_folder)
                
                zip_filename = f"okladki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                
                st.download_button(
                    label=f"⬇️ Pobierz {stats['sukces']} plików (ZIP)",
                    data=zip_buffer,
                    file_name=zip_filename,
                    mime="application/zip",
                    use_container_width=True
                )
                
                # Lista plików
                with st.expander(f"📋 Lista pobranych plików ({stats['sukces']})"):
                    files = sorted(os.listdir(output_folder))
                    for i, file in enumerate(files, 1):
                        st.text(f"{i}. {file}")
            else:
                st.warning("⚠️ Nie pobrano żadnych plików")
    
    except Exception as e:
        st.error(f"❌ Błąd: {str(e)}")
        st.exception(e)

else:
    # Ekran powitalny
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.info("👆 Wgraj plik Excel, aby rozpocząć")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>Made with ❤️ using Streamlit</div>",
    unsafe_allow_html=True
)