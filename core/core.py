
import chess
import chess.pgn
import io
import re
from collections import defaultdict
from core.ai_integration import get_comprehensive_analysis
from core.openings import detect_opening, load_opening_database
from core.chess_api import get_user_games_from_chess_com, fetch_lichess_puzzles

def extract_user_rating(games, username):
    ratings = []
    username_lower = username.strip().lower()
    
    for game in games:
        white_player = game.headers.get("White", "").strip().lower()
        black_player = game.headers.get("Black", "").strip().lower()
        
        if username_lower == white_player:
            white_elo = game.headers.get("WhiteElo", "")
            if white_elo and white_elo.isdigit():
                ratings.append(int(white_elo))
        
        elif username_lower == black_player:
            black_elo = game.headers.get("BlackElo", "")
            if black_elo and black_elo.isdigit():
                ratings.append(int(black_elo))
    
    if ratings:
        avg_rating = sum(ratings) // len(ratings)
        return avg_rating
    
    return 1500

def analyze_games(username_chesscom, pgn_file, username_pgn):
    actual_username = None
    pgn_content = None
    user_rating = 1500  # Default rating

    if username_chesscom:
        pgn_content, error = get_user_games_from_chess_com(username_chesscom)
        if error:
            return error, "", "", "", None, None, None, None, None
        actual_username = username_chesscom
    
    elif pgn_file:
        pgn_content = pgn_file.decode('utf-8') if isinstance(pgn_file, bytes) else pgn_file
        
        if username_pgn and username_pgn.strip():
            actual_username = username_pgn.strip()
        else:
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
    
    else:
        return "❌ Chess.com foydalanuvchi nomini kiriting yoki PGN faylni yuklang", "", "", "", None, None, None, None, None

    games = parse_pgn_content(pgn_content)
    
    if not games:
        return "❌ O'yinlar topilmadi yoki tahlil qilinmadi", "", "", "", None, None, None, None, None
    
    # Extract user rating from games
    user_rating = extract_user_rating(games, actual_username)
    
    all_analyses = []
    opening_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})
    color_stats = {
        'white': {'wins': 0, 'losses': 0, 'draws': 0},
        'black': {'wins': 0, 'losses': 0, 'draws': 0}
    }
    
    for game in games:
        analysis = analyze_game_detailed(game, actual_username)
        all_analyses.append(analysis)
        
        opening = analysis['opening']
        user_result = analysis.get('user_result')
        user_color = analysis['user_color']
        
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
    
    weaknesses = categorize_mistakes(all_analyses)
    
    all_mistakes = []
    for analysis in all_analyses:
        all_mistakes.extend(analysis.get('mistakes', []))
    
    stats_report = f"## 📊 {len(games)} ta o'yin tahlili\n\n"
    stats_report += f"**Sizning reytingingiz:** {user_rating}\n"
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
    
    ai_analysis = get_comprehensive_analysis(weaknesses, opening_stats, color_stats, len(games))
    ai_report = f"## 🤖 AI Murabbiy: To'liq Tahlil va O'quv Rejasi\n\n{ai_analysis}"
    
    weakness_themes = [w['category'] for w in weaknesses[:3]]
    puzzles = fetch_lichess_puzzles(weakness_themes, user_rating=user_rating, count=5)
    
    puzzle_text = "## 🧩 Sizning shaxsiy masalalaringiz\n\n"
    puzzle_text += f"Sizning reytingingiz: **{user_rating}** - Masalalar shu darajaga moslashtirilgan\n\n"
    for i, puzzle in enumerate(puzzles, 1):
        theme = puzzle.get('theme', 'Tactics')
        rating = puzzle.get('rating', user_rating)
        url = puzzle.get('url', 'https://lichess.org/training')
        puzzle_text += f"**Puzzle {i}: {theme}** (Rating: {rating})\n"
        puzzle_text += f"- [Lichess Training]({url})\n\n"
    
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
    
    user_result = None
    if user_color is not None and result != "*":
        if result == "1-0":
            user_result = "win" if user_color == chess.WHITE else "loss"
        elif result == "0-1":
            user_result = "win" if user_color == chess.BLACK else "loss"
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
    if not all_analyses:
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
    
    if total == 0:
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
    
    return weaknesses
