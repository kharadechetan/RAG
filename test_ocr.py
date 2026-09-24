import asyncio
import os
import sys

from app.documents.ocr.local_ocr import LocalPaddleOCRClient

async def main():
    # Check if OCR initializes correctly
    print("Initializing OCR...", flush=True)
    ocr_client = LocalPaddleOCRClient()
    ocr = ocr_client.get_instance()
    print("OCR Initialized.", flush=True)
    
    # Let's test with b:\navgurukul\test\image.png
    image_path = r"b:\navgurukul\test\image.png"
    if os.path.exists(image_path):
        print(f"Testing image: {image_path}", flush=True)
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            
        res = await ocr_client.extract_text_from_bytes(image_bytes)
        print(f"Image processed OCR output:\n{res}", flush=True)
    else:
        print(f"Image not found at {image_path}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
