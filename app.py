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

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

def get_user_games_from_chess_com(username):
    try:
        username = username.strip().lower()
        
        user_url = f"https://api.chess.com/pub/player/{username}"
        response = requests.get(user_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            return None, f"❌ Foydalanuvchi topilmadi: {username}. Chess.com'da mavjudligini tekshiring."
        
        archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
        response = requests.get(archives_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            return None, "❌ O'yinlar arxivi topilmadi."
        
        archives = response.json()['archives']
        if not archives:
            return None, "❌ O'yinlar topilmadi."
        
        all_games = []
        for archive_url in reversed(archives[-3:]):
            time.sleep(0.3)
            response = requests.get(archive_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:
                games = response.json()['games']
                all_games.extend(games)
            if len(all_games) >= 50:
                break
        
        rapid_games = [g for g in all_games if g.get('time_class') in ['rapid', 'blitz']]
        if not rapid_games:
            rapid_games = all_games[:50]
        
        pgn_list = [g['pgn'] for g in rapid_games[:50] if 'pgn' in g]
        
        if not pgn_list:
            return None, "❌ PGN formatdagi o'yinlar topilmadi."
        
        return pgn_list, None
        
    except Exception as e:
        return None, f"❌ Xatolik: {str(e)}"

def parse_pgn_content(pgn_content):
    games = []
    if isinstance(pgn_content, list):
        for pgn_text in pgn_content:
            try:
                game = chess.pgn.read_game(io.StringIO(pgn_text))
                if game:
                    games.append(game)
            except:
                pass
    else:
        pgn_io = io.StringIO(pgn_content)
        while True:
            try:
                game = chess.pgn.read_game(pgn_io)
                if game is None:
                    break
                games.append(game)
            except:
                break
    return games

def detect_opening(game):
    """Detect opening from ECO code or Opening header"""
    opening = game.headers.get("Opening", "")
    eco = game.headers.get("ECO", "")
    
    if opening:
        return opening
    elif eco:
        return f"ECO {eco}"
    else:
        return "Unknown Opening"

def analyze_game_detailed(game, username):
    board = game.board()
    mistakes = []
    move_number = 0
    
    white_player = game.headers.get("White", "").lower()
    black_player = game.headers.get("Black", "").lower()
    username_lower = username.lower()
    
    user_color = None
    if username_lower in white_player:
        user_color = chess.WHITE
    elif username_lower in black_player:
        user_color = chess.BLACK
    
    result = game.headers.get("Result", "*")
    opening = detect_opening(game)
    
    # Determine user result
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
            phase = 'opening_mistake'
        elif len(board.piece_map()) <= 10:
            phase = 'endgame_mistake'
        else:
            phase = 'middlegame_mistake'
        
        if mistake_type:
            mistakes.append({'type': mistake_type, 'phase': phase, 'move_number': move_number})
    
    return {
        'mistakes': mistakes,
        'opening': opening,
        'result': result,
        'user_color': user_color,
        'user_result': user_result
    }

def categorize_mistakes(all_mistakes):
    if not all_mistakes:
        return []
    
    types = []
    for m in all_mistakes:
        types.append(m['type'])
        types.append(m['phase'])
    
    counts = Counter(types)
    
    categories_map = {
        'blunder': "Qo'pol xatolar",
        'mistake': 'Kichik xatolar',
        'hanging_piece': 'Himoyasiz qoldirish',
        'opening_mistake': 'Debyut xatolari',
        'middlegame_mistake': "O'rta o'yin xatolari",
        'endgame_mistake': 'Endshpil xatolari'
    }
    
    weaknesses = []
    for mistake_type, count in counts.most_common(6):
        if mistake_type in categories_map:
            weaknesses.append({
                'category': categories_map[mistake_type],
                'count': count,
                'percentage': (count / len(all_mistakes) * 100)
            })
    
    return weaknesses[:3]

def fetch_lichess_puzzles(count=5):
    """Fetch real puzzles from Lichess API"""
    puzzles = []
    
    try:
        url = "https://lichess.org/api/puzzle/daily"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            puzzle = data['puzzle']
            game = data['game']
            
            puzzles.append({
                'id': puzzle['id'],
                'fen': puzzle['initialPly']['fen'] if 'initialPly' in puzzle else game['fen'],
                'moves': puzzle['solution'],
                'rating': puzzle['rating'],
                'themes': puzzle.get('themes', ['tactics'])
            })
    except:
        pass
    
    # If we couldn't fetch puzzles, return empty list
    return puzzles

def create_board_svg(fen, size=400):
    """Create SVG representation of chess position"""
    board = chess.Board(fen)
    svg = chess.svg.board(board, size=size)
    return svg

def get_comprehensive_analysis(weaknesses, opening_stats, color_stats, total_games):
    """Get AI-powered comprehensive analysis and learning plan"""
    
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
   - Onlayn kurslar (ChessBase, Chess.com, Lichess)
   - YouTube kanallari
   - Mashq uchun maxsus botlar yoki dasturlar

4. **DEBYUT TAVSIYALARI**: Statistikaga asoslanib, qaysi debyutlarni davom ettirish va qaysilarini o'zgartirish kerak.

5. **MOTIVATSION XULOSA**: Qisqa va rag'batlantiruvchi xulosa.

MUHIM: Javobni FAQAT O'ZBEK TILIDA yozing! Aniq va amaliy maslahatlar bering."""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI tahlil hozircha mavjud emas: {str(e)}"

def analyze_games(username, pgn_file):
    if username:
        pgn_content, error = get_user_games_from_chess_com(username)
        if error:
            return error, "", "", "", None, None, None, None, None
    elif pgn_file:
        username = "Player"
        pgn_content = pgn_file.decode('utf-8') if isinstance(pgn_file, bytes) else pgn_file
    else:
        return "❌ Foydalanuvchi nomini kiriting yoki PGN faylni yuklang", "", "", "", None, None, None, None, None
    
    games = parse_pgn_content(pgn_content)
    
    if not games:
        return "❌ O'yinlar topilmadi yoki tahlil qilinmadi", "", "", "", None, None, None, None, None
    
    all_mistakes = []
    opening_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})
    color_stats = {
        'white': {'wins': 0, 'losses': 0, 'draws': 0},
        'black': {'wins': 0, 'losses': 0, 'draws': 0}
    }
    
    for game in games[:30]:
        analysis = analyze_game_detailed(game, username)
        all_mistakes.extend(analysis['mistakes'])
        
        opening = analysis['opening']
        user_result = analysis.get('user_result')
        user_color = analysis['user_color']
        
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
    
    weaknesses = categorize_mistakes(all_mistakes)
    
    # Statistics Report
    stats_report = f"## 📊 {len(games)} ta o'yin tahlili\n\n"
    stats_report += f"**Jami xatolar:** {len(all_mistakes)} ta\n\n"
    
    stats_report += "### 🎯 Eng zaif 3 tomoningiz:\n\n"
    for i, w in enumerate(weaknesses, 1):
        stats_report += f"**{i}. {w['category']}** - {w['count']} marta ({w['percentage']:.1f}%)\n"
    
    # Opening Statistics
    opening_report = "\n\n## 🎭 Debyut Statistikasi\n\n"
    sorted_openings = sorted(opening_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:5]
    
    for opening, stats in sorted_openings:
        total = stats['total']
        wins = stats['wins']
        losses = stats['losses']
        draws = stats['draws']
        win_rate = (wins / total * 100) if total > 0 else 0
        
        opening_report += f"**{opening}** ({total} o'yin)\n"
        opening_report += f"- G'alabalar: {wins} ({win_rate:.1f}%) | Yutqazishlar: {losses} | Duranglar: {draws}\n\n"
    
    # Color Statistics
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
    
    # Get AI Analysis
    ai_analysis = get_comprehensive_analysis(weaknesses, opening_stats, color_stats, len(games))
    ai_report = f"## 🤖 AI Murabbiy: To'liq Tahlil va O'quv Rejasi\n\n{ai_analysis}"
    
    # Fetch puzzles
    puzzles = fetch_lichess_puzzles(5)
    
    if not puzzles:
        # If no puzzles fetched, show Lichess link
        return (
            full_report,
            ai_report,
            "## 🧩 Masalalar\n\nMasalalarni [Lichess.org](https://lichess.org/training) saytidan ishlang",
            "",
            None,
            "",
            None,
            "",
            None
        )
    
    puzzle_svgs = []
    puzzle_info = []
    
    for i, puzzle in enumerate(puzzles):
        svg = create_board_svg(puzzle['fen'], size=300)
        puzzle_svgs.append(svg)
        
        themes = ", ".join(puzzle['themes'][:2]) if 'themes' in puzzle else "Taktika"
        info = f"**Masala {i+1}**: {themes.title()} (Reyting: {puzzle['rating']})"
        puzzle_info.append(info)
    
    return (
        full_report,
        ai_report,
        "## 🧩 Sizning shaxsiy masalalaringiz\n\nQuyidagi pozitsiyalarda eng yaxshi yurishni toping:",
        puzzle_info[0] if len(puzzle_info) > 0 else "",
        puzzle_svgs[0] if len(puzzle_svgs) > 0 else None,
        puzzle_info[1] if len(puzzle_info) > 1 else "",
        puzzle_svgs[1] if len(puzzle_svgs) > 1 else None,
        puzzle_info[2] if len(puzzle_info) > 2 else "",
        puzzle_svgs[2] if len(puzzle_svgs) > 2 else None
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
            username_input = gr.Textbox(
                label="Chess.com foydalanuvchi nomi",
                placeholder="Foydalanuvchi nomini kiriting",
            )
            pgn_upload = gr.File(
                label="📁 Yoki PGN faylni yuklang",
                file_types=[".pgn"],
                type="binary"
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
        inputs=[username_input, pgn_upload],
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
    - **Chess.com:** Foydalanuvchi nomingizni kiriting (oxirgi 30-50 ta o'yin tahlil qilinadi)
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