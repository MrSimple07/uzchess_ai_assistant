

import os
from collections import defaultdict
import logging
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_comprehensive_analysis(weaknesses, opening_stats, color_stats, total_games):
    weakness_text = "\n".join([f"- {w['category']}: {w['count']} marta ({w['percentage']:.1f}%)" for w in weaknesses])
    
    opening_text = "\n".join([f"- {opening}: {stats['total']} o'yin (G'alabalar: {stats['wins']}, Yutqazishlar: {stats['losses']}, Duranglar: {stats['draws']})" 
                              for opening, stats in list(opening_stats.items())[:5]])
    
    color_text = f"Oq rangda: {color_stats['white']['wins']}G-{color_stats['white']['losses']}Y-{color_stats['white']['draws']}D\n"
    color_text += f"Qora rangda: {color_stats['black']['wins']}G-{color_stats['black']['losses']}Y-{color_stats['black']['draws']}D"
    
    prompt = f"""Siz professional шахмат murabbiy va tahlilchisiz. O'yinchining {total_games} ta o'yinini tahlil qildingiz.

STATISTIKA:

Zaif tomonlar:
{weakness_text}

Eng ko'p o'ynaladigan debyutlar:
{opening_text}

Rang bo'yicha natijalar:
{color_text}

Quyidagilarni taqdim eting:

1. **ZAIF TOMONLAR TAHLILI**: Har bir zaif tomonni chuqur tahlil qiling va nima uchun bu muammo kelib chiqayotganini tushuntiring.

2. **SHAXSIY O'QUV REJASI**: Kundalik mashg'ulotlar rejasini tuzing:
   - Har kuni nechta masala yechish kerak va qanday turdagi masalalar
   - Qaysi debyutlarni o'rganish kerak
   - Qaysi o'yin bosqichiga ko'proq e'tibor berish kerak
   - Kompyuter yoki botlar bilan qanday mashq qilish kerak

3. **TAVSIYA ETILGAN RESURSLAR**:
   - Kitoblar (muallif va nom bilan)
   - Onlayn kurslar (Uzchess, Chess.com, Lichess)
   - YouTube kanallari
   - Mashq uchun maxsus botlar yoki dasturlar

4. **DEBYUT TAVSIYALARI**: Statistikaga asoslanib, qaysi debyutlarni davom ettirish va qaysilarini o'zgartirish kerak.

5. **MOTIVATSION XULOSA**: Qisqa va rag'batlantiruvchi xulosa.

MUHIM: Javobni FAQAT O'ZBEK TILIDA yozing! Aniq va amaliy maslahatlar bering."""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"AI analysis failed: {str(e)}")
        return f"AI tahlil hozircha mavjud emas: {str(e)}"
