import gradio as gr
import chess
import chess.pgn
import chess.svg
import io
import requests
import google.generativeai as genai
from collections import Counter, defaultdict
import os
import time
import re
import chess.polyglot
import logging
from openings import get_opening_name_from_eco, detect_opening

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

def get_user_games_from_chess_com(username):
    try:
        logger.info(f"Starting to fetch games for user: {username}")
        username_original = username.strip()
        username = username_original.lower()
        
        user_url = f"https://api.chess.com/pub/player/{username}"
        response = requests.get(user_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            logger.error(f"User not found: {username}")
            return None, f"❌ Foydalanuvchi topilmadi: {username}. Chess.com'da mavjudligini tekshiring."
        
        logger.info(f"User found: {username}")
        archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
        response = requests.get(archives_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            logger.error("Archives not found")
            return None, "❌ O'yinlar arxivi topilmadi."
        
        archives = response.json()['archives']
        if not archives:
            logger.error("No archives available")
            return None, "❌ O'yinlar topilmadi."
        
        logger.info(f"Found {len(archives)} archives")
        
        all_games = []
        for archive_url in reversed(archives[-3:]):
            time.sleep(0.3)
            response = requests.get(archive_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:
                games = response.json()['games']
                all_games.extend(games)
                logger.info(f"Fetched {len(games)} games from archive")
            if len(all_games) >= 50:
                break
        
        logger.info(f"Total games fetched: {len(all_games)}")
        
        rapid_games = [g for g in all_games if g.get('time_class') in ['rapid', 'blitz']]
        if not rapid_games:
            rapid_games = all_games[:50]
        
        pgn_list = [g['pgn'] for g in rapid_games[:50] if 'pgn' in g]
        
        logger.info(f"Total PGN games prepared: {len(pgn_list)}")
        
        if not pgn_list:
            logger.error("No PGN games found")
            return None, "❌ PGN formatdagi o'yinlar topilmadi."
        
        return pgn_list, None
        
    except Exception as e:
        logger.error(f"Error fetching games: {str(e)}")
        return None, f"❌ Xatolik: {str(e)}"

def parse_pgn_content(pgn_content):
    logger.info("Starting to parse PGN content")
    games = []
    if isinstance(pgn_content, list):
        for idx, pgn_text in enumerate(pgn_content):
            try:
                game = chess.pgn.read_game(io.StringIO(pgn_text))
                if game:
                    games.append(game)
            except Exception as e:
                logger.warning(f"Failed to parse game {idx}: {str(e)}")
                pass
    else:
        pgn_io = io.StringIO(pgn_content)
        idx = 0
        while True:
            try:
                game = chess.pgn.read_game(pgn_io)
                if game is None:
                    break
                games.append(game)
                idx += 1
            except Exception as e:
                logger.warning(f"Failed to parse game {idx}: {str(e)}")
                break
    
    logger.info(f"Successfully parsed {len(games)} games")
    return games


def analyze_game_detailed(game, username):
    board = game.board()
    mistakes = []
    
    move_number = 0
    
    white_player = game.headers.get("White", "").strip().lower()
    black_player = game.headers.get("Black", "").strip().lower()
    username_lower = username.strip().lower()
    
    user_color = None
    if username_lower == white_player:
        user_color = chess.WHITE
    elif username_lower == black_player:
        user_color = chess.BLACK
    
    result = game.headers.get("Result", "*")
    opening = detect_opening(game)
    
    user_won = None
    user_result = None
    if user_color is not None and result != "*":
        if result == "1-0":
            user_won = (user_color == chess.WHITE)
            user_result = "win" if user_won else "loss"
        elif result == "0-1":
            user_won = (user_color == chess.BLACK)
            user_result = "win" if user_won else "loss"
        elif result == "1/2-1/2":
            user_result = "draw"
    
    material_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    
    def count_material(board):
        total = 0
        for piece_type in material_values:
            total += len(board.pieces(piece_type, chess.WHITE)) * material_values[piece_type]
            total -= len(board.pieces(piece_type, chess.BLACK)) * material_values[piece_type]
        return total
    
    for move in game.mainline_moves():
        move_number += 1
        
        if user_color is not None and board.turn != user_color:
            board.push(move)
            continue
        
        material_before = count_material(board)
        board.push(move)
        material_after = count_material(board)
        
        material_loss = abs(material_after - material_before) if board.turn == chess.WHITE else abs(material_before - material_after)
        
        moved_piece = board.piece_at(move.to_square)
        mistake_type = None
        
        if material_loss >= 3:
            mistake_type = 'blunder'
        elif material_loss >= 1:
            mistake_type = 'mistake'
        elif moved_piece and board.is_attacked_by(not board.turn, move.to_square):
            attackers = len(board.attackers(not board.turn, move.to_square))
            defenders = len(board.attackers(board.turn, move.to_square))
            if attackers > defenders:
                mistake_type = 'hanging_piece'
        
        if move_number <= 10:
            phase = 'opening'
        elif len(board.piece_map()) <= 10:
            phase = 'endgame'
        else:
            phase = 'middlegame'
        
        if mistake_type:
            mistakes.append({
                'type': mistake_type,
                'phase': phase,
                'move_number': move_number
            })
    
    return {
        'mistakes': mistakes,
        'opening': opening,
        'result': result,
        'user_color': user_color,
        'user_result': user_result
    }

def categorize_mistakes(all_analyses):
    logger.info("Categorizing mistakes from all games")
    
    if not all_analyses:
        logger.warning("No analyses provided for categorization")
        return []
    
    blunders = 0
    regular_mistakes = 0
    hanging = 0
    opening = 0
    middlegame = 0
    endgame = 0
    
    for analysis in all_analyses:
        for mistake in analysis.get('mistakes', []):
            mistake_type = mistake.get('type')
            phase = mistake.get('phase')
            
            if mistake_type == 'blunder':
                blunders += 1
            elif mistake_type == 'mistake':
                regular_mistakes += 1
            elif mistake_type == 'hanging_piece':
                hanging += 1
            
            if phase == 'opening':
                opening += 1
            elif phase == 'middlegame':
                middlegame += 1
            elif phase == 'endgame':
                endgame += 1
    
    total = blunders + regular_mistakes + hanging + opening + middlegame + endgame
    
    logger.info(f"Total mistakes found: {total}")
    logger.info(f"Blunders: {blunders}, Mistakes: {regular_mistakes}, Hanging: {hanging}")
    logger.info(f"Opening: {opening}, Middlegame: {middlegame}, Endgame: {endgame}")
    
    if total == 0:
        logger.warning("No mistakes found in any game")
        return []
    
    weaknesses = []
    
    if blunders > 0:
        weaknesses.append({
            'category': "Qo'pol xatolar",
            'count': blunders,
            'percentage': (blunders / total * 100)
        })
    
    if regular_mistakes > 0:
        weaknesses.append({
            'category': 'Kichik xatolar',
            'count': regular_mistakes,
            'percentage': (regular_mistakes / total * 100)
        })
    
    if hanging > 0:
        weaknesses.append({
            'category': 'Himoyasiz qoldirish',
            'count': hanging,
            'percentage': (hanging / total * 100)
        })
    
    if opening > 0:
        weaknesses.append({
            'category': 'Debyut xatolari',
            'count': opening,
            'percentage': (opening / total * 100)
        })
    
    if middlegame > 0:
        weaknesses.append({
            'category': "O'rta o'yin xatolari",
            'count': middlegame,
            'percentage': (middlegame / total * 100)
        })
    
    if endgame > 0:
        weaknesses.append({
            'category': 'Endshpil xatolari',
            'count': endgame,
            'percentage': (endgame / total * 100)
        })
    
    weaknesses.sort(key=lambda x: x['count'], reverse=True)
    
    logger.info(f"Total weakness categories: {len(weaknesses)}")
    return weaknesses

import json

def fetch_lichess_puzzles(themes, count=5):
    logger.info(f"Fetching {count} puzzles for themes: {themes}")
    puzzles = []
    
    theme_map = {
        "Qo'pol xatolar": ['hangingPiece', 'discoveredAttack', 'fork'],
        'Kichik xatolar': ['advantage', 'crushing', 'attackingF2F7'],
        'Himoyasiz qoldirish': ['hangingPiece', 'pin', 'skewer'],
        'Debyut xatolari': ['opening', 'short', 'middlegame'],
        "O'rta o'yin xatolari": ['middlegame', 'attackingF2F7', 'advancedPawn'],
        'Endshpil xatolari': ['endgame', 'queenEndgame', 'rookEndgame']
    }
    
    lichess_themes = []
    for theme_name in themes:
        if theme_name in theme_map:
            lichess_themes.extend(theme_map[theme_name])
    
    lichess_themes = list(set(lichess_themes))[:3]
    logger.info(f"Selected Lichess themes: {lichess_themes}")
    
    try:
        # Fetch puzzles using the daily puzzle API and database
        for theme in lichess_themes:
            if len(puzzles) >= count:
                break
            
            # Use Lichess puzzle database API
            url = f"https://lichess.org/api/puzzle/batch/mix?nb=2&themes={theme}"
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/x-ndjson'
            })
            
            if response.status_code == 200:
                # Parse NDJSON (newline-delimited JSON)
                lines = response.text.strip().split('\n')
                for line in lines:
                    if len(puzzles) >= count:
                        break
                    if not line.strip():
                        continue
                    try:
                        puzzle_data = json.loads(line)  # Use json.loads instead of eval
                        game_data = puzzle_data.get('game', {})
                        puzzle_info = puzzle_data.get('puzzle', {})
                        
                        puzzle_id = puzzle_info.get('id', '')
                        
                        if puzzle_id and not any(p['id'] == puzzle_id for p in puzzles):
                            puzzles.append({
                                'id': puzzle_id,
                                'fen': game_data.get('fen', ''),
                                'moves': ' '.join(puzzle_info.get('solution', [])),
                                'solution': puzzle_info.get('solution', []),
                                'rating': puzzle_info.get('rating', 1500),
                                'themes': puzzle_info.get('themes', []),
                                'url': f"https://lichess.org/training/{puzzle_id}"
                            })
                            logger.info(f"Added puzzle {puzzle_id} with rating {puzzle_info.get('rating')}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse puzzle line: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Error processing puzzle: {str(e)}")
            
            time.sleep(0.3)
    except Exception as e:
        logger.error(f"Error fetching puzzles: {str(e)}")
    
    # Fill remaining with daily puzzle if needed
    if len(puzzles) < count:
        try:
            url = "https://lichess.org/api/puzzle/daily"
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            
            if response.status_code == 200:
                daily_data = response.json()
                game_data = daily_data.get('game', {})
                puzzle_info = daily_data.get('puzzle', {})
                puzzle_id = puzzle_info.get('id', '')
                
                if puzzle_id and not any(p['id'] == puzzle_id for p in puzzles):
                    puzzles.append({
                        'id': puzzle_id,
                        'fen': game_data.get('fen', ''),
                        'moves': ' '.join(puzzle_info.get('solution', [])),
                        'solution': puzzle_info.get('solution', []),
                        'rating': puzzle_info.get('rating', 1500),
                        'themes': puzzle_info.get('themes', []),
                        'url': f"https://lichess.org/training/{puzzle_id}"
                    })
                    logger.info(f"Added daily puzzle {puzzle_id}")
        except Exception as e:
            logger.error(f"Error fetching daily puzzle: {str(e)}")
    
    # Fill with fallback training links if still not enough
    while len(puzzles) < count:
        puzzles.append({
            'id': f'training_{len(puzzles)+1}',
            'fen': '',
            'moves': '',
            'solution': [],
            'rating': 1500,
            'themes': ['Mixed'],
            'url': "https://lichess.org/training"
        })
        logger.info(f"Added fallback puzzle link {len(puzzles)}")
    
    logger.info(f"Total puzzles prepared: {len(puzzles)}")
    return puzzles[:count]

def get_comprehensive_analysis(weaknesses, opening_stats, color_stats, total_games):
    logger.info("Generating AI comprehensive analysis")
    
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
        logger.info("AI analysis generated successfully")
        return response.text
    except Exception as e:
        logger.error(f"AI analysis failed: {str(e)}")
        return f"AI tahlil hozircha mavjud emas: {str(e)}"

def analyze_games(username_chesscom, pgn_file, username_pgn):
    logger.info("=== Starting game analysis ===")
    actual_username = None
    pgn_content = None

    if username_chesscom:
        pgn_content, error = get_user_games_from_chess_com(username_chesscom)
        if error:
            logger.error(f"Failed to fetch games: {error}")
            return error, "", "", "", None, None, None, None, None
        actual_username = username_chesscom
    
    # PGN file upload
    elif pgn_file:
        logger.info("Processing uploaded PGN file")
        pgn_content = pgn_file.decode('utf-8') if isinstance(pgn_file, bytes) else pgn_file
        
        if username_pgn and username_pgn.strip():
            actual_username = username_pgn.strip()
        else:
            # Try to extract username from first game headers
            try:
                first_game = chess.pgn.read_game(io.StringIO(pgn_content))
                if first_game:
                    white = first_game.headers.get("White", "")
                    black = first_game.headers.get("Black", "")
                    actual_username = white if white else black if black else "Player"
                else:
                    actual_username = "Player"
            except:
                actual_username = "Player"
            
            logger.info(f"Extracted username from PGN: {actual_username}")
    
    else:
        logger.error("No username or file provided")
        return "❌ Chess.com foydalanuvchi nomini kiriting yoki PGN faylni yuklang", "", "", "", None, None, None, None, None

    games = parse_pgn_content(pgn_content)
    
    if not games:
        logger.error("No games parsed")
        return "❌ O'yinlar topilmadi yoki tahlil qilinmadi", "", "", "", None, None, None, None, None
    
    logger.info(f"Analyzing {len(games)} games")
    
    all_analyses = []
    opening_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})
    color_stats = {
        'white': {'wins': 0, 'losses': 0, 'draws': 0},
        'black': {'wins': 0, 'losses': 0, 'draws': 0}
    }
    
    for idx, game in enumerate(games):
        logger.info(f"Analyzing game {idx + 1}/{len(games)}")
        analysis = analyze_game_detailed(game, actual_username)
        all_analyses.append(analysis)
        
        opening = analysis['opening']
        user_result = analysis.get('user_result')
        user_color = analysis['user_color']
        
        logger.info(f"Game {idx + 1}: {opening}, Result: {user_result}, Color: {user_color}")
        
        if user_color is not None:
            opening_stats[opening]['total'] += 1
            
            if user_result == 'win':
                opening_stats[opening]['wins'] += 1
                color_key = 'white' if user_color == chess.WHITE else 'black'
                color_stats[color_key]['wins'] += 1
            elif user_result == 'loss':
                opening_stats[opening]['losses'] += 1
                color_key = 'white' if user_color == chess.WHITE else 'black'
                color_stats[color_key]['losses'] += 1
            elif user_result == 'draw':
                opening_stats[opening]['draws'] += 1
                color_key = 'white' if user_color == chess.WHITE else 'black'
                color_stats[color_key]['draws'] += 1
    
    logger.info("Categorizing mistakes")
    weaknesses = categorize_mistakes(all_analyses)
    
    all_mistakes = []
    for analysis in all_analyses:
        all_mistakes.extend(analysis.get('mistakes', []))
    
    logger.info(f"Total mistakes collected: {len(all_mistakes)}")
    
    stats_report = f"## 📊 {len(games)} ta o'yin tahlili\n\n"
    stats_report += f"**Jami xatolar:** {len(all_mistakes)} ta\n\n"
    
    stats_report += "### 🎯 Eng zaif 3 tomoningiz:\n\n"
    if weaknesses:
        for i, w in enumerate(weaknesses[:3], 1):
            stats_report += f"**{i}. {w['category']}** - {w['count']} marta ({w['percentage']:.1f}%)\n"
    else:
        stats_report += "Xatolar topilmadi yoki tahlil qilinmadi.\n"
    
    opening_report = "\n\n## 🎭 Debyut Statistikasi\n\n"
    sorted_openings = sorted(opening_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
    
    for opening, stats in sorted_openings:
        total = stats['total']
        wins = stats['wins']
        losses = stats['losses']
        draws = stats['draws']
        win_rate = (wins / total * 100) if total > 0 else 0
        
        opening_report += f"**{opening}** ({total} o'yin)\n"
        opening_report += f"- G'alabalar: {wins} ({win_rate:.1f}%) | Yutqazishlar: {losses} | Duranglar: {draws}\n\n"
    
    color_report = "\n\n## ⚪⚫ Rang bo'yicha natijalar\n\n"
    
    white_total = sum(color_stats['white'].values())
    black_total = sum(color_stats['black'].values())
    
    if white_total > 0:
        white_wr = color_stats['white']['wins'] / white_total * 100
        color_report += f"**Oq figuralar bilan:**\n"
        color_report += f"- G'alabalar: {color_stats['white']['wins']} ({white_wr:.1f}%)\n"
        color_report += f"- Yutqazishlar: {color_stats['white']['losses']}\n"
        color_report += f"- Duranglar: {color_stats['white']['draws']}\n\n"
    
    if black_total > 0:
        black_wr = color_stats['black']['wins'] / black_total * 100
        color_report += f"**Qora figuralar bilan:**\n"
        color_report += f"- G'alabalar: {color_stats['black']['wins']} ({black_wr:.1f}%)\n"
        color_report += f"- Yutqazishlar: {color_stats['black']['losses']}\n"
        color_report += f"- Duranglar: {color_stats['black']['draws']}\n"
    
    full_report = stats_report + opening_report + color_report
    
    logger.info("Generating AI analysis")
    ai_analysis = get_comprehensive_analysis(weaknesses, opening_stats, color_stats, len(games))
    ai_report = f"## 🤖 AI Murabbiy: To'liq Tahlil va O'quv Rejasi\n\n{ai_analysis}"
    
    weakness_themes = [w['category'] for w in weaknesses[:3]]
    logger.info(f"Fetching puzzles for themes: {weakness_themes}")
    puzzles = fetch_lichess_puzzles(weakness_themes, count=5)
    
    puzzle_text = "## 🧩 Sizning shaxsiy masalalaringiz\n\n"
    if puzzles:
        for i, puzzle in enumerate(puzzles, 1):
            theme = puzzle.get('themes', ['Tactics'])[0].title() if puzzle.get('themes') else 'Tactics'
            rating = puzzle.get('rating', 1500)
            url = puzzle.get('url', 'https://lichess.org/training')
            fen = puzzle.get('fen', '')[:40] if puzzle.get('fen') else 'N/A'
            puzzle_text += f"**Puzzle {i}: {theme}** (Rating: {rating})\n"
            puzzle_text += f"- [Solve on Lichess]({url})\n"
            puzzle_text += f"- Position: `{fen}...`\n\n"
    else:
        puzzle_text += "- Masalalarni [Lichess.org](https://lichess.org/training) saytidan ishlang\n"
    
    logger.info("=== Analysis completed successfully ===")
    
    return (
        full_report,
        ai_report,
        puzzle_text,
        "",
        None,
        "",
        None,
        "",
        None
    )

with gr.Blocks(title="Chess Study Plan Pro", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # ♟️ Professional Шахмат O'quv Rejasi
    
    ### To'liq tahlil va shaxsiy o'quv rejasi:
    - 📊 Batafsil statistika (debyutlar, ranglar, natijalar)
    - 🎯 Zaif tomonlar tahlili
    - 🤖 AI murabbiy tavsiyalari
    - 📚 Kitoblar va kurslar tavsiyasi
    - 🧩 Interaktiv masalalar (gradio interfeysi ichida)
    """)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🌐 Uzchess.com dan tahlil")
            username_chesscom = gr.Textbox(
                label="Uzchess.com foydalanuvchi nomi",
                placeholder="Foydalanuvchi nomini kiriting",
            )
        
        with gr.Column():
            gr.Markdown("### 📁 PGN fayl yuklash")
            pgn_upload = gr.File(
                label="PGN faylni yuklang",
                file_types=[".pgn"],
                type="binary"
            )
            username_pgn = gr.Textbox(
                label="Foydalanuvchi nomi (PGN uchun)",
                placeholder="PGN dagi o'yinchi nomi (ixtiyoriy)",
                info="Bo'sh qoldiring, avtomatik aniqlanadi"
            )
    
    analyze_btn = gr.Button("🔍 To'liq tahlil qilish", variant="primary", size="lg")
    
    with gr.Row():
        stats_output = gr.Markdown(label="Statistika")
    
    with gr.Row():
        ai_output = gr.Markdown(label="AI Tahlil")
    
    gr.Markdown("---")
    
    puzzle_header = gr.Markdown()
    
    with gr.Row():
        with gr.Column():
            puzzle1_info = gr.Markdown()
            puzzle1_board = gr.HTML()
        
        with gr.Column():
            puzzle2_info = gr.Markdown()
            puzzle2_board = gr.HTML()
        
        with gr.Column():
            puzzle3_info = gr.Markdown()
            puzzle3_board = gr.HTML()
    
    analyze_btn.click(
        fn=analyze_games,
        inputs=[username_chesscom, pgn_upload, username_pgn],
        outputs=[
            stats_output,
            ai_output,
            puzzle_header,
            puzzle1_info,
            puzzle1_board,
            puzzle2_info,
            puzzle2_board,
            puzzle3_info,
            puzzle3_board
        ]
    )
    
    gr.Markdown("""
    ---
    ### 📝 Qanday foydalanish:
    - **Uzchess.com:** Foydalanuvchi nomingizni kiriting (oxirgi 30-50 ta o'yin tahlil qilinadi)
    - **Lichess:** Profile → Games → Export orqali PGN faylni yuklang
    - **Masalalar:** Har bir masalani tahlil qiling va eng yaxshi yurishni toping
    
    ### 🎯 Yangi xususiyatlar:
    - ✅ Debyut statistikasi (qaysi debyutlarda yaxshi/yomon o'ynaysiz)
    - ✅ Oq/Qora rang bo'yicha natijalar
    - ✅ Interaktiv masalalar (gradio interfeysi ichida)
    - ✅ Shaxsiy o'quv rejasi (kundalik mashg'ulotlar)
    - ✅ Kitoblar va kurslar tavsiyasi
    """)

demo.launch()