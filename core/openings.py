
import csv
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_opening_database():
    openings = {}
    try:
        with open('data/Chess Opening Reference - Sheet1.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eco = row.get('ECO Code', '').strip()
                name = row.get('Name', '').strip()
                if eco and name:
                    openings[eco] = name
    except Exception as e:
        logger.error(f"Failed to load openings CSV: {e}")
    return openings

OPENING_DB = load_opening_database()

def detect_opening(game):
    eco = game.headers.get("ECO", "")
    opening = game.headers.get("Opening", "")
    
    if eco and eco in OPENING_DB:
        return OPENING_DB[eco]
    elif opening:
        return opening
    else:
        return "Unknown Opening"
