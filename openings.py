
def get_opening_name_from_eco(eco_code):
    eco_openings = {
        'A00': 'Uncommon Opening',
        'A01': "Nimzowitsch-Larsen Attack",
        'A02': "Bird's Opening",
        'A03': "Bird's Opening: Dutch Variation",
        'A04': 'Reti Opening',
        'A05': 'Reti Opening: 1...Nf6',
        'A06': 'Reti Opening: 2.b3',
        'A10': 'English Opening',
        'A15': 'English Opening: Anglo-Indian Defense',
        'A20': 'English Opening: 1...e5',
        'A30': 'English Opening: Symmetrical Variation',
        "A34": "English Opening: Botvinnik System",
        "A36": "English Opening: King's English Variation",
        'A40': 'Queen Pawn Game',
        'A45': 'Indian Defense',
        'A46': 'Indian Defense: 2.Nf3',
        'A50': 'Indian Defense: Normal Variation',
        'B00': 'Uncommon King Pawn Opening',
        'B01': 'Scandinavian Defense',
        'B02': "Alekhine's Defense",
        'B03': "Alekhine's Defense: Four Pawns Attack",
        'B10': 'Caro-Kann Defense',
        'B12': 'Caro-Kann Defense: Advance Variation',
        "B13": 'Caro-Kann Defense: Classical Variation',
        "B14": 'Caro-Kann Defense: Panov-Botvinnik Attack',
        "B15": 'Caro-Kann Defense: Panov-Botvinnik Attack',
        'B20': 'Sicilian Defense',
        'B22': 'Sicilian Defense: Alapin Variation',
        'B23': 'Sicilian Defense: Closed',
        'B30': 'Sicilian Defense: 2...Nc6',
        "B32": 'Sicilian Defense: Hyperaccelerated Dragon',
        'B40': 'Sicilian Defense: French Variation',
        'B50': 'Sicilian Defense: 2...d6',
        'B90': 'Sicilian Defense: Najdorf',
        'C00': 'French Defense',
        "C01": 'French Defense: Exchange Variation',
        'C02': 'French Defense: Advance Variation',
        'C10': 'French Defense: Rubinstein Variation',
        'C20': 'King Pawn Game',
        'C30': "King's Gambit",
        'C40': "King's Knight Opening",
        'C41': 'Philidor Defense',
        'C42': 'Russian Game (Petrov Defense)',
        'C44': 'Scotch Game',
        'C50': 'Italian Game',
        "C54": "Italian Game: Giuoco Piano",
        'C55': 'Italian Game: Two Knights Defense',
        'C60': 'Spanish Opening (Ruy Lopez)',
        'C65': 'Spanish Opening: Berlin Defense',
        'C70': 'Spanish Opening',
        'C78': 'Spanish Opening: Morphy Defense',
        'C80': 'Spanish Opening: Open Variation',
        'D00': 'Queen Pawn Game',
        'D02': 'Queen Pawn Game: 2.Nf3',
        'D10': 'Slav Defense',
        'D20': "Queen's Gambit Accepted",
        'D30': "Queen's Gambit Declined",
        'D50': "Queen's Gambit Declined: 4.Bg5",
        'E00': 'Indian Defense',
        'E10': 'Indian Defense: 3.Nf3',
        'E20': 'Nimzo-Indian Defense',
        'E30': 'Nimzo-Indian Defense: Leningrad Variation',
        'E60': "King's Indian Defense",
        'E70': "King's Indian Defense: Normal Variation",
        'E90': "King's Indian Defense: Orthodox Variation",
    }
    
    return eco_openings.get(eco_code, f"Opening ECO {eco_code}")

def detect_opening(game):
    opening = game.headers.get("Opening", "")
    eco = game.headers.get("ECO", "")
    
    if opening:
        return opening
    elif eco:
        return get_opening_name_from_eco(eco)
    else:
        return "Unknown Opening"