import gradio as gr
import chess
import chess.svg
import logging
from handlers import analyze_user_games
import config

logger = logging.getLogger(__name__)

def create_chess_board(fen):
    """FEN dan shaxmat taxtasi SVG yaratish"""
    try:
        board = chess.Board(fen)
        svg = chess.svg.board(board, size=300)
        return svg
    except Exception as e:
        logger.error(f"Taxta chizish xatosi: {e}")
        return "<svg></svg>"

def format_puzzles_html(puzzles):
    """Masalalarni HTML formatda tayyorlash"""
    if not puzzles:
        return "<p>Masalalar topilmadi</p>"
    
    html = "<div style='display: grid; gap: 20px;'>"
    
    for i, puzzle in enumerate(puzzles, 1):
        board_svg = create_chess_board(puzzle['fen'])
        
        html += f"""
        <div style='border: 2px solid #e0e0e0; border-radius: 10px; padding: 15px; background: #f9f9f9;'>
            <h3 style='margin-top: 0;'>🧩 Masala {i}: {puzzle['theme']}</h3>
            <div style='display: flex; gap: 20px; align-items: start;'>
                <div style='flex-shrink: 0;'>
                    {board_svg}
                </div>
                <div style='flex-grow: 1;'>
                    <p><strong>Qiyinlik reytingi:</strong> {puzzle['rating']}</p>
                    <p><strong>Vazifa:</strong> Eng yaxshi harakatni toping</p>
                    <p><strong>Pozitsiya:</strong> <code style='background: #fff; padding: 5px; border-radius: 3px; font-size: 11px;'>{puzzle['fen'][:50]}...</code></p>
                    <a href='{puzzle['url']}' target='_blank' 
                       style='display: inline-block; background: #7fa650; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 5px; margin-top: 10px;'>
                        Lichess da yechish →
                    </a>
                </div>
            </div>
        </div>
        """
    
    html += "</div>"
    return html

# ============= ASOSIY TAHLIL FUNKSIYASI =============

def process_analysis(username):
    """Tahlilni boshlash va natijalarni qaytarish"""
    if not username or username.strip() == "":
        return (
            "❌ Iltimos, foydalanuvchi nomini kiriting",
            "",
            "<p>Masalalar ko'rsatilmaydi</p>"
        )
    
    username = username.strip()
    logger.info(f"Tahlil boshlandi: {username}")
    
    # Tahlil qilish
    report, explanation, _, puzzles = analyze_user_games(username)
    
    # Masalalarni HTML ga o'tkazish
    puzzles_html = format_puzzles_html(puzzles)
    
    return report, explanation, puzzles_html

# ============= GRADIO INTERFEYS =============

def create_interface():
    """Gradio interfeys yaratish"""
    
    # CSS stillari
    custom_css = """
    .main-container {
        max-width: 1200px;
        margin: 0 auto;
    }
    .puzzle-container {
        margin-top: 20px;
    }
    """
    
    with gr.Blocks(
        title="Shaxmat Tahlil",
        theme=gr.themes.Soft(primary_hue="green"),
        css=custom_css
    ) as app:
        
        gr.Markdown(f"# {config.UI_TEXTS['title']}")
        gr.Markdown(config.UI_TEXTS['description'])
        
        with gr.Row():
            with gr.Column(scale=1):
                username_input = gr.Textbox(
                    label=config.UI_TEXTS['username_label'],
                    placeholder=config.UI_TEXTS['username_placeholder'],
                    lines=1
                )
                
                analyze_btn = gr.Button(
                    config.UI_TEXTS['analyze_button'],
                    variant="primary",
                    size="lg"
                )
                
                gr.Markdown(config.UI_TEXTS['instructions'])
        
        with gr.Row():
            with gr.Column():
                weakness_output = gr.Markdown(
                    label=config.UI_TEXTS['weakness_title']
                )
        
        with gr.Row():
            with gr.Column():
                explanation_output = gr.Markdown(
                    label=config.UI_TEXTS['explanation_title']
                )
        
        gr.Markdown(f"## {config.UI_TEXTS['puzzles_title']}")
        
        with gr.Row():
            with gr.Column():
                puzzles_output = gr.HTML(
                    label="Masalalar",
                    elem_classes="puzzle-container"
                )
        
        # Tugmani bog'lash
        analyze_btn.click(
            fn=process_analysis,
            inputs=[username_input],
            outputs=[weakness_output, explanation_output, puzzles_output]
        )
        
        gr.Markdown("""
        ---
        ### ℹ️ Ma'lumot:
        - Dastur so'nggi 50 ta blitz o'yiningizni tahlil qiladi
        - Agar blitz o'yinlar bo'lmasa, bullet o'yinlar tahlil qilinadi
        - Tahlil 2-3 daqiqa davom etishi mumkin
        - Stockfish 15 chuqurlikda tahlil qiladi
        """)
    
    return app
if __name__ == "__main__":
    logger.info("Dastur ishga tushmoqda...")
    
    # Konfiguratsiyani tekshirish
    if not config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY sozlanmagan!")
    
    logger.info(f"Stockfish yo'li: {config.STOCKFISH_PATH}")
    
    # Interfeys yaratish va ishga tushirish
    app = create_interface()
    app.launch(
        share=False,
        server_name="0.0.0.0",
        server_port=7860
    )