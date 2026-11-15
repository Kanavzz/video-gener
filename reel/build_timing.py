"""Write build/scenes.json: overlay data plus subtitle timings for each scene.

Subtitle timings come from build/cues/<id>.json when present (written by
transcribe.py from the generated clip's audio); otherwise lines are spread
evenly across the clip so stills can be previewed before any clip exists.
"""
import json
from pathlib import Path

from scenes import SCENES

HERE = Path(__file__).parent
B = HERE / "build"
DURATION = 8.0
CHIPS = {"scene1": "Calcutta · 1829", "scene2": "Seminar · Today", "scene3": "North India · 1857",
         "scene4": "Classroom · Today", "scene5": "The Club · 1858"}


def even_cues(lines, start=0.4, end=DURATION - 0.3):
    step = (end - start) / len(lines)
    return [{"who": w, "text": t, "start": start + i * step, "end": start + (i + 1) * step - 0.05}
            for i, (w, t) in enumerate(lines)]


durs_file = B / "durations.json"
DURS = json.loads(durs_file.read_text()) if durs_file.exists() else {}

out = []
for s in SCENES:
    cue_file = B / "cues" / f"{s['id']}.json"
    cues = json.loads(cue_file.read_text()) if cue_file.exists() else even_cues(s["lines"])
    meta = DURS.get(s["id"], {})
    out.append({"id": s["id"], "duration": meta.get("duration", DURATION), "chip": CHIPS[s["id"]], "context": s["context"], "cues": cues,
                **{k: s[k] for k in ("lower_third", "end_card", "context_at") if k in s},
                **({"context_at": meta["context_at"]} if "context_at" in meta else {})})
B.mkdir(exist_ok=True)
(B / "scenes.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(f"wrote {B / 'scenes.json'}")
