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
    """
    Fetches relevant Lichess puzzles based on error types and user rating.
    error_types: list of strings (e.g. ['hangingPiece', 'blunder'])
    user_rating: int, target puzzle rating
    count: int, number of puzzles to fetch
    """
    puzzles = []
    try:
        # Lichess API: https://lichess.org/api/puzzle
        # We'll use the public puzzle endpoint and filter locally
        url = f"https://lichess.org/api/puzzle"
        headers = {'Accept': 'application/x-ndjson'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error("Failed to fetch puzzles from Lichess")
            return puzzles

        lines = response.text.strip().split('\n')
        for line in lines:
            if len(puzzles) >= count:
                break
            try:
                puzzle = requests.utils.json.loads(line)
                # Filter by rating and theme (error type)
                if abs(puzzle.get('rating', 1500) - user_rating) <= 150:
                    if any(theme in puzzle.get('themes', []) for theme in error_types):
                        puzzles.append({
                            'id': puzzle['id'],
                            'url': f"https://lichess.org/training/{puzzle['id']}",
                            'theme': ', '.join(puzzle.get('themes', [])),
                            'rating': puzzle.get('rating', 1500),
                            'fen': puzzle.get('fen', '')
                        })
            except Exception as e:
                continue
    except Exception as e:
        logger.error(f"Error fetching puzzles: {str(e)}")
    return puzzles