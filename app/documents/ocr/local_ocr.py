import os
import tempfile
import asyncio
import functools

# Set PaddleOCR environment variables
os.environ["PADDLE_PDX_CACHE_HOME"] = r"B:\ocr\paddlex_cache"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

class LocalPaddleOCRClient:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            # Import inside so we only load if needed
            from paddleocr import PaddleOCR
            cls._instance = PaddleOCR(
                lang="en",
                ocr_version="PP-OCRv5",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return cls._instance

    async def extract_text_from_bytes(self, image_bytes: bytes) -> dict:
        """Helper to extract text from bytes by saving to temp file first"""
        fd, temp_path = tempfile.mkstemp(suffix=".png")
        with os.fdopen(fd, 'wb') as f:
            f.write(image_bytes)
        
        try:
            return await self.extract_text(temp_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    async def extract_text(self, image_path: str) -> dict:
        loop = asyncio.get_event_loop()
        try:
            ocr = self.get_instance()
            # run_in_executor runs in thread pool
            # Use functools.partial to safely pass keyword arguments
            ocr_func = functools.partial(ocr.ocr, image_path, cls=False)
            result = await loop.run_in_executor(None, ocr_func)
            
            if not result or not result[0]:
                return {"success": True, "text": ""}
                
            extracted_lines = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text, confidence = line[1]
                    extracted_lines.append(text)
                    
            return {"success": True, "text": "\n".join(extracted_lines)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
