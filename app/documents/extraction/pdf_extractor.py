import fitz  # PyMuPDF
from typing import Generator, Dict, Any

class PyMuPDFExtractor:
    def extract_pages(self, file_bytes: bytes) -> Generator[Dict[str, Any], None, None]:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            
            # Extract basic bounding box info if needed (blocks)
            raw_blocks = page.get_text("blocks")
            blocks = []
            for b in raw_blocks:
                if b[6] == 0:  # block_type == 0 (text)
                    blocks.append({
                        "bbox": [b[0], b[1], b[2], b[3]],
                        "text": b[4]
                    })
            
            # Render page to image (useful if OCR is needed later)
            # scale=2.0 for ~150 DPI
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            image_bytes = pix.tobytes("png")
            
            yield {
                "page_number": page_num + 1,
                "text": text,
                "blocks": blocks,
                "image_bytes": image_bytes
            }
        
        doc.close()
