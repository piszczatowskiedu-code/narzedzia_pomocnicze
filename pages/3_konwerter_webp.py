import streamlit as st
from PIL import Image
import io
import zipfile
from datetime import datetime

# ============================================
# KONFIGURACJA STRONY
# ============================================
st.set_page_config(
    page_title="Konwerter WebP",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #28a745;
        text-align: center;
        margin-bottom: 1rem;
    }
    .upload-box {
        border: 2px dashed #ccc;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# FUNKCJE POMOCNICZE
# ============================================

def convert_image(image_bytes, input_format, output_format, quality=95):
    """Konwertuje obraz do wybranego formatu"""
    try:
        # Otwórz obraz
        image = Image.open(io.BytesIO(image_bytes))
        
        # Konwersja RGBA na RGB jeśli potrzeba (dla JPEG)
        if output_format.upper() in ['JPEG', 'JPG'] and image.mode in ('RGBA', 'LA', 'P'):
            # Utwórz białe tło
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Konwertuj
        output = io.BytesIO()
        save_format = 'JPEG' if output_format.upper() == 'JPG' else output_format.upper()
        
        if save_format == 'JPEG':
            image.save(output, format=save_format, quality=quality, optimize=True)
        else:
            image.save(output, format=save_format, optimize=True)
        
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Błąd konwersji: {str(e)}")

def create_zip(files_dict):
    """Tworzy archiwum ZIP z plików"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, file_data in files_dict.items():
            zip_file.writestr(filename, file_data)
    zip_buffer.seek(0)
    return zip_buffer

def get_image_info(image_bytes):
    """Zwraca informacje o obrazie"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return {
            'size': image.size,
            'mode': image.mode,
            'format': image.format,
            'size_kb': len(image_bytes) / 1024
        }
    except:
        return None

# ============================================
# INTERFEJS UŻYTKOWNIKA
# ============================================

# Nagłówek
st.markdown("<div class='main-header'>🖼️ Konwerter WebP</div>", unsafe_allow_html=True)
st.markdown("---")

# Sidebar z opcjami
with st.sidebar:
    st.header("⚙️ Ustawienia konwersji")
    
    # Format wyjściowy
    output_format = st.selectbox(
        "Format wyjściowy:",
        ["PNG", "JPG", "BMP", "TIFF"],
        index=0,
        help="Wybierz format docelowy"
    )
    
    # Jakość (tylko dla JPEG)
    quality = 95
    if output_format == "JPG":
        quality = st.slider(
            "Jakość JPEG:",
            min_value=10,
            max_value=100,
            value=95,
            step=5,
            help="Wyższa wartość = lepsza jakość, większy plik"
        )
    
    # Opcje nazewnictwa
    st.markdown("---")
    st.markdown("### 📝 Nazewnictwo")
    
    keep_original_name = st.checkbox(
        "Zachowaj oryginalną nazwę",
        value=True,
        help="Zachowuje nazwę pliku, zmienia tylko rozszerzenie"
    )
    
    if not keep_original_name:
        prefix = st.text_input("Prefiks:", value="converted_")
    else:
        prefix = ""

# Główna część aplikacji
st.markdown("### 📤 Wybierz pliki do konwersji")

# Upload plików
uploaded_files = st.file_uploader(
    "Wybierz obrazy WebP",
    type=['webp', 'jpg', 'jpeg', 'png', 'bmp', 'gif', 'tiff'],
    accept_multiple_files=True,
    help="Możesz wybrać wiele plików jednocześnie. Obsługiwane formaty: WebP, JPG, PNG, BMP, GIF, TIFF"
)

if uploaded_files:
    # Pokaż informacje o wgranych plikach
    st.info(f"📁 Wybrano **{len(uploaded_files)}** plików")
    
    # Tabela z informacjami o plikach
    with st.expander("📋 Lista plików"):
        for i, file in enumerate(uploaded_files, 1):
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                st.text(f"{i}.")
            with col2:
                st.text(file.name)
            with col3:
                st.text(f"{file.size / 1024:.1f} KB")
    
    # Przycisk konwersji
    st.markdown("---")
    
    if st.button(f"🚀 KONWERTUJ DO {output_format}", type="primary", use_container_width=True):
        converted_files = {}
        errors = []
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Konwertuj każdy plik
        for idx, uploaded_file in enumerate(uploaded_files):
            progress = (idx + 1) / len(uploaded_files)
            progress_bar.progress(progress)
            status_text.text(f"Konwertuję: {uploaded_file.name} ({idx + 1}/{len(uploaded_files)})")
            
            try:
                # Odczytaj plik
                file_bytes = uploaded_file.read()
                
                # Pobierz format wejściowy
                input_format = uploaded_file.name.split('.')[-1].upper()
                
                # Konwertuj
                if output_format == "JPG":
                    converted_bytes = convert_image(file_bytes, input_format, output_format, quality)
                else:
                    converted_bytes = convert_image(file_bytes, input_format, output_format)
                
                # Ustal nazwę pliku wyjściowego
                if keep_original_name:
                    base_name = uploaded_file.name.rsplit('.', 1)[0]
                    output_filename = f"{base_name}.{output_format.lower()}"
                else:
                    base_name = uploaded_file.name.rsplit('.', 1)[0]
                    output_filename = f"{prefix}{base_name}.{output_format.lower()}"
                
                converted_files[output_filename] = converted_bytes
                
            except Exception as e:
                errors.append(f"❌ {uploaded_file.name}: {str(e)}")
        
        # Zakończenie
        progress_bar.progress(1.0)
        status_text.text("✅ Konwersja zakończona!")
        
        # Pokaż błędy jeśli wystąpiły
        if errors:
            st.warning(f"⚠️ Wystąpiły błędy w {len(errors)} plikach")
            with st.expander("Zobacz błędy"):
                for error in errors:
                    st.text(error)
        
        # Statystyki konwersji
        if converted_files:
            st.markdown("---")
            
            # Pokaż statystyki
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Skonwertowano", len(converted_files))
            with col2:
                total_size = sum(len(data) for data in converted_files.values())
                st.metric("Całkowity rozmiar", f"{total_size / (1024*1024):.1f} MB")
            with col3:
                st.metric("Format wyjściowy", output_format)
            
            # Pobieranie
            st.markdown("---")
            st.markdown("### 💾 Pobierz skonwertowane pliki")
            
            if len(converted_files) == 1:
                # Pojedynczy plik - bezpośrednie pobieranie
                filename = list(converted_files.keys())[0]
                file_data = list(converted_files.values())[0]
                
                st.download_button(
                    label=f"⬇️ POBIERZ {filename}",
                    data=file_data,
                    file_name=filename,
                    mime=f"image/{output_format.lower()}",
                    use_container_width=True,
                    type="primary"
                )
            else:
                # Wiele plików - tworzenie ZIP
                zip_buffer = create_zip(converted_files)
                zip_filename = f"converted_images_{output_format.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                
                st.download_button(
                    label=f"⬇️ POBIERZ ZIP ({len(converted_files)} plików)",
                    data=zip_buffer,
                    file_name=zip_filename,
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
            
            # Lista skonwertowanych plików
            with st.expander(f"📋 Skonwertowane pliki ({len(converted_files)})"):
                for i, (filename, file_data) in enumerate(converted_files.items(), 1):
                    col1, col2, col3 = st.columns([1, 4, 2])
                    with col1:
                        st.text(f"{i}.")
                    with col2:
                        st.text(filename)
                    with col3:
                        st.text(f"{len(file_data) / 1024:.1f} KB")

else:
    # Ekran powitalny
    st.info("📤 Wybierz pliki graficzne do konwersji")
    
    # Informacje o wspieranych formatach
    with st.expander("ℹ️ Informacje o konwerterze"):
        st.markdown("""
        ### Wspierane formaty wejściowe:
        - **WebP** - nowoczesny format Google
        - **JPG/JPEG** - uniwersalny format ze stratną kompresją
        - **PNG** - format z bezstratną kompresją
        - **BMP** - format bitmap
        - **GIF** - format z animacjami
        - **TIFF** - format wysokiej jakości
        
        ### Formaty wyjściowe:
        - **PNG** - najlepsza jakość, przezroczystość
        - **JPG** - mniejsze pliki, regulowana jakość
        - **BMP** - format bez kompresji
        - **TIFF** - profesjonalna jakość
        
        ### Funkcje:
        - ✅ Konwersja wielu plików jednocześnie
        - ✅ Automatyczna konwersja RGBA → RGB dla JPEG
        - ✅ Zachowanie oryginalnych nazw plików
        - ✅ Regulacja jakości dla JPEG
        - ✅ Automatyczne pakowanie do ZIP przy wielu plikach
        """)

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>🖼️ Konwerter obrazów</div>",
    unsafe_allow_html=True
)