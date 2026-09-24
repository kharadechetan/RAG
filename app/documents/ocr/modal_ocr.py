import httpx
from app.config import settings

class ModalOCRClient:
    def __init__(self):
        self.url = settings.modal_ocr_url

    async def extract_text(self, image_bytes: bytes, filename: str = "page.png") -> dict:
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self.url,
                    files={"file": (filename, image_bytes, "image/png")}
                )
                response.raise_for_status()
                data = response.json()
                if not data.get("success"):
                    return {"success": False, "error": data.get("error", "Unknown OCR error")}
                return data
            except Exception as e:
                return {"success": False, "error": str(e)}
