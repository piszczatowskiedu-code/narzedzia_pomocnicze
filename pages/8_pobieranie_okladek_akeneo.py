import streamlit as st
import requests
import io
import time
import zipfile
import base64
from datetime import datetime
from PIL import Image
from urllib.parse import quote

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 1rem; }
    textarea::placeholder { color: #e0e0e0 !important; opacity: 0.4 !important; }
    .akeneo-slot {
        width: 100%;
        aspect-ratio: 1 / 1;
        border-radius: 8px;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 6px;
    }
    .akeneo-slot img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    .akeneo-slot-filled { background: rgba(255,255,255,0.04); }
    .akeneo-slot-empty {
        background: transparent;
        border: 1px dashed rgba(255,255,255,0.15);
        color: rgba(255,255,255,0.25);
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

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
#  KONFIGURACJA (Streamlit secrets)
# ══════════════════════════════════════════════════════════════════
#
# Wymagany wpis w .streamlit/secrets.toml:
#
# [akeneo]
# base_url = "https://pimbl.mhost.eu"
# client_id = "xxxxxxxx"
# client_secret = "xxxxxxxx"
# username = "xxxxxxxx"
# password = "xxxxxxxx"

def get_akeneo_config():
    try:
        cfg = st.secrets["akeneo"]
    except Exception:
        return None, "Brak sekcji [akeneo] w Streamlit secrets."

    required = ["base_url", "client_id", "client_secret", "username", "password"]
    missing = [k for k in required if k not in cfg]
    if missing:
        return None, f"Brak kluczy w st.secrets['akeneo']: {', '.join(missing)}"

    return cfg, None


# ══════════════════════════════════════════════════════════════════
#  API AKENEO
# ══════════════════════════════════════════════════════════════════

def get_token(cfg):
    """Pobiera token OAuth2 (grant_type=password), cache'owany w session_state."""
    cached = st.session_state.get('akeneo_token')
    expiry = st.session_state.get('akeneo_token_expiry', 0)
    if cached and time.time() < expiry:
        return cached

    base_url = cfg["base_url"].rstrip("/")
    resp = requests.post(
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


def fetch_product(cfg, token, ean):
    """Pobiera produkt po identyfikatorze (EAN). Zwraca (dane, blad)."""
    base_url = cfg["base_url"].rstrip("/")
    try:
        resp = requests.get(
            f"{base_url}/api/rest/v1/products/{quote(ean, safe='')}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        return None, f"Błąd połączenia: {e}"

    if resp.status_code == 404:
        return None, "Nie znaleziono produktu w Akeneo (404)"
    if resp.status_code == 401:
        # token mógł wygasnąć w trakcie — wyczyść cache, spróbuj raz jeszcze wyżej w pętli
        st.session_state.pop('akeneo_token', None)
        return None, "Błąd autoryzacji (401) — token wygasł"
    if resp.status_code != 200:
        return None, f"Błąd API: status {resp.status_code}"

    return resp.json(), None


def normalize_media_code(code):
    """Zamienia płaski kod media na ścieżkę katalogową (jak w Akeneo media/cache)."""
    if not code:
        return code
    if "/" in code:
        return code
    if len(code) < 4:
        return code
    prefix = "/".join(code[:4])
    return f"{prefix}/{code}"


GALLERY_ATTRS = ["image2", "image3", "image4", "image5"]


def extract_image_codes(product):
    """Ekstrahuje kody grafik z produktu: 'base_image' (główna), potem 'image2'..'image5' (dodatkowe, w tej kolejności).

    Każdy wpis w API zawiera gotowy link _links.download.href — używamy go bezpośrednio
    zamiast ręcznie rekonstruować ścieżkę media-file.
    """
    values = product.get("values", {}) or {}
    images = []
    seen = set()

    def first_entry_with_data(attr):
        arr = values.get(attr)
        if not arr:
            return None
        # Atrybut może być scopable/localizable — ma wtedy kilka wpisów
        # (po jednym na kanał/język). Szukamy pierwszego z realną wartością,
        # zamiast bezwarunkowo brać arr[0], który może być pusty dla danego scope.
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
        images.append({"code": code, "label": label, "attribute": attribute, "download_url": download_url})

    add_image(first_entry_with_data("base_image"), "base_image")
    for attr in GALLERY_ATTRS:
        add_image(first_entry_with_data(attr), attr)

    return images


def fetch_media_metadata(cfg, token, media_code, metadata_url=None):
    """Pobiera metadane pliku (original_filename, mime_type, size) — best effort, None jeśli niedostępne."""
    if metadata_url:
        url = metadata_url
    else:
        base_url = cfg["base_url"].rstrip("/")
        normalized = normalize_media_code(media_code)
        encoded = "/".join(quote(part, safe="") for part in normalized.split("/"))
        url = f"{base_url}/api/rest/v1/media-files/{encoded}"

    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException:
        pass
    return None


def guess_extension(media_code, metadata):
    """Ustala rozszerzenie pliku: najpierw z metadanych API, potem z kodu media."""
    if metadata:
        original = metadata.get("original_filename") or ""
        if "." in original:
            return "." + original.rsplit(".", 1)[-1].lower()
        mime = metadata.get("mime_type") or ""
        if "/" in mime:
            sub = mime.split("/")[-1].lower()
            mime_map = {"jpeg": ".jpg", "png": ".png", "gif": ".gif", "webp": ".webp",
                        "bmp": ".bmp", "tiff": ".tiff", "svg+xml": ".svg"}
            if sub in mime_map:
                return mime_map[sub]

    if "." in media_code:
        return "." + media_code.rsplit(".", 1)[-1].lower()
    return ".jpg"


def download_media_file(cfg, token, media_code, metadata=None, download_url=None):
    """Pobiera oryginalny (pełnej jakości) plik grafiki z Akeneo.

    Jeśli mamy gotowy download_url z odpowiedzi API (_links.download.href), używamy go
    bezpośrednio — jest pewniejszy niż ręczna rekonstrukcja ścieżki media-file.
    """
    if download_url:
        url = download_url
    else:
        base_url = cfg["base_url"].rstrip("/")
        normalized = normalize_media_code(media_code)
        encoded = "/".join(quote(part, safe="") for part in normalized.split("/"))
        url = f"{base_url}/api/rest/v1/media-files/{encoded}/download"

    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"błąd połączenia: {e}") from e

    if resp.status_code == 404:
        raise requests.exceptions.RequestException("plik nie istnieje w Akeneo (404)")
    resp.raise_for_status()

    ext = guess_extension(media_code, metadata)
    return resp.content, ext


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
        st.markdown("Dodaj sekcję w pliku `.streamlit/secrets.toml` (lub w Streamlit Cloud → Settings → Secrets):")
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
        "Tylko zdjęcie główne",
        value=False,
        help="Jeśli zaznaczone, pobiera tylko 'base_image', pomijając image_2–image_5."
    )

    max_gallery = 4
    delay_between = 0.10
    fetch_metadata = True

    if st.session_state.akeneo_results:
        st.markdown("---")
        if st.button("🗑️ Wyczyść wyniki", type="secondary", use_container_width=True):
            st.session_state.akeneo_results = None
            st.rerun()


with st.expander("🐞 Debug: podejrzyj surowe dane produktu z Akeneo"):
    st.caption(
        "Wpisz jeden EAN i pobierz jego pełne dane z API, żeby sprawdzić, "
        "jak faktycznie nazywają się atrybuty grafik i czy mają wypełnione wartości."
    )
    debug_ean = st.text_input("EAN do sprawdzenia", key="debug_ean_input")
    if st.button("🔍 Pobierz surowe dane", key="debug_fetch_btn"):
        if not debug_ean.strip():
            st.warning("Podaj EAN.")
        else:
            try:
                debug_token = get_token(cfg)
                debug_product, debug_err = fetch_product(cfg, debug_token, debug_ean.strip())
                if debug_err:
                    st.error(debug_err)
                elif debug_product:
                    values = debug_product.get("values", {}) or {}

                    image_like_keys = {
                        k: v for k, v in values.items()
                        if any(kw in k.lower() for kw in ("image", "zdj", "grafik", "foto", "cover", "oklad"))
                    }

                    if image_like_keys:
                        st.success(f"Znaleziono {len(image_like_keys)} atrybutów pasujących do wzorca grafiki:")
                        st.json(image_like_keys)
                    else:
                        st.warning(
                            "Nie znaleziono atrybutów zawierających w nazwie 'image', 'zdj', 'grafik', "
                            "'foto', 'cover' ani 'oklad'. Zobacz pełną listę atrybutów poniżej."
                        )
                        st.write("Wszystkie dostępne atrybuty (klucze):")
                        st.code("\n".join(sorted(values.keys())))

                    show_full_json = st.checkbox("Pokaż pełny JSON produktu", key="debug_show_full_json")
                    if show_full_json:
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
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Nie udało się uzyskać tokenu API: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ Błąd konfiguracji API: {e}")
        st.stop()

    downloaded_files = {}       # nazwa_pliku.ext -> bytes
    product_previews = {}       # ean -> [(filename, bytes), ...]  (w kolejności pobierania)
    stats = {'sukces': 0, 'brak_produktu': 0, 'brak_grafik': 0, 'blad': 0}
    errors_log = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_expander = st.expander("⚠️ Dziennik zdarzeń", expanded=True)

    for idx, ean in enumerate(ean_list):
        progress_bar.progress((idx + 1) / len(ean_list))
        status_text.text(f"Przetwarzanie: {ean} ({idx + 1}/{len(ean_list)})")

        product, err = fetch_product(cfg, token, ean)

        # jeśli token wygasł w trakcie, spróbuj raz jeszcze z nowym tokenem
        if err and "wygasł" in err:
            try:
                token = get_token(cfg)
                product, err = fetch_product(cfg, token, ean)
            except Exception as e:
                err = f"Błąd odświeżania tokenu: {e}"

        if err:
            msg = f"EAN {ean}: {err}"
            errors_log.append(msg)
            log_expander.warning(msg)
            stats['brak_produktu'] += 1
            time.sleep(delay_between)
            continue

        image_codes = extract_image_codes(product)
        if only_main_image:
            image_codes = image_codes[:1]
        else:
            image_codes = image_codes[: 1 + max_gallery]

        if not image_codes:
            msg = f"EAN {ean}: produkt znaleziony, ale brak przypisanych grafik"
            errors_log.append(msg)
            log_expander.info(msg)
            stats['brak_grafik'] += 1
            time.sleep(delay_between)
            continue

        product_name = None
        name_attr = (product.get("values", {}) or {}).get("name")
        if name_attr:
            product_name = name_attr[0].get("data")

        product_previews[ean] = {'name': product_name, 'files': []}

        for i, img_info in enumerate(image_codes):
            download_url = img_info.get("download_url")
            metadata_url = f"{download_url.rsplit('/download', 1)[0]}" if download_url else None
            metadata = fetch_media_metadata(cfg, token, img_info["code"], metadata_url) if fetch_metadata else None

            try:
                image_bytes, ext = download_media_file(cfg, token, img_info["code"], metadata, download_url)
            except requests.exceptions.RequestException as e:
                msg = f"EAN {ean}: błąd pobierania grafiki '{img_info['code']}': {e}"
                errors_log.append(msg)
                log_expander.error(msg)
                stats['blad'] += 1
                continue

            suffix = "" if i == 0 else f"_{i}"
            filename = f"{ean}{suffix}{ext}"

            downloaded_files[filename] = image_bytes
            product_previews[ean]['files'].append((filename, image_bytes))
            stats['sukces'] += 1

        if not product_previews[ean]['files']:
            del product_previews[ean]

        time.sleep(delay_between)

    st.session_state.akeneo_results = {
        'stats': stats,
        'errors_log': errors_log,
        'downloaded_files': downloaded_files,
        'product_previews': product_previews,
        'ean_order': list(product_previews.keys()),
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

        selected_files = {}  # filename -> bytes (tylko zaznaczone checkboxem)

        for ean in res['ean_order']:
            entry = res['product_previews'].get(ean)
            if not entry:
                continue
            files = entry['files']  # max 5: [główna, dod.1, dod.2, dod.3, dod.4]

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
                            label,
                            value=(i == 0),
                            key=f"sel_{ean}_{i}"
                        )
                        st.caption(filename)
                        st.download_button(
                            "⬇️ Pobierz",
                            data=file_data,
                            file_name=filename,
                            mime=mime,
                            key=f"dl_{ean}_{i}",
                            use_container_width=True
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
    st.info("💡 Wklej listę EAN-ów i kliknij „POBIERZ GRAFIKI”, aby rozpocząć.")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>📥 Pobieranie okładek z Akeneo</div>",
    unsafe_allow_html=True
)
