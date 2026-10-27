"""Everything you'd want to tweak for the "Time Is Earned" spec ad lives here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIPS_DIR = ROOT / "clips"            # raw Pexels downloads + manifest.json
SFX_DIR = ROOT / "sfx"                # Mixkit sound effects (downloaded on first render)
WORK_DIR = ROOT / "work"              # normalised clips, voiceover, intermediate renders
FINAL_DIR = ROOT / "final"
FONTS_DIR = ROOT / "fonts"
MANIFEST = CLIPS_DIR / "manifest.json"
CREDITS = ROOT / "credits.txt"
OUTPUT = FINAL_DIR / "rolex_spec_ad.mp4"
TTS_PYTHON = ROOT / ".venv-tts" / "bin" / "python"   # Python 3.12 env with Kokoro (see README)

WIDTH, HEIGHT, FPS = 1920, 1080, 24
CROSSFADE = 0.4                       # seconds, between every pair of shots
KEN_BURNS_END_SCALE = 1.08            # 100% -> 108%
LETTERBOX_RATIO = 2.39

# Each shot: search terms are tried in order until one returns a usable clip.
# The first entry is the brief's term; the rest are close synonyms.
# ken_burns: "auto" applies the slow zoom only when the clip looks static.
# sfx: ambience laid under the shot -> (Mixkit id, gain dB, extra ffmpeg filter or "").
SHOTS = [
    {"id": 1, "duration": 1.5, "ken_burns": "auto",
     "queries": ["watch macro gears", "watch movement gears", "watch mechanism"],
     "sfx": [(1059, -14, "")]},                                     # tick tock, close up
    {"id": 2, "duration": 2.0, "ken_burns": "auto",
     "queries": ["mountain climber summit snow", "mountaineer summit", "climber snowy mountain"],
     "sfx": [(1267, -10, "")]},                                     # wind at the top of the mountain
    {"id": 3, "duration": 2.0, "ken_burns": "auto",
     "queries": ["deep sea diver underwater", "scuba diver underwater", "underwater diver"],
     "sfx": [(1194, -6, "lowpass=f=380,lowpass=f=380"),             # muffled sea = underwater rumble
             (1321, -12, "")]},                                     # deep water bubbles
    {"id": 4, "duration": 2.0, "ken_burns": "auto",
     "queries": ["surfer riding big wave", "surfer big wave", "surfing"],
     "sfx": [(1194, -10, "")]},                                     # rough sea
    {"id": 5, "duration": 1.5, "ken_burns": "auto",
     "queries": ["ocean waves slow motion", "ocean waves", "waves at sunset"],
     "sfx": [(1206, -8, "")]},                                      # breaking waves
    {"id": 6, "duration": 3.0, "ken_burns": "auto",
     "queries": ["gold watch rotating black background", "gold watch black background", "luxury watch rotating"],
     "sfx": [(1177, -16, ""), (1059, -20, "")]},                    # low cinematic hum + soft ticking
]
END_CARD_DURATION = 3
END_CARD_SFX = [(1059, -22, "")]                                    # the tick carries into the card
HERO_WHOOSH = (1471, -14)                                           # swoosh into the hero shot
SFX_FADE = 0.35                                                     # each ambience fades in/out over this

# Voiceover: each line starts `offset` seconds into its shot. `say` is what the voice reads,
# `text` is the subtitle.
TTS_ENGINE = "kokoro"                 # "kokoro" (natural, local) or "edge" (edge-tts)
KOKORO_VOICE = "bm_george"            # British male; try bm_fable, am_michael, af_heart
KOKORO_SPEED = 0.9
EDGE_VOICE, EDGE_RATE = "en-GB-RyanNeural", "-10%"
VOICEOVER = [
    {"shot": 1, "offset": 0.3, "say": "Some moments... can't be rushed.",
     "text": "Some moments can't be rushed."},
    {"shot": 3, "offset": 0.4, "say": "They're waited for. Worked for. Earned.",
     "text": "They're waited for. Worked for. Earned."},
    {"shot": 6, "offset": 0.4, "say": "You'll want to remember... exactly when.",
     "text": "You'll want to remember exactly when."},
]

FONT_REGULAR = FONTS_DIR / "CormorantGaramond-Regular.ttf"
FONT_LIGHT = FONTS_DIR / "CormorantGaramond-Light.ttf"
TEXT_FADE = 0.7
SUBTITLE_SIZE = 46
HERO_TITLE = "ROLEX"
END_TITLE = "A crown for every achievement."
END_DISCLAIMER = "Spec advertisement — not affiliated with or endorsed by Rolex SA."


def shot_starts():
    """Start time of each shot and of the end card, in seconds.

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
