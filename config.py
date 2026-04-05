import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_FILE)

DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:11434").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "llama3").strip()
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "180"))
AI_HISTORY_LIMIT = int(os.getenv("AI_HISTORY_LIMIT", "8"))
AI_APP_NAME = os.getenv("AI_APP_NAME", "Chotu").strip()
AI_SITE_URL = os.getenv("AI_SITE_URL", "").strip()

ASSISTANT_NAME = "Chotu"
ASSISTANT_ROLE = (
    "You are Chotu, a smart personal AI assistant inspired by JARVIS and Google Assistant. "
    "Be calm, capable, and concise. Reply in simple language, stay practical, and maintain context across turns. "
    "When the user asks for help with tasks, guide them step by step and sound like a polished assistant."
)
