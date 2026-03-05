import streamlit as st
import pandas as pd
import re
from io import BytesIO
from typing import Optional

# ============================================
# KONFIGURACJA STRONY
# ============================================
st.set_page_config(
    page_title="Konwerter opisów na HTML",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #ff7f0e;
        text-align: center;
        margin-bottom: 1rem;
    }
    textarea::placeholder {
        color: #e0e0e0 !important;
        opacity: 0.4 !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# FUNKCJE POMOCNICZE
# ============================================

def parse_ean_list(ean_text):
    """Parsuje listę kodów EAN z tekstu"""
    if not ean_text:
        return set()
    
    ean_list = []
    for line in ean_text.strip().split('\n'):
        ean = line.strip()
        if ean:
            ean = str(ean).strip().replace(' ', '')
            ean_list.append(ean)
    
    return set(ean_list)

# ============================================
# FUNKCJE KONWERSJI TEKSTU NA HTML
# ============================================

def convert_inline_formatting(text: str) -> str:
    """Konwertuje formatowanie inline (pogrubienie, kursywa)."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_]+)_', r'<em>\1</em>', text)
    return text


def detect_heading(line: str) -> Optional[tuple[int, str]]:
    """Wykrywa nagłówki w różnych formatach."""
    match = re.match(r'^(#{1,6})\s+(.+)$', line)
    if match:
        level = len(match.group(1))
        return (level, match.group(2))
    
    if line.endswith(':') and len(line) < 60 and not line.startswith('-'):
        return (3, line[:-1])
    
    return None


def text_to_html(text: str, options: dict) -> str:
    """Główna funkcja konwertująca tekst na HTML."""
    if not text or pd.isna(text):
        return ""
    
    text = str(text).strip()
    lines = text.split('\n')
    html_parts = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Nagłówki
        if options.get('convert_headings', True):
            heading = detect_heading(line)
            if heading:
                level, heading_text = heading
                if options.get('convert_formatting', True):
                    heading_text = convert_inline_formatting(heading_text)
                html_parts.append(f"<h{level}>{heading_text}</h{level}>")
                i += 1
                continue
        
        # Listy
        if options.get('convert_lists', True):
            # Lista punktowana
            if re.match(r'^[-*•]\s+', line):
                list_items = []
                while i < len(lines) and re.match(r'^[-*•]\s+', lines[i].strip()):
                    item_text = re.sub(r'^[-*•]\s+', '', lines[i].strip())
                    if options.get('convert_formatting', True):
                        item_text = convert_inline_formatting(item_text)
                    list_items.append(f"  <li>{item_text}</li>")
                    i += 1
                html_parts.append("<ul>\n" + "\n".join(list_items) + "\n</ul>")
                continue
            
            # Lista numerowana
            if re.match(r'^\d+[.)]\s+', line):
                list_items = []
                while i < len(lines) and re.match(r'^\d+[.)]\s+', lines[i].strip()):
                    item_text = re.sub(r'^\d+[.)]\s+', '', lines[i].strip())
                    if options.get('convert_formatting', True):
                        item_text = convert_inline_formatting(item_text)
                    list_items.append(f"  <li>{item_text}</li>")
                    i += 1
                html_parts.append("<ol>\n" + "\n".join(list_items) + "\n</ol>")
                continue
        
        # Zwykły paragraf
        paragraph_lines = []
        while i < len(lines) and lines[i].strip():
            current_line = lines[i].strip()
            
            if options.get('convert_lists', True):
                if re.match(r'^[-*•]\s+', current_line) or re.match(r'^\d+[.)]\s+', current_line):
                    break
            if options.get('convert_headings', True) and detect_heading(current_line):
                break
                
            paragraph_lines.append(current_line)
            i += 1
        
        if paragraph_lines:
            paragraph_text = ' '.join(paragraph_lines)
            if options.get('convert_formatting', True):
                paragraph_text = convert_inline_formatting(paragraph_text)
            if options.get('add_paragraphs', True):
                html_parts.append(f"<p>{paragraph_text}</p>")
            else:
                html_parts.append(paragraph_text)
    
    html = '\n\n'.join(html_parts)
    
    if options.get('wrap_in_div', False):
        html = f'<div class="product-description">\n{html}\n</div>'
    
    return html


# ============================================
# INTERFEJS UŻYTKOWNIKA
# ============================================

# Nagłówek
st.markdown("<div class='main-header'>📝 Konwerter opisów na HTML</div>", unsafe_allow_html=True)
st.markdown("---")

# Sidebar z opcjami
with st.sidebar:
    st.header("⚙️ Opcje konwersji")
    
    options = {
        'add_paragraphs': st.checkbox("Dodaj tagi <p>", value=True),
        'convert_lists': st.checkbox("Konwertuj listy", value=True),
        'convert_headings': st.checkbox("Konwertuj nagłówki", value=True),
        'convert_formatting': st.checkbox("Pogrubienie/kursywa", value=True),
        'wrap_in_div': st.checkbox("Opakuj w <div>", value=False),
    }

# Główna część aplikacji
uploaded_file = st.file_uploader(
    "Wybierz plik Excel",
    type=['xlsx', 'xls'],
    help="Plik powinien zawierać kolumny z kodami EAN i opisami produktów"
)

if uploaded_file is not None:
    try:
        # Wczytaj plik
        with st.spinner("Wczytywanie..."):
            df = pd.read_excel(uploaded_file, dtype=str)
        
        columns = df.columns.tolist()
        
        # Wybór kolumn
        col1, col2 = st.columns(2)
        
        with col1:
            ean_column = st.selectbox(
                "Kolumna z kodami EAN:",
                columns,
                index=columns.index('EAN') if 'EAN' in columns else 0
            )
        
        with col2:
            default_desc_index = 1 if len(columns) > 1 else 0
            for i, col in enumerate(columns):
                if 'opis' in col.lower() or 'desc' in col.lower():
                    default_desc_index = i
                    break
                    
            description_column = st.selectbox(
                "Kolumna z opisami:",
                columns,
                index=default_desc_index
            )
        
        # Sekcja filtrowania EAN
        st.markdown("---")
        st.markdown("### 🔍 Filtrowanie po kodach EAN (opcjonalne)")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            ean_filter_text = st.text_area(
                "Wklej kody EAN do konwersji (jeden kod na linię)",
                height=150,
                placeholder="5901234567890\n5907654321098\n9788374959216",
                help="Zostaw puste aby skonwertować wszystkie produkty"
            )
        
        with col2:
            if ean_filter_text:
                ean_filter_set = parse_ean_list(ean_filter_text)
                st.info(f"Kodów: **{len(ean_filter_set)}**")
                
                df_eans = set(df[ean_column].dropna().astype(str))
                matching = sum(1 for ean in ean_filter_set if ean in df_eans)
                st.success(f"Znaleziono: **{matching}**")
        
        # Przycisk konwersji
        st.markdown("---")
        
        if st.button("🚀 KONWERTUJ NA HTML", type="primary", width="stretch"):
            with st.spinner("Konwertuję..."):
                # Przygotuj dane do konwersji
                working_df = df.copy()
                missing_eans = None
                
                # Zastosuj filtr EAN jeśli podany
                if ean_filter_text:
                    ean_filter_set = parse_ean_list(ean_filter_text)
                    working_df = working_df[working_df[ean_column].isin(ean_filter_set)]
                    found_eans = set(working_df[ean_column].dropna())
                    missing_eans = ean_filter_set - found_eans
                
                # Konwersja
                export_df = pd.DataFrame({
                    'sku': working_df[ean_column].fillna(''),
                    'description-B2B': working_df[description_column].apply(
                        lambda x: text_to_html(x, options)
                    )
                })
                
                # Raport brakujących EAN
                if missing_eans:
                    st.warning(f"⚠️ Nie znaleziono {len(missing_eans)} kodów EAN")
                    with st.expander("Zobacz brakujące kody"):
                        st.text_area(
                            "",
                            value='\n'.join(sorted(list(missing_eans))),
                            height=200
                        )
                
                # Przygotuj plik Excel
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    export_df.to_excel(
                        writer, 
                        index=False, 
                        sheet_name='Produkty_HTML'
                    )
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Produkty_HTML']
                    
                    text_format = workbook.add_format({'num_format': '@'})
                    worksheet.set_column(0, 0, 20, text_format)
                    worksheet.set_column(1, 1, 100)
                    
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#D7E4BD',
                        'border': 1
                    })
                    for col_num, value in enumerate(export_df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                
                output.seek(0)
                
                # Nazwa pliku
                original_name = uploaded_file.name.rsplit('.', 1)[0]
                output_filename = f"{original_name}_HTML.xlsx"
                
                # Pobieranie
                st.markdown("---")
                st.download_button(
                    label=f"⬇️ POBIERZ EXCEL ({len(export_df)} produktów)",
                    data=output,
                    file_name=output_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    type="primary"
                )

                # ── Podgląd wyrenderowanego HTML ──────────────────────────────
                st.markdown("---")
                st.markdown("## 👁️ Podgląd opisów HTML")
                st.caption(f"Wyrenderowany widok dla {len(export_df)} produktów.")

                import streamlit.components.v1 as _components

                rows_html_parts = []
                for _, row in export_df.iterrows():
                    ean_val  = str(row['sku'])
                    desc_val = str(row['description-B2B']) if row['description-B2B'] else "<em style='color:#bbb'>— brak opisu —</em>"
                    rows_html_parts.append(
                        "<tr>"
                        f"<td class='ean-cell'>{ean_val}</td>"
                        f"<td class='desc-cell'>{desc_val}</td>"
                        "</tr>"
                    )
                rows_html = "\n".join(rows_html_parts)

                preview_html = (
                    "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
                    "* {box-sizing:border-box;margin:0;padding:0;}"
                    "body {font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
                    "font-size:14px;color:#222;background:#fff;padding:8px;}"
                    "table {width:100%;border-collapse:collapse;}"
                    "thead th {background:#f0f2f6;padding:10px 14px;text-align:left;"
                    "font-weight:700;font-size:13px;color:#444;border-bottom:2px solid #dde;"
                    "position:sticky;top:0;z-index:10;}"
                    "th.ean-head {width:170px;}"
                    "tr:nth-child(even) td {background:#fafbfc;}"
                    "tr:hover td {background:#f0f4ff;}"
                    "td {padding:12px 14px;vertical-align:top;border-bottom:1px solid #eee;}"
                    "td.ean-cell {font-family:monospace;font-size:12px;color:#666;"
                    "width:170px;white-space:nowrap;}"
                    "td.desc-cell h1,td.desc-cell h2,td.desc-cell h3,"
                    "td.desc-cell h4,td.desc-cell h5,td.desc-cell h6 {"
                    "margin:.5em 0 .3em;font-weight:700;color:#000;}"
                    "td.desc-cell h1 {font-size:1.4em;}"
                    "td.desc-cell h2 {font-size:1.25em;}"
                    "td.desc-cell h3 {font-size:1.1em;}"
                    "td.desc-cell p {margin:.4em 0;line-height:1.6;}"
                    "td.desc-cell ul,td.desc-cell ol {margin:.4em 0 .4em 1.4em;line-height:1.7;}"
                    "td.desc-cell li {margin-bottom:2px;}"
                    "td.desc-cell strong {font-weight:700;}"
                    "td.desc-cell em {font-style:italic;color:#555;}"
                    "</style></head><body>"
                    "<table><thead><tr>"
                    "<th class='ean-head'>EAN / SKU</th>"
                    "<th>Opis (wyrenderowany HTML)</th>"
                    "</tr></thead><tbody>"
                    + rows_html +
                    "</tbody></table></body></html>"
                )

                preview_height = min(200 + len(export_df) * 120, 4000)
                _components.html(preview_html, height=preview_height, scrolling=True)
                    
    except Exception as e:
        st.error(f"❌ Błąd: {str(e)}")

else:
    st.info("📤 Wgraj plik Excel z opisami produktów")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>📝 Konwerter opisów na HTML</div>",
    unsafe_allow_html=True
)