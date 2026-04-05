import os
import shutil
import subprocess


def _open_target(target: str) -> None:
    subprocess.Popen(
        ["cmd", "/c", "start", "", target],
        shell=False,
    )


def _launch_command(command: list[str]) -> None:
    subprocess.Popen(command, shell=False)


def _existing_path(paths: list[str]) -> str | None:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def _pretty_name(value: str) -> str:
    text = " ".join(str(value or "").replace("_", " ").split()).strip()
    return text.title() if text else "Target"


def _chrome_command() -> list[str]:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    chrome_path = _existing_path(
        [
            shutil.which("chrome.exe") or "",
            shutil.which("chrome") or "",
            os.path.join(local_app_data, "Google", "Chrome", "Application", "chrome.exe"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    )
    if chrome_path:
        return [chrome_path]
    return ["cmd", "/c", "start", "", "https://www.google.com/"]


APP_ALIASES = {
    "browser": "browser",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "youtube": "youtube",
    "whatsapp": "whatsapp",
    "instagram": "instagram",
    "facebook": "facebook",
    "telegram": "telegram",
    "google maps": "maps",
    "maps": "maps",
    "gmail": "gmail",
    "google": "google",
    "notepad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "files": "files",
    "file explorer": "files",
    "explorer": "files",
    "settings": "settings",
    "camera": "camera",
    "paint": "paint",
    "recycle bin": "recycle_bin",
    "trash": "recycle_bin",
    "trash bin": "recycle_bin",
    "bin": "recycle_bin",
    "terminal": "terminal",
    "command prompt": "terminal",
    "cmd": "terminal",
    "vscode": "vscode",
    "vs code": "vscode",
    "visual studio code": "vscode",
}


def normalize_app_name(app_name: str) -> str:
    normalized = " ".join(str(app_name or "").strip().lower().split())
    return APP_ALIASES.get(normalized, normalized)


def supported_apps() -> list[str]:
    return sorted(set(APP_ALIASES.values()))


def _open_generic_target(target: str) -> str:
    raw_target = str(target or "").strip().strip('"')
    if not raw_target:
        raise ValueError("Missing app name.")

    candidates: list[str] = []
    resolved = shutil.which(raw_target) or shutil.which(f"{raw_target}.exe")
    if resolved:
        candidates.append(resolved)
    candidates.append(raw_target)
    if "." not in raw_target and ":" not in raw_target and "\\" not in raw_target and "/" not in raw_target:
        candidates.append(f"{raw_target}.exe")

    seen: set[str] = set()
    errors: list[str] = []
    for candidate in candidates:
        normalized_candidate = candidate.strip()
        if not normalized_candidate or normalized_candidate.lower() in seen:
            continue
        seen.add(normalized_candidate.lower())
        try:
            os.startfile(normalized_candidate)
            return f"Opened {_pretty_name(raw_target)}."
        except OSError as exc:
            errors.append(str(exc))

    raise ValueError(
        f"I couldn't open '{raw_target}' on this PC. "
        "Try the exact app name, full path, URL, or Windows shortcut name."
    )


def open_device_app(app_name: str) -> str:
    raw_app_name = str(app_name or "").strip()
    app = normalize_app_name(raw_app_name)

    if app == "browser":
        _open_target("https://www.google.com/")
        return "Opened the default browser."

    if app == "chrome":
        _launch_command(_chrome_command())
        return "Opened Chrome."

    if app == "edge":
        edge_path = shutil.which("msedge.exe") or shutil.which("msedge")
        if edge_path:
            _launch_command([edge_path])
        else:
            _open_target("microsoft-edge:")
        return "Opened Microsoft Edge."

    if app == "youtube":
        _open_target("https://www.youtube.com/")
        return "Opened YouTube."

    if app == "whatsapp":
        _open_target("https://web.whatsapp.com/")
        return "Opened WhatsApp."

    if app == "instagram":
        _open_target("https://www.instagram.com/")
        return "Opened Instagram."

    if app == "facebook":
        _open_target("https://www.facebook.com/")
        return "Opened Facebook."

    if app == "telegram":
        _open_target("https://t.me/")
        return "Opened Telegram."

    if app == "maps":
        _open_target("https://www.google.com/maps")
        return "Opened Google Maps."

    if app == "gmail":
        _open_target("https://mail.google.com/")
        return "Opened Gmail."

    if app == "google":
        _open_target("https://www.google.com/")
        return "Opened Google."

    if app == "notepad":
        _launch_command(["notepad.exe"])
        return "Opened Notepad."

    if app == "calculator":
        _launch_command(["calc.exe"])
        return "Opened Calculator."

    if app == "files":
        _launch_command(["explorer.exe"])
        return "Opened File Explorer."

    if app == "settings":
        _open_target("ms-settings:")
        return "Opened Settings."

    if app == "camera":
        _open_target("microsoft.windows.camera:")
        return "Opened Camera."

    if app == "paint":
        _launch_command(["mspaint.exe"])
        return "Opened Paint."

    if app == "recycle_bin":
        _launch_command(["explorer.exe", "shell:RecycleBinFolder"])
        return "Opened Recycle Bin."

    if app == "terminal":
        terminal_path = shutil.which("wt.exe")
        if terminal_path:
            _launch_command([terminal_path])
        else:
            _launch_command(["cmd.exe"])
        return "Opened Terminal."

    if app == "vscode":
        vscode_path = shutil.which("code.cmd") or shutil.which("code")
        if not vscode_path:
            raise ValueError("VS Code is not installed or not available on PATH.")
        _launch_command([vscode_path])
        return "Opened Visual Studio Code."

    return _open_generic_target(raw_app_name)
