from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)


class ChatAction(BaseModel):
    label: str
    url: str | None = None
    kind: str = "url"
    app: str | None = None


class ChatResponse(BaseModel):
    reply: str
    action: ChatAction | None = None


class DeviceActionRequest(BaseModel):
    app: str


class DeviceActionResponse(BaseModel):
    ok: bool
    message: str


class WeatherResponse(BaseModel):
    city: str
    condition: str
    temperature_c: int
    feels_like_c: int
    min_temp_c: int
    max_temp_c: int
    humidity: int
    wind_kph: int
    wind_text: str
    moon_phase: str
    is_day: bool
    hourly: list[dict]


class PDFReadResponse(BaseModel):
    filename: str
    text: str
