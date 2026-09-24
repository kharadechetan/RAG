from langdetect import detect, LangDetectException

class LanguageDetector:
    @staticmethod
    def detect_language(text: str) -> str:
        if not text or len(text.strip()) < 10:
            return "unknown"
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"
