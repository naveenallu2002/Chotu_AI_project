import os
from fastapi import APIRouter, UploadFile, File
from app.config import UPLOAD_DIR
from app.schemas import PDFReadResponse
from app.services.pdf_service import read_pdf_text

router = APIRouter(prefix="/pdf", tags=["PDF"])


@router.post("/read", response_model=PDFReadResponse)
async def upload_and_read_pdf(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    text = read_pdf_text(file_path)
    return PDFReadResponse(filename=file.filename, text=text)
