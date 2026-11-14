"""Scene data for the "Colonial PR Team, 1829-1858" reel (Kanav Agarwal).

Each scene is one 8-second clip. `prompt` goes to the video model (it speaks the
dialogue itself); `lines` are the subtitles; `context` is the fact-check box.
"""

CHARACTERS = (
    "THE OFFICIAL: a portly British East India Company official, about 50, grey "
    "sideburns, red coat with gold buttons, white cravat, pompous but likeable. "
    "THE STUDENT: a young Indian university student, about 18, short black hair, "
    "plain dark grey hoodie, deadpan delivery."
)

STYLE = (
    "Vertical 9:16 framing. Comedic mockumentary tone. Clear, natural voices with "
    "British and Indian English accents. No subtitles, no captions, no on-screen "
    "text, no logos, no watermarks."
)

SCENES = [
    {
        "id": "scene1",
        "title": "Press conference, Calcutta, 1829",
        "prompt": (
            "Cinematic mockumentary, 1829 colonial Calcutta. On the steps of a white "
            "colonnaded building, THE OFFICIAL stands at a wooden podium covered in "
            "modern press microphones. A small crowd of Indian and British reporters "
            "in 1820s clothing hold notepads. Bright afternoon daylight, warm tones. "
            "The official says proudly: \"We have abolished sati. Because we... are "
            "civilised.\" An Indian reporter in a dhoti and shawl raises his pen and "
            "asks: \"Wasn't that Rammohun Roy's scriptural argument?\" The official "
            "freezes, gives a tight awkward smile and says: \"...Next question.\""
        ),
        "lines": [
            ("OFFICIAL", "We have abolished sati. Because we… are civilised."),
            ("REPORTER", "Wasn’t that Rammohun Roy’s scriptural argument?"),
            ("OFFICIAL", "…Next question."),
        ],
        "context": {
            "heading": "CONTEXT",
            "body": "Sati stayed legal for 60+ years. Police just asked the widow, “Do you consent?”",
            "author": "Sarkar",
        },
    },
    {
        "id": "scene2",
        "title": "University seminar, today",
        "prompt": (
            "Modern Indian university seminar room, wooden desks, natural daylight "
            "from windows, realistic. A projector screen shows a blank slide. A "
            "professor in a kurta and glasses stands beside it. THE STUDENT sits in "
            "the second row and says deadpan: \"So the civilising mission was... a "
            "sixty-year consent form?\" The classmates laugh warmly. The professor "
            "raises one finger dramatically and says: \"Plot twist. That form "
            "changed history.\""
        ),
        "lines": [
            ("STUDENT", "So the civilising mission was… a sixty-year consent form?"),
            ("PROFESSOR", "Plot twist — that form changed history."),
        ],
        "context": {
            "heading": "SARKAR’S TWIST",
            "body": "Asking for her “consent” made her voice count in law — “something like rights.”",
            "author": "Sarkar",
        },
    },
    {
        "id": "scene3",
        "title": "Live news broadcast, 1857",
        "prompt": (
            "Comedic contrast shot, 1857 North India, golden hour, cinematic. On a "
            "dusty village road THE OFFICIAL holds a microphone and speaks calmly to "
            "camera like a TV news reporter: \"Just a small sepoy mutiny. Totally "
            "under control.\" Behind him, unnoticed by him, a large crowd walks past "
            "determinedly: Indian farmers carrying ploughs and sickles, tribal men "
            "carrying bows, women in saris, and landholders on horseback. Far from "
            "the women, one man tosses a bundle of official papers onto a small "
            "bonfire. The official does not notice. No violence, no weapons pointed "
            "at anyone."
        ),
        "lines": [
            ("OFFICIAL", "Just a small sepoy mutiny. Totally under control."),
        ],
        "context": {
            "heading": "CONTEXT",
            "body": "“Mutiny” was the colonial label. Peasants, adivasis and courtesans rebelled too. The sepoy was a “peasant in uniform.”",
            "author": "Pati",
        },
        "lower_third": "BREAKING: SMALL SEPOY MUTINY",
    },
    {
        "id": "scene4",
        "title": "Smartboard timeline, today",
        "prompt": (
            "Modern classroom, bright clean lighting, realistic. THE STUDENT stands "
            "at a large interactive smartboard showing a plain horizontal timeline "
            "and drags a glowing highlight bar across it, saying: \"And it didn't "
            "start in 1857... or end in 1858.\" A female classmate at a desk leans "
            "back with an impressed smirk and says: \"So the High Noon had a really "
            "long afternoon.\""
        ),
        "lines": [
            ("STUDENT", "And it didn’t start in 1857… or end in 1858."),
            ("CLASSMATE", "So the ‘High Noon’ had a really long afternoon."),
        ],
        "context": {
            "heading": "PATI",
            "body": "Resistance ran from the 1830s to the 1870s, across peasant and tribal India — not just the North.",
            "author": "Pati",
        },
        "timeline": ["1830s", "1857", "1870s"],
    },
    {
        "id": "scene5",
        "title": "Colonial gentlemen's club, 1858",
        "prompt": (
            "1858 colonial British gentlemen's club interior, dark wood panels, "
            "leather armchairs, teacups and cigars, warm lamplight, cinematic. Three "
            "British officials in Victorian dress, including THE OFFICIAL in his red "
            "coat, stand in a circle. A framed notice hangs on the wall behind them. "
            "THE OFFICIAL says, exasperated: \"Who told us to tinker with Indian "
            "law?!\" Then all three point accusingly at each other in a circle with "
            "comedic exasperated expressions."
        ),
        "lines": [
            ("OFFICIAL", "Who told us to tinker with Indian law?!"),
        ],
        "context": {
            "heading": "SEN",
            "body": "After 1857, colonial writers blamed these reforms — though “saving Indian women” was the empire’s excuse for ruling.",
            "author": "Sen",
        },
        "notice": ["1829: Sati banned.", "1856: Widow remarriage allowed."],
        "end_card": ("Civilisation? It’s complicated.", "Kanav Agarwal"),
    },
]


def full_prompt(scene):
    return f"{CHARACTERS} {scene['prompt']} {STYLE}"
