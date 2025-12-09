import streamlit as st

# Konfiguracja strony głównej
st.set_page_config(
    page_title="Narzędzia Excel",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS dla lepszego wyglądu
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .tool-card {
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #f0f2f6;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
        height: 100%;
    }
    .tool-card:hover {
        border-color: #1f77b4;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    .stButton > button {
        width: 100%;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Nagłówek
st.markdown("<div class='main-header'>🛠️ Narzędzia Excel & Grafika</div>", unsafe_allow_html=True)
st.markdown("---")

# Pierwszy rząd - 2 kolumny
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class='tool-card'>
    <h3>📥 Pobieranie Okładek</h3>
    <p>Automatyczne pobieranie obrazów okładek produktów na podstawie linków z pliku Excel.</p>
    <ul>
        <li>✅ Wsparcie dla wielu formatów obrazów</li>
        <li>✅ Konwersja WebP na PNG</li>
        <li>✅ Filtrowanie po kodach EAN</li>
        <li>✅ Eksport do ZIP</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Otwórz narzędzie pobierania", key="btn_covers", type="primary"):
        st.switch_page("pages/1_pobieranie_okladek.py")

with col2:
    st.markdown("""
    <div class='tool-card'>
    <h3>📝 Konwerter HTML</h3>
    <p>Konwersja opisów produktów z formatu tekstowego na HTML z zachowaniem formatowania.</p>
    <ul>
        <li>✅ Automatyczne wykrywanie nagłówków</li>
        <li>✅ Konwersja list punktowanych</li>
        <li>✅ Formatowanie tekstu (bold, italic)</li>
        <li>✅ Eksport do Excel</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Otwórz konwerter HTML", key="btn_html", type="primary"):
        st.switch_page("pages/2_zmiana_opisu_html.py")

# Drugi rząd - tylko 1 kolumna (trzecie narzędzie)
st.markdown("---")
col3, col4 = st.columns(2)

with col3:
    st.markdown("""
    <div class='tool-card'>
    <h3>🖼️ Konwerter WebP</h3>
    <p>Konwersja obrazów WebP i innych formatów graficznych z obsługą przetwarzania wsadowego.</p>
    <ul>
        <li>✅ Konwersja między formatami (WebP, PNG, JPG)</li>
        <li>✅ Przetwarzanie wielu plików jednocześnie</li>
        <li>✅ Regulacja jakości JPEG</li>
        <li>✅ Automatyczne pakowanie do ZIP</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Otwórz konwerter obrazów", key="btn_webp", type="primary"):
        st.switch_page("pages/3_konwerter_webp.py")

# Informacje dodatkowe
st.markdown("---")
with st.expander("ℹ️ Informacje o aplikacji"):
    st.markdown("""
    ### Dostępne narzędzia:
    
    #### 📥 Pobieranie okładek:
    - Automatyczne pobieranie obrazów z URL
    - Konwersja formatów (WebP → PNG)
    - Filtrowanie po kodach EAN
    - Pomijanie plików PDF
    - Raport z błędami i statystykami
    
    #### 📝 Konwerter HTML:
    - Konwersja markdown na HTML
    - Obsługa list i nagłówków
    - Formatowanie tekstu (bold, italic)
    - Zachowanie struktury dokumentu
    - Filtrowanie po kodach EAN
    
    #### 🖼️ Konwerter WebP:
    - Konwersja między popularnymi formatami obrazów
    - Wsadowe przetwarzanie wielu plików
    - Regulowana jakość kompresji
    - Automatyczna obsługa przezroczystości
    - Inteligentne pakowanie do ZIP
    
    ### Wymagania:
    - Format plików Excel: `.xlsx` lub `.xls`
    - Formaty obrazów: WebP, PNG, JPG, BMP, GIF, TIFF
    - Kodowanie UTF-8 dla polskich znaków
    """)

# Statystyki użycia
with st.expander("📊 Statystyki"):
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Dostępne narzędzia", "3", "🛠️")
    
    with col2:
        st.metric("Formaty Excel", "XLSX, XLS", "📄")
    
    with col3:
        st.metric("Formaty obrazów", "6+", "🖼️")
    
    with col4:
        st.metric("Wersja", "1.1.0", "🔧")

# Stopka
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>Made with ❤️ using Streamlit</div>",
    unsafe_allow_html=True
)