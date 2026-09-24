import re
import unicodedata

class TextCleaner:
    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
            
        # Unicode normalization
        text = unicodedata.normalize("NFKC", text)
        
        # Remove null characters and control characters
        text = re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]', '', text)
        
        # Clean obvious extraction artifacts like page numbers on lines by themselves
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Remove isolated numbers or "Page X"
            if re.match(r'^(page\s*\d+(?:\s*of\s*\d+)?|\d+|-\s*\d+\s*-)$', stripped, re.IGNORECASE):
                continue
            cleaned_lines.append(stripped)
            
        text = "\n".join(cleaned_lines)
        
        # Fix broken line wrapping (lines ending without punctuation followed by lowercase letter)
        text = re.sub(r'([^\.\!\?\:\;\n])\n+([a-z])', r'\1 \2', text)
        
        # Remove repeated newlines (more than 2)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove excessive spaces
        text = re.sub(r'[ \t]{2,}', ' ', text)
        
        return text.strip()
