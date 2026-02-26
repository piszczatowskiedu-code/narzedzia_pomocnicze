import streamlit as st

if st.query_params.get("health") == "check":
    st.write("OK")
    st.stop()

# Konfiguracja musi być PRZED st.navigation
st.set_page_config(
    page_title="Narzędzia Excel",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Definicja stron
pages = {
        "": [
            st.Page("pages/home.py", title="Strona główna", icon="🏠", default=True)
        ],
        "Narzędzia": [
            st.Page("pages/1_pobieranie_okladek.py", title="Pobieranie okładek", icon="📥"),
            st.Page("pages/2_zmiana_opisu_html.py", title="Konwerter HTML", icon="📝"),
            st.Page("pages/3_konwerter_webp.py", title="Konwerter obrazów", icon="🖼️"),
            st.Page("pages/4_weryfikator_dubli.py", title="Weryfikator duplikatów", icon="🔍"),
            st.Page("pages/5_weryfikator_serii.py", title="Weryfikator serii", icon="📚"),
        ]
}

# Nawigacja
pg = st.navigation(pages, position="top")
pg.run()