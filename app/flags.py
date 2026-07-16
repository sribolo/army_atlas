"""Country name -> flag emoji, for the mono "🇰🇷 Seoul" labels used across
the ARMY Atlas UI. Keyed by the exact `Concert.country` strings used in
app/data/concerts.json — add an entry here whenever a new country shows up
in seed data.
"""

COUNTRY_FLAGS = {
    "South Korea": "🇰🇷",
    "Japan": "🇯🇵",
    "United States": "🇺🇸",
    "Mexico": "🇲🇽",
    "Belgium": "🇧🇪",
    "United Kingdom": "🇬🇧",
    "Germany": "🇩🇪",
    "France": "🇫🇷",
    "Spain": "🇪🇸",
    "Canada": "🇨🇦",
    "Colombia": "🇨🇴",
    "Peru": "🇵🇪",
    "Chile": "🇨🇱",
    "Argentina": "🇦🇷",
    "Brazil": "🇧🇷",
    "Taiwan": "🇹🇼",
    "Thailand": "🇹🇭",
    "Malaysia": "🇲🇾",
    "Singapore": "🇸🇬",
    "Indonesia": "🇮🇩",
    "Australia": "🇦🇺",
    "Hong Kong": "🇭🇰",
    "Philippines": "🇵🇭",
    "Saudi Arabia": "🇸🇦",
    "Netherlands": "🇳🇱",
    "Macau": "🇲🇴",
}


def country_flag(country: str | None) -> str:
    if not country:
        return "🌍"
    return COUNTRY_FLAGS.get(country, "🌍")
