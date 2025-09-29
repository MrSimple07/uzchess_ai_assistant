import gradio as gr
import chess
import chess.pgn
import io
import requests
import google.generativeai as genai
from collections import Counter
import os
import time

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
            if len(all_games) >= 30:
                break
        
        rapid_games = [g for g in all_games if g.get('time_class') in ['rapid', 'blitz']]
        if not rapid_games:
            rapid_games = all_games[:30]
        
        pgn_list = [g['pgn'] for g in rapid_games[:30] if 'pgn' in g]
        
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

def analyze_game_simple(game, username):
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
    
    return mistakes

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
    for mistake_type, count in counts.most_common(5):
        if mistake_type in categories_map:
            weaknesses.append({
                'category': categories_map[mistake_type],
                'count': count,
                'percentage': (count / len(all_mistakes) * 100)
            })
    
    return weaknesses[:3]

def get_ai_explanation(weaknesses):
    weakness_text = "\n".join([f"- {w['category']}: {w['count']} marta ({w['percentage']:.1f}%)" for w in weaknesses])
    
    prompt = f"""Siz шахмат murabbiysiz. O'yinchi o'zining so'nggi o'yinlarida quyidagi zaif tomonlarni ko'rsatdi:

{weakness_text}

Har bir zaif tomonni oddiy va rag'batlantiruvchi tilda tushuntiring (har biri uchun 2-3 jumla). Yaxshilash uchun amaliy maslahatlar bering. Do'stona va motivatsion bo'ling.

MUHIM: Javobni FAQAT O'ZBEK TILIDA yozing!"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI tushuntirish hozircha mavjud emas: {str(e)}"

def fetch_puzzles(weaknesses, count=5):
    puzzles = []
    
    for _ in range(count):
        try:
            url = "https://lichess.org/api/puzzle/daily"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                puzzle = data['puzzle']
                
                theme = weaknesses[len(puzzles) % len(weaknesses)]['category'] if weaknesses else 'Amaliyot'
                
                puzzles.append({
                    'id': puzzle['id'],
                    'rating': puzzle['rating'],
                    'theme': theme,
                    'url': f"https://lichess.org/training/{puzzle['id']}"
                })
        except:
            pass
        
        time.sleep(0.5)
    
    while len(puzzles) < count:
        puzzles.append({
            'id': f'default_{len(puzzles)}',
            'rating': 1500,
            'theme': 'Amaliyot',
            'url': 'https://lichess.org/training'
        })
    
    return puzzles

def analyze_games(username, pgn_file):
    if username:
        pgn_content, error = get_user_games_from_chess_com(username)
        if error:
            return error, "", ""
    elif pgn_file:
        username = "Player"
        pgn_content = pgn_file.decode('utf-8') if isinstance(pgn_file, bytes) else pgn_file
    else:
        return "❌ Foydalanuvchi nomini kiriting yoki PGN faylni yuklang", "", ""
    
    games = parse_pgn_content(pgn_content)
    
    if not games:
        return "❌ O'yinlar topilmadi yoki tahlil qilinmadi", "", ""
    
    all_mistakes = []
    for game in games[:20]:
        mistakes = analyze_game_simple(game, username)
        all_mistakes.extend(mistakes)
    
    if not all_mistakes:
        return f"✅ Ajoyib! {len(games)} ta o'yinda katta xatolar topilmadi!", "", ""
    
    weaknesses = categorize_mistakes(all_mistakes)
    
    report = f"## 📊 {len(games)} ta o'yin tahlili\n\n"
    report += f"**Topilgan xatolar:** {len(all_mistakes)} ta\n\n"
    report += "### 🎯 Eng zaif 3 tomoningiz:\n\n"
    
    for i, w in enumerate(weaknesses, 1):
        report += f"**{i}. {w['category']}**\n"
        report += f"   - {w['count']} marta ({w['percentage']:.1f}%)\n\n"
    
    explanation = get_ai_explanation(weaknesses)
    explanation_text = f"## 🤖 AI Murabbiy Tahlili\n\n{explanation}"
    
    puzzles = fetch_puzzles(weaknesses, count=5)
    
    puzzle_text = "## 🧩 Shaxsiy O'quv Rejangiz (5 ta masala)\n\n"
    for i, puzzle in enumerate(puzzles, 1):
        puzzle_text += f"**Masala {i}: {puzzle['theme']}** (Reyting: {puzzle['rating']})\n"
        puzzle_text += f"- [Lichess'da yechish]({puzzle['url']})\n\n"
    
    return report, explanation_text, puzzle_text

with gr.Blocks(title="Chess Study Plan", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # ♟️ Shaxsiy Шахмат O'quv Rejasi
    
    Chess.com foydalanuvchi nomingizni kiriting yoki PGN faylni yuklang:
    - 📊 Eng zaif 3 tomoningizni tahlil
    - 🤖 AI murabbiy tushuntirishlari
    - 🧩 5 ta shaxsiy masala
    """)
    
    with gr.Row():
        with gr.Column():
            username_input = gr.Textbox(
                label="Chess.com foydalanuvchi nomi",
                placeholder="muslimbek_01"
            )
            pgn_upload = gr.File(
                label="📁 Yoki PGN faylni yuklang",
                file_types=[".pgn"],
                type="binary"
            )
            analyze_btn = gr.Button("🔍 O'yinlarni tahlil qilish", variant="primary", size="lg")
    
    with gr.Row():
        weakness_output = gr.Markdown()
    
    with gr.Row():
        explanation_output = gr.Markdown()
    
    with gr.Row():
        puzzle_output = gr.Markdown()
    
    analyze_btn.click(
        fn=analyze_games,
        inputs=[username_input, pgn_upload],
        outputs=[weakness_output, explanation_output, puzzle_output]
    )
    
    gr.Markdown("""
    ---
    ### 📝 Qanday foydalanish:
    - **Chess.com:** Foydalanuvchi nomingizni kiriting (masalan: muslimbek_01)
    - **Lichess:** Profile → Games → Export orqali PGN faylni yuklang
    """)

demo.launch()