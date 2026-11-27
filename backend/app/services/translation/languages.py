"""Language definitions.

DEFAULT_LANGUAGES seeds the `languages` table. To add a language (e.g. Malayalam):
1. add a row here (or insert it in the DB from the admin side),
2. add its script range to SCRIPT_RANGES if it uses a new script,
3. run `python -m scripts.seed_data`.
No pipeline code changes are needed.
"""

DEFAULT_LANGUAGES = [
    # code, name, native, whisper, nllb, edge-tts voice, script
    {"code": "te", "name": "Telugu", "native_name": "తెలుగు", "whisper_code": "te",
     "nllb_code": "tel_Telu", "tts_voice": "te-IN-ShrutiNeural", "script": "Telugu"},
    {"code": "hi", "name": "Hindi", "native_name": "हिन्दी", "whisper_code": "hi",
     "nllb_code": "hin_Deva", "tts_voice": "hi-IN-SwaraNeural", "script": "Devanagari"},
    {"code": "ta", "name": "Tamil", "native_name": "தமிழ்", "whisper_code": "ta",
     "nllb_code": "tam_Taml", "tts_voice": "ta-IN-PallaviNeural", "script": "Tamil"},
    {"code": "kn", "name": "Kannada", "native_name": "ಕನ್ನಡ", "whisper_code": "kn",
     "nllb_code": "kan_Knda", "tts_voice": "kn-IN-SapnaNeural", "script": "Kannada"},
    # Added Nov 2026; supported end to end but not formally evaluated ("beta" in the app)
    {"code": "ml", "name": "Malayalam", "native_name": "മലയാളം", "whisper_code": "ml",
     "nllb_code": "mal_Mlym", "tts_voice": "ml-IN-SobhanaNeural", "script": "Malayalam"},
    {"code": "mr", "name": "Marathi", "native_name": "मराठी", "whisper_code": "mr",
     "nllb_code": "mar_Deva", "tts_voice": "mr-IN-AarohiNeural", "script": "Devanagari"},
    {"code": "bn", "name": "Bengali", "native_name": "বাংলা", "whisper_code": "bn",
     "nllb_code": "ben_Beng", "tts_voice": "bn-IN-TanishaaNeural", "script": "Bengali"},
    {"code": "gu", "name": "Gujarati", "native_name": "ગુજરાતી", "whisper_code": "gu",
     "nllb_code": "guj_Gujr", "tts_voice": "gu-IN-DhwaniNeural", "script": "Gujarati"},
    {"code": "ur", "name": "Urdu", "native_name": "اردو", "whisper_code": "ur",
     "nllb_code": "urd_Arab", "tts_voice": "ur-IN-GulNeural", "script": "Arabic"},
    {"code": "en", "name": "English", "native_name": "English", "whisper_code": "en",
     "nllb_code": "eng_Latn", "tts_voice": "en-IN-NeerjaNeural", "script": "Latin"},
]

# Unicode blocks per script (inclusive code-point ranges)
SCRIPT_RANGES: dict[str, list[tuple[int, int]]] = {
    "Devanagari": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],
    "Bengali": [(0x0980, 0x09FF)],
    "Gurmukhi": [(0x0A00, 0x0A7F)],
    "Gujarati": [(0x0A80, 0x0AFF)],
    "Odia": [(0x0B00, 0x0B7F)],
    "Tamil": [(0x0B80, 0x0BFF)],
    "Telugu": [(0x0C00, 0x0C7F)],
    "Kannada": [(0x0C80, 0x0CFF)],
    "Malayalam": [(0x0D00, 0x0D7F)],
    "Arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "Latin": [(0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)],
}

INTENTS = [
    ("crop_cultivation", "Sowing, varieties, seed rate, spacing, crop calendar, general crop management"),
    ("pest_disease", "Pests, insects, plant diseases, symptoms and their control"),
    ("fertilizer_soil", "Fertilizer doses, manure, soil health, soil testing, nutrient deficiency"),
    ("irrigation_water", "Irrigation scheduling, water management, drip and sprinkler systems"),
    ("weather", "Current weather, rain forecast, weather-based farm decisions"),
    ("harvest_storage", "Harvest timing, post-harvest handling, drying and storage"),
    ("market_price", "Today's mandi (market) prices of crops, from Agmarknet"),
    ("greeting", "Hello, thanks and other small talk"),
    ("other", "Anything outside the topics above"),
]
