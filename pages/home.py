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

# Drugi rząd - 3 kolumny
col4, col5, col6 = st.columns(3)

with col4:
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

with col5:
    st.markdown("""
    <div class='tool-card'>
    <h3>📚 Weryfikator Serii</h3>
    <p>Znajdowanie niekompletnych lub niespójnych informacji o seriach książek. Bazowane na eksporcie z ERP</p>
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

with col6:
    st.markdown("""
    <div class='tool-card'>
    <h3>📄 Konwerter PDF → JPG</h3>
    <p>Konwersja wielostronicowych plików PDF na obrazy JPG o wybranej rozdzielczości i jakości.</p>
    <ul>
        <li>✅ Konwersja każdej strony na osobny obraz</li>
        <li>✅ Regulowana rozdzielczość (72-600 DPI)</li>
        <li>✅ Kontrola jakości JPEG</li>
        <li>✅ Automatyczne pakowanie do ZIP</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Otwórz konwerter PDF", key="btn_pdf", type="primary", icon="🚀", use_container_width=True):
        st.switch_page("pages/6_konwerter_pdf_jpg.py")

# Trzeci rząd - 1 kolumna (wyśrodkowana)
col7, _, _ = st.columns(3)

with col7:
    st.markdown("""
    <div class='tool-card'>
    <h3>🧬 Generator Kopii Grafik</h3>
    <p>Tworzenie wielu kopii tej samej grafiki pod różnymi, zdefiniowanymi nazwami plików.</p>
    <ul>
        <li>✅ Jedna grafika → wiele nazwanych kopii</li>
        <li>✅ Wiele zestawów grafika+nazwy naraz</li>
        <li>✅ Automatyczne czyszczenie nazw plików</li>
        <li>✅ Eksport do ZIP</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Otwórz generator kopii", key="btn_copies", type="primary", icon="🚀", use_container_width=True):
        st.switch_page("pages/7_generator_kopii.py")

# Informacje dodatkowe
with st.expander("ℹ️ Informacje o aplikacji"):
    st.markdown("""
    ### 🛠️ Pakiet narzędzi do pracy z danymi produktowymi
    
    Ta aplikacja zawiera 7 narzędzi usprawniających pracę z danymi produktów w plikach Excel:
    
    1. **Pobieranie okładek** - automatyczne pobieranie obrazów produktów
    2. **Konwerter HTML** - konwersja opisów tekstowych na HTML
    3. **Konwerter obrazów** - konwersja formatów graficznych
    4. **Weryfikator duplikatów** - wykrywanie zduplikowanych produktów
    5. **Weryfikator serii** - znajdowanie problemów z seriami książek
    6. **Konwerter PDF → JPG** - konwersja stron PDF na obrazy JPG
    7. **Generator kopii grafik** - tworzenie nazwanych kopii jednej grafiki
    """)

# Stopka
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>Made with ❤️ using Streamlit</div>",
    unsafe_allow_html=True
)
