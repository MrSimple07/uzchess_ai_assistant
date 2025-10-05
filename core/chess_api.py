import logging
import requests
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_user_games_from_chess_com(username):
    try:
        logger.info(f"Fetching games for: {username}")
        username = username.strip().lower()
        
        user_url = f"https://api.chess.com/pub/player/{username}"
        response = requests.get(user_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            return None, f"❌ Foydalanuvchi topilmadi: {username}"
        
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
        logger.error(f"Error fetching games: {str(e)}")
        return None, f"❌ Xatolik: {str(e)}"


def fetch_lichess_puzzles(error_types, user_rating=1500, count=5):
    puzzles = []
    
    # Map Uzbek error categories to Lichess puzzle themes
    theme_mapping = {
        "Qo'pol xatolar": ["mate", "mateIn1", "mateIn2", "hangingPiece"],
        "Kichik xatolar": ["advantage", "crushing", "attackingF2F7"],
        "Himoyasiz qoldirish": ["hangingPiece", "pin", "skewer", "discoveredAttack"],
        "Debyut xatolari": ["opening", "middlegame"],
        "O'rta o'yin xatolari": ["middlegame", "fork", "defensiveMove"],
        "Endshpil xatolari": ["endgame", "advancedPawn", "promotion"]
    }
    
    # Convert error types to Lichess themes
    lichess_themes = []
    for error_type in error_types:
        if error_type in theme_mapping:
            lichess_themes.extend(theme_mapping[error_type])
    
    lichess_themes = list(set(lichess_themes))
    
    if not lichess_themes:
        lichess_themes = ["tactics"]
    
    try:
        for theme in lichess_themes[:3]:  # Limit to top 3 themes
            if len(puzzles) >= count:
                break
                
            url = f"https://lichess.org/api/puzzle/daily"
            headers = {'Accept': 'application/json'}
            
            params = {
                'max': count,
                'theme': theme
            }
            
            try:
                response = requests.get(
                    "https://lichess.org/api/puzzle/activity",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Filter by rating range
                    for item in data.get('puzzles', []):
                        if len(puzzles) >= count:
                            break
                            
                        puzzle_rating = item.get('puzzle', {}).get('rating', 1500)
                        
                        if abs(puzzle_rating - user_rating) <= 300:
                            puzzle_id = item.get('puzzle', {}).get('id')
                            puzzle_themes = item.get('puzzle', {}).get('themes', [])
                            
                            puzzles.append({
                                'id': puzzle_id,
                                'url': f"https://lichess.org/training/{puzzle_id}",
                                'theme': theme.title(),
                                'rating': puzzle_rating,
                                'themes': puzzle_themes
                            })
            except:
                pass
        
        # If no puzzles found, provide generic training links
        if not puzzles:
            for i, theme in enumerate(lichess_themes[:count]):
                puzzles.append({
                    'id': f'theme_{i}',
                    'url': f"https://lichess.org/training/{theme}",
                    'theme': theme.title(),
                    'rating': user_rating,
                    'themes': [theme]
                })
                
    except Exception as e:
        logger.error(f"Error fetching puzzles: {str(e)}")
        
        for i, error_type in enumerate(error_types[:count]):
            theme = theme_mapping.get(error_type, ["tactics"])[0]
            puzzles.append({
                'id': f'fallback_{i}',
                'url': f"https://lichess.org/training/{theme}",
                'theme': error_type,
                'rating': user_rating,
                'themes': [theme]
            })
    
    return puzzles