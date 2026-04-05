from fastapi import APIRouter
from app.schemas import WeatherResponse
from app.services.weather_service import get_weather

router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get("/{city}", response_model=WeatherResponse)
def weather(city: str):
    return WeatherResponse(**get_weather(city))
