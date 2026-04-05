import json
import base64
import html
import os
import re

import requests
import streamlit as st
import streamlit.components.v1 as components

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
PDF_EXTENSIONS = {"pdf"}


def read_tunnel_url(log_name: str) -> str:
    log_path = os.path.join(os.path.dirname(__file__), "..", log_name)
    if not os.path.exists(log_path):
        return ""

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read()
    except OSError:
        return ""

    match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", content, re.IGNORECASE)
    return match.group(0) if match else ""


def read_ngrok_urls() -> dict[str, str]:
    try:
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}

    urls: dict[str, str] = {}
    for tunnel in payload.get("tunnels", []):
        public_url = str(tunnel.get("public_url", "")).strip()
        addr = str(tunnel.get("config", {}).get("addr", "")).strip().lower()
        if not public_url.startswith("https://"):
            continue
        if "8501" in addr and not urls.get("frontend"):
            urls["frontend"] = public_url
        if "8000" in addr and not urls.get("backend"):
            urls["backend"] = public_url
    return urls


def uploaded_image_to_data_url(uploaded_file) -> str:
    mime_type = uploaded_file.type or "image/png"
    encoded = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def uploaded_file_extension(uploaded_file) -> str:
    return os.path.splitext(getattr(uploaded_file, "name", ""))[1].lower().lstrip(".")


def render_file_chips(files: list[str], prefix: str = "") -> None:
    if not files:
        return

    chips = "".join(
        f'<span class="chatgpt-chip">{html.escape(file_name)}</span>'
        for file_name in files
    )
    label = f'<span class="chatgpt-chip-label">{html.escape(prefix)}</span>' if prefix else ""
    st.markdown(
        f'<div class="chatgpt-chip-row">{label}{chips}</div>',
        unsafe_allow_html=True,
    )


def build_chat_history(messages: list[dict]) -> list[dict]:
    history = []
    for message in messages[-8:]:
        history.append(
            {
                "role": message.get("role", ""),
                "content": message.get("ai_content", message.get("content", "")),
            }
        )
    return history


def extract_pdf_text(uploaded_file, server_api_base: str) -> str:
    response = requests.post(
        f"{server_api_base}/pdf/read",
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/pdf",
            )
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("text", "")).strip()


def build_prompt_with_pdf_context(
    prompt: str,
    pdf_files: list,
    server_api_base: str,
) -> tuple[str, list[str]]:
    pdf_sections = []
    pdf_errors = []

    for uploaded_file in pdf_files or []:
        try:
            extracted_text = extract_pdf_text(uploaded_file, server_api_base)
            if extracted_text.startswith("Error reading PDF:"):
                pdf_errors.append(f"{uploaded_file.name}: {extracted_text}")
            elif extracted_text in {"PDF file not found.", "No readable text found in the PDF."}:
                pdf_errors.append(f"{uploaded_file.name}: {extracted_text}")
            elif extracted_text:
                pdf_sections.append(f"[PDF: {uploaded_file.name}]\n{extracted_text}")
            else:
                pdf_errors.append(f"{uploaded_file.name}: No readable text returned.")
        except Exception as exc:
            pdf_errors.append(f"{uploaded_file.name}: {exc}")

    if not pdf_sections:
        return prompt, pdf_errors

    pdf_context = "\n\n".join(pdf_sections)
    combined_prompt = (
        f"{prompt}\n\n"
        "Use the following extracted PDF text as supporting context when it is relevant:\n\n"
        f"{pdf_context}"
    )
    return combined_prompt, pdf_errors


def run_device_action(action: dict, server_api_base: str) -> str:
    app_name = str((action or {}).get("app", "")).strip()
    if not app_name:
        return "Missing app name for this action."

    response = requests.post(
        f"{server_api_base}/device/open",
        json={"app": app_name},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("message", "Action completed.")).strip()


def render_chat_action(action: dict, server_api_base: str, action_key: str) -> None:
    if not action:
        return

    action_label = action.get("label")
    action_url = action.get("url")
    action_kind = action.get("kind", "url")
    feedback_key = f"{action_key}_feedback"

    if action_kind == "device" and action_label:
        if st.button(action_label, key=action_key):
            try:
                st.session_state[feedback_key] = run_device_action(action, server_api_base)
            except Exception as exc:
                st.session_state[feedback_key] = f"Action failed: {exc}"
        if st.session_state.get(feedback_key):
            st.caption(st.session_state[feedback_key])
        return

    if action_label and action_url:
        st.markdown(f"[{action_label}]({action_url})")


def normalize_url_text(value: str) -> str:
    return str(value or "").strip().rstrip("/")


NGROK_URLS = read_ngrok_urls()

SERVER_API_BASE = os.getenv(
    "SERVER_API_BASE_URL",
    "http://127.0.0.1:8000",
)
PUBLIC_API_BASE = os.getenv(
    "PUBLIC_API_BASE_URL",
    NGROK_URLS.get("backend") or read_tunnel_url("cloudflared-backend.err.log"),
)
PUBLIC_APP_URL = os.getenv(
    "PUBLIC_APP_URL",
    NGROK_URLS.get("frontend") or read_tunnel_url("cloudflared-frontend.err.log"),
)
LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "chotu_logo.svg")

st.set_page_config(page_title="Chotu AI Assistant", page_icon=LOGO_PATH, layout="wide")
logo_col, title_col = st.columns([1, 10])
with logo_col:
    st.image(LOGO_PATH, width=56)
with title_col:
    st.title("Chotu v4")
st.write("FastAPI + Streamlit full-stack AI assistant")

if "server_api_base" not in st.session_state:
    st.session_state.server_api_base = SERVER_API_BASE
if "public_backend_url" not in st.session_state or (
    not st.session_state.public_backend_url and PUBLIC_API_BASE
):
    st.session_state.public_backend_url = PUBLIC_API_BASE
if "public_app_url" not in st.session_state or (
    not st.session_state.public_app_url and PUBLIC_APP_URL
):
    st.session_state.public_app_url = PUBLIC_APP_URL
if (
    "public_backend_url" in st.session_state
    and "public_app_url" in st.session_state
    and not NGROK_URLS.get("backend")
    and normalize_url_text(st.session_state.public_backend_url)
    == normalize_url_text(st.session_state.public_app_url)
):
    st.session_state.public_backend_url = ""

st.sidebar.header("Backend Settings")
SERVER_API_BASE = st.sidebar.text_input(
    "Backend API URL (this PC)",
    key="server_api_base",
    placeholder="http://127.0.0.1:8000",
)
PUBLIC_API_BASE = st.sidebar.text_input(
    "Public Backend URL for Phone Voice",
    key="public_backend_url",
    placeholder="Run start_phone_access.ps1 to fill this",
)
st.sidebar.header("Phone Access")
PUBLIC_APP_URL = st.sidebar.text_input(
    "Public App URL",
    key="public_app_url",
    placeholder="Run start_phone_access.ps1 to fill this",
)
if PUBLIC_APP_URL:
    st.sidebar.markdown(f"[Open This Link]({PUBLIC_APP_URL})")
if PUBLIC_APP_URL or PUBLIC_API_BASE:
    st.sidebar.markdown("**Current public links**")
    if PUBLIC_APP_URL:
        st.sidebar.caption("Phone app link")
        st.sidebar.code(PUBLIC_APP_URL, language=None)
    if PUBLIC_API_BASE:
        st.sidebar.caption("Phone backend API link")
        st.sidebar.code(PUBLIC_API_BASE, language=None)
    if PUBLIC_APP_URL and not PUBLIC_API_BASE:
        st.sidebar.warning(
            "Phone page is public, but phone Voice/AI actions still need a separate public backend URL."
        )
    if (
        PUBLIC_APP_URL
        and PUBLIC_API_BASE
        and normalize_url_text(PUBLIC_APP_URL) == normalize_url_text(PUBLIC_API_BASE)
    ):
        st.sidebar.error(
            "The phone app link and phone backend link are the same. "
            "Open only the app link in the browser, and use a separate backend public URL for Voice/API."
        )
    st.sidebar.caption("Open only the phone app link on your mobile browser. Do not open the backend API link directly.")
else:
    st.sidebar.info(
        "Phone links are not active yet.\n\n"
        "Run `powershell -ExecutionPolicy Bypass -File .\\start_phone_access.ps1`, "
        "then refresh this page."
    )
st.sidebar.caption("Public tunnel links change when the tunnel is restarted.")

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None
if "active_view" not in st.session_state:
    st.session_state.active_view = "AI Chat"
if st.session_state.active_view == "Sources Q&A":
    st.session_state.active_view = "AI Chat"
if "chat_input_text" not in st.session_state:
    st.session_state.chat_input_text = ""
if st.session_state.pop("clear_chat_input", False):
    st.session_state.chat_input_text = ""
if "chat_image_uploader_key" not in st.session_state:
    st.session_state.chat_image_uploader_key = 0
if "show_chat_upload_picker" not in st.session_state:
    st.session_state.show_chat_upload_picker = False


def weather_icon(condition: str, is_day: bool = False) -> str:
    text = str(condition or "").lower()
    if "rain" in text or "drizzle" in text or "shower" in text:
        return "🌧️"
    if "cloud" in text or "overcast" in text:
        return "☁️"
    if "thunder" in text or "storm" in text:
        return "⛈️"
    if "mist" in text or "fog" in text or "haze" in text:
        return "🌫️"
    if "clear" in text and not is_day:
        return "🌙"
    return "☀️" if is_day else "🌙"


def display_value(value, suffix: str = "") -> str:
    if value in (None, "", "Unknown"):
        return "N/A"
    return f"{value}{suffix}"


def display_temp(value) -> str:
    if value in (None, ""):
        return "N/A"
    return f"{value}°C"


def display_percent(value) -> str:
    if value in (None, ""):
        return "N/A"
    return f"{value}%"
def clean_weather_text(value: str) -> str:
    text = str(value or "").strip()
    replacements = {
        "Ã¢Â˜Â€Ã¯Â¸Â": "Sunny",
        "Ã¢Â˜ÂÃ¯Â¸Â": "Cloudy",
        "Ã¢Â›Â…": "Partly cloudy",
        "Ã°ÂŸÂŒÂ§Ã¯Â¸Â": "Rainy",
        "Ã°ÂŸÂŒÂ¦Ã¯Â¸Â": "Rainy",
        "Ã°ÂŸÂŒÂ™": "Clear night",
        "Ã‚Â°C": "Â°C",
        "Ã‚Â°": "Â°",
        "+": "",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text or "Weather update"


def normalize_weather_payload(payload: dict | None) -> dict | None:
    if not payload or not isinstance(payload, dict):
        return None

    if "condition" in payload:
        hourly = payload.get("hourly") or []
        if hourly:
            normalized_hourly = hourly
        else:
            normalized_hourly = [
                {"time": "Now", "wind_kph": 0, "chance_of_rain": 0},
                {"time": "1 AM", "wind_kph": 0, "chance_of_rain": 0},
                {"time": "2 AM", "wind_kph": 0, "chance_of_rain": 0},
                {"time": "3 AM", "wind_kph": 0, "chance_of_rain": 0},
                {"time": "4 AM", "wind_kph": 0, "chance_of_rain": 0},
            ]

        return {
            "city": payload.get("city", "Weather"),
            "condition": clean_weather_text(payload.get("condition", "Clear")),
            "temperature_c": payload.get("temperature_c", 0),
            "feels_like_c": payload.get("feels_like_c", payload.get("temperature_c", 0)),
            "min_temp_c": payload.get("min_temp_c", payload.get("temperature_c", 0)),
            "max_temp_c": payload.get("max_temp_c", payload.get("temperature_c", 0)),
            "humidity": payload.get("humidity", 0),
            "wind_kph": payload.get("wind_kph", 0),
            "moon_phase": payload.get("moon_phase", "Unknown"),
            "is_day": payload.get("is_day", False),
            "hourly": normalized_hourly[:5],
        }

    result = str(payload.get("result", "")).strip()
    city = payload.get("city", "Weather")
    temperature = 0
    condition = "Weather update"

    if ":" in result:
        summary = result.split(":", 1)[1].strip()
    else:
        summary = result
    summary = clean_weather_text(summary)

    if summary:
        parts = [part.strip() for part in summary.split(",") if part.strip()]
        if parts:
            condition = parts[0]
        for part in parts[1:]:
            if "c" in part.lower():
                digits = "".join(ch for ch in part if ch.isdigit() or ch == "-")
                if digits:
                    temperature = int(digits)
                    break

    return {
        "city": city,
        "condition": condition,
        "temperature_c": temperature,
        "feels_like_c": temperature,
        "min_temp_c": temperature,
        "max_temp_c": temperature,
        "humidity": 0,
        "wind_kph": 0,
        "moon_phase": "Unknown",
        "is_day": False,
        "hourly": [
            {"time": "Now", "wind_kph": 0, "chance_of_rain": 0},
            {"time": "1 AM", "wind_kph": 0, "chance_of_rain": 0},
            {"time": "2 AM", "wind_kph": 0, "chance_of_rain": 0},
            {"time": "3 AM", "wind_kph": 0, "chance_of_rain": 0},
            {"time": "4 AM", "wind_kph": 0, "chance_of_rain": 0},
        ],
    }

def render_switch_menu(key_prefix: str) -> None:
    with st.popover("+"):
        st.caption("Switch options")
        if st.button("AI Chat", key=f"{key_prefix}_menu_ai_chat", use_container_width=True):
            st.session_state.active_view = "AI Chat"
            st.rerun()
        if st.button("Weather", key=f"{key_prefix}_menu_weather", use_container_width=True):
            st.session_state.active_view = "Weather"
            st.rerun()
        if st.button("Voice", key=f"{key_prefix}_menu_voice", use_container_width=True):
            st.session_state.active_view = "Voice"
            st.rerun()


def render_chat_plus_menu() -> tuple[list, list]:
    with st.popover("+"):
        if st.button("Add photos & files", key="chat_show_upload_picker_btn", use_container_width=True):
            st.session_state.show_chat_upload_picker = True
            st.rerun()

        if st.session_state.show_chat_upload_picker and st.button(
            "Hide photos & files",
            key="chat_hide_upload_picker_btn",
            use_container_width=True,
        ):
            st.session_state.show_chat_upload_picker = False
            st.rerun()

        st.divider()
        st.caption("Switch options")
        if st.button("Weather", key="chat_menu_weather", use_container_width=True):
            st.session_state.active_view = "Weather"
            st.rerun()
        if st.button("Voice", key="chat_menu_voice", use_container_width=True):
            st.session_state.active_view = "Voice"
            st.rerun()

    upload_files = st.session_state.get(f"chat_uploads_{st.session_state.chat_image_uploader_key}", [])
    chat_images = [
        file for file in (upload_files or [])
        if uploaded_file_extension(file) in IMAGE_EXTENSIONS
    ]
    chat_pdfs = [
        file for file in (upload_files or [])
        if uploaded_file_extension(file) in PDF_EXTENSIONS
    ]
    return chat_images, chat_pdfs

if st.session_state.active_view == "AI Chat":
    st.markdown(
        """
        <style>
        .chatgpt-shell {
            max-width: 980px;
            margin: 0 auto;
        }
        .chatgpt-hero {
            text-align: center;
            padding: 2.4rem 0 1.4rem;
        }
        .chatgpt-pill {
            display: inline-flex;
            align-items: center;
            gap: .5rem;
            padding: .7rem 1rem;
            border: 1px solid #e5e7eb;
            border-radius: 999px;
            background: #ffffff;
            color: #111827;
            font-size: .96rem;
            font-weight: 600;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }
        .chatgpt-hero h1 {
            margin: 1rem 0 .45rem;
            font-size: clamp(2.4rem, 4.8vw, 4.2rem);
            line-height: 1.03;
            font-weight: 500;
            letter-spacing: -0.05em;
            color: #111827;
        }
        .chatgpt-hero p {
            margin: 0;
            color: #6b7280;
            font-size: 1rem;
        }
        .chatgpt-chip-row {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: .55rem;
            margin: .5rem 0 1rem;
        }
        .chatgpt-chip-label {
            color: #6b7280;
            font-size: .92rem;
            margin-right: .1rem;
        }
        .chatgpt-chip {
            display: inline-flex;
            align-items: center;
            padding: .48rem .82rem;
            border-radius: 999px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            color: #111827;
            font-size: .93rem;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stChatMessage"] {
            background: transparent;
            border: none;
            padding-top: .6rem;
            padding-bottom: .6rem;
        }
        div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
            font-size: 1.03rem;
            line-height: 1.72;
            color: #111827;
        }
        div[data-testid="stPopover"] > div > button {
            width: 52px;
            height: 52px;
            border-radius: 999px;
            padding: 0;
            font-size: 24px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
        }
        div[data-testid="stFileUploader"] section {
            border-radius: 28px;
            border: 1px dashed #d1d5db;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stChatInput"] {
            border-radius: 32px;
        }
        div[data-testid="stChatInput"] > div {
            border-radius: 32px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
        }
        div[data-testid="stChatInput"] textarea,
        div[data-testid="stChatInput"] input {
            font-size: 1.04rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="chatgpt-shell">', unsafe_allow_html=True)
    if not st.session_state.chat_messages:
        st.markdown(
            """
            <div class="chatgpt-hero">
              <div class="chatgpt-pill">Chotu AI Assistant</div>
              <h1>What can I help with?</h1>
              <p>Ask anything, attach photos, or add a PDF for more context.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    for idx, msg in enumerate(st.session_state.chat_messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            attachments = msg.get("attachments") or []
            if attachments:
                render_file_chips(attachments, "Files")
            action = msg.get("action") or {}
            render_chat_action(action, SERVER_API_BASE, f"chat_action_{idx}")

    if st.session_state.show_chat_upload_picker:
        st.file_uploader(
            "Add photos & files",
            type=["png", "jpg", "jpeg", "webp", "pdf"],
            accept_multiple_files=True,
            key=f"chat_uploads_{st.session_state.chat_image_uploader_key}",
        )

    menu_col, input_col = st.columns([1, 10])
    with menu_col:
        chat_images, chat_pdfs = render_chat_plus_menu()
    with input_col:
        prompt = st.chat_input("Ask anything")

    pending_attachments = [file.name for file in (chat_images + chat_pdfs)]
    if pending_attachments:
        render_file_chips(pending_attachments, "Ready")

    if prompt:
        history = build_chat_history(st.session_state.chat_messages)
        image_payloads = [uploaded_image_to_data_url(file) for file in chat_images or []]
        attachment_names = [file.name for file in (chat_images + chat_pdfs)]
        prompt_for_ai, pdf_errors = build_prompt_with_pdf_context(prompt, chat_pdfs, SERVER_API_BASE)
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": prompt,
                "ai_content": prompt_for_ai,
                "attachments": attachment_names,
            }
        )
        with st.chat_message("user"):
            st.markdown(prompt)
            if attachment_names:
                render_file_chips(attachment_names, "Files")
        with st.chat_message("assistant"):
            try:
                response = requests.post(
                    f"{SERVER_API_BASE}/ai/chat",
                    json={"message": prompt_for_ai, "history": history, "images": image_payloads},
                    timeout=240,
                )
                response.raise_for_status()
                data = response.json()
                reply = data.get("reply", "No reply returned.")
                action = data.get("action")
            except Exception as e:
                reply = f"Request failed: {e}"
                action = None
            if pdf_errors:
                reply = "Some attached PDFs could not be read:\n" + "\n".join(
                    f"- {error}" for error in pdf_errors
                ) + f"\n\n{reply}"
            st.markdown(reply)
            render_chat_action(action or {}, SERVER_API_BASE, f"chat_action_live_{len(st.session_state.chat_messages)}")
        st.session_state.chat_messages.append({"role": "assistant", "content": reply, "action": action})
        if attachment_names:
            st.session_state.chat_image_uploader_key += 1
            st.session_state.show_chat_upload_picker = False
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.active_view == "Weather":
    st.subheader("Weather")
    switch_col, city_col, action_col = st.columns([1, 7, 2])
    with switch_col:
        render_switch_menu("weather")
    with city_col:
        city = st.text_input("Enter city", value="Kukatpalle", key="weather_city")
    with action_col:
        show_weather = st.button("Show Weather", use_container_width=True)

    if show_weather:
        if city.strip():
            try:
                response = requests.get(f"{SERVER_API_BASE}/weather/{city}", timeout=20)
                response.raise_for_status()
                st.session_state.weather_data = response.json()
            except Exception as e:
                st.error(f"Request failed: {e}")
        else:
            st.warning("Please enter a city name.")

    weather = normalize_weather_payload(st.session_state.weather_data)
    if weather:
        weather_card = f"""
        <style>
          .weather-shell {{
            position: relative;
            overflow: hidden;
            border-radius: 34px;
            padding: 32px 28px 22px;
            min-height: 760px;
            color: #f7f7fb;
            background:
              radial-gradient(circle at 50% 33%, rgba(255,255,255,.24), transparent 12%),
              radial-gradient(circle at 16% 14%, rgba(255,255,255,.75) 1px, transparent 1.8px),
              radial-gradient(circle at 32% 6%, rgba(255,255,255,.65) 1px, transparent 1.7px),
              radial-gradient(circle at 58% 12%, rgba(255,255,255,.7) 1px, transparent 1.6px),
              radial-gradient(circle at 76% 8%, rgba(255,255,255,.68) 1px, transparent 1.8px),
              radial-gradient(circle at 90% 18%, rgba(255,255,255,.72) 1px, transparent 1.8px),
              linear-gradient(180deg, #0a1230 0%, #28376e 42%, #223569 100%);
            box-shadow: 0 24px 80px rgba(6, 10, 28, .35);
            font-family: "Segoe UI", sans-serif;
          }}
          .weather-shell::after {{
            content: "";
            position: absolute;
            inset: auto 0 0 0;
            height: 230px;
            background: linear-gradient(180deg, rgba(12, 20, 48, 0), rgba(12, 20, 48, .28));
            pointer-events: none;
          }}
          .weather-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
          }}
          .weather-city {{
            font-size: 2.5rem;
            font-weight: 300;
            line-height: 1.1;
            letter-spacing: .2px;
          }}
          .weather-actions {{
            font-size: 1.8rem;
            opacity: .92;
            display: flex;
            gap: 16px;
          }}
          .weather-moon {{
            text-align: center;
            font-size: 4rem;
            margin: 26px 0 8px;
            filter: drop-shadow(0 0 18px rgba(255,255,255,.2));
          }}
          .weather-condition {{
            text-align: center;
            font-size: 2rem;
            margin-bottom: 2px;
          }}
          .weather-range {{
            text-align: center;
            color: rgba(255,255,255,.74);
            font-size: 1.2rem;
          }}
          .weather-temp {{
            text-align: center;
            font-size: 8.3rem;
            line-height: .92;
            font-weight: 300;
            letter-spacing: -3px;
            margin: 16px 0 18px;
          }}
          .weather-temp span {{
            font-size: 3rem;
            opacity: .5;
            vertical-align: top;
            margin-left: 6px;
          }}
          .weather-glow {{
            width: 160px;
            height: 26px;
            margin: 0 auto 28px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(255,255,255,.32), rgba(255,255,255,0));
            filter: blur(4px);
          }}
          .forecast-line {{
            position: relative;
            height: 94px;
            margin: 8px 0 8px;
          }}
          .forecast-line svg {{
            width: 100%;
            height: 100%;
            display: block;
          }}
          .forecast-row {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            margin-top: -4px;
          }}
          .forecast-item {{
            text-align: center;
            color: rgba(255,255,255,.92);
          }}
          .forecast-icon {{
            font-size: 2rem;
            margin-bottom: 10px;
          }}
          .forecast-wind {{
            font-size: .98rem;
            opacity: .95;
          }}
          .forecast-rain {{
            font-size: .92rem;
            color: #b995ff;
            margin-top: 4px;
          }}
          .forecast-time {{
            font-size: 1.3rem;
            font-weight: 300;
            margin-top: 10px;
            color: rgba(255,255,255,.9);
          }}
          .weather-footer {{
            margin-top: 30px;
            padding: 20px 18px;
            border-radius: 24px;
            background: rgba(10, 18, 48, .26);
            backdrop-filter: blur(12px);
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
          }}
          .weather-metric-label {{
            font-size: .8rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: rgba(255,255,255,.55);
          }}
          .weather-metric-value {{
            font-size: 1.2rem;
            margin-top: 6px;
          }}
          @media (max-width: 700px) {{
            .weather-shell {{ min-height: 680px; padding: 26px 18px 20px; }}
            .weather-city {{ font-size: 2rem; }}
            .weather-temp {{ font-size: 6.4rem; }}
            .weather-footer {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
          }}
        </style>
        <div class="weather-shell">
          <div class="weather-top">
            <div class="weather-city">{weather["city"]}</div>
            <div class="weather-actions"><span>&#9776;</span><span>&#8942;</span></div>
          </div>
          <div class="weather-moon">{weather_icon(weather["condition"], weather["is_day"])}</div>
          <div class="weather-condition">{weather["condition"]}</div>
          <div class="weather-range">{display_temp(weather["min_temp_c"])} ~ {display_temp(weather["max_temp_c"])}&nbsp;&nbsp; Feels like {display_temp(weather["feels_like_c"])}</div>
          <div class="weather-temp">{weather["temperature_c"]}<span>°C</span></div>
          <div class="weather-glow"></div>
          <div class="forecast-line">
            <svg viewBox="0 0 1000 120" preserveAspectRatio="none" aria-hidden="true">
              <path d="M0 60 C130 46, 250 72, 390 64 S650 68, 1000 62" stroke="rgba(255,255,255,.6)" stroke-dasharray="5 6" stroke-width="2" fill="none"/>
              <path d="M0 66 C130 58, 250 76, 390 70 S650 72, 1000 76" stroke="#7ef0ad" stroke-width="5" fill="none" stroke-linecap="round"/>
              <circle cx="42" cy="65" r="22" fill="#f9fff8" stroke="#7ef0ad" stroke-width="5"/>
              <text x="42" y="73" text-anchor="middle" font-size="28" fill="#1c2552" font-family="Segoe UI">{weather["temperature_c"]}</text>
            </svg>
          </div>
          <div class="forecast-row">
            {"".join(
                f'''
                <div class="forecast-item">
                  <div class="forecast-icon">{weather_icon(item.get("condition", ""), weather["is_day"])}</div>
                  <div class="forecast-wind">{display_temp(item.get("temp_c"))}</div>
                  <div class="forecast-rain">{clean_weather_text(item.get("condition", ""))}</div>
                  <div class="forecast-time">{item["time"]}</div>
                </div>
                '''
                for item in weather["hourly"]
            )}
          </div>
          <div class="weather-footer">
            <div>
              <div class="weather-metric-label">Humidity</div>
              <div class="weather-metric-value">{display_percent(weather["humidity"])}</div>
            </div>
            <div>
              <div class="weather-metric-label">Wind</div>
              <div class="weather-metric-value">{display_value(weather["wind_kph"], " km/h")}</div>
            </div>
            <div>
              <div class="weather-metric-label">Moon Phase</div>
              <div class="weather-metric-value">{display_value(weather["moon_phase"])}</div>
            </div>
            <div>
              <div class="weather-metric-label">Sky</div>
              <div class="weather-metric-value">{'Day' if weather["is_day"] else 'Night'}</div>
            </div>
          </div>
        </div>
        """
        st.components.v1.html(weather_card, height=860, scrolling=False)
if st.session_state.active_view == "Voice":
    st.subheader("Voice Control")
    switch_col, info_col = st.columns([1, 9])
    with switch_col:
        render_switch_menu("voice")
    with info_col:
        st.caption("Use the + button to switch sections.")
    st.caption(
        "Use Chrome or Edge. Press Start Listening and speak directly, or say 'Hey Chotu' for hands-free mode."
    )

    voice_widget = f"""
    <div style="font-family: Arial, sans-serif; padding: 16px; border: 1px solid #dcdcdc; border-radius: 14px; background: linear-gradient(135deg, #f7fbff, #eef7f1);">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
        <div>
          <div style="font-size: 20px; font-weight: 700; color: #10324a;">Chotu Voice Mode</div>
          <div style="font-size: 13px; color: #4a6275;">Wake phrase: <strong>Hey Chotu</strong></div>
        </div>
      </div>

      <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:14px;">
        <button id="toggle-listening" style="background:#10324a; color:white; border:none; border-radius:999px; padding:10px 16px; cursor:pointer;">
          Start Listening
        </button>
        <button id="run-last-action" style="background:white; color:#10324a; border:1px solid #cbd5e1; border-radius:999px; padding:10px 16px; cursor:pointer; opacity:.55;" disabled>
          Open Last Action
        </button>
        <button id="toggle-mute" style="background:white; color:#10324a; border:1px solid #cbd5e1; border-radius:999px; padding:10px 16px; cursor:pointer;">
          Mute Replies
        </button>
        <button id="stop-speaking" style="background:white; color:#10324a; border:1px solid #cbd5e1; border-radius:999px; padding:10px 16px; cursor:pointer;">
          Stop Reply
        </button>
        <button id="clear-voice" style="background:white; color:#10324a; border:1px solid #cbd5e1; border-radius:999px; padding:10px 16px; cursor:pointer;">
          Clear
        </button>
      </div>

      <div id="voice-status" style="margin-top:14px; padding:10px 12px; background:white; border-radius:10px; color:#10324a;">
        Idle. Click Start Listening to enable voice mode.
      </div>

      <div style="margin-top:14px;">
        <div style="font-size:12px; color:#5a6b78; margin-bottom:4px;">Heard</div>
        <div id="heard-text" style="min-height:48px; background:white; border-radius:10px; padding:10px 12px; color:#20313f;"></div>
      </div>

      <div style="margin-top:14px;">
        <div style="font-size:12px; color:#5a6b78; margin-bottom:4px;">Chotu Reply</div>
        <div id="reply-text" style="min-height:90px; background:white; border-radius:10px; padding:10px 12px; color:#20313f; white-space:pre-wrap;"></div>
      </div>

      <div style="margin-top:14px;">
        <div style="font-size:12px; color:#5a6b78; margin-bottom:4px;">Last Action</div>
        <div id="last-action-text" style="min-height:42px; background:white; border-radius:10px; padding:10px 12px; color:#20313f;"></div>
      </div>
    </div>

    <script>
      const localApiBase = {json.dumps(SERVER_API_BASE)};
      const publicApiBase = {json.dumps(PUBLIC_API_BASE)};
      const publicAppUrl = {json.dumps(PUBLIC_APP_URL)};
      const isLocalPage = ["localhost", "127.0.0.1"].includes(window.location.hostname);
      const apiBases = [];

      function normalizeUrl(value) {{
        return String(value || "").trim().replace(/\\/+$/, "");
      }}

      function buildLocalQuickAction(message) {{
        const original = String(message || "").trim();
        const text = original.toLowerCase().replace(/\\s+/g, " ");
        if (!text) {{
          return null;
        }}

        const normalized = text
          .replaceAll("whats app", "whatsapp")
          .replaceAll("you tube", "youtube")
          .replaceAll("google map", "google maps");

        const numberMatch = original.match(/(\\+?\\d[\\d\\s-]{{5,}}\\d)/);
        if (numberMatch && /\\b(call|dial)\\b/.test(normalized)) {{
          const number = numberMatch[1].replace(/[^\\d+]/g, "");
          return {{
            reply: `Opening the phone app to call ${{number}}.`,
            action: {{ label: "Call now", url: `tel:${{number}}`, kind: "url" }},
          }};
        }}

        if (numberMatch && /\\b(text|sms|message)\\b/.test(normalized)) {{
          const number = numberMatch[1].replace(/[^\\d+]/g, "");
          return {{
            reply: `Opening messages for ${{number}}.`,
            action: {{ label: "Send SMS", url: `sms:${{number}}`, kind: "url" }},
          }};
        }}

        const emailMatch = original.match(/([A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{{2,}})/i);
        if (emailMatch && /\\b(email|mail)\\b/.test(normalized)) {{
          const email = emailMatch[1];
          return {{
            reply: `Opening email for ${{email}}.`,
            action: {{ label: "Send email", url: `mailto:${{email}}`, kind: "url" }},
          }};
        }}

        if (!/\\b(open|launch|start|go to|show)\\b/.test(normalized)) {{
          return null;
        }}

        const appActions = [
          ["Open Browser", "https://www.google.com/", ["browser", "internet", "web browser", "chrome"]],
          ["Open Google Maps", "https://www.google.com/maps", ["google maps", "maps"]],
          ["Open YouTube", "https://www.youtube.com/", ["youtube"]],
          ["Open WhatsApp", "https://web.whatsapp.com/", ["whatsapp"]],
          ["Open Gmail", "https://mail.google.com/", ["gmail", "email"]],
          ["Open Instagram", "https://www.instagram.com/", ["instagram"]],
          ["Open Facebook", "https://www.facebook.com/", ["facebook"]],
          ["Open Telegram", "https://t.me/", ["telegram"]],
          ["Open Google", "https://www.google.com/", ["google"]],
        ];

        for (const [label, url, keywords] of appActions) {{
          if (keywords.some((keyword) => normalized.includes(keyword))) {{
            return {{
              reply: `Opening ${{label.replace("Open ", "")}}.`,
              action: {{ label, url, kind: "url" }},
            }};
          }}
        }}

        return null;
      }}

      function pushApiBase(value) {{
        const clean = normalizeUrl(value);
        if (!clean || apiBases.includes(clean)) {{
          return;
        }}
        apiBases.push(clean);
      }}

      const normalizedPublicApiBase = normalizeUrl(publicApiBase);
      const normalizedPublicAppUrl = normalizeUrl(publicAppUrl);

      if (isLocalPage) {{
        pushApiBase(localApiBase);
        if (!normalizedPublicApiBase || normalizedPublicApiBase !== normalizedPublicAppUrl) {{
          pushApiBase(publicApiBase);
        }}
      }} else {{
        if (!normalizedPublicApiBase || normalizedPublicApiBase === normalizedPublicAppUrl) {{
          // A frontend URL is not a usable backend API URL on the public phone page.
        }} else {{
          pushApiBase(publicApiBase);
        }}
      }}
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const statusEl = document.getElementById("voice-status");
      const heardEl = document.getElementById("heard-text");
      const replyEl = document.getElementById("reply-text");
      const toggleBtn = document.getElementById("toggle-listening");
      const runLastActionBtn = document.getElementById("run-last-action");
      const muteBtn = document.getElementById("toggle-mute");
      const stopSpeakBtn = document.getElementById("stop-speaking");
      const clearBtn = document.getElementById("clear-voice");
      const lastActionTextEl = document.getElementById("last-action-text");

      let recognition = null;
      let listening = false;
      let wakeArmed = false;
      let sending = false;
      let speaking = false;
      let recognitionRunning = false;
      let muteReplies = false;
      let directCommandArmed = false;
      let lastAction = null;
      let autoStartAttempted = false;

      function setStatus(text) {{
        statusEl.textContent = text;
      }}

      function updateButtons() {{
        toggleBtn.textContent = listening ? "Stop Listening" : "Start Listening";
        muteBtn.textContent = muteReplies ? "Unmute Replies" : "Mute Replies";
        runLastActionBtn.disabled = !lastAction;
        runLastActionBtn.style.opacity = lastAction ? "1" : ".55";
      }}

      function updateLastAction(action) {{
        lastAction = action || null;
        lastActionTextEl.textContent = lastAction
          ? (
              lastAction.kind === "device"
                ? `${{lastAction.label || "Open now"}} -> ${{lastAction.app || "this PC"}}`
                : `${{lastAction.label || "Open now"}} -> ${{lastAction.url}}`
            )
          : "No action yet.";
        updateButtons();
      }}

      async function ensureMicrophoneAccess() {{
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
          setStatus("This browser cannot access the microphone. Use Chrome or Edge.");
          return false;
        }}

        if (!window.isSecureContext && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {{
          setStatus("Microphone access needs HTTPS or localhost.");
          return false;
        }}

        try {{
          const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
          stream.getTracks().forEach((track) => track.stop());
          return true;
        }} catch (error) {{
          const name = error?.name || "";
          if (name === "NotAllowedError" || name === "SecurityError") {{
            setStatus("Microphone permission is blocked. Allow microphone access in the browser, then try again.");
          }} else if (name === "NotFoundError" || name === "DevicesNotFoundError") {{
            setStatus("No microphone was found on this device.");
          }} else {{
            setStatus(`Microphone error: ${{error.message || error}}`);
          }}
          return false;
        }}
      }}

      function startRecognitionSafely() {{
        if (!recognition || recognitionRunning || speaking || sending) return;
        try {{
          recognition.start();
        }} catch (error) {{
          setStatus(`Voice restart issue: ${{error.message || error}}`);
        }}
      }}

      function speakReply(text) {{
        if (muteReplies || !("speechSynthesis" in window) || !text) return Promise.resolve();
        window.speechSynthesis.cancel();
        speaking = true;

        return new Promise((resolve) => {{
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.rate = 1;
          utterance.pitch = 1;
          utterance.onend = () => {{
            speaking = false;
            resolve();
            if (listening) {{
              directCommandArmed = true;
              setStatus("Listening. Speak now, or say 'Hey Chotu'.");
              startRecognitionSafely();
            }}
          }};
          utterance.onerror = () => {{
            speaking = false;
            resolve();
            if (listening) {{
              directCommandArmed = true;
              startRecognitionSafely();
            }}
          }};
          window.speechSynthesis.speak(utterance);
        }});
      }}

      function stopSpeakingReply() {{
        window.speechSynthesis?.cancel();
        speaking = false;
        if (listening && !sending) {{
          directCommandArmed = true;
          setStatus("Listening. Speak now, or say 'Hey Chotu'.");
          startRecognitionSafely();
        }} else {{
          setStatus("Reply stopped.");
        }}
      }}

      function renderReply(reply, action) {{
        replyEl.textContent = reply || "";
        updateLastAction(action);
        if (action && (action.url || action.kind === "device")) {{
          const spacer = document.createElement("div");
          spacer.style.height = "10px";
          const actionButton = document.createElement("button");
          actionButton.type = "button";
          actionButton.textContent = action.label || "Open now";
          actionButton.style.display = "inline-block";
          actionButton.style.background = "#10324a";
          actionButton.style.color = "white";
          actionButton.style.padding = "10px 14px";
          actionButton.style.borderRadius = "999px";
          actionButton.style.border = "none";
          actionButton.style.cursor = "pointer";
          actionButton.addEventListener("click", () => {{
            openAction(action);
          }});
          replyEl.appendChild(spacer);
          replyEl.appendChild(actionButton);
        }}
      }}

      async function postToBackend(path, payload) {{
        if (!isLocalPage && apiBases.length === 0) {{
          throw new Error(
            "Phone voice needs a real public backend URL. Add it in the sidebar field 'Public Backend URL for Phone Voice'."
          );
        }}

        let lastError = "No reachable backend URL.";

        for (const base of apiBases) {{
          if (!base) continue;
          try {{
            const response = await fetch(`${{base}}${{path}}`, {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify(payload)
            }});
            return response;
          }} catch (error) {{
            lastError = `${{base}} -> ${{error}}`;
          }}
        }}

        throw new Error(lastError);
      }}

      function inferDeviceApp(action) {{
        if (!action) return null;
        if (action.kind === "device" && action.app) {{
          return action.app;
        }}

        const label = String(action.label || "").toLowerCase();
        const url = String(action.url || "").toLowerCase();
        const candidates = [
          ["maps", ["google maps", "google.com/maps", "/maps"]],
          ["youtube", ["youtube"]],
          ["whatsapp", ["whatsapp", "wa.me", "web.whatsapp.com"]],
          ["gmail", ["gmail", "mail.google.com"]],
          ["instagram", ["instagram"]],
          ["facebook", ["facebook"]],
          ["telegram", ["telegram", "t.me"]],
          ["google", ["open google", "google.com"]],
          ["chrome", ["open chrome"]],
          ["edge", ["open edge"]],
          ["browser", ["open browser"]],
          ["notepad", ["notepad"]],
          ["calculator", ["calculator", "calc"]],
          ["files", ["file explorer", "explorer", "open files"]],
          ["settings", ["settings", "ms-settings"]],
          ["camera", ["camera"]],
          ["paint", ["paint"]],
          ["recycle_bin", ["recycle bin", "trash bin", "trash"]],
          ["terminal", ["terminal", "command prompt", "cmd"]],
          ["vscode", ["visual studio code", "vs code", "vscode"]],
        ];

        for (const [app, tokens] of candidates) {{
          if (tokens.some((token) => label.includes(token) || url.includes(token))) {{
            return app;
          }}
        }}

        return null;
      }}

      function fallbackUrlForApp(app) {{
        const urls = {{
          browser: "https://www.google.com/",
          chrome: "https://www.google.com/",
          edge: "https://www.microsoft.com/edge",
          google: "https://www.google.com/",
          youtube: "https://www.youtube.com/",
          whatsapp: "https://web.whatsapp.com/",
          maps: "https://www.google.com/maps",
          gmail: "https://mail.google.com/",
          instagram: "https://www.instagram.com/",
          facebook: "https://www.facebook.com/",
          telegram: "https://t.me/",
        }};
        return urls[app] || null;
      }}

      function openUrl(url, manual = false) {{
        if (!url) return;
        try {{
          const opened = window.open(url, "_blank", "noopener,noreferrer");
          if (opened) {{
            setStatus(manual ? "Action opened in a new tab." : "Action opened in a new tab.");
            return;
          }}
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.target = "_blank";
          anchor.rel = "noopener noreferrer";
          anchor.style.display = "none";
          document.body.appendChild(anchor);
          anchor.click();
          anchor.remove();
          setStatus(manual ? "Action sent." : "Action sent. If nothing opened, tap Open Last Action.");
        }} catch (error) {{
          console.error(error);
          setStatus(manual ? "Browser blocked the action." : "Browser blocked automatic opening. Tap Open Last Action.");
        }}
      }}

      async function openAction(action, manual = false) {{
        if (!action) return;

        const deviceApp = inferDeviceApp(action);
        if (deviceApp) {{
          const fallbackUrl = fallbackUrlForApp(deviceApp);
          try {{
            const response = await postToBackend("/device/open", {{ app: deviceApp }});
            const responseText = await response.text();
            if (!response.ok) {{
              if (fallbackUrl) {{
                openUrl(fallbackUrl, manual);
                return;
              }}
              setStatus(`Action failed: ${{response.status}} ${{responseText}}`);
              return;
            }}
            let message = "Action completed.";
            try {{
              const data = JSON.parse(responseText);
              message = data.message || message;
            }} catch (error) {{
              message = responseText || message;
            }}
            setStatus(message);
          }} catch (error) {{
            console.error(error);
            if (fallbackUrl) {{
              openUrl(fallbackUrl, manual);
              return;
            }}
            setStatus(manual ? "Could not reach the PC app launcher." : "Action is ready, but the PC app launcher could not be reached.");
          }}
          return;
        }}

        if (!action.url) return;
        openUrl(action.url, manual);
      }}

      async function postChatMessage(message) {{
        return postToBackend("/ai/chat", {{ message, history: [] }});
      }}

      async function sendMessage(message) {{
        if (!message || sending) return;
        sending = true;
        heardEl.textContent = message;
        replyEl.textContent = "";
        setStatus("Thinking...");
        wakeArmed = false;

        if (recognition && recognitionRunning) {{
          recognition.stop();
        }}

        try {{
          const localQuickAction = buildLocalQuickAction(message);
          if (localQuickAction) {{
            const reply = localQuickAction.reply || "Action ready.";
            const action = localQuickAction.action || null;
            renderReply(reply, action);
            await openAction(action);
            await speakReply(reply);
            return;
          }}

          const response = await postChatMessage(message);

          let reply = "No reply returned.";
          let action = null;
          if (!response.ok) {{
            const errorText = await response.text();
            reply = `Request failed: ${{response.status}} ${{errorText}}`;
          }} else {{
            const data = await response.json();
            reply = data.reply || "No reply returned.";
            action = data.action || null;
          }}
          renderReply(reply, action);
          if (action) {{
            await openAction(action);
          }} else {{
            setStatus(
              action
                ? "Action ready. Tap Open Last Action."
                : (muteReplies ? "Reply ready. Spoken replies are muted." : "Reply ready.")
            );
          }}
          await speakReply(reply);
        }} catch (error) {{
          replyEl.textContent = `Request failed: ${{error}}`;
          setStatus("Voice mode is still listening, but the backend request failed.");
        }} finally {{
          sending = false;
          if (listening && !speaking) {{
            directCommandArmed = true;
            setStatus("Listening. Speak now, or say 'Hey Chotu'.");
            startRecognitionSafely();
          }}
        }}
      }}

      function handleTranscript(transcript) {{
        const clean = transcript.trim();
        if (!clean) return;
        heardEl.textContent = clean;

        const lower = clean.toLowerCase();
        const wakePhrase = "hey chotu";

        if (lower.includes(wakePhrase)) {{
          const afterWake = clean.slice(lower.indexOf(wakePhrase) + wakePhrase.length).trim();
          if (afterWake) {{
            setStatus("Wake phrase detected. Sending command...");
            sendMessage(afterWake);
          }} else {{
            wakeArmed = true;
            heardEl.textContent = clean;
            setStatus("Wake phrase detected. I'm ready for your command.");
          }}
          return;
        }}

        if (wakeArmed || directCommandArmed) {{
          setStatus("Command heard. Sending...");
          sendMessage(clean);
          return;
        }}

        setStatus("I heard you. Say 'Hey Chotu' or press Start Listening and speak your command.");
      }}

      async function startListening(isAutoStart = false) {{
        if (!SpeechRecognition) {{
          setStatus("This browser does not support voice recognition. Use Chrome or Edge.");
          return false;
        }}

        const micReady = await ensureMicrophoneAccess();
        if (!micReady) {{
          if (isAutoStart) {{
            setStatus("Auto-start was blocked by the browser. Tap Start Listening once to allow hands-free mode.");
          }}
          return false;
        }}

        if (isAutoStart && !window.isSecureContext && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {{
          setStatus("Auto-start needs HTTPS and browser microphone permission.");
          return;
        }}

        directCommandArmed = true;
        try {{
          window.localStorage.setItem("chotu_voice_auto_start", "1");
        }} catch (error) {{
          console.debug("Could not save voice auto-start preference.", error);
        }}

        if (!recognition) {{
          recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = false;
          recognition.lang = navigator.language || "en-IN";

          recognition.onstart = () => {{
            listening = true;
            recognitionRunning = true;
            updateButtons();
            setStatus("Listening. Speak now, or say 'Hey Chotu'.");
          }};

          recognition.onresult = (event) => {{
            for (let i = event.resultIndex; i < event.results.length; i += 1) {{
              if (event.results[i].isFinal) {{
                handleTranscript(event.results[i][0].transcript);
              }}
            }}
          }};

          recognition.onerror = (event) => {{
            if (event.error === "not-allowed" || event.error === "service-not-allowed") {{
              setStatus("Microphone permission was denied. Allow it in the browser and try again.");
            }} else if (event.error === "no-speech") {{
              setStatus("I could not hear anything. Try speaking closer to the microphone.");
            }} else if (event.error === "audio-capture") {{
              setStatus("The microphone is not available right now.");
            }} else {{
              setStatus(`Voice recognition error: ${{event.error}}`);
            }}
          }};

          recognition.onend = () => {{
            recognitionRunning = false;
            if (listening && !sending && !speaking) {{
              startRecognitionSafely();
            }} else {{
              updateButtons();
              if (!listening) {{
                setStatus("Idle. Click Start Listening to enable voice mode.");
              }}
            }}
          }};
        }}

        startRecognitionSafely();
        return true;
      }}

      function stopListening() {{
        listening = false;
        wakeArmed = false;
        directCommandArmed = false;
        if (recognition) {{
          recognition.stop();
        }}
        window.speechSynthesis?.cancel();
        updateButtons();
      }}

      async function autoStartListening() {{
        if (autoStartAttempted || listening || sending || speaking) {{
          return;
        }}
        autoStartAttempted = true;
        await startListening(true);
      }}

      toggleBtn.addEventListener("click", () => {{
        if (listening) {{
          stopListening();
        }} else {{
          startListening();
        }}
      }});

      muteBtn.addEventListener("click", () => {{
        muteReplies = !muteReplies;
        if (muteReplies) {{
          window.speechSynthesis?.cancel();
          speaking = false;
          setStatus(listening ? "Listening. Spoken replies are muted." : "Replies are muted.");
        }} else {{
          setStatus(listening ? "Listening. Speak now, or say 'Hey Chotu'." : "Replies are unmuted.");
        }}
        updateButtons();
      }});

      stopSpeakBtn.addEventListener("click", () => {{
        stopSpeakingReply();
      }});

      runLastActionBtn.addEventListener("click", () => {{
        if (lastAction) {{
          openAction(lastAction, true);
        }}
      }});

      clearBtn.addEventListener("click", () => {{
        wakeArmed = false;
        directCommandArmed = false;
        heardEl.textContent = "";
        replyEl.textContent = "";
        updateLastAction(null);
        setStatus(listening ? "Listening. Speak now, or say 'Hey Chotu'." : "Idle. Click Start Listening to enable voice mode.");
      }});

      updateLastAction(null);
      updateButtons();
      try {{
        if (window.localStorage.getItem("chotu_voice_auto_start") === "1") {{
          setTimeout(() => {{
            autoStartListening();
          }}, 700);
        }}
      }} catch (error) {{
        console.debug("Could not read voice auto-start preference.", error);
      }}
    </script>
    """

    components.html(voice_widget, height=380)


