import os

# ============= API SOZLAMALARI =============
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# ============= STOCKFISH SOZLAMALARI =============
# Stockfish dasturining yo'lini kiriting
# Windows: "C:/stockfish/stockfish.exe"
# Linux/Mac: "/usr/local/bin/stockfish"
STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH', 'stockfish')
STOCKFISH_DEPTH = 15  # Tahlil chuqurligi (15-20 yetarli)
STOCKFISH_TIME = 0.1  # Har bir harakat uchun vaqt (sekundlarda)

# ============= O'YIN SOZLAMALARI =============
MAX_GAMES_TO_ANALYZE = 50  # Tahlil qilinadigan o'yinlar soni
BLUNDER_THRESHOLD = 200  # Qo'pol xato chegarasi (santipawn)
MISTAKE_THRESHOLD = 100  # Xato chegarasi (santipawn)

# ============= CHESS.COM API =============
CHESS_COM_API_BASE = "https://api.chess.com/pub"
REQUEST_TIMEOUT = 10  # Sekundlarda

# ============= LICHESS API =============
LICHESS_API_BASE = "https://lichess.org/api"

# ============= GEMINI PROMPT SHABLONLARI =============

WEAKNESS_ANALYSIS_PROMPT = """Siz шахмат murabbiysiz. O'yinchi o'zining so'nggi o'yinlarida quyidagi zaif tomonlarni ko'rsatdi:

{weakness_text}

Har bir zaif tomonni oddiy va rag'batlantiruvchi tilda tushuntiring (har biri uchun 2-3 jumla). Yaxshilash uchun amaliy maslahatlar bering. Do'stona va motivatsion bo'ling.

MUHIM: Javobni FAQAT O'ZBEK TILIDA yozing!"""

MISTAKE_EXPLANATION_PROMPT = """Siz шахмат o'qituvchisisiz. O'yinchining quyidagi harakati tahlil qilindi:

Harakat: {move}
Pozitsiya: {position}
Xato turi: {mistake_type}
Baholash farqi: {eval_diff} santipawn

Bu xatoni oddiy tilda tushuntiring va qanday qilib oldini olish mumkinligini aytib bering. 2-3 jumlada javob bering.

MUHIM: Javobni FAQAT O'ZBEK TILIDA yozing!"""

# ============= XATO KATEGORIYALARI =============

MISTAKE_CATEGORIES = {
    'blunder': 'Qo\'pol xatolar',
    'mistake': 'Kichik xatolar',
    'hanging_piece': 'Himoyasiz qoldirish',
    'tactical_miss': 'Taktik imkoniyatni o\'tkazib yuborish',
    'positional_error': 'Pozitsion xatolar',
    'time_trouble': 'Vaqt muammolari',
    'opening_mistake': 'Debyut xatolari',
    'middlegame_mistake': 'O\'rta o\'yin xatolari',
    'endgame_mistake': 'Endshpil xatolari'
}

# ============= INTERFACE MATNLARI =============

UI_TEXTS = {
    'title': '♟️ Shaxsiy Шахмат O\'quv Rejasi Generatori',
    'description': """Chess.com foydalanuvchi nomingizni kiriting va quyidagilarni oling:
    - 📊 Eng zaif 3 tomoningizni tahlil
    - 🤖 AI murabbiy tushuntirishlari
    - 🧩 Yaxshilash uchun 5 ta shaxsiy masala""",
    'username_label': 'Chess.com foydalanuvchi nomi',
    'username_placeholder': 'Foydalanuvchi nomini kiriting',
    'analyze_button': '🔍 O\'yinlarni tahlil qilish',
    'upload_pgn': '📁 PGN faylni yuklash',
    'weakness_title': '📊 Zaif Tomonlar',
    'explanation_title': '🤖 AI Murabbiy Tahlili',
    'puzzles_title': '🧩 Sizning Shaxsiy O\'quv Rejangiz',
    'instructions': """
    ### 📝 Qanday foydalanish:
    1. Chess.com foydalanuvchi nomingizni kiriting
    2. "O'yinlarni tahlil qilish" tugmasini bosing
    3. Dastur so'nggi 50 ta blitz o'yiningizni tahlil qiladi
    4. Zaif tomonlaringiz va shaxsiy masalalarni ko'ring
    
    **Yoki** PGN faylni yuklashingiz mumkin
    """
}

# ============= PUZZLE TEMALARI =============

PUZZLE_THEMES = {
    'blunder': 'mix',
    'hanging_piece': 'hangingPiece',
    'tactical_miss': 'fork,pin,skewer',
    'positional_error': 'advantage',
    'opening_mistake': 'opening',
    'middlegame_mistake': 'middlegame',
    'endgame_mistake': 'endgame'
}