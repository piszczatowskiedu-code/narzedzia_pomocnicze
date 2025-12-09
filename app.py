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
st.markdown("<div class='main-header'>🛠️ Narzędzia Excel</div>", unsafe_allow_html=True)
st.markdown("---")

# Wprowadzenie
st.markdown("""
### Witaj w zestawie narzędzi do przetwarzania plików Excel!

Wybierz narzędzie poniżej lub z menu bocznego, aby rozpocząć.
""")

# Karty z narzędziami - teraz jako klikalne elementy
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

# Sekcja z szybkimi linkami
st.markdown("---")
st.markdown("### 🔗 Szybkie linki do narzędzi")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.page_link("pages/1_pobieranie_okladek.py", 
                 label="📥 Pobieranie okładek", 
                 icon="📥",
                 use_container_width=True)

with col2:
    st.page_link("pages/2_zmiana_opisu_html.py", 
                 label="📝 Konwerter HTML", 
                 icon="📝",
                 use_container_width=True)

with col3:
    st.info("🔜 Więcej narzędzi wkrótce...")

with col4:
    st.info("💡 Masz pomysł? Zgłoś!")

# Instrukcja
st.markdown("---")
st.markdown("### 📖 Jak korzystać?")

col1, col2, col3 = st.columns(3)

with col1:
    st.info("""
    **Krok 1:**  
    Kliknij przycisk przy wybranym narzędziu lub wybierz z menu bocznego
    """)

with col2:
    st.info("""
    **Krok 2:**  
    Wgraj plik Excel z danymi
    """)

with col3:
    st.info("""
    **Krok 3:**  
    Skonfiguruj opcje i uruchom przetwarzanie
    """)

# Informacje dodatkowe
with st.expander("ℹ️ Informacje o aplikacji"):
    st.markdown("""
    ### Wymagania dla plików Excel:
    - Format: `.xlsx` lub `.xls`
    - Kodowanie UTF-8 dla polskich znaków
    - Nagłówki kolumn w pierwszym wierszu
    
    ### Wspierane funkcje:
    
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
    
    ### Wsparcie techniczne:
    - W razie problemów sprawdź format pliku
    - Upewnij się, że kolumny mają poprawne nazwy
    - Sprawdź połączenie internetowe (dla pobierania okładek)
    """)

# Statystyki użycia (opcjonalne)
with st.expander("📊 Statystyki użycia"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Dostępne narzędzia", "2", "🛠️")
    
    with col2:
        st.metric("Obsługiwane formaty", "XLSX, XLS", "📄")
    
    with col3:
        st.metric("Wersja aplikacji", "1.0.0", "🔧")

# Stopka
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>Made with ❤️ using Streamlit</div>",
    unsafe_allow_html=True
)