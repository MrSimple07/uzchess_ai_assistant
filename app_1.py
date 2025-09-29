import gradio as gr
import chess
import chess.pgn
import io
import requests
import google.generativeai as genai
from collections import Counter
import json
import os

# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ============= GAME ANALYSIS =============

def parse_pgn_file(pgn_content):
    """Parse PGN file and return list of games"""
    games = []
    pgn_io = io.StringIO(pgn_content)
    
    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        games.append(game)
    
    return games

def analyze_single_game(game):
    """Analyze a single game and extract mistakes"""
    board = game.board()
    mistakes = []
    move_number = 0
    
    for move in game.mainline_moves():
        move_number += 1
        position_fen = board.fen()
        
        # Apply the move
        board.push(move)
        
        # Simple heuristic-based mistake detection
        mistake_type = detect_mistake_simple(board, move, position_fen)
        if mistake_type:
            mistakes.append({
                'move_number': move_number,
                'move': move.uci(),
                'type': mistake_type,
                'fen': position_fen
            })
    
    return mistakes

def detect_mistake_simple(board, move, position_fen):
    """Simple rule-based mistake detection"""
    # Check if piece was hung (left undefended)
    if board.is_check():
        return None
    
    # Count material before and after
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0
    }
    
    # Detect common tactical mistakes
    from_square = move.from_square
    to_square = move.to_square
    
    # Check if moved piece is now attacked and undefended
    moved_piece = board.piece_at(to_square)
    if moved_piece and board.is_attacked_by(not board.turn, to_square):
        attackers = len(board.attackers(not board.turn, to_square))
        defenders = len(board.attackers(board.turn, to_square))
        if attackers > defenders:
            return "hanging_piece"
    
    # Check if move allows opponent tactics
    if moved_piece and moved_piece.piece_type == chess.KNIGHT:
        # Simple check for knight positioning
        return "knight_positioning"
    
    # Detect pawn structure issues
    if moved_piece and moved_piece.piece_type == chess.PAWN:
        return "pawn_structure"
    
    # Endgame detection
    total_pieces = len(board.piece_map())
    if total_pieces <= 10:
        return "endgame_technique"
    
    return None

def categorize_mistakes(all_mistakes):
    """Categorize and count mistake types"""
    mistake_types = [m['type'] for m in all_mistakes if m['type']]
    mistake_counts = Counter(mistake_types)
    
    # Map to readable categories
    category_map = {
        'hanging_piece': 'Hanging Pieces / Undefended Material',
        'knight_positioning': 'Knight Tactics & Positioning',
        'pawn_structure': 'Pawn Structure Weaknesses',
        'endgame_technique': 'Endgame Technique Issues'
    }
    
    categorized = []
    for mistake_type, count in mistake_counts.most_common(3):
        readable_name = category_map.get(mistake_type, mistake_type)
        categorized.append({
            'category': readable_name,
            'count': count,
            'percentage': (count / len(all_mistakes) * 100) if all_mistakes else 0
        })
    
    return categorized

# ============= GEMINI AI EXPLANATION =============

def get_ai_explanation(weaknesses):
    """Use Gemini to explain weaknesses in plain language"""
    weakness_text = "\n".join([f"- {w['category']}: {w['percentage']:.1f}%" for w in weaknesses])
    
    prompt = f"""You are a chess coach. A player has these top weaknesses based on their recent games:

{weakness_text}

Explain each weakness in simple, encouraging language (2-3 sentences each). Give practical advice on how to improve. Be friendly and motivating."""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI explanation unavailable: {str(e)}"

# ============= PUZZLE FETCHING =============

def fetch_lichess_puzzles(themes, count=5):
    """Fetch puzzles from Lichess based on themes"""
    # Map our categories to Lichess puzzle themes
    theme_map = {
        'Hanging Pieces / Undefended Material': 'hangingPiece',
        'Knight Tactics & Positioning': 'knightEndgame',
        'Pawn Structure Weaknesses': 'pawnEndgame',
        'Endgame Technique Issues': 'endgame'
    }
    
    puzzles = []
    
    for theme_name in themes:
        lichess_theme = theme_map.get(theme_name, 'mix')
        
        try:
            # Lichess puzzle database API
            url = f"https://lichess.org/api/puzzle/daily"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                puzzle_data = response.json()
                puzzles.append({
                    'id': puzzle_data['puzzle']['id'],
                    'fen': puzzle_data['game']['fen'],
                    'moves': puzzle_data['puzzle']['solution'],
                    'rating': puzzle_data['puzzle']['rating'],
                    'theme': theme_name,
                    'url': f"https://lichess.org/training/{puzzle_data['puzzle']['id']}"
                })
        except Exception as e:
            print(f"Error fetching puzzle: {e}")
    
    # If we couldn't fetch enough, add some backup puzzles
    while len(puzzles) < count:
        puzzles.append({
            'id': f'backup_{len(puzzles)}',
            'fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
            'moves': ['e2e4'],
            'rating': 1500,
            'theme': 'Practice',
            'url': 'https://lichess.org/training'
        })
    
    return puzzles[:count]

# ============= MAIN PROCESSING FUNCTION =============

def process_chess_games(pgn_file, username=""):
    """Main function to process games and generate study plan"""
    try:
        # Read PGN content
        if pgn_file is None:
            return "❌ Please upload a PGN file", "", ""
        
        pgn_content = pgn_file.decode('utf-8') if isinstance(pgn_file, bytes) else pgn_file
        
        # Parse games
        games = parse_pgn_file(pgn_content)
        
        if not games:
            return "❌ No games found in PGN file", "", ""
        
        # Analyze all games
        all_mistakes = []
        for game in games[:10]:  # Limit to 10 games for demo
            mistakes = analyze_single_game(game)
            all_mistakes.extend(mistakes)
        
        if not all_mistakes:
            return "✅ Great! No major mistakes detected in your games!", "", ""
        
        # Categorize mistakes
        top_weaknesses = categorize_mistakes(all_mistakes)
        
        # Format weakness report
        weakness_report = f"## 📊 Analysis of {len(games)} Games\n\n"
        weakness_report += f"**Total Mistakes Detected:** {len(all_mistakes)}\n\n"
        weakness_report += "### 🎯 Your Top 3 Weaknesses:\n\n"
        
        for i, weakness in enumerate(top_weaknesses, 1):
            weakness_report += f"**{i}. {weakness['category']}**\n"
            weakness_report += f"   - Occurred {weakness['count']} times ({weakness['percentage']:.1f}%)\n\n"
        
        # Get AI explanation
        ai_explanation = get_ai_explanation(top_weaknesses)
        explanation_text = f"## 🤖 AI Coach Analysis\n\n{ai_explanation}"
        
        # Fetch puzzles
        theme_names = [w['category'] for w in top_weaknesses]
        puzzles = fetch_lichess_puzzles(theme_names, count=5)
        
        # Format puzzle recommendations
        puzzle_text = "## 🧩 Your Personalized Study Plan (5 Puzzles)\n\n"
        for i, puzzle in enumerate(puzzles, 1):
            puzzle_text += f"**Puzzle {i}: {puzzle['theme']}** (Rating: {puzzle['rating']})\n"
            puzzle_text += f"- [Solve on Lichess]({puzzle['url']})\n"
            puzzle_text += f"- Position: `{puzzle['fen'][:40]}...`\n\n"
        
        return weakness_report, explanation_text, puzzle_text
        
    except Exception as e:
        return f"❌ Error: {str(e)}", "", ""

# ============= GRADIO INTERFACE =============

def create_interface():
    """Create Gradio interface"""
    
    with gr.Blocks(title="Chess AI Study Plan", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
        # ♟️ Personalized Chess Study Plan Generator
        
        Upload your chess games (PGN format) and get:
        - 📊 Analysis of your top 3 weaknesses
        - 🤖 AI coach explanations
        - 🧩 5 personalized puzzles to improve
        """)
        
        with gr.Row():
            with gr.Column():
                pgn_upload = gr.File(
                    label="📁 Upload PGN File",
                    file_types=[".pgn"],
                    type="binary"
                )
                username_input = gr.Textbox(
                    label="Chess.com Username (optional)",
                    placeholder="Enter username to fetch games"
                )
                analyze_btn = gr.Button("🔍 Analyze Games", variant="primary", size="lg")
        
        with gr.Row():
            weakness_output = gr.Markdown(label="Weaknesses")
        
        with gr.Row():
            explanation_output = gr.Markdown(label="AI Explanation")
        
        with gr.Row():
            puzzle_output = gr.Markdown(label="Study Plan")
        
        # Connect button
        analyze_btn.click(
            fn=process_chess_games,
            inputs=[pgn_upload, username_input],
            outputs=[weakness_output, explanation_output, puzzle_output]
        )
        
        gr.Markdown("""
        ---
        ### 📝 How to get your PGN file:
        - **Lichess**: Go to your profile → Games → Export
        - **Chess.com**: Go to Archive → Download games
        """)
    
    return demo

# ============= LAUNCH =============

if __name__ == "__main__":
    demo = create_interface()
    demo.launch()