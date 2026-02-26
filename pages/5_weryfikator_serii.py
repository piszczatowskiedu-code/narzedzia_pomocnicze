import streamlit as st
import pandas as pd
from io import BytesIO
from difflib import SequenceMatcher
import re
from collections import defaultdict
import time

# ============================================
# KONFIGURACJA STRONY
# ============================================
st.set_page_config(
    page_title="Weryfikator serii",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #17a2b8;
        text-align: center;
        margin-bottom: 1rem;
    }
    .series-group {
        background-color: #e7f3ff;
        border-left: 4px solid #17a2b8;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# FUNKCJE POMOCNICZE
# ============================================

def normalize_text(text, ignore_case=True, ignore_special=True):
    """Normalizuje tekst do porównania"""
    if pd.isna(text):
        return ""
    
    text = str(text).strip()
    
    if ignore_case:
        text = text.lower()
    
    if ignore_special:
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
    
    return text


def extract_series_prefix(text):
    """
    Wyciąga wspólny prefix z nazwy który prawdopodobnie jest nazwą serii
    Np. "Biuro detektywistyczne Lassego i Mai. Tajemnica detektywa" 
    -> "Biuro detektywistyczne Lassego i Mai"
    """
    if not text:
        return ""
    
    # Szukaj separatorów typowych dla serii: ".", ":", "-", "Tom", "Część"
    separators = [
        r'\.\s+(?:tajemnica|przygoda|historia|opowieść|tom|część|cz)',  # kropka + słowo kluczowe
        r':\s+',  # dwukropek
        r'\s+-\s+(?=\w)',  # myślnik z spacjami
        r'\s+tom\s+\d+',  # " Tom 1"
        r'\s+cz[ęe][śs][ćc]\s+\d+',  # " część 1"
    ]
    
    text_lower = text.lower()
    best_split = len(text)
    
    for sep_pattern in separators:
        match = re.search(sep_pattern, text_lower)
        if match:
            best_split = min(best_split, match.start())
    
    if best_split < len(text):
        prefix = text[:best_split].strip()
        # Usuń końcowe znaki interpunkcyjne
        prefix = re.sub(r'[.,;:\-]+$', '', prefix).strip()
        return prefix
    
    return text


def calculate_similarity(text1, text2, ignore_case=True, ignore_special=True):
    """Oblicza podobieństwo dwóch tekstów"""
    norm1 = normalize_text(text1, ignore_case, ignore_special)
    norm2 = normalize_text(text2, ignore_case, ignore_special)
    
    if not norm1 or not norm2:
        return 0
    
    if norm1 == norm2:
        return 100
    
    tokens1 = sorted(norm1.split())
    tokens2 = sorted(norm2.split())
    sorted1 = ' '.join(tokens1)
    sorted2 = ' '.join(tokens2)
    token_ratio = SequenceMatcher(None, sorted1, sorted2).ratio()
    
    plain_ratio = SequenceMatcher(None, norm1, norm2).ratio()
    
    set1 = set(tokens1)
    set2 = set(tokens2)
    if len(set1) == 0 or len(set2) == 0:
        set_ratio = 0
    else:
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        set_ratio = intersection / union if union > 0 else 0
    
    max_ratio = max(token_ratio, plain_ratio, set_ratio)
    return round(max_ratio * 100, 2)


def find_series_groups(df, wydawca_col, autor_col, nazwa_col, seria_col, ean_col,
                      threshold=70, ignore_case=True, ignore_special=True,
                      progress_callback=None):
    """
    Znajduje grupy produktów należących do tej samej serii
    
    Returns:
        list: Lista słowników z informacjami o seriach
    """
    
    # Przygotowanie danych
    df_clean = df.copy()
    df_clean['_normalized_wydawca'] = df_clean[wydawca_col].apply(
        lambda x: normalize_text(x, ignore_case, ignore_special)
    )
    df_clean['_normalized_autor'] = df_clean[autor_col].apply(
        lambda x: normalize_text(x, ignore_case, ignore_special)
    )
    # PRE-NORMALIZACJA - robimy raz, nie za każdym razem!
    df_clean['_normalized_nazwa'] = df_clean[nazwa_col].apply(
        lambda x: normalize_text(x, ignore_case, ignore_special)
    )
    
    # Zamień puste na marker
    df_clean['_normalized_wydawca'] = df_clean['_normalized_wydawca'].replace('', '__EMPTY__')
    df_clean['_normalized_autor'] = df_clean['_normalized_autor'].replace('', '__EMPTY__')
    
    # Grupowanie po wydawcy i autorze
    grouped = df_clean.groupby(['_normalized_wydawca', '_normalized_autor'])
    
    series_groups = []
    total_groups = len(grouped)
    processed = 0
    
    # Cache dla podobieństw
    similarity_cache = {}
    
    for (norm_wydawca, norm_autor), group in grouped:
        processed += 1
        if progress_callback and processed % 5 == 0:
            progress_callback(processed / total_groups)
        
        if len(group) < 2:
            continue
        
        # OPTYMALIZACJA: Dla dużych grup (>100), użyj sampling
        if len(group) > 100:
            # Losowo wybierz 100 produktów do analizy
            group = group.sample(n=100, random_state=42)
        
        # Dla każdej grupy wydawca+autor, znajdź potencjalne serie
        products = group.to_dict('records')
        n = len(products)
        
        # Znajdź połączenia między produktami (podobne nazwy)
        connections = defaultdict(set)
        
        for i in range(n):
            # Wczesne przerwanie - jeśli już ma wystarczająco połączeń
            if len(connections[i]) > 20:
                continue
            
            for j in range(i + 1, n):
                # Cache key z znormalizowanych nazw
                name_i = products[i]['_normalized_nazwa']
                name_j = products[j]['_normalized_nazwa']
                
                cache_key = (name_i, name_j) if name_i < name_j else (name_j, name_i)
                
                if cache_key in similarity_cache:
                    similarity = similarity_cache[cache_key]
                else:
                    # SZYBKIE ODRZUCANIE - różnica długości
                    len_diff = abs(len(name_i) - len(name_j))
                    max_len = max(len(name_i), len(name_j))
                    
                    if max_len > 0 and (len_diff / max_len) > 0.5:
                        similarity = 0
                    else:
                        # Szybki test Jaccard
                        tokens_i = set(name_i.split())
                        tokens_j = set(name_j.split())
                        
                        if len(tokens_i) == 0 or len(tokens_j) == 0:
                            similarity = 0
                        else:
                            intersection = len(tokens_i & tokens_j)
                            union = len(tokens_i | tokens_j)
                            quick_sim = (intersection / union * 100) if union > 0 else 0
                            
                            # Pełne porównanie tylko jeśli szybki test pozytywny
                            if quick_sim >= threshold - 10:
                                similarity = calculate_similarity(
                                    products[i][nazwa_col],
                                    products[j][nazwa_col],
                                    ignore_case,
                                    ignore_special
                                )
                            else:
                                similarity = quick_sim
                    
                    similarity_cache[cache_key] = similarity
                
                if similarity >= threshold:
                    connections[i].add(j)
                    connections[j].add(i)
        
        # Grupuj połączone produkty
        visited = set()
        
        for idx in range(n):
            if idx in visited:
                continue
            
            # Znajdź wszystkie połączone produkty
            current_group = []
            stack = [idx]
            
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                
                visited.add(current)
                current_group.append(products[current])
                
                for connected in connections[current]:
                    if connected not in visited:
                        stack.append(connected)
            
            # Analizuj tylko grupy z >1 produktem
            if len(current_group) > 1:
                # Zbierz informacje o serii
                series_values = []
                has_empty_series = False
                has_filled_series = False
                
                for product in current_group:
                    seria_value = product.get(seria_col, '')
                    if pd.isna(seria_value) or str(seria_value).strip() == '':
                        has_empty_series = True
                    else:
                        has_filled_series = True
                        seria_value = str(seria_value).strip()
                        if seria_value not in series_values:
                            series_values.append(seria_value)
                
                # Sugerowana nazwa serii (wyciągnij wspólny prefix)
                first_name = current_group[0][nazwa_col]
                suggested_series = extract_series_prefix(first_name)
                if not suggested_series or len(suggested_series) < 10:
                    # Jeśli nie udało się wyciągnąć, użyj pierwszych 3-5 słów
                    words = normalize_text(first_name, ignore_case=False, ignore_special=False).split()
                    suggested_series = ' '.join(words[:min(5, len(words))])
                
                # Określ typ problemu
                problem_type = None
                if has_empty_series and has_filled_series:
                    problem_type = "incomplete"  # Część ma, część nie ma
                elif has_empty_series and not has_filled_series:
                    problem_type = "missing"  # Wszystkie puste
                elif len(series_values) > 1:
                    problem_type = "inconsistent"  # Różne wartości serii
                
                if problem_type:
                    series_groups.append({
                        'type': problem_type,
                        'products': current_group,
                        'series_values': series_values,
                        'suggested_series': suggested_series,
                        'wydawca': current_group[0].get(wydawca_col, ''),
                        'autor': current_group[0].get(autor_col, '')
                    })
    
    return series_groups


def create_export_dataframe(series_groups, ean_col, wydawca_col, autor_col, nazwa_col, seria_col, all_columns):
    """Tworzy DataFrame do eksportu z sugestiami uzupełnienia serii"""
    export_data = []
    
    for group_num, group_info in enumerate(series_groups, 1):
        problem_type = group_info['type']
        suggested = group_info['suggested_series']
        
        # Ustal rekomendację
        if problem_type == "incomplete":
            # Znajdź najczęstszą wypełnioną serię
            filled_series = [p.get(seria_col, '') for p in group_info['products'] 
                           if not pd.isna(p.get(seria_col, '')) and str(p.get(seria_col, '')).strip() != '']
            if filled_series:
                recommendation = max(set(filled_series), key=filled_series.count)
            else:
                recommendation = suggested
        elif problem_type == "inconsistent":
            recommendation = f"UWAGA: Ujednolicić ({', '.join(group_info['series_values'])})"
        else:  # missing
            recommendation = suggested
        
        for product in group_info['products']:
            seria_value = product.get(seria_col, '')
            if pd.isna(seria_value) or str(seria_value).strip() == '':
                seria_value = '[BRAK]'
            
            row_data = {
                'Grupa': group_num,
                'Problem': {
                    'incomplete': 'Niekompletne',
                    'missing': 'Brak serii',
                    'inconsistent': 'Niespójne'
                }.get(problem_type, problem_type),
                'Rekomendacja': recommendation
            }
            
            # Dodaj wszystkie oryginalne kolumny
            for col in all_columns:
                value = product.get(col, '')
                if col == wydawca_col or col == autor_col:
                    if pd.isna(value) or str(value).strip() == '':
                        value = '[BRAK]'
                row_data[col] = value
            
            export_data.append(row_data)
    
    return pd.DataFrame(export_data)


# ============================================
# INTERFEJS UŻYTKOWNIKA
# ============================================

# Nagłówek
st.markdown("<div class='main-header'>📚 Weryfikator kompletności serii</div>", unsafe_allow_html=True)
st.markdown("Znajdź gdzie brakuje informacji o serii lub gdzie serie są niespójne")
st.markdown("---")

# Sidebar z opcjami
with st.sidebar:
    st.header("⚙️ Ustawienia analizy")
    
    st.markdown("### 🎯 Próg podobieństwa")
    threshold = st.slider(
        "Minimalne podobieństwo nazw (%):",
        min_value=60,
        max_value=95,
        value=70,
        step=5,
        help="Niższy próg łapie więcej produktów (może być za dużo). 70% jest dobrym startem."
    )
    
    st.markdown("---")
    st.markdown("### 🔧 Opcje normalizacji")
    
    ignore_case = st.checkbox(
        "Ignoruj wielkość liter",
        value=True,
        help="'HARRY POTTER' = 'harry potter'"
    )
    
    ignore_special = st.checkbox(
        "Ignoruj znaki specjalne",
        value=True,
        help="Usuwa znaki interpunkcyjne"
    )
    
    st.markdown("---")
    st.markdown("### 💡 Wskazówki")
    st.info("""
    **Próg 60-70%**: Łapie więcej serii, może dać fałszywe alarmy
    
    **Próg 75-80%**: Zbalansowany - polecany
    
    **Próg 85-95%**: Restrykcyjny, tylko bardzo podobne nazwy
    """)

# Główna część aplikacji
uploaded_file = st.file_uploader(
    "Wybierz plik Excel z produktami",
    type=['xlsx', 'xls'],
    help="Plik powinien zawierać kolumny: EAN, Wydawca, Autor, Nazwa, Seria"
)

if uploaded_file is not None:
    try:
        # Wczytaj plik
        with st.spinner("Wczytywanie pliku..."):
            df = pd.read_excel(uploaded_file, dtype=str)
        
        st.success(f"✅ Wczytano: **{uploaded_file.name}** | Produktów: **{len(df):,}**")
        
        columns = df.columns.tolist()
        
        # Wybór kolumn
        st.markdown("### 📋 Mapowanie kolumn")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            ean_default = 0
            for i, col in enumerate(columns):
                if col.upper() in ['EAN', 'EAN13', 'BARCODE', 'ISBN']:
                    ean_default = i
                    break
            ean_column = st.selectbox("Kolumna EAN:", columns, index=ean_default)
        
        with col2:
            wydawca_default = 0
            for i, col in enumerate(columns):
                if 'wydaw' in col.lower() or 'publisher' in col.lower():
                    wydawca_default = i
                    break
            wydawca_column = st.selectbox("Kolumna Wydawca:", columns, index=wydawca_default)
        
        with col3:
            autor_default = 0
            for i, col in enumerate(columns):
                if 'autor' in col.lower() or 'author' in col.lower():
                    autor_default = i
                    break
            autor_column = st.selectbox("Kolumna Autor:", columns, index=autor_default)
        
        with col4:
            nazwa_default = 0
            for i, col in enumerate(columns):
                if any(x in col.lower() for x in ['nazwa', 'tytuł', 'tytul', 'title', 'name']):
                    nazwa_default = i
                    break
            nazwa_column = st.selectbox("Kolumna Nazwa:", columns, index=nazwa_default)
        
        with col5:
            seria_default = 0
            for i, col in enumerate(columns):
                if 'seria' in col.lower() or 'series' in col.lower():
                    seria_default = i
                    break
            seria_column = st.selectbox("Kolumna Seria:", columns, index=seria_default)
        
        # Przycisk analizy
        st.markdown("---")
        
        if st.button("🚀 ZNAJDŹ PROBLEMY Z SERIAMI", type="primary", use_container_width=True):
            
            # Sprawdzenie danych
            if df[nazwa_column].isna().all() or df[nazwa_column].astype(str).str.strip().eq('').all():
                st.error("❌ Kolumna z nazwami jest pusta!")
            else:
                # Analiza
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("🔍 Grupowanie po wydawcy i autorze...")
                start_time = time.time()
                
                def update_progress(progress):
                    elapsed = time.time() - start_time
                    progress_bar.progress(progress)
                    status_text.text(f"🔍 Analizowanie grup... {int(progress * 100)}% | Czas: {elapsed:.1f}s")
                
                with st.spinner("Szukam problemów z seriami..."):
                    series_groups = find_series_groups(
                        df,
                        wydawca_column,
                        autor_column,
                        nazwa_column,
                        seria_column,
                        ean_column,
                        threshold=threshold,
                        ignore_case=ignore_case,
                        ignore_special=ignore_special,
                        progress_callback=update_progress
                    )
                
                elapsed_time = time.time() - start_time
                progress_bar.progress(1.0)
                status_text.text(f"✅ Analiza zakończona w {elapsed_time:.1f}s!")
                
                # Wyniki
                st.markdown("---")
                st.markdown("## 📊 Wyniki analizy")
                
                if not series_groups:
                    st.success("🎉 Nie znaleziono problemów! Wszystkie serie są kompletne i spójne.")
                    st.info(f"Przeanalizowano **{len(df):,}** produktów z progiem podobieństwa **{threshold}%**")
                else:
                    # Statystyki
                    total_products = sum(len(g['products']) for g in series_groups)
                    incomplete = sum(1 for g in series_groups if g['type'] == 'incomplete')
                    missing = sum(1 for g in series_groups if g['type'] == 'missing')
                    inconsistent = sum(1 for g in series_groups if g['type'] == 'inconsistent')
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Grup z problemami", len(series_groups))
                    with col2:
                        st.metric("Produktów do poprawy", total_products)
                    with col3:
                        st.metric("Brak serii", missing)
                    with col4:
                        st.metric("Niespójne", inconsistent + incomplete)
                    
                    # Przygotowanie danych do eksportu
                    export_df = create_export_dataframe(
                        series_groups,
                        ean_column,
                        wydawca_column,
                        autor_column,
                        nazwa_column,
                        seria_column,
                        df.columns.tolist()
                    )
                    
                    # Czyszczenie NaN
                    export_df = export_df.fillna('')
                    export_df = export_df.replace([float('inf'), float('-inf')], '')
                    
                    # Eksport do Excel
                    st.markdown("---")
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        export_df.to_excel(writer, index=False, sheet_name='Problemy_z_seriami')
                        
                        workbook = writer.book
                        worksheet = writer.sheets['Problemy_z_seriami']
                        
                        # Formatowanie
                        header_format = workbook.add_format({
                            'bold': True,
                            'bg_color': '#17a2b8',
                            'font_color': 'white',
                            'border': 1,
                            'align': 'center'
                        })
                        
                        # Kolory dla typów problemów
                        format_incomplete = workbook.add_format({'bg_color': '#fff3cd'})
                        format_missing = workbook.add_format({'bg_color': '#f8d7da'})
                        format_inconsistent = workbook.add_format({'bg_color': '#ffe5e5'})
                        
                        # Nagłówki
                        for col_num, value in enumerate(export_df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        
                        # Kolorowanie wierszy
                        for row_num in range(len(export_df)):
                            problem_type = export_df.iloc[row_num]['Problem']
                            
                            if problem_type == 'Niekompletne':
                                row_format = format_incomplete
                            elif problem_type == 'Brak serii':
                                row_format = format_missing
                            else:
                                row_format = format_inconsistent
                            
                            for col_num in range(len(export_df.columns)):
                                worksheet.write(row_num + 1, col_num,
                                              export_df.iloc[row_num, col_num],
                                              row_format)
                        
                        # Szerokości kolumn
                        for idx, col in enumerate(export_df.columns):
                            max_length = max(
                                export_df[col].astype(str).apply(len).max(),
                                len(str(col))
                            )
                            max_length = min(max_length + 2, 80)
                            worksheet.set_column(idx, idx, max_length)
                    
                    output.seek(0)
                    
                    st.download_button(
                        label=f"⬇️ POBIERZ RAPORT ({len(series_groups)} grup, {total_products} produktów)",
                        data=output,
                        file_name=f"problemy_serie.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # Podgląd problemów
                    st.markdown("---")
                    st.markdown("### 👀 Podgląd znalezionych problemów")
                    
                    # Sortuj grupy po typie problemu
                    sorted_groups = sorted(series_groups, 
                                         key=lambda x: {'missing': 0, 'incomplete': 1, 'inconsistent': 2}[x['type']])
                    
                    for idx, group_info in enumerate(sorted_groups[:10], 1):
                        problem_type = group_info['type']
                        
                        # Ikona i kolor
                        if problem_type == 'missing':
                            icon = "❌"
                            problem_label = "BRAK SERII"
                        elif problem_type == 'incomplete':
                            icon = "⚠️"
                            problem_label = "NIEKOMPLETNE"
                        else:
                            icon = "🔀"
                            problem_label = "NIESPÓJNE"
                        
                        wydawca_display = group_info['wydawca']
                        autor_display = group_info['autor']
                        
                        if pd.isna(wydawca_display) or str(wydawca_display).strip() == '':
                            wydawca_display = '[BRAK]'
                        if pd.isna(autor_display) or str(autor_display).strip() == '':
                            autor_display = '[BRAK]'
                        
                        with st.expander(
                            f"{icon} Grupa {idx} - {problem_label} ({len(group_info['products'])} produktów) | "
                            f"Wydawca: {wydawca_display} | Autor: {autor_display}",
                            expanded=(idx <= 3)
                        ):
                            st.markdown(f"**Sugerowana seria:** `{group_info['suggested_series']}`")
                            
                            if group_info['series_values']:
                                st.markdown(f"**Obecne wartości:** {', '.join([f'`{s}`' for s in group_info['series_values']])}")
                            
                            # Tabela z produktami
                            group_data = []
                            for p in group_info['products']:
                                seria_val = p.get(seria_column, '')
                                if pd.isna(seria_val) or str(seria_val).strip() == '':
                                    seria_val = '[BRAK]'
                                
                                row = {
                                    'EAN': p.get(ean_column, ''),
                                    'Nazwa': p.get(nazwa_column, ''),
                                    'Seria': seria_val
                                }
                                group_data.append(row)
                            
                            group_df = pd.DataFrame(group_data)
                            st.dataframe(group_df, use_container_width=True, hide_index=True)
                    
                    if len(sorted_groups) > 10:
                        st.info(f"ℹ️ Pokazano 10 z {len(sorted_groups)} grup. "
                               f"Pobierz pełny raport Excel aby zobaczyć wszystkie.")
    
    except Exception as e:
        st.error(f"❌ Wystąpił błąd: {str(e)}")
        import traceback
        with st.expander("🔧 Szczegóły techniczne"):
            st.code(traceback.format_exc())

else:
    # Ekran powitalny
    st.info("📤 Wgraj plik Excel z danymi produktów")
    
    # Instrukcje
    with st.expander("ℹ️ Jak działa weryfikator serii?"):
        st.markdown("""
        ### 🎯 Co robi narzędzie:
        
        1. **Grupuje produkty** po wydawcy i autorze
        2. **Znajduje podobne nazwy** (seria książek)
        3. **Sprawdza kolumnę "Seria"** i wykrywa 3 typy problemów:
        
        ### 📊 Typy problemów:
        
        **❌ BRAK SERII**
        - Wszystkie produkty w grupie mają pustą kolumnę "Seria"
        - Przykład: 5 książek z serii "Harry Potter", wszystkie bez wypełnionej serii
        
        **⚠️ NIEKOMPLETNE**
        - Część produktów ma wypełnioną serię, część nie
        - Przykład: 3 książki mają "Biuro detektywistyczne", 2 mają puste
        
        **🔀 NIESPÓJNE**
        - Produkty mają różne wartości w kolumnie "Seria"
        - Przykład: jedna książka ma "Harry Potter", inna "Harry Potter seria"
        
        ### 💡 Co dostaniesz:
        
        - **Raport Excel** z listą wszystkich problemów
        - **Kolumna "Rekomendacja"** z sugestią co wpisać
        - **Kolorowanie wierszy** (żółte = niekompletne, czerwone = brak)
        - **Wszystkie oryginalne kolumny** zachowane
        
        ### 📥 Format pliku Excel:
        
        Wymagane kolumny:
        - **EAN** - identyfikator produktu
        - **Wydawca** - nazwa wydawcy (może być pusta)
        - **Autor** - autor (może być pusta)
        - **Nazwa** - pełna nazwa produktu (WYMAGANA!)
        - **Seria** - kolumna którą chcemy weryfikować
        
        ### 🔧 Sugestie nazw serii:
        
        Narzędzie automatycznie próbuje wyciągnąć nazwę serii z nazw produktów:
        - "Biuro detektywistyczne Lassego i Mai. Tajemnica X" → "Biuro detektywistyczne Lassego i Mai"
        - "Harry Potter i Kamień Filozoficzny" → "Harry Potter"
        - Jeśli nie da się wyciągnąć, użyje pierwszych 3-5 słów
        """)
    
    # Przykładowe dane
    with st.expander("📋 Przykładowe dane"):
        st.markdown("**Przykład 1: Brak serii (wszystkie puste)**")
        example_data1 = pd.DataFrame({
            'EAN': ['9788374950001', '9788374950002', '9788374950003'],
            'Wydawca': ['Media Rodzina', 'Media Rodzina', 'Media Rodzina'],
            'Autor': ['J.K. Rowling', 'J.K. Rowling', 'J.K. Rowling'],
            'Nazwa': [
                'Harry Potter i Kamień Filozoficzny',
                'Harry Potter i Komnata Tajemnic',
                'Harry Potter i Więzień Azkabanu'
            ],
            'Seria': ['', '', '']
        })
        st.dataframe(example_data1, use_container_width=True, hide_index=True)
        st.caption("💡 Problem: BRAK SERII | Rekomendacja: Harry Potter")
        
        st.markdown("---")
        st.markdown("**Przykład 2: Niekompletne (część ma, część nie)**")
        example_data2 = pd.DataFrame({
            'EAN': ['9788374950001', '9788374950002', '9788374950003'],
            'Wydawca': ['Egmont', 'Egmont', 'Egmont'],
            'Autor': ['Martin Widmark', 'Martin Widmark', 'Martin Widmark'],
            'Nazwa': [
                'Biuro detektywistyczne. Tajemnica detektywa',
                'Biuro detektywistyczne. Tajemnica filmu',
                'Biuro detektywistyczne. Tajemnica zamku'
            ],
            'Seria': ['Biuro detektywistyczne', '', 'Biuro detektywistyczne']
        })
        st.dataframe(example_data2, use_container_width=True, hide_index=True)
        st.caption("💡 Problem: NIEKOMPLETNE | Rekomendacja: Biuro detektywistyczne")
        
        st.markdown("---")
        st.markdown("**Przykład 3: Niespójne (różne wartości)**")
        example_data3 = pd.DataFrame({
            'EAN': ['9788374950001', '9788374950002', '9788374950003'],
            'Wydawca': ['Media Rodzina', 'Media Rodzina', 'Media Rodzina'],
            'Autor': ['J.K. Rowling', 'J.K. Rowling', 'J.K. Rowling'],
            'Nazwa': [
                'Harry Potter i Kamień Filozoficzny',
                'Harry Potter i Komnata Tajemnic',
                'Harry Potter i Więzień Azkabanu'
            ],
            'Seria': ['Harry Potter', 'Harry Potter seria', 'HP']
        })
        st.dataframe(example_data3, use_container_width=True, hide_index=True)
        st.caption("💡 Problem: NIESPÓJNE | Rekomendacja: UWAGA: Ujednolicić (Harry Potter, Harry Potter seria, HP)")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>📚 Weryfikator kompletności serii</div>",
    unsafe_allow_html=True
)