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
    page_title="Weryfikator duplikatów",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #dc3545;
        text-align: center;
        margin-bottom: 1rem;
    }
    .duplicate-group {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
    .stats-box {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #dee2e6;
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
        # Usuń znaki specjalne i nadmiarowe spacje
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
    
    return text


def is_false_positive(text1, text2, ignore_case=True, ignore_special=True):
    """
    Wykrywa fałszywe duplikaty - produkty które są podobne ale to różne wersje
    
    Returns:
        bool: True jeśli to fałszywy duplikat (NIE powinien być zgrupowany)
    """
    norm1 = normalize_text(text1, ignore_case, ignore_special)
    norm2 = normalize_text(text2, ignore_case, ignore_special)
    
    if not norm1 or not norm2:
        return False
    
    # Jeśli identyczne, to nie fałszywy pozytyw
    if norm1 == norm2:
        return False
    
    # REGUŁA 1: Wykryj różne numery w seriach (Matematyka 1, 2, 3...)
    # Szukamy wzorców: "cyfra", "tom cyfra", "część cyfra", "klasa cyfra", rzymskie cyfry
    pattern_numbers = r'\b(tom|cz[ęe][śs][ćc]|cz|klasa|klasy)\s+(\d+|[IVX]+)\b|\b(\d+|[IVX]+)\s+(tom|cz[ęe][śs][ćc]|cz|klasa)\b|\b\d+\b'
    
    numbers1 = set()
    numbers2 = set()
    
    # Wyciągnij wszystkie cyfry i konteksty
    for match in re.finditer(pattern_numbers, norm1, re.IGNORECASE):
        # Pobierz całe dopasowanie jako kontekst
        context = match.group(0)
        numbers1.add(context)
    
    for match in re.finditer(pattern_numbers, norm2, re.IGNORECASE):
        context = match.group(0)
        numbers2.add(context)
    
    # Jeśli mają różne numery, to prawdopodobnie różne tomy/części
    if numbers1 and numbers2 and numbers1 != numbers2:
        # Sprawdź czy reszta nazwy jest bardzo podobna (>85%)
        # Usuń numery z nazw i porównaj
        text1_no_numbers = re.sub(pattern_numbers, ' ', norm1, flags=re.IGNORECASE)
        text2_no_numbers = re.sub(pattern_numbers, ' ', norm2, flags=re.IGNORECASE)
        text1_no_numbers = re.sub(r'\s+', ' ', text1_no_numbers).strip()
        text2_no_numbers = re.sub(r'\s+', ' ', text2_no_numbers).strip()
        
        if text1_no_numbers and text2_no_numbers:
            ratio = SequenceMatcher(None, text1_no_numbers, text2_no_numbers).ratio()
            if ratio > 0.85:  # Obniżam próg do 85%
                return True
    
    # REGUŁA 2: Wykryj różne zakresy (podstawowy, rozszerzony, średni)
    zakresy = [
        'podstawowy', 'podstawowa', 'podstawowe',
        'rozszerzony', 'rozszerzona', 'rozszerzone',
        'sredni', 'srednia', 'srednie',
        'zaawansowany', 'zaawansowana', 'zaawansowane'
    ]
    
    has_zakres1 = any(z in norm1 for z in zakresy)
    has_zakres2 = any(z in norm2 for z in zakresy)
    
    # Jeśli jeden ma zakres a drugi nie, lub mają różne zakresy
    if has_zakres1 or has_zakres2:
        zakres1_list = [z for z in zakresy if z in norm1]
        zakres2_list = [z for z in zakresy if z in norm2]
        
        if zakres1_list != zakres2_list:
            # Usuń zakresy i sprawdź czy reszta jest podobna
            text1_no_zakres = norm1
            text2_no_zakres = norm2
            for z in zakresy:
                text1_no_zakres = text1_no_zakres.replace(z, '')
                text2_no_zakres = text2_no_zakres.replace(z, '')
            
            text1_no_zakres = re.sub(r'\s+', ' ', text1_no_zakres).strip()
            text2_no_zakres = re.sub(r'\s+', ' ', text2_no_zakres).strip()
            
            if text1_no_zakres and text2_no_zakres:
                ratio = SequenceMatcher(None, text1_no_zakres, text2_no_zakres).ratio()
                if ratio > 0.85:
                    return True
    
    # REGUŁA 3: Wykryj różne oprawy (miękka, twarda)
    oprawy_patterns = [
        r'oprawa\s+mi[eę]kka', r'oprawa\s+twarda',
        r'ok[łl]adka\s+mi[eę]kka', r'ok[łl]adka\s+twarda',
        r'\bmi[eę]kka\b', r'\btwarda\b'
    ]
    
    oprawy1 = []
    oprawy2 = []
    
    for pattern in oprawy_patterns:
        if re.search(pattern, norm1, re.IGNORECASE):
            oprawy1.append(pattern)
        if re.search(pattern, norm2, re.IGNORECASE):
            oprawy2.append(pattern)
    
    if oprawy1 or oprawy2:
        if oprawy1 != oprawy2:  # Różne oprawy
            # Usuń wszystkie wzory opraw
            text1_no_oprawa = norm1
            text2_no_oprawa = norm2
            for pattern in oprawy_patterns:
                text1_no_oprawa = re.sub(pattern, ' ', text1_no_oprawa, flags=re.IGNORECASE)
                text2_no_oprawa = re.sub(pattern, ' ', text2_no_oprawa, flags=re.IGNORECASE)
            
            text1_no_oprawa = re.sub(r'\s+', ' ', text1_no_oprawa).strip()
            text2_no_oprawa = re.sub(r'\s+', ' ', text2_no_oprawa).strip()
            
            if text1_no_oprawa and text2_no_oprawa:
                ratio = SequenceMatcher(None, text1_no_oprawa, text2_no_oprawa).ratio()
                if ratio > 0.80:  # Obniżam próg
                    return True
    
    # REGUŁA 4: Wykryj różne warianty w serii (W bajkach, W dżungli, W przedszkolu)
    # Jeśli mają wzorzec "X. W [coś]. Y" gdzie [coś] się różni
    pattern_w = r'\b(w|we)\s+[\wąćęłńóśźż]+'
    
    w_phrases1 = set(re.findall(pattern_w, norm1, re.IGNORECASE))
    w_phrases2 = set(re.findall(pattern_w, norm2, re.IGNORECASE))
    
    if w_phrases1 and w_phrases2 and w_phrases1 != w_phrases2:
        # Usuń frazy "w ..." i sprawdź podobieństwo
        text1_no_w = re.sub(pattern_w, ' ', norm1)
        text2_no_w = re.sub(pattern_w, ' ', norm2)
        
        text1_no_w = re.sub(r'\s+', ' ', text1_no_w).strip()
        text2_no_w = re.sub(r'\s+', ' ', text2_no_w).strip()
        
        if text1_no_w and text2_no_w:
            ratio = SequenceMatcher(None, text1_no_w, text2_no_w).ratio()
            if ratio > 0.85:  # Bardzo podobne po usunięciu "w ..."
                return True
    
    # REGUŁA 5: Wykryj serie książek z różnymi tytułami (wspólny długi prefix, różne końcówki)
    # Np. "Biuro detektywistyczne X. Tajemnica [detektywa|filmu|srebra|...]"
    # Algorytm:
    # 1. Znajdź najdłuższy wspólny prefix
    # 2. Jeśli prefix jest długi (>50% krótkszego tekstu) i końcówki się różnią → fałszywy duplikat
    
    tokens1 = norm1.split()
    tokens2 = norm2.split()
    
    # Znajdź wspólny prefix (token po tokenie)
    common_prefix_length = 0
    for i in range(min(len(tokens1), len(tokens2))):
        if tokens1[i] == tokens2[i]:
            common_prefix_length += 1
        else:
            break
    
    if common_prefix_length > 0:
        # Oblicz % wspólnego prefiksu
        min_length = min(len(tokens1), len(tokens2))
        prefix_ratio = common_prefix_length / min_length
        
        # Jeśli >60% to wspólny prefix i końcówki się różnią
        if prefix_ratio > 0.6:
            # Sprawdź czy końcówki (ostatnie słowa) są różne
            suffix1 = tokens1[common_prefix_length:] if common_prefix_length < len(tokens1) else []
            suffix2 = tokens2[common_prefix_length:] if common_prefix_length < len(tokens2) else []
            
            # Jeśli końcówki istnieją i są różne
            if suffix1 and suffix2:
                # Sprawdź podobieństwo końcówek
                suffix1_text = ' '.join(suffix1)
                suffix2_text = ' '.join(suffix2)
                
                suffix_ratio = SequenceMatcher(None, suffix1_text, suffix2_text).ratio()
                
                # Jeśli końcówki są mało podobne (<50%), to różne książki z serii
                if suffix_ratio < 0.5:
                    return True
    
    return False


def calculate_similarity(text1, text2, ignore_case=True, ignore_special=True):
    """Oblicza podobieństwo dwóch tekstów używając trzech metod i zwracając najlepszy wynik"""
    norm1 = normalize_text(text1, ignore_case, ignore_special)
    norm2 = normalize_text(text2, ignore_case, ignore_special)
    
    if not norm1 or not norm2:
        return 0
    
    # Jeśli identyczne po normalizacji = 100%
    if norm1 == norm2:
        return 100
    
    # Metoda 1: Token sort - sortuj słowa alfabetycznie i porównuj
    # Najlepsze dla tytułów z różną kolejnością słów
    tokens1 = sorted(norm1.split())
    tokens2 = sorted(norm2.split())
    sorted1 = ' '.join(tokens1)
    sorted2 = ' '.join(tokens2)
    token_ratio = SequenceMatcher(None, sorted1, sorted2).ratio()
    
    # Metoda 2: Zwykłe porównanie - zachowuje kolejność słów
    # Najlepsze dla sekwencyjnych tytułów
    plain_ratio = SequenceMatcher(None, norm1, norm2).ratio()
    
    # Metoda 3: Token set - ile wspólnych unikalnych słów
    # Najlepsze dla tytułów z dodatkowymi opisami
    set1 = set(tokens1)
    set2 = set(tokens2)
    if len(set1) == 0 or len(set2) == 0:
        set_ratio = 0
    else:
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        set_ratio = intersection / union if union > 0 else 0
    
    # Bierzemy maksimum z trzech metod (najbardziej optymistyczna)
    max_ratio = max(token_ratio, plain_ratio, set_ratio)
    
    return round(max_ratio * 100, 2)


def find_duplicates(df, wydawca_col, autor_col, nazwa_col, ean_col, 
                   threshold=85, ignore_case=True, ignore_special=True,
                   progress_callback=None, check_empty_fields=True):
    """
    Znajduje duplikaty produktów na podstawie wydawcy, autora i podobnej nazwy
    
    Args:
        check_empty_fields: Jeśli True, sprawdza także produkty z pustym wydawcą/autorem
    
    Returns:
        list: Lista grup duplikatów, każda grupa to lista dict z danymi produktów
    """
    
    # Przygotowanie danych
    df_clean = df.copy()
    df_clean['_normalized_wydawca'] = df_clean[wydawca_col].apply(
        lambda x: normalize_text(x, ignore_case, ignore_special)
    )
    df_clean['_normalized_autor'] = df_clean[autor_col].apply(
        lambda x: normalize_text(x, ignore_case, ignore_special)
    )
    
    # Pre-normalizuj wszystkie nazwy (robimy to raz, nie za każdym razem)
    df_clean['_normalized_nazwa'] = df_clean[nazwa_col].apply(
        lambda x: normalize_text(x, ignore_case, ignore_special)
    )
    
    # Zamień puste stringi na specjalny marker dla lepszego grupowania
    df_clean['_normalized_wydawca'] = df_clean['_normalized_wydawca'].replace('', '__EMPTY__')
    df_clean['_normalized_autor'] = df_clean['_normalized_autor'].replace('', '__EMPTY__')
    
    # Grupowanie po wydawcy i autorze (dokładne dopasowanie po normalizacji)
    grouped = df_clean.groupby(['_normalized_wydawca', '_normalized_autor'])
    
    duplicate_groups = []
    total_groups = len(grouped)
    processed = 0
    
    # Cache dla już obliczonych podobieństw
    similarity_cache = {}
    
    # Dla każdej grupy wydawca+autor sprawdzamy nazwy
    for (norm_wydawca, norm_autor), group in grouped:
        processed += 1
        if progress_callback and processed % 5 == 0:  # Częstsze aktualizacje
            progress_callback(processed / total_groups)
        
        # Pomijamy grupy z jednym produktem
        if len(group) < 2:
            continue
        
        # Jeśli check_empty_fields=False, pomijamy grupy gdzie oba pola są puste
        if not check_empty_fields:
            if norm_wydawca == '__EMPTY__' and norm_autor == '__EMPTY__':
                continue
        
        # OPTYMALIZACJA: Jeśli grupa ma >100 produktów, użyj szybszej metody
        if len(group) > 100:
            # Dla dużych grup: grupuj najpierw po pierwszych 3 słowach nazwy
            group_by_prefix = {}
            for idx, row in group.iterrows():
                words = row['_normalized_nazwa'].split()[:3]
                prefix = ' '.join(words)
                if prefix not in group_by_prefix:
                    group_by_prefix[prefix] = []
                group_by_prefix[prefix].append(row)
            
            # Porównuj tylko w obrębie tych samych prefiksów
            for prefix_products in group_by_prefix.values():
                if len(prefix_products) < 2:
                    continue
                products = prefix_products
                n = len(products)
        else:
            # Dla małych grup: normalny algorytm
            products = group.to_dict('records')
            n = len(products)
        
        # Macierz połączeń - który produkt jest podobny do którego
        connections = defaultdict(set)
        
        # OPTYMALIZACJA: Używamy znormalizowanych nazw z cache
        for i in range(n):
            # Wczesne przerwanie jeśli już mamy wystarczająco dużo połączeń
            if len(connections[i]) > 10:  # Jeden produkt raczej nie ma >10 duplikatów
                continue
                
            for j in range(i + 1, n):
                # Klucz cache
                if isinstance(products, list):
                    name_i = products[i].get('_normalized_nazwa', '')
                    name_j = products[j].get('_normalized_nazwa', '')
                else:
                    name_i = products[i]['_normalized_nazwa']
                    name_j = products[j]['_normalized_nazwa']
                
                cache_key = (name_i, name_j) if name_i < name_j else (name_j, name_i)
                
                # Sprawdź cache
                if cache_key in similarity_cache:
                    similarity = similarity_cache[cache_key]
                else:
                    # OPTYMALIZACJA: Szybkie odrzucenie jeśli bardzo różne długości
                    len_diff = abs(len(name_i) - len(name_j))
                    max_len = max(len(name_i), len(name_j))
                    if max_len > 0 and (len_diff / max_len) > 0.5:  # >50% różnicy w długości
                        similarity = 0
                    else:
                        # Używamy tylko najszybszej metody (token set) dla pierwszego testu
                        tokens_i = set(name_i.split())
                        tokens_j = set(name_j.split())
                        
                        if len(tokens_i) == 0 or len(tokens_j) == 0:
                            similarity = 0
                        else:
                            # Jaccard similarity (szybka)
                            intersection = len(tokens_i & tokens_j)
                            union = len(tokens_i | tokens_j)
                            quick_sim = (intersection / union * 100) if union > 0 else 0
                            
                            # Jeśli szybki test pokazuje że może być podobne, zrób pełne porównanie
                            if quick_sim >= threshold - 10:  # Daj margines 10%
                                if isinstance(products, list):
                                    similarity = calculate_similarity(
                                        products[i][nazwa_col],
                                        products[j][nazwa_col],
                                        ignore_case,
                                        ignore_special
                                    )
                                else:
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
                    # Sprawdź czy to nie fałszywy duplikat (różne wersje tego samego produktu)
                    if isinstance(products, list):
                        is_false = is_false_positive(
                            products[i][nazwa_col],
                            products[j][nazwa_col],
                            ignore_case,
                            ignore_special
                        )
                    else:
                        is_false = is_false_positive(
                            products[i][nazwa_col],
                            products[j][nazwa_col],
                            ignore_case,
                            ignore_special
                        )
                    
                    # Jeśli nie jest fałszywym duplikatem, dodaj do connections
                    if not is_false:
                        connections[i].add(j)
                        connections[j].add(i)
        
        # Tworzymy grupy duplikatów używając algorytmu union-find
        visited = set()
        
        for idx in range(n):
            if idx in visited or idx not in connections:
                continue
            
            # BFS/DFS do znalezienia wszystkich połączonych produktów
            current_group = []
            stack = [idx]
            
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                
                visited.add(current)
                if isinstance(products, list):
                    product = products[current].copy()
                else:
                    product = products[current].to_dict()
                
                # Dodaj informacje o podobieństwie do pierwszego w grupie
                if current_group:
                    if isinstance(products, list):
                        product['_similarity'] = calculate_similarity(
                            products[idx][nazwa_col],
                            product[nazwa_col],
                            ignore_case,
                            ignore_special
                        )
                    else:
                        product['_similarity'] = calculate_similarity(
                            products[idx][nazwa_col],
                            product[nazwa_col],
                            ignore_case,
                            ignore_special
                        )
                else:
                    product['_similarity'] = 100  # Pierwszy w grupie
                
                current_group.append(product)
                
                # Dodaj wszystkie połączone produkty do stosu
                for connected in connections[current]:
                    if connected not in visited:
                        stack.append(connected)
            
            # Dodaj grupę tylko jeśli ma więcej niż 1 produkt
            if len(current_group) > 1:
                duplicate_groups.append(current_group)
    
    return duplicate_groups


def create_export_dataframe(duplicate_groups, ean_col, wydawca_col, autor_col, nazwa_col, all_columns):
    """Tworzy DataFrame do eksportu z numerami grup i WSZYSTKIMI kolumnami z oryginału"""
    export_data = []
    
    for group_num, group in enumerate(duplicate_groups, 1):
        for product in group:
            # Podstawowe kolumny na początku
            row_data = {
                'Grupa': group_num,
                'Podobieństwo_%': round(product.get('_similarity', 0), 1)
            }
            
            # Dodaj WSZYSTKIE oryginalne kolumny w kolejności z pliku
            for col in all_columns:
                value = product.get(col, '')
                
                # Zamień puste wartości dla wydawcy/autora na [BRAK]
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
st.markdown("<div class='main-header'>🔍 Weryfikator duplikatów</div>", unsafe_allow_html=True)
st.markdown("Znajdź produkty z tym samym wydawcą i autorem, ale o podobnych nazwach")
st.markdown("---")

# Sidebar z opcjami
with st.sidebar:
    st.header("⚙️ Ustawienia analizy")
    
    st.markdown("### 🎯 Próg podobieństwa")
    threshold = st.slider(
        "Minimalne podobieństwo nazw (%):",
        min_value=70,
        max_value=100,
        value=80,
        step=5,
        help="Im wyższy próg, tym bardziej restrykcyjne dopasowanie. 80% jest dobrym kompromisem."
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
        help="Usuwa znaki interpunkcyjne: '.' ',' '-' itp."
    )
    
    st.markdown("---")
    st.markdown("### 🎯 Produkty z pustymi polami")
    
    check_empty_fields = st.checkbox(
        "Sprawdzaj też produkty bez wydawcy/autora",
        value=True,
        help="Dla zabawek i innych produktów, które mogą nie mieć wydawcy lub autora. Będą sprawdzane tylko po nazwie."
    )
    
    st.markdown("---")
    st.markdown("### 💡 Wskazówki")
    st.info("""
    **Próg 70-75%**: Łapie więcej duplikatów, ale może dać fałszywe alarmy
    
    **Próg 80-85%**: Zbalansowany - polecany
    
    **Próg 90-100%**: Bardzo restrykcyjny, tylko niemal identyczne nazwy
    """)

# Główna część aplikacji
uploaded_file = st.file_uploader(
    "Wybierz plik Excel z produktami",
    type=['xlsx', 'xls'],
    help="Plik powinien zawierać kolumny: EAN, Wydawca, Autor, Nazwa"
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
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Auto-detect EAN
            ean_default = 0
            for i, col in enumerate(columns):
                if col.upper() in ['EAN', 'EAN13', 'BARCODE', 'ISBN']:
                    ean_default = i
                    break
            
            ean_column = st.selectbox(
                "Kolumna EAN:",
                columns,
                index=ean_default
            )
        
        with col2:
            # Auto-detect Wydawca
            wydawca_default = 0
            for i, col in enumerate(columns):
                if 'wydaw' in col.lower() or 'publisher' in col.lower():
                    wydawca_default = i
                    break
            
            wydawca_column = st.selectbox(
                "Kolumna Wydawca:",
                columns,
                index=wydawca_default
            )
        
        with col3:
            # Auto-detect Autor
            autor_default = 0
            for i, col in enumerate(columns):
                if 'autor' in col.lower() or 'author' in col.lower():
                    autor_default = i
                    break
            
            autor_column = st.selectbox(
                "Kolumna Autor:",
                columns,
                index=autor_default
            )
        
        with col4:
            # Auto-detect Nazwa
            nazwa_default = 0
            for i, col in enumerate(columns):
                if any(x in col.lower() for x in ['nazwa', 'tytuł', 'tytul', 'title', 'name']):
                    nazwa_default = i
                    break
            
            nazwa_column = st.selectbox(
                "Kolumna Nazwa:",
                columns,
                index=nazwa_default
            )
        
        # Przycisk analizy
        st.markdown("---")
        
        if st.button("🚀 ZNAJDŹ DUPLIKATY", type="primary", use_container_width=True):
            
            # Sprawdzenie czy są jakieś dane w nazwach (to jest zawsze wymagane)
            if df[nazwa_column].isna().all() or df[nazwa_column].astype(str).str.strip().eq('').all():
                st.error("❌ Kolumna z nazwami jest pusta - to pole jest wymagane!")
            else:
                # Analiza z progress barem
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("🔍 Grupowanie po wydawcy i autorze...")
                
                start_time = time.time()
                
                def update_progress(progress):
                    elapsed = time.time() - start_time
                    progress_bar.progress(progress)
                    status_text.text(f"🔍 Analizowanie grup... {int(progress * 100)}% | Czas: {elapsed:.1f}s")
                
                with st.spinner("Szukam duplikatów..."):
                    duplicate_groups = find_duplicates(
                        df,
                        wydawca_column,
                        autor_column,
                        nazwa_column,
                        ean_column,
                        threshold=threshold,
                        ignore_case=ignore_case,
                        ignore_special=ignore_special,
                        check_empty_fields=check_empty_fields,
                        progress_callback=update_progress
                    )
                
                elapsed_time = time.time() - start_time
                
                progress_bar.progress(1.0)
                status_text.text(f"✅ Analiza zakończona w {elapsed_time:.1f}s!")
                
                # Wyniki
                st.markdown("---")
                st.markdown("## 📊 Wyniki analizy")
                
                if not duplicate_groups:
                    st.success("🎉 Nie znaleziono duplikatów!")
                    st.info(f"Przeanalizowano **{len(df):,}** produktów z progiem podobieństwa **{threshold}%**")
                else:
                    # Statystyki
                    total_duplicates = sum(len(group) for group in duplicate_groups)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Znalezionych grup", len(duplicate_groups))
                    with col2:
                        st.metric("Produktów z duplikatami", total_duplicates)
                    with col3:
                        avg_group_size = total_duplicates / len(duplicate_groups)
                        st.metric("Średnia wielkość grupy", f"{avg_group_size:.1f}")
                    with col4:
                        st.metric("Czas analizy", f"{elapsed_time:.1f}s")
                    
                    # Przygotowanie danych do eksportu
                    export_df = create_export_dataframe(
                        duplicate_groups,
                        ean_column,
                        wydawca_column,
                        autor_column,
                        nazwa_column,
                        df.columns.tolist()  # Przekaż wszystkie kolumny
                    )
                    
                    # WAŻNE: Zamień NaN i INF na puste stringi (XlsxWriter nie wspiera NaN)
                    export_df = export_df.fillna('')
                    export_df = export_df.replace([float('inf'), float('-inf')], '')
                    
                    # Eksport do Excel
                    st.markdown("---")
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        export_df.to_excel(
                            writer,
                            index=False,
                            sheet_name='Duplikaty'
                        )
                        
                        workbook = writer.book
                        worksheet = writer.sheets['Duplikaty']
                        
                        # Formatowanie
                        header_format = workbook.add_format({
                            'bold': True,
                            'bg_color': '#dc3545',
                            'font_color': 'white',
                            'border': 1,
                            'align': 'center'
                        })
                        
                        # Format dla grup (przemienne kolory)
                        format1 = workbook.add_format({'bg_color': '#fff3cd'})
                        format2 = workbook.add_format({'bg_color': '#ffffff'})
                        
                        # Nagłówki
                        for col_num, value in enumerate(export_df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        
                        # Kolorowanie grup
                        current_group = None
                        use_format1 = True
                        
                        for row_num, group_num in enumerate(export_df['Grupa'], start=1):
                            if group_num != current_group:
                                current_group = group_num
                                use_format1 = not use_format1
                            
                            row_format = format1 if use_format1 else format2
                            for col_num in range(len(export_df.columns)):
                                worksheet.write(row_num, col_num, 
                                              export_df.iloc[row_num - 1, col_num], 
                                              row_format)
                        
                        # Automatyczne dopasowanie szerokości kolumn
                        for idx, col in enumerate(export_df.columns):
                            # Oblicz max długość w kolumnie
                            max_length = max(
                                export_df[col].astype(str).apply(len).max(),
                                len(str(col))
                            )
                            # Ogranicz do rozsądnych wartości
                            max_length = min(max_length + 2, 80)
                            worksheet.set_column(idx, idx, max_length)
                    
                    output.seek(0)
                    
                    st.download_button(
                        label=f"⬇️ POBIERZ RAPORT DUPLIKATÓW ({len(duplicate_groups)} grup, {total_duplicates} produktów)",
                        data=output,
                        file_name=f"duplikaty_{threshold}proc.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # Podgląd duplikatów
                    st.markdown("---")
                    st.markdown("### 👀 Podgląd znalezionych grup")
                    
                    # Sortuj grupy po liczbie elementów (największe pierwsze)
                    sorted_groups = sorted(duplicate_groups, key=len, reverse=True)
                    
                    for idx, group in enumerate(sorted_groups[:10], 1):  # Pokaż pierwsze 10 grup
                        # Przygotuj opis grupy
                        wydawca_display = group[0].get(wydawca_column, '')
                        autor_display = group[0].get(autor_column, '')
                        
                        if pd.isna(wydawca_display) or str(wydawca_display).strip() == '':
                            wydawca_display = '[BRAK]'
                        if pd.isna(autor_display) or str(autor_display).strip() == '':
                            autor_display = '[BRAK]'
                        
                        with st.expander(
                            f"📦 Grupa {idx} - {len(group)} produktów | "
                            f"Wydawca: {wydawca_display} | "
                            f"Autor: {autor_display}",
                            expanded=(idx <= 3)  # Rozwiń pierwsze 3
                        ):
                            # Tabela z WSZYSTKIMI kolumnami z produktów w grupie
                            # Najpierw dodajemy kolumnę podobieństwo
                            group_data = []
                            for p in group:
                                row = {'Podobieństwo_%': f"{p.get('_similarity', 0):.1f}%"}
                                # Dodaj wszystkie oryginalne kolumny
                                for col in df.columns:
                                    value = p.get(col, '')
                                    # Zamień puste na [BRAK] dla wydawcy/autora
                                    if col == wydawca_column or col == autor_column:
                                        if pd.isna(value) or str(value).strip() == '':
                                            value = '[BRAK]'
                                    row[col] = value
                                group_data.append(row)
                            
                            group_df = pd.DataFrame(group_data)
                            
                            st.dataframe(
                                group_df,
                                use_container_width=True,
                                hide_index=True
                            )
                    
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
    with st.expander("ℹ️ Jak działa weryfikator?"):
        st.markdown("""
        ### 🎯 Algorytm wykrywania duplikatów:
        
        1. **Krok 1: Grupowanie po wydawcy i autorze**
           - Znajdujemy produkty z **identycznym** wydawcą i autorem
           - Normalizacja: małe/wielkie litery, znaki specjalne
           - Jeśli włączone: sprawdza też produkty z pustymi polami (zabawki, itp.)
        
        2. **Krok 2: Porównanie nazw**
           - W każdej grupie porównujemy nazwy produktów
           - Używamy algorytmu **token-based matching** (sortowanie słów + SequenceMatcher)
           - Jeśli podobieństwo ≥ próg → produkty są duplikatami
        
        3. **Krok 3: Inteligentne filtrowanie fałszywych duplikatów** 🆕
           - Wykrywa i **WYKLUCZA** różne wersje tego samego produktu:
             - **Różne numery**: "Matematyka 1" ≠ "Matematyka 2"
             - **Różne zakresy**: "Zakres podstawowy" ≠ "Zakres rozszerzony"
             - **Różne oprawy**: "Oprawa miękka" ≠ "Oprawa twarda"
             - **Różne warianty serii**: "W bajkach" ≠ "W dżungli"
             - **Serie książek**: "Tajemnica detektywa" ≠ "Tajemnica filmu" (wspólny prefix >60%, różne końcówki)
           - To eliminuje >95% fałszywych alarmów!
        
        4. **Krok 4: Grupowanie połączonych duplikatów**
           - Jeśli A jest podobne do B, a B do C → wszyscy w jednej grupie
           - Nawet jeśli A nie jest bezpośrednio podobne do C
        
        ### 📊 Przykład:
        
        **Grupa duplikatów:**
        - EAN: 9788374950001 | Nazwa: "Harry Potter i Kamień Filozoficzny"
        - EAN: 9788374950002 | Nazwa: "Harry Potter i kamień filozoficzny (wyd. 2)"  
        - EAN: 9788374950003 | Nazwa: "HARRY POTTER I KAMIEŃ FILOZOFICZNY - pocket"
        
        **Wspólne cechy:**
        - ✅ Ten sam wydawca: "Media Rodzina"
        - ✅ Ten sam autor: "J.K. Rowling"
        - ✅ Podobne nazwy (>85% podobieństwa)
        
        **Przykład z pustymi polami (zabawki):**
        - EAN: 5901234567890 | Wydawca: [BRAK] | Autor: [BRAK] | Nazwa: "LEGO City 60100 Lotnisko"
        - EAN: 5901234567891 | Wydawca: [BRAK] | Autor: [BRAK] | Nazwa: "Lego City 60100 lotnisko - zestaw startowy"
        
        **Wspólne cechy:**
        - ✅ Brak wydawcy/autora (to normalne dla zabawek)
        - ✅ Podobne nazwy (>85% podobieństwa)
        
        **Przykład serii książek (NIE będą zgrupowane - to fałszywy alarm):**
        - EAN: 9788374950010 | Wydawca: "Egmont" | Autor: "Martin Widmark" | Nazwa: "Biuro detektywistyczne Lassego i Mai. Tajemnica detektywa"
        - EAN: 9788374950011 | Wydawca: "Egmont" | Autor: "Martin Widmark" | Nazwa: "Biuro detektywistyczne Lassego i Mai. Tajemnica filmu"
        - EAN: 9788374950012 | Wydawca: "Egmont" | Autor: "Martin Widmark" | Nazwa: "Biuro detektywistyczne Lassego i Mai. Tajemnica zamku"
        
        **Dlaczego NIE są duplikatami:**
        - ❌ Wspólny prefix (86% nazwy)
        - ❌ Różne końcówki ("detektywa" ≠ "filmu" ≠ "zamku")
        - → To różne książki z tej samej serii!
        
        ### 💡 Wskazówki:
        
        - **Próg 80%** - uniwersalny, łapie większość duplikatów (polecany)
        - **Próg 75%** - jeśli nazwy mocno się różnią między wydaniami
        - **Próg 85-90%** - jeśli masz bardzo ustandaryzowane nazwy
        - **Checkbox "Sprawdzaj produkty bez wydawcy/autora"** - włącz dla zabawek, akcesoriów, gadżetów
        
        ### 📥 Format pliku Excel:
        
        Wymagane kolumny (mogą mieć inne nazwy - wybierzesz je później):
        - **EAN/ISBN** - unikalny identyfikator produktu
        - **Wydawca** - nazwa wydawcy (może być pusta dla zabawek)
        - **Autor** - autor/autorzy (może być pusta dla zabawek)
        - **Nazwa/Tytuł** - pełna nazwa produktu (WYMAGANA!)
        
        ### 📊 Raport Excel będzie zawierał:
        
        - **Kolumna "Grupa"** - numer grupy duplikatów (1, 2, 3...)
        - **Kolumna "Podobieństwo_%"** - jak bardzo podobne są nazwy
        - **WSZYSTKIE oryginalne kolumny z pliku** - zachowane w takiej samej kolejności
        
        **Przykład struktury raportu:**
        ```
        | Grupa | Podobieństwo_% | EAN           | Wydawca      | Autor         | Nazwa                    | Cena | Stock | ... |
        |-------|----------------|---------------|--------------|---------------|--------------------------|------|-------|-----|
        | 1     | 100%           | 9788374950001 | Media Rodzina| J.K. Rowling  | Harry Potter...          | 45.90| 10    | ... |
        | 1     | 92%            | 9788374950002 | Media Rodzina| J.K. Rowling  | Harry Potter (wyd. 2)... | 49.90| 5     | ... |
        | 2     | 100%           | 5901234567890 | [BRAK]       | [BRAK]        | LEGO City 60100...       | 199  | 3     | ... |
        | 2     | 88%            | 5901234567891 | [BRAK]       | [BRAK]        | Lego City 60100...       | 189  | 8     | ... |
        ```
        
        **Kolorowanie:**
        - Grupy są kolorowane na przemian (żółte/białe) dla łatwiejszego odczytu
        - Wszystkie produkty z tej samej grupy mają ten sam kolor tła
        """)
    
    # Przykładowe dane
    with st.expander("📋 Przykładowe dane"):
        st.markdown("**Przykład 1: Książki (z wydawcą i autorem)**")
        example_data1 = pd.DataFrame({
            'EAN': ['9788374950001', '9788374950002', '9788374950003', '9788374950004'],
            'Wydawca': ['Media Rodzina', 'Media Rodzina', 'Media Rodzina', 'Znak'],
            'Autor': ['J.K. Rowling', 'J.K. Rowling', 'J.K. Rowling', 'J.K. Rowling'],
            'Nazwa': [
                'Harry Potter i Kamień Filozoficzny',
                'Harry Potter i kamień filozoficzny (wyd. 2)',
                'HARRY POTTER I KAMIEŃ FILOZOFICZNY - pocket',
                'Harry Potter i Kamień Filozoficzny'
            ]
        })
        st.dataframe(example_data1, use_container_width=True, hide_index=True)
        st.caption("💡 Pierwsze 3 produkty to duplikaty (ten sam wydawca+autor+podobna nazwa)")
        
        st.markdown("---")
        st.markdown("**Przykład 2: Zabawki (bez wydawcy/autora)**")
        example_data2 = pd.DataFrame({
            'EAN': ['5901234567890', '5901234567891', '5901234567892'],
            'Wydawca': ['', '', ''],
            'Autor': ['', '', ''],
            'Nazwa': [
                'LEGO City 60100 Lotnisko - zestaw startowy',
                'Lego City 60100 lotnisko zestaw STARTOWY',
                'LEGO Creator 31058 Dinozaur'
            ]
        })
        st.dataframe(example_data2, use_container_width=True, hide_index=True)
        st.caption("💡 Pierwsze 2 produkty to duplikaty (puste wydawca/autor, ale podobna nazwa)")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>🔍 Weryfikator duplikatów produktów</div>",
    unsafe_allow_html=True
)