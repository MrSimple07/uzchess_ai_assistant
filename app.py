import gradio as gr
import chess
import chess.pgn
import io
import requests
from collections import defaultdict
import os
import logging
from core.core import analyze_games

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

with gr.Blocks(title="Chess Study Plan Pro", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # ♟️ Professional Шахмат O'quv Rejasi
    
    ### To'liq tahlil va shaxsiy o'quv rejasi:
    - 📊 Batafsil statistika (debyutlar, ranglar, natijalar)
    - 🎯 Zaif tomonlar tahlili
    - 🤖 AI murabbiy tavsiyalari
    - 📚 Kitoblar va kurslar tavsiyasi
    - 🧩 Lichess mashq masalalari
    """)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🌐 Chess.com dan tahlil")
            username_chesscom = gr.Textbox(
                label="Chess.com foydalanuvchi nomi",
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
    - **Chess.com:** Foydalanuvchi nomingizni kiriting (oxirgi 30-50 ta o'yin tahlil qilinadi)
    - **Lichess:** Profile → Games → Export orqali PGN faylni yuklang
    - **Masalalar:** Lichess.org saytida mashq qiling
    
    ### 🎯 Xususiyatlar:
    - ✅ Debyut statistikasi (qaysi debyutlarda yaxshi/yomon o'ynaysiz)
    - ✅ Oq/Qora rang bo'yicha natijalar
    - ✅ Lichess mashq havolalari
    - ✅ Shaxsiy o'quv rejasi (kundalik mashg'ulotlar)
    - ✅ Kitoblar va kurslar tavsiyasi
    """)

demo.launch()