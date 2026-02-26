import streamlit as st

# CSS dla lepszego wyglądu
st.markdown("""
<style>
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

# Pierwszy rząd - 3 kolumny
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class='tool-card'>
    <h3>📥 Pobieranie Okładek</h3>
    <p>Automatyczne pobieranie obrazów okładek produktów na podstawie linków z pliku Excel.</p>
    <ul>
        <li>✅ Wsparcie dla wielu formatów obrazów</li>
        <li>✅ Konwersja WebP na PNG + Usuwanie przezroczystego tła</li>
        <li>✅ Filtrowanie po kodach EAN</li>
        <li>✅ Eksport do ZIP</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Otwórz narzędzie pobierania", key="btn_covers", type="primary", icon="🚀", use_container_width=True):
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
    
    if st.button("Otwórz konwerter HTML", key="btn_html", type="primary", icon="🚀", use_container_width=True):
        st.switch_page("pages/2_zmiana_opisu_html.py")

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
    
    if st.button("Otwórz konwerter obrazów", key="btn_webp", type="primary", icon="🚀", use_container_width=True):
        st.switch_page("pages/3_konwerter_webp.py")

# Drugi rząd - 2 kolumny (wycentrowane)
col4, col5, col6 = st.columns([1, 2, 1])

with col5:
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("""
        <div class='tool-card'>
        <h3>🔍 Weryfikator Duplikatów</h3>
        <p>Wykrywanie duplikatów produktów na podstawie wydawcy, autora i podobieństwa nazwy.</p>
        <ul>
            <li>✅ Inteligentne wykrywanie (fuzzy matching)</li>
            <li>✅ Filtrowanie fałszywych duplikatów (5 reguł)</li>
            <li>✅ Grupowanie połączonych duplikatów</li>
            <li>✅ Raport Excel z kolorowaniem grup</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Otwórz weryfikator duplikatów", key="btn_duplicates", type="primary", icon="🚀", use_container_width=True):
            st.switch_page("pages/4_weryfikator_dubli.py")
    
    with col_right:
        st.markdown("""
        <div class='tool-card'>
        <h3>📚 Weryfikator Serii</h3>
        <p>Znajdowanie niekompletnych lub niespójnych informacji o seriach książek.</p>
        <ul>
            <li>✅ Wykrywa brak wypełnienia kolumny "Seria"</li>
            <li>✅ Znajduje niespójności w nazwach serii</li>
            <li>✅ Sugeruje prawidłowe nazwy serii</li>
            <li>✅ Raport Excel z rekomendacjami</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Otwórz weryfikator serii", key="btn_series", type="primary", icon="🚀", use_container_width=True):
            st.switch_page("pages/5_weryfikator_serii.py")

# Informacje dodatkowe
with st.expander("ℹ️ Informacje o aplikacji"):
    st.markdown("""
    ### 🛠️ Pakiet narzędzi do pracy z danymi produktowymi
    
    Ta aplikacja zawiera 5 narzędzi usprawniających pracę z danymi produktów w plikach Excel:
    
    1. **Pobieranie okładek** - automatyczne pobieranie obrazów produktów
    2. **Konwerter HTML** - konwersja opisów tekstowych na HTML
    3. **Konwerter obrazów** - konwersja formatów graficznych
    4. **Weryfikator duplikatów** - wykrywanie zduplikowanych produktów
    5. **Weryfikator serii** - znajdowanie problemów z seriami książek
    
    Każde narzędzie działa niezależnie i jest zoptymalizowane pod konkretne zadanie.
    """)

# Stopka
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>Made with ❤️ using Streamlit</div>",
    unsafe_allow_html=True
)