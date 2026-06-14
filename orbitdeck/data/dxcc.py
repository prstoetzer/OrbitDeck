"""
dxcc.py - reference points for DXCC entities, keyed by common prefix.

A satellite footprint "works" an entity when the entity's reference point lies
inside the footprint cap. This is the point-based half of CardSat's hybrid model
(big countries would use polygons; the long tail uses a single reference point).
Bundled here is a practical set of the commonly worked / geographically spread
entities so the screen is useful for satellite DX without shipping cty.dat.

Each value is (entity_name, lat, lon). Multiple prefixes can map to the same
entity where that aids recognition; large countries carry several sample points
under suffixed keys so partial footprint coverage is caught.
"""

DXCC = {
    # North America
    "K": ("United States", 39.0, -98.0),
    "K-W": ("United States (W)", 39.5, -119.0),
    "K-NE": ("United States (NE)", 42.0, -74.0),
    "K-SE": ("United States (SE)", 31.0, -84.0),
    "VE": ("Canada", 56.0, -106.0),
    "VE-W": ("Canada (W)", 54.0, -123.0),
    "VE-E": ("Canada (E)", 46.0, -71.0),
    "XE": ("Mexico", 23.6, -102.5),
    "CM": ("Cuba", 21.5, -79.5),
    "TI": ("Costa Rica", 9.7, -84.0),
    "TG": ("Guatemala", 15.5, -90.3),
    "HP": ("Panama", 8.5, -80.0),
    "KP4": ("Puerto Rico", 18.2, -66.4),
    "FM": ("Martinique", 14.6, -61.0),
    "8P": ("Barbados", 13.1, -59.6),
    # South America
    "PY": ("Brazil", -10.0, -52.0),
    "PY-S": ("Brazil (S)", -25.0, -49.0),
    "PY-NE": ("Brazil (NE)", -8.0, -35.0),
    "LU": ("Argentina", -34.0, -64.0),
    "CE": ("Chile", -33.5, -70.7),
    "HK": ("Colombia", 4.6, -74.1),
    "OA": ("Peru", -12.0, -77.0),
    "YV": ("Venezuela", 8.0, -66.0),
    "CX": ("Uruguay", -34.9, -56.2),
    "CP": ("Bolivia", -16.5, -68.1),
    "HC": ("Ecuador", -0.2, -78.5),
    # Europe
    "G": ("England", 52.5, -1.5),
    "GM": ("Scotland", 56.8, -4.2),
    "GW": ("Wales", 52.3, -3.8),
    "GI": ("Northern Ireland", 54.6, -6.5),
    "EI": ("Ireland", 53.3, -8.0),
    "F": ("France", 47.0, 2.5),
    "DL": ("Germany", 51.0, 10.0),
    "PA": ("Netherlands", 52.2, 5.3),
    "ON": ("Belgium", 50.6, 4.6),
    "EA": ("Spain", 40.2, -3.7),
    "CT": ("Portugal", 39.6, -8.0),
    "I": ("Italy", 42.8, 12.8),
    "HB": ("Switzerland", 46.8, 8.2),
    "OE": ("Austria", 47.6, 14.1),
    "SP": ("Poland", 52.1, 19.3),
    "OK": ("Czech Republic", 49.8, 15.5),
    "OM": ("Slovakia", 48.7, 19.5),
    "HA": ("Hungary", 47.2, 19.4),
    "YO": ("Romania", 45.9, 25.0),
    "LZ": ("Bulgaria", 42.7, 25.3),
    "SM": ("Sweden", 62.0, 15.0),
    "LA": ("Norway", 62.0, 9.0),
    "OH": ("Finland", 63.0, 26.0),
    "OZ": ("Denmark", 56.0, 9.5),
    "ES": ("Estonia", 58.6, 25.0),
    "YL": ("Latvia", 56.9, 24.6),
    "LY": ("Lithuania", 55.2, 23.9),
    "UR": ("Ukraine", 49.0, 31.0),
    "EW": ("Belarus", 53.7, 27.9),
    "SV": ("Greece", 39.0, 22.0),
    "TA": ("Turkey", 39.0, 35.0),
    "9A": ("Croatia", 45.1, 15.5),
    "S5": ("Slovenia", 46.1, 14.8),
    "YU": ("Serbia", 44.0, 20.9),
    "Z3": ("North Macedonia", 41.6, 21.7),
    "LX": ("Luxembourg", 49.8, 6.1),
    "EA6": ("Balearic Is", 39.6, 2.9),
    "IS": ("Sardinia", 40.0, 9.0),
    # Russia (spread)
    "UA": ("European Russia", 55.8, 37.6),
    "UA9": ("Asiatic Russia (W)", 56.0, 68.0),
    "UA0": ("Asiatic Russia (E)", 62.0, 130.0),
    # Africa
    "CN": ("Morocco", 32.0, -6.5),
    "SU": ("Egypt", 27.0, 30.0),
    "ZS": ("South Africa", -29.0, 24.0),
    "5Z": ("Kenya", 0.5, 37.5),
    "5N": ("Nigeria", 9.5, 8.0),
    "EL": ("Liberia", 6.4, -9.4),
    "ET": ("Ethiopia", 9.1, 40.0),
    "CN8": ("Morocco (N)", 34.0, -5.0),
    "7X": ("Algeria", 28.0, 3.0),
    "3V": ("Tunisia", 34.0, 9.5),
    "5R": ("Madagascar", -19.0, 46.7),
    "9J": ("Zambia", -14.0, 27.8),
    "Z2": ("Zimbabwe", -19.0, 29.8),
    "V5": ("Namibia", -22.0, 17.0),
    # Asia
    "JA": ("Japan", 36.0, 138.0),
    "JA8": ("Japan (Hokkaido)", 43.3, 142.5),
    "HL": ("South Korea", 36.5, 127.8),
    "BY": ("China", 35.0, 103.0),
    "BY-E": ("China (E)", 31.2, 121.5),
    "BY-S": ("China (S)", 23.1, 113.3),
    "VU": ("India", 21.0, 78.0),
    "VU-S": ("India (S)", 13.0, 80.2),
    "9V": ("Singapore", 1.35, 103.8),
    "9M2": ("West Malaysia", 3.8, 102.3),
    "YB": ("Indonesia", -6.2, 106.8),
    "HS": ("Thailand", 15.0, 101.0),
    "XV": ("Vietnam", 16.0, 107.8),
    "DU": ("Philippines", 13.0, 122.0),
    "4X": ("Israel", 31.5, 34.9),
    "A4": ("Oman", 21.0, 57.0),
    "A6": ("United Arab Emirates", 24.0, 54.0),
    "EP": ("Iran", 32.0, 53.0),
    "YK": ("Syria", 35.0, 38.0),
    "EX": ("Kyrgyzstan", 41.5, 75.0),
    "UN": ("Kazakhstan", 48.0, 67.0),
    "9N": ("Nepal", 28.2, 84.0),
    "S2": ("Bangladesh", 23.7, 90.4),
    "4S": ("Sri Lanka", 7.5, 80.7),
    # Oceania
    "VK": ("Australia", -25.0, 134.0),
    "VK-E": ("Australia (E)", -33.9, 151.2),
    "VK-W": ("Australia (W)", -31.9, 115.9),
    "VK6": ("Australia (W coast)", -32.0, 116.0),
    "ZL": ("New Zealand", -41.0, 174.0),
    "ZL-S": ("New Zealand (S)", -45.0, 170.5),
    "KH6": ("Hawaii", 20.8, -156.3),
    "FK": ("New Caledonia", -21.5, 165.5),
    "3D2": ("Fiji", -17.8, 178.0),
    "KH2": ("Guam", 13.4, 144.8),
    "P2": ("Papua New Guinea", -6.3, 147.0),
    # Atlantic / misc islands
    "TF": ("Iceland", 64.1, -21.9),
    "OX": ("Greenland", 64.2, -51.7),
    "CU": ("Azores", 38.5, -28.0),
    "EA8": ("Canary Is", 28.3, -16.5),
    "CT3": ("Madeira", 32.7, -16.9),
    "ZD7": ("St Helena", -15.9, -5.7),
}


def workable_dxcc(in_footprint):
    """Return a sorted list of (prefix, name) whose reference point is in the
    footprint. `in_footprint(lat, lon) -> bool`."""
    out = []
    seen = set()
    for prefix, (name, lat, lon) in DXCC.items():
        if in_footprint(lat, lon):
            # collapse the per-region split keys (e.g. K-W) to their base label
            base = prefix.split("-")[0]
            key = (base, name)
            if key not in seen:
                seen.add(key)
                out.append((prefix, name))
    return sorted(out, key=lambda x: x[0])
