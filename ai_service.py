import re

import requests
from app.config import (
    AI_APP_NAME,
    AI_API_KEY,
    AI_BASE_URL,
    AI_HISTORY_LIMIT,
    AI_MODEL,
    AI_PROVIDER,
    AI_SITE_URL,
    AI_TIMEOUT,
    ASSISTANT_NAME,
    ASSISTANT_ROLE,
)


def normalize_history(chat_history: list[dict] | None = None) -> list[dict]:
    if not chat_history:
        return []

    valid_roles = {"user", "assistant"}
    cleaned_history = []
    for message in chat_history:
        role = str(message.get("role", "")).strip().lower()
        content = str(message.get("content", "")).strip()
        if role in valid_roles and content:
            cleaned_history.append({"role": role, "content": content})

    return cleaned_history[-AI_HISTORY_LIMIT:]


def build_messages(
    user_query: str,
    chat_history: list[dict] | None = None,
) -> list:
    system_prompt = (
        f"{ASSISTANT_ROLE} "
        f"Assistant name: {ASSISTANT_NAME}."
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(normalize_history(chat_history))
    messages.append({"role": "user", "content": user_query})
    return messages


def extract_image_payload(image_data: str) -> str:
    value = str(image_data or "").strip()
    if value.startswith("data:") and "," in value:
        return value.split(",", 1)[1]
    return value


def attach_images_to_messages(
    messages: list[dict],
    provider_kind: str,
    images: list[str] | None = None,
) -> list[dict]:
    if not images:
        return messages

    cleaned_images = [image for image in images if str(image).strip()]
    if not cleaned_images or not messages:
        return messages

    user_message = messages[-1]
    user_text = str(user_message.get("content", "")).strip()

    if provider_kind in {"openai", "openrouter"}:
        content = [{"type": "text", "text": user_text}]
        for image in cleaned_images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image},
                }
            )
        user_message["content"] = content
        return messages

    if provider_kind == "ollama":
        user_message["images"] = [extract_image_payload(image) for image in cleaned_images]

    return messages


def get_provider_kind() -> str:
    provider = AI_PROVIDER.lower()
    base_url = AI_BASE_URL.lower()

    if provider == "openrouter" or "openrouter.ai" in base_url:
        return "openrouter"
    if provider == "openai":
        return "openai"
    if provider == "ollama":
        return "ollama"
    return provider


def build_openai_compatible_headers() -> dict:
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }

    if get_provider_kind() == "openrouter":
        if AI_SITE_URL:
            headers["HTTP-Referer"] = AI_SITE_URL
        if AI_APP_NAME:
            headers["X-Title"] = AI_APP_NAME

    return headers


def build_quick_action(
    label: str,
    reply: str,
    url: str | None = None,
    kind: str = "url",
    app: str | None = None,
) -> dict:
    return {
        "reply": reply,
        "action": {
            "label": label,
            "url": url,
            "kind": kind,
            "app": app,
        },
    }


def detect_quick_action(user_query: str) -> dict | None:
    text = re.sub(r"\s+", " ", str(user_query or "").strip().lower())
    if not text:
        return None

    text = (
        text.replace("whats app", "whatsapp")
        .replace("you tube", "youtube")
        .replace("google map", "google maps")
    )

    call_match = re.search(r"(\+?\d[\d\s-]{5,}\d)", user_query)
    if call_match and re.search(r"\b(call|dial)\b", text):
        number = re.sub(r"[^\d+]", "", call_match.group(1))
        return build_quick_action(
            "Call now",
            f"Opening the phone app to call {number}.",
            url=f"tel:{number}",
        )

    if call_match and re.search(r"\b(text|sms|message)\b", text):
        number = re.sub(r"[^\d+]", "", call_match.group(1))
        return build_quick_action(
            "Send SMS",
            f"Opening messages for {number}.",
            url=f"sms:{number}",
        )

    email_match = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", user_query, re.I)
    if email_match and re.search(r"\b(email|mail)\b", text):
        email = email_match.group(1)
        return build_quick_action(
            "Send email",
            f"Opening email for {email}.",
            url=f"mailto:{email}",
        )

    open_command = re.search(r"\b(open|launch|start|go to|show)\b", text)
    if open_command:
        requested_target = re.sub(
            r"^\s*(open|launch|start|go to|show)\s+",
            "",
            str(user_query or "").strip(),
            flags=re.I,
        ).strip(" .")

        device_actions = [
            ("Open Browser", "browser", ("browser", "internet", "web browser")),
            ("Open Chrome", "chrome", ("chrome", "google chrome")),
            ("Open Edge", "edge", ("edge", "microsoft edge")),
            ("Open Google Maps", "maps", ("google maps", "maps")),
            ("Open Gmail", "gmail", ("gmail",)),
            ("Open YouTube", "youtube", ("youtube",)),
            ("Open WhatsApp", "whatsapp", ("whatsapp",)),
            ("Open Instagram", "instagram", ("instagram",)),
            ("Open Facebook", "facebook", ("facebook",)),
            ("Open Telegram", "telegram", ("telegram",)),
            ("Open Google", "google", ("google",)),
            ("Open Notepad", "notepad", ("notepad",)),
            ("Open Calculator", "calculator", ("calculator", "calc")),
            ("Open File Explorer", "files", ("file explorer", "explorer", "files")),
            ("Open Settings", "settings", ("settings",)),
            ("Open Camera", "camera", ("camera",)),
            ("Open Paint", "paint", ("paint",)),
            ("Open Recycle Bin", "recycle_bin", ("recycle bin", "trash bin", "trash")),
            ("Open Terminal", "terminal", ("terminal", "cmd", "command prompt")),
            ("Open Visual Studio Code", "vscode", ("vscode", "vs code", "visual studio code")),
        ]
        for label, app_name, keywords in device_actions:
            if any(keyword in text for keyword in keywords):
                return build_quick_action(
                    label,
                    f"Opening {label.replace('Open ', '')}.",
                    kind="device",
                    app=app_name,
                )

        web_actions = []

        for label, url, keywords in web_actions:
            if any(keyword in text for keyword in keywords):
                return build_quick_action(
                    label,
                    f"Opening {label.replace('Open ', '')}.",
                    url=url,
                )

        if requested_target:
            title_target = " ".join(word.capitalize() for word in requested_target.split())
            return build_quick_action(
                f"Open {title_target}",
                f"Opening {title_target}.",
                kind="device",
                app=requested_target,
            )

        return {
            "reply": "Tell me which app, folder, file, or site you want me to open.",
            "action": None,
        }


def get_ai_response(
    user_query: str,
    chat_history: list[dict] | None = None,
    images: list[str] | None = None,
) -> str:
    response = None
    provider_kind = get_provider_kind()
    messages = build_messages(user_query, chat_history)
    messages = attach_images_to_messages(messages, provider_kind, images)

    try:
        if provider_kind == "ollama":
            url = f"{AI_BASE_URL}/api/chat"
            payload = {
                "model": AI_MODEL,
                "messages": messages,
                "stream": False,
            }
            response = requests.post(url, json=payload, timeout=AI_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"].strip()

        if provider_kind in {"openai", "openrouter"}:
            if not AI_API_KEY:
                return "AI error: Missing AI_API_KEY for the configured AI provider."

            url = f"{AI_BASE_URL}/chat/completions"
            payload = {
                "model": AI_MODEL,
                "messages": messages,
            }
            headers = build_openai_compatible_headers()
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=AI_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        return "Unsupported AI provider."

    except requests.HTTPError:
        detail = response.text.strip() if response is not None else "No response body"
        status = response.status_code if response is not None else "unknown"
        if status == 401 and provider_kind == "openrouter":
            return (
                "AI error: OpenRouter rejected the API key with 401 Unauthorized. "
                "Update AI_API_KEY in backend/.env with a valid OpenRouter key for this account."
            )
        return f"AI error: {status} {detail}"

    except requests.ConnectionError:
        if provider_kind == "ollama":
            return (
                "AI error: Could not connect to Ollama at "
                f"{AI_BASE_URL}. Start Ollama and make sure the model '{AI_MODEL}' is available."
            )
        return f"AI error: Could not connect to AI provider at {AI_BASE_URL}."

    except requests.Timeout:
        if provider_kind == "ollama":
            return (
                "AI error: Ollama took too long to respond. "
                f"Try again after the model '{AI_MODEL}' finishes loading, or increase AI_TIMEOUT."
            )
        return "AI error: The AI provider took too long to respond."

    except Exception as e:
        return f"AI error: {str(e)}"
