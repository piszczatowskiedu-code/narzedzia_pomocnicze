import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import io
import time
import json
import zipfile
import base64
import concurrent.futures
from datetime import datetime
from urllib.parse import quote

# ⚡ Ustawienie układu aplikacji na szeroki (WIDE)
try:
    st.set_page_config(
        page_title="Pobieranie okładek z Akeneo",
        page_icon="📥",
        layout="wide"
    )
except Exception:
    pass  # Jeśli st.set_page_config zostało wywołane wcześniej w app.py

# ⚡ Dodatkowy CSS znoszący ograniczenia szerokości i dostosowujący wygląd
st.markdown("""
<style>
    /* Wymuszenie szerokości na 95% ekranu */
    .main .block-container {
        max-width: 95% !important;
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 1rem; }
    textarea::placeholder { color: #e0e0e0 !important; opacity: 0.4 !important; }
    .akeneo-slot {
        width: 100%; aspect-ratio: 1 / 1; border-radius: 8px;
        overflow: hidden; display: flex; align-items: center;
        justify-content: center; margin-bottom: 6px;
    }
    .akeneo-slot img { max-width: 100%; max-height: 100%; object-fit: contain; }
    .akeneo-slot-filled { background: rgba(255,255,255,0.04); }
    .akeneo-slot-empty {
        background: transparent; border: 1px dashed rgba(255,255,255,0.15);
        color: rgba(255,255,255,0.25); font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  POŁĄCZENIE I SESJA (Connection Pooling + Bezpieczny Auto-Retry)
# ══════════════════════════════════════════════════════════════════

def get_session() -> requests.Session:
    """Współdzielona sesja z connection poolingiem i bezpiecznym ponawianiem prób."""
    if "_http_session" not in st.session_state:
        s = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=retries,
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        st.session_state._http_session = s
    return st.session_state._http_session


TIMEOUT = 30
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.tiff')
MIME_BY_EXT = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
    '.tiff': 'image/tiff', '.svg': 'image/svg+xml',
}

def guess_mime(filename):
    lower = filename.lower()
    for ext, mime in MIME_BY_EXT.items():
        if lower.endswith(ext):
            return mime
    return "image/jpeg"


# ══════════════════════════════════════════════════════════════════
#  KONFIGURACJA
# ══════════════════════════════════════════════════════════════════

def get_akeneo_config():
    try:
        cfg = st.secrets["akeneo"]
    except Exception:
        return None, "Brak sekcji [akeneo] w Streamlit secrets."
    required = ["base_url", "client_id", "client_secret", "username", "password"]
    missing = [k for k in required if k not in cfg]
    if missing:
        return None, f"Brak kluczy: {', '.join(missing)}"
    return cfg, None


# ══════════════════════════════════════════════════════════════════
#  API AKENEO
# ══════════════════════════════════════════════════════════════════

def get_token(cfg):
    cached = st.session_state.get('akeneo_token')
    expiry = st.session_state.get('akeneo_token_expiry', 0)
    if cached and time.time() < expiry:
        return cached

    session = get_session()
    base_url = cfg["base_url"].rstrip("/")
    resp = session.post(
        f"{base_url}/api/oauth/v1/token",
        auth=(cfg["client_id"], cfg["client_secret"]),
        json={
            "grant_type": "password",
            "username": cfg["username"],
            "password": cfg["password"],
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    st.session_state.akeneo_token = token
    st.session_state.akeneo_token_expiry = time.time() + data.get("expires_in", 3600) - 60
    return token


def fetch_products_batch(cfg, token, eans):
    """Pobiera wiele produktów jednym requestem (batch)."""
    if not eans:
        return {}, []

    session = get_session()
    base_url = cfg["base_url"].rstrip("/")
    results = {}
    errors = []

    CHUNK = 100
    for i in range(0, len(eans), CHUNK):
        chunk = eans[i:i + CHUNK]
        search = json.dumps({
            "identifier": [{"operator": "IN", "value": chunk}]
        })
        try:
            resp = session.get(
                f"{base_url}/api/rest/v1/products",
                params={"search": search, "limit": len(chunk)},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=TIMEOUT,
            )
            if resp.status_code == 401:
                st.session_state.pop('akeneo_token', None)
                return {}, ["Błąd autoryzacji (401) — token wygasł"]
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("_embedded", {}).get("items", []):
                ident = item.get("identifier", "")
                if ident:
                    results[ident] = item

        except requests.exceptions.RequestException as e:
            errors.append(f"Batch request error: {e}")

    for ean in eans:
        if ean not in results:
            errors.append(f"EAN {ean}: Nie znaleziono produktu w Akeneo (404)")

    return results, errors


def fetch_product_single(cfg, token, ean):
    """Fallback — pojedynczy produkt do debugu."""
    session = get_session()
    base_url = cfg["base_url"].rstrip("/")
    try:
        resp = session.get(
            f"{base_url}/api/rest/v1/products/{quote(ean, safe='')}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        return None, f"Błąd połączenia: {e}"

    if resp.status_code == 404:
        return None, "Nie znaleziono produktu (404)"
    if resp.status_code == 401:
        st.session_state.pop('akeneo_token', None)
        return None, "Błąd autoryzacji (401)"
    if resp.status_code != 200:
        return None, f"Błąd API: status {resp.status_code}"
    return resp.json(), None


GALLERY_ATTRS = ["image2", "image3", "image4", "image5"]


def extract_image_codes(product):
    values = product.get("values", {}) or {}
    images = []
    seen = set()

    def first_entry_with_data(attr):
        arr = values.get(attr)
        if not arr:
            return None
        for entry in arr:
            if entry.get("data"):
                return entry
        return None

    def add_image(entry, attribute):
        if not entry:
            return
        code = entry.get("data")
        if not code or code in seen:
            return
        seen.add(code)
        download_url = ((entry.get("_links") or {}).get("download") or {}).get("href")
        label = "Zdjęcie główne" if not images else f"Grafika {len(images)}"
        images.append({"code": code, "label": label, "attribute": attribute,
                        "download_url": download_url})

    add_image(first_entry_with_data("base_image"), "base_image")
    for attr in GALLERY_ATTRS:
        add_image(first_entry_with_data(attr), attr)
    return images


def _ext_from_response(resp, media_code):
    cd = resp.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        fname = cd.split("filename=")[-1].strip().strip('"').strip("'")
        if "." in fname:
            return "." + fname.rsplit(".", 1)[-1].lower()

    ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    mime_map = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
        "image/webp": ".webp", "image/bmp": ".bmp", "image/tiff": ".tiff",
        "image/svg+xml": ".svg",
    }
    if ct in mime_map:
        return mime_map[ct]

    if "." in media_code:
        return "." + media_code.rsplit(".", 1)[-1].lower()
    return ".jpg"


def _download_one_image(args):
    session, token, base_url, ean, idx, img_info = args
    download_url = img_info.get("download_url")
    if not download_url:
        code = img_info["code"]
        if "/" not in code and len(code) >= 4:
            code = "/".join(code[:4]) + "/" + code
        encoded = "/".join(quote(p, safe="") for p in code.split("/"))
        download_url = f"{base_url}/api/rest/v1/media-files/{encoded}/download"

    try:
        resp = session.get(
            download_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 429:
            return (ean, idx, None, "Przekroczono limit zapytań (Rate Limit 429)")
        if resp.status_code == 404:
            return (ean, idx, None, f"plik nie istnieje (404): {img_info['code']}")
        resp.raise_for_status()

        ext = _ext_from_response(resp, img_info["code"])
        suffix = "" if idx == 0 else f"_{idx}"
        filename = f"{ean}{suffix}{ext}"
        return (ean, idx, filename, resp.content)

    except Exception as e:
        return (ean, idx, None, f"błąd pobierania '{img_info['code']}': {e}")


# ══════════════════════════════════════════════════════════════════
#  POMOCNICZE
# ══════════════════════════════════════════════════════════════════

def create_zip(files_dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files_dict.items():
            zf.writestr(name, data)
    buf.seek(0)
    return buf


def parse_ean_list(text):
    if not text:
        return []
    result, seen = [], set()
    for line in text.strip().split("\n"):
        ean = line.strip()
        if not ean:
            continue
        try:
            ean = str(int(float(ean)))
        except (ValueError, OverflowError):
            pass
        if ean not in seen:
            seen.add(ean)
            result.append(ean)
    return result


# ══════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════

if 'akeneo_results' not in st.session_state:
    st.session_state.akeneo_results = None


# ══════════════════════════════════════════════════════════════════
#  UI
# ══════════════════════════════════════════════════════════════════

st.markdown("<div class='main-header'>📥 Pobieranie okładek z Akeneo</div>", unsafe_allow_html=True)
st.markdown("---")

cfg, cfg_error = get_akeneo_config()

if cfg_error:
    st.error(f"⚠️ {cfg_error}")
    with st.expander("ℹ️ Jak skonfigurować dostęp do Akeneo"):
        st.markdown("Dodaj sekcję w `.streamlit/secrets.toml`:")
        st.code(
            '[akeneo]\n'
            'base_url = "https://pimbl.mhost.eu"\n'
            'client_id = "twoj_client_id"\n'
            'client_secret = "twoj_client_secret"\n'
            'username = "twoj_login_api"\n'
            'password = "twoje_haslo_api"',
            language="toml"
        )
    st.stop()

with st.sidebar:
    st.header("⚙️ Ustawienia")
    only_main_image = st.checkbox(
        "Tylko zdjęcie główne", value=False,
        help="Pobiera tylko 'base_image', pomijając image_2–image_5."
    )
    max_workers = st.slider(
        "Równoległe pobieranie (wątki)", 
        min_value=1, 
        max_value=8, 
        value=4,
        help="Zalecane: 3-5. Bezpieczne dla zasobów serwera Akeneo."
    )
    max_gallery = 4

    if st.session_state.akeneo_results:
        st.markdown("---")
        if st.button("🗑️ Wyczyść wyniki", type="secondary", use_container_width=True):
            st.session_state.akeneo_results = None
            st.rerun()


with st.expander("🐞 Debug: podejrzyj surowe dane produktu z Akeneo"):
    st.caption("Wpisz jeden EAN i pobierz jego pełne dane z API.")
    debug_ean = st.text_input("EAN do sprawdzenia", key="debug_ean_input")
    if st.button("🔍 Pobierz surowe dane", key="debug_fetch_btn"):
        if not debug_ean.strip():
            st.warning("Podaj EAN.")
        else:
            try:
                debug_token = get_token(cfg)
                debug_product, debug_err = fetch_product_single(cfg, debug_token, debug_ean.strip())
                if debug_err:
                    st.error(debug_err)
                elif debug_product:
                    values = debug_product.get("values", {}) or {}
                    image_like_keys = {
                        k: v for k, v in values.items()
                        if any(kw in k.lower() for kw in ("image", "zdj", "grafik", "foto", "cover", "oklad"))
                    }
                    if image_like_keys:
                        st.success(f"Znaleziono {len(image_like_keys)} atrybutów grafiki:")
                        st.json(image_like_keys)
                    else:
                        st.warning("Brak atrybutów grafiki. Wszystkie klucze:")
                        st.code("\n".join(sorted(values.keys())))
                    if st.checkbox("Pokaż pełny JSON", key="debug_show_full_json"):
                        st.json(debug_product)
            except Exception as e:
                st.error(f"Błąd: {e}")

st.markdown("### 🔢 Lista EAN-ów")
ean_text = st.text_area(
    "Wklej kody EAN (jeden na linię):",
    height=180,
    placeholder="9788301234567\n9788301234568\n9788301234569"
)

ean_list = parse_ean_list(ean_text)
if ean_text.strip():
    st.caption(f"Wykryto **{len(ean_list)}** unikalnych EAN-ów.")

if st.button("🚀 POBIERZ GRAFIKI", type="primary", use_container_width=True, disabled=not ean_list):

    try:
        with st.spinner("Autoryzacja w Akeneo..."):
            token = get_token(cfg)
    except Exception as e:
        st.error(f"❌ Błąd autoryzacji: {e}")
        st.stop()

    session = get_session()
    base_url = cfg["base_url"].rstrip("/")

    downloaded_files = {}
    product_previews = {}
    stats = {'sukces': 0, 'brak_produktu': 0, 'brak_grafik': 0, 'blad': 0}
    errors_log = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_expander = st.expander("⚠️ Dziennik zdarzeń", expanded=True)

    # ── KROK 1: Batch fetch (1 request) ───────────────────────────
    status_text.text("📦 Pobieranie danych produktów (batch)...")
    products_map, batch_errors = fetch_products_batch(cfg, token, ean_list)

    for err_msg in batch_errors:
        if "404" in err_msg:
            stats['brak_produktu'] += 1
        else:
            stats['blad'] += 1
        errors_log.append(err_msg)
        log_expander.warning(err_msg)

    progress_bar.progress(0.2)

    # ── KROK 2: Przygotowanie listy grafik ────────────────────────
    download_tasks = []

    for ean in ean_list:
        product = products_map.get(ean)
        if not product:
            continue

        image_codes = extract_image_codes(product)
        if only_main_image:
            image_codes = image_codes[:1]
        else:
            image_codes = image_codes[: 1 + max_gallery]

        if not image_codes:
            msg = f"EAN {ean}: produkt znaleziony, brak grafik"
            errors_log.append(msg)
            log_expander.info(msg)
            stats['brak_grafik'] += 1
            continue

        product_name = None
        name_attr = (product.get("values", {}) or {}).get("name")
        if name_attr:
            product_name = name_attr[0].get("data")
        product_previews[ean] = {'name': product_name, 'files': []}

        for i, img_info in enumerate(image_codes):
            download_tasks.append((session, token, base_url, ean, i, img_info))

    progress_bar.progress(0.3)

    # ── KROK 3: Równoległe pobieranie grafik ──────────────────────
    status_text.text(f"🖼️ Pobieranie {len(download_tasks)} grafik równolegle...")

    if download_tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_download_one_image, task): task
                for task in download_tasks
            }

            done_count = 0
            total = len(futures)
            for future in concurrent.futures.as_completed(futures):
                done_count += 1
                ean, idx, filename, data_or_err = future.result()

                pct = 0.3 + 0.7 * (done_count / total)
                progress_bar.progress(min(pct, 1.0))
                status_text.text(f"🖼️ Pobrano {done_count}/{total} grafik...")

                if filename is None:
                    msg = f"EAN {ean}: {data_or_err}"
                    errors_log.append(msg)
                    log_expander.error(msg)
                    stats['blad'] += 1
                    continue

                downloaded_files[filename] = data_or_err
                if ean in product_previews:
                    product_previews[ean]['files'].append((filename, data_or_err))
                stats['sukces'] += 1

    for ean in product_previews:
        product_previews[ean]['files'].sort(
            key=lambda x: (
                0 if "_" not in x[0].replace(ean, "", 1).split(".")[0]
                else int(x[0].replace(ean, "", 1).split("_")[1].split(".")[0])
            )
        )

    product_previews = {k: v for k, v in product_previews.items() if v['files']}

    progress_bar.progress(1.0)
    status_text.text("✅ Gotowe!")

    st.session_state.akeneo_results = {
        'stats': stats,
        'errors_log': errors_log,
        'downloaded_files': downloaded_files,
        'product_previews': product_previews,
        'ean_order': [e for e in ean_list if e in product_previews],
    }
    st.rerun()


# ══════════════════════════════════════════════════════════════════
#  WYNIKI
# ══════════════════════════════════════════════════════════════════

if st.session_state.akeneo_results:
    res = st.session_state.akeneo_results
    s = res['stats']

    st.markdown("---")
    st.markdown("## 📊 Wyniki")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Pobrane grafiki", s['sukces'])
    c2.metric("❓ Nie znaleziono produktu", s['brak_produktu'])
    c3.metric("🖼️ Bez grafik", s['brak_grafik'])
    c4.metric("❌ Błędy", s['blad'])

    if res['errors_log']:
        with st.expander(f"📋 Log zdarzeń ({len(res['errors_log'])})", expanded=False):
            for msg in res['errors_log']:
                st.warning(msg)

    if res['downloaded_files']:
        st.markdown("---")
        st.markdown("## 🖼️ Podgląd i wybór grafik do pobrania")
        st.caption(
            "Domyślnie zaznaczona jest tylko grafika główna (slot 1). "
            "Zaznacz dodatkowe, które chcesz dołączyć do paczki ZIP."
        )

        selected_files = {}

        for ean in res['ean_order']:
            entry = res['product_previews'].get(ean)
            if not entry:
                continue
            files = entry['files']

            title = f"#### {ean}"
            if entry.get('name'):
                title += f" — {entry['name']}"
            st.markdown(title)

            cols = st.columns(5)
            for i in range(5):
                with cols[i]:
                    if i < len(files):
                        filename, file_data = files[i]
                        mime = guess_mime(filename)
                        b64 = base64.b64encode(file_data).decode()

                        st.markdown(
                            f'<div class="akeneo-slot akeneo-slot-filled">'
                            f'<img src="data:{mime};base64,{b64}" alt="{filename}" />'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                        label = "Główna" if i == 0 else f"Dod. {i}"
                        checked = st.checkbox(
                            label, value=(i == 0), key=f"sel_{ean}_{i}"
                        )
                        st.caption(filename)
                        st.download_button(
                            "⬇️ Pobierz", data=file_data,
                            file_name=filename, mime=mime,
                            key=f"dl_{ean}_{i}", use_container_width=True
                        )
                        if checked:
                            selected_files[filename] = file_data
                    else:
                        st.markdown(
                            '<div class="akeneo-slot akeneo-slot-empty">brak</div>',
                            unsafe_allow_html=True
                        )
                        st.caption("—")
            st.markdown("")

        st.markdown("---")
        if selected_files:
            zip_buffer = create_zip(selected_files)
            st.download_button(
                label=f"⬇️ POBIERZ ZAZNACZONE JAKO ZIP ({len(selected_files)} plików)",
                data=zip_buffer,
                file_name=f"okladki_akeneo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )
        else:
            st.info("Zaznacz przynajmniej jedną grafikę, aby pobrać ZIP.")
else:
    st.info('💡 Wklej listę EAN-ów i kliknij "POBIERZ GRAFIKI", aby rozpocząć.')

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>📥 Pobieranie okładek z Akeneo</div>",
    unsafe_allow_html=True
)