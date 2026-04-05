from fastapi import APIRouter, HTTPException

from app.schemas import DeviceActionRequest, DeviceActionResponse
from app.services.device_service import open_device_app

router = APIRouter(prefix="/device", tags=["Device"])


@router.post("/open", response_model=DeviceActionResponse)
def open_app(payload: DeviceActionRequest):
    try:
        message = open_device_app(payload.app)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not open app: {exc}") from exc

    return DeviceActionResponse(ok=True, message=message)
