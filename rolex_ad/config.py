"""Everything you'd want to tweak for the "Time Is Earned" spec ad lives here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIPS_DIR = ROOT / "clips"            # raw Pexels downloads + manifest.json
WORK_DIR = ROOT / "work"              # normalised clips, voiceover, intermediate renders
FINAL_DIR = ROOT / "final"
FONTS_DIR = ROOT / "fonts"
MANIFEST = CLIPS_DIR / "manifest.json"
CREDITS = ROOT / "credits.txt"
MUSIC = ROOT / "music.mp3"            # optional; skipped if missing
OUTPUT = FINAL_DIR / "rolex_spec_ad.mp4"

WIDTH, HEIGHT, FPS = 1920, 1080, 24
CROSSFADE = 0.6                       # seconds, between every pair of shots
KEN_BURNS_END_SCALE = 1.08            # 100% -> 108%
LETTERBOX_RATIO = 2.39

# Each shot: search terms are tried in order until one returns a usable clip.
# The first entry is the brief's term; the rest are close synonyms.
# ken_burns: "auto" applies the slow zoom only when the clip looks static.
SHOTS = [
    {"id": 1, "duration": 4, "ken_burns": "auto",
     "queries": ["watch macro gears", "watch movement gears", "clock mechanism gears", "watch mechanism"]},
    {"id": 2, "duration": 5, "ken_burns": "auto",
     "queries": ["mountain climber summit snow", "mountaineer summit", "climber snowy mountain peak", "hiker summit snow"]},
    {"id": 3, "duration": 4, "ken_burns": "auto",
     "queries": ["watchmaker hands workshop", "watchmaker", "watch repair", "craftsman hands workshop"]},
    {"id": 4, "duration": 5, "ken_burns": "auto",
     "queries": ["deep sea diver underwater", "scuba diver underwater", "diver deep ocean", "underwater diver"]},
    {"id": 5, "duration": 4, "ken_burns": "auto",
     "queries": ["luxury wristwatch close up", "luxury watch close up", "wristwatch macro", "watch on wrist close up"]},
    {"id": 6, "duration": 4, "ken_burns": "auto",
     "queries": ["ocean waves slow motion", "ocean waves", "sea waves crashing slow motion", "waves at sunset"]},
    {"id": 7, "duration": 4, "ken_burns": "auto",
     "queries": ["man adjusting watch suit", "businessman checking watch", "man in suit looking at watch", "man wearing wristwatch suit"]},
    {"id": 8, "duration": 5, "ken_burns": "auto",
     "queries": ["gold watch rotating black background", "gold watch black background", "luxury watch rotating", "watch rotating dark background"]},
]
END_CARD_DURATION = 5

# Voiceover: line starts VO_OFFSET seconds into its shot.
VOICE = "en-GB-RyanNeural"
VOICE_RATE = "-10%"
VO_OFFSET = 0.5
VOICEOVER = [
    {"shot": 2, "text": "Some moments can't be rushed."},
    {"shot": 4, "text": "They're waited for. Worked for. Earned."},
    {"shot": 6, "text": "And when they arrive…"},
    {"shot": 8, "text": "…you'll want to remember exactly when."},
]

# Music: shot 1 opens on silence, so the bed comes in with shot 2.
MUSIC_START_SHOT = 2
MUSIC_GAIN_DB = -18
MUSIC_FADE_IN = 2.0
MUSIC_FADE_OUT = 3.0

FONT_REGULAR = FONTS_DIR / "CormorantGaramond-Regular.ttf"
FONT_LIGHT = FONTS_DIR / "CormorantGaramond-Light.ttf"
TEXT_FADE = 1.0
HERO_TITLE = "ROLEX"
END_TITLE = "A crown for every achievement."
END_DISCLAIMER = "Spec advertisement — not affiliated with or endorsed by Rolex SA."


def shot_starts():
    """Start time of each shot (1..8) and of the end card, in seconds.

    Every clip runs CROSSFADE seconds past its nominal duration and the next one
    fades in over that tail, so the cut lengths above add up to the total runtime.
    """
    starts, t = {}, 0.0
    for shot in SHOTS:
        starts[shot["id"]] = t
        t += shot["duration"]
    starts["end"] = t
    return starts


def total_duration():
    return sum(s["duration"] for s in SHOTS) + END_CARD_DURATION
