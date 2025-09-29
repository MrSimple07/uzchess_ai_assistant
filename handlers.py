import chess
import chess.pgn
import chess.engine
import io
import requests
import google.generativeai as genai
from collections import Counter
import logging
from datetime import datetime
import time
import config

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Gemini sozlash
genai.configure(api_key=config.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# ============= CHESS.COM DAN O'YINLARNI OLISH =============

def get_user_games(username):
    """Chess.com dan foydalanuvchi o'yinlarini olish"""
    logger.info(f"Foydalanuvchi o'yinlarini olish: {username}")
    
    try:
        # Foydalanuvchini tekshirish
        user_url = f"{config.CHESS_COM_API_BASE}/player/{username}"
        logger.info(f"Foydalanuvchini tekshirish: {user_url}")
        
        response = requests.get(user_url, timeout=config.REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.error(f"Foydalanuvchi topilmadi: {username}")
            return None, "❌ Foydalanuvchi topilmadi. Nomni tekshiring."
        
        logger.info(f"Foydalanuvchi topildi: {username}")
        
        # Arxivlarni olish
        archives_url = f"{config.CHESS_COM_API_BASE}/player/{username}/games/archives"
        logger.info(f"Arxivlarni olish: {archives_url}")
        
        response = requests.get(archives_url, timeout=config.REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.error("Arxivlar olinmadi")
            return None, "❌ O'yinlar arxivi topilmadi."
        
        archives = response.json()['archives']
        if not archives:
            logger.warning("Arxivlar bo'sh")
            return None, "❌ O'yinlar topilmadi."
        
        logger.info(f"Jami arxivlar: {len(archives)}")
        
        # So'nggi oylarning o'yinlarini olish
        all_games = []
        for archive_url in reversed(archives[-3:]):  # So'nggi 3 oy
            logger.info(f"Arxivdan o'yinlarni olish: {archive_url}")
            time.sleep(0.5)  # Rate limiting
            
            response = requests.get(archive_url, timeout=config.REQUEST_TIMEOUT)
            if response.status_code == 200:
                games = response.json()['games']
                all_games.extend(games)
                logger.info(f"Olindi: {len(games)} ta o'yin")
            
            if len(all_games) >= config.MAX_GAMES_TO_ANALYZE:
                break
        
        # Blitz o'yinlarni filtrlash
        blitz_games = [g for g in all_games if g.get('time_class') == 'blitz']
        logger.info(f"Blitz o'yinlar: {len(blitz_games)}")
        
        if not blitz_games:
            # Agar blitz bo'lmasa, bullet olish
            bullet_games = [g for g in all_games if g.get('time_class') == 'bullet']
            logger.info(f"Bullet o'yinlar: {len(bullet_games)}")
            selected_games = bullet_games[:config.MAX_GAMES_TO_ANALYZE]
        else:
            selected_games = blitz_games[:config.MAX_GAMES_TO_ANALYZE]
        
        logger.info(f"Tanlangan o'yinlar: {len(selected_games)}")
        
        # PGN formatga o'tkazish
        pgn_games = []
        for game in selected_games:
            if 'pgn' in game:
                pgn_games.append(game['pgn'])
        
        logger.info(f"PGN formatdagi o'yinlar: {len(pgn_games)}")
        
        if not pgn_games:
            return None, "❌ PGN formatdagi o'yinlar topilmadi."
        
        return pgn_games, None
        
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {str(e)}")
        return None, f"❌ Xatolik: {str(e)}"

# ============= PGN TAHLIL =============

def parse_pgn_games(pgn_list):
    """PGN formatdagi o'yinlarni tahlil qilish"""
    logger.info(f"PGN tahlil qilish: {len(pgn_list)} ta o'yin")
    
    games = []
    for i, pgn_text in enumerate(pgn_list):
        try:
            pgn_io = io.StringIO(pgn_text)
            game = chess.pgn.read_game(pgn_io)
            if game:
                games.append(game)
                logger.info(f"O'yin {i+1} tahlil qilindi")
        except Exception as e:
            logger.error(f"O'yin {i+1} tahlil xatosi: {str(e)}")
    
    logger.info(f"Jami tahlil qilindi: {len(games)} ta o'yin")
    return games

# ============= STOCKFISH BILAN TAHLIL =============

def analyze_game_with_engine(game, username):
    """Stockfish yordamida o'yinni tahlil qilish"""
    logger.info("Stockfish bilan tahlil boshlandi")
    
    try:
        # Stockfish ni ishga tushirish
        engine = chess.engine.SimpleEngine.popen_uci(config.STOCKFISH_PATH)
        logger.info("Stockfish muvaffaqiyatli ishga tushdi")
        
        board = game.board()
        mistakes = []
        move_number = 0
        
        # Foydalanuvchi qaysi rangda o'ynaganini aniqlash
        white_player = game.headers.get("White", "").lower()
        black_player = game.headers.get("Black", "").lower()
        user_color = None
        
        if username.lower() in white_player:
            user_color = chess.WHITE
            logger.info(f"Foydalanuvchi oq rangda: {username}")
        elif username.lower() in black_player:
            user_color = chess.BLACK
            logger.info(f"Foydalanuvchi qora rangda: {username}")
        
        # Har bir harakatni tahlil qilish
        for move in game.mainline_moves():
            move_number += 1
            
            # Faqat foydalanuvchi harakatlarini tahlil qilish
            if user_color is not None and board.turn != user_color:
                board.push(move)
                continue
            
            # Harakat oldin pozitsiyani baholash
            try:
                info_before = engine.analyse(
                    board, 
                    chess.engine.Limit(depth=config.STOCKFISH_DEPTH)
                )
                eval_before = info_before['score'].relative.score(mate_score=10000)
                
                # Harakatni qo'llash
                board.push(move)
                
                # Harakat keyin pozitsiyani baholash
                info_after = engine.analyse(
                    board,
                    chess.engine.Limit(depth=config.STOCKFISH_DEPTH)
                )
                eval_after = info_after['score'].relative.score(mate_score=10000)
                
                # Baholash farqini hisoblash (foydalanuvchi nuqtai nazaridan)
                eval_diff = eval_before - eval_after
                
                # Xatolarni aniqlash
                mistake_type = None
                if eval_diff >= config.BLUNDER_THRESHOLD:
                    mistake_type = 'blunder'
                    logger.info(f"Qo'pol xato topildi: harakat {move_number}, farq {eval_diff}")
                elif eval_diff >= config.MISTAKE_THRESHOLD:
                    mistake_type = 'mistake'
                    logger.info(f"Xato topildi: harakat {move_number}, farq {eval_diff}")
                
                if mistake_type:
                    # Eng yaxshi harakatni topish
                    best_move = info_before['pv'][0] if 'pv' in info_before else None
                    
                    mistakes.append({
                        'move_number': move_number,
                        'move': move.uci(),
                        'best_move': best_move.uci() if best_move else None,
                        'type': mistake_type,
                        'eval_before': eval_before,
                        'eval_after': eval_after,
                        'eval_diff': eval_diff,
                        'fen': board.fen(),
                        'game_phase': get_game_phase(board)
                    })
                
            except Exception as e:
                logger.error(f"Harakat {move_number} tahlil xatosi: {str(e)}")
                board.push(move)
        
        engine.quit()
        logger.info(f"Tahlil tugadi. Topildi: {len(mistakes)} ta xato")
        return mistakes
        
    except Exception as e:
        logger.error(f"Stockfish xatosi: {str(e)}")
        return []

def get_game_phase(board):
    """O'yin bosqichini aniqlash"""
    move_count = board.fullmove_number
    piece_count = len(board.piece_map())
    
    if move_count <= 10:
        return 'opening_mistake'
    elif piece_count <= 10:
        return 'endgame_mistake'
    else:
        return 'middlegame_mistake'

# ============= XATOLARNI KATEGORIYALASH =============

def categorize_all_mistakes(all_mistakes):
    """Barcha xatolarni kategoriyalash"""
    logger.info(f"Kategoriyalash: {len(all_mistakes)} ta xato")
    
    # Xato turlarini sanash
    mistake_types = []
    for mistake in all_mistakes:
        mistake_types.append(mistake['type'])
        mistake_types.append(mistake['game_phase'])
    
    counts = Counter(mistake_types)
    
    # Eng ko'p uchragan 3 ta zaif tomonni topish
    top_weaknesses = []
    for mistake_type, count in counts.most_common(5):
        if mistake_type in config.MISTAKE_CATEGORIES:
            percentage = (count / len(all_mistakes) * 100) if all_mistakes else 0
            top_weaknesses.append({
                'category': config.MISTAKE_CATEGORIES[mistake_type],
                'type': mistake_type,
                'count': count,
                'percentage': percentage
            })
    
    logger.info(f"Eng ko'p zaif tomonlar: {len(top_weaknesses)}")
    return top_weaknesses[:3]

# ============= AI TUSHUNTIRISH =============

def get_ai_explanation(weaknesses):
    """Gemini dan tushuntirish olish"""
    logger.info("AI tushuntirish olish")
    
    weakness_text = "\n".join([
        f"- {w['category']}: {w['count']} marta ({w['percentage']:.1f}%)"
        for w in weaknesses
    ])
    
    prompt = config.WEAKNESS_ANALYSIS_PROMPT.format(weakness_text=weakness_text)
    
    try:
        response = model.generate_content(prompt)
        logger.info("AI javob olindi")
        return response.text
    except Exception as e:
        logger.error(f"AI xatosi: {str(e)}")
        return "AI tushuntirish hozircha mavjud emas."

# ============= LICHESS DAN MASALALAR OLISH =============

def fetch_puzzles_for_weaknesses(weaknesses, count=5):
    """Zaif tomonlar uchun masalalar olish"""
    logger.info(f"Masalalar olish: {count} ta")
    
    puzzles = []
    
    for weakness in weaknesses:
        theme = config.PUZZLE_THEMES.get(weakness['type'], 'mix')
        logger.info(f"Tema: {theme}")
        
        try:
            # Lichess dan tasodifiy masala olish
            url = f"{config.LICHESS_API_BASE}/puzzle/daily"
            response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                puzzle = data['puzzle']
                game = data['game']
                
                puzzles.append({
                    'id': puzzle['id'],
                    'fen': game['pgn'].split('\n')[-1],  # Oxirgi pozitsiya
                    'rating': puzzle['rating'],
                    'theme': weakness['category'],
                    'solution': puzzle['solution'],
                    'url': f"https://lichess.org/training/{puzzle['id']}"
                })
                logger.info(f"Masala olindi: {puzzle['id']}")
        
        except Exception as e:
            logger.error(f"Masala olish xatosi: {str(e)}")
    
    # Yetarlicha bo'lmasa, standart masalalar qo'shish
    while len(puzzles) < count:
        puzzles.append({
            'id': f'default_{len(puzzles)}',
            'fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
            'rating': 1500,
            'theme': 'Amaliyot',
            'solution': ['e2e4'],
            'url': 'https://lichess.org/training'
        })
    
    logger.info(f"Jami masalalar: {len(puzzles)}")
    return puzzles[:count]

# ============= ASOSIY TAHLIL FUNKSIYASI =============

def analyze_user_games(username):
    """Foydalanuvchi o'yinlarini to'liq tahlil qilish"""
    logger.info(f"===== TAHLIL BOSHLANDI: {username} =====")
    
    # 1. O'yinlarni olish
    pgn_games, error = get_user_games(username)
    if error:
        logger.error(f"O'yinlar olinmadi: {error}")
        return error, "", "", []
    
    # 2. PGN tahlil qilish
    games = parse_pgn_games(pgn_games)
    if not games:
        logger.error("O'yinlar tahlil qilinmadi")
        return "❌ O'yinlar tahlil qilinmadi.", "", "", []
    
    # 3. Har bir o'yinni Stockfish bilan tahlil qilish
    all_mistakes = []
    for i, game in enumerate(games[:10], 1):  # Birinchi 10 ta
        logger.info(f"O'yin {i}/{len(games[:10])} tahlil qilinmoqda...")
        mistakes = analyze_game_with_engine(game, username)
        all_mistakes.extend(mistakes)
    
    if not all_mistakes:
        logger.info("Xatolar topilmadi")
        return "✅ Ajoyib! Sizning o'yinlaringizda katta xatolar topilmadi!", "", "", []
    
    # 4. Zaif tomonlarni aniqlash
    weaknesses = categorize_all_mistakes(all_mistakes)
    
    # 5. Hisobot tayyorlash
    report = f"## 📊 {len(games)} ta o'yin tahlili\n\n"
    report += f"**Topilgan xatolar:** {len(all_mistakes)} ta\n\n"
    report += "### 🎯 Sizning eng zaif 3 tomoningiz:\n\n"
    
    for i, w in enumerate(weaknesses, 1):
        report += f"**{i}. {w['category']}**\n"
        report += f"   - {w['count']} marta ({w['percentage']:.1f}%)\n\n"
    
    # 6. AI tushuntirish
    explanation = get_ai_explanation(weaknesses)
    explanation_text = f"## 🤖 AI Murabbiy Tahlili\n\n{explanation}"
    
    # 7. Masalalar olish
    puzzles = fetch_puzzles_for_weaknesses(weaknesses, count=5)
    
    logger.info("===== TAHLIL TUGADI =====")
    return report, explanation_text, "", puzzles