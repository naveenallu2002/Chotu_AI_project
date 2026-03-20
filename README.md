# Chotu v4

FastAPI + Streamlit full-stack AI assistant.

## Features
- AI chat
- Weather lookup
- Reminders
- Memory storage
- PDF read and summarize
- Streamlit UI + FastAPI backend

## Backend setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`
Docs: `http://127.0.0.1:8000/docs`

## Frontend setup
```bash
cd frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Notes
- Add your API key in `backend/.env`
- Weather uses `wttr.in`
- PDF summarization needs working AI API access
