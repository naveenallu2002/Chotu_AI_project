from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.routes.ai import router as ai_router
from app.routes.device import router as device_router
from app.routes.weather import router as weather_router
from app.routes.pdf import router as pdf_router

app = FastAPI(title="Chotu API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)
app.include_router(device_router)
app.include_router(weather_router)
app.include_router(pdf_router)


@app.get("/")
def root():
    return {"message": "Chotu FastAPI backend is running"}


@app.get("/favicon.ico", include_in_schema=False, status_code=status.HTTP_204_NO_CONTENT)
def favicon():
    return Response(status_code=status.HTTP_204_NO_CONTENT)
