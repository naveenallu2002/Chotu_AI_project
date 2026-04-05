import os
import fitz


def read_pdf_text(path: str, max_chars: int | None = 8000) -> str:
    if not os.path.exists(path):
        return "PDF file not found."

    try:
        doc = fitz.open(path)
        pages = [page.get_text() for page in doc]
        doc.close()
        text = "\n".join(pages).strip()

        if not text:
            return "No readable text found in the PDF."

        if max_chars is None:
            return text
        return text[:max_chars]
    except Exception as e:
        return f"Error reading PDF: {str(e)}"
