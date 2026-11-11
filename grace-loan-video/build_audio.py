"""Synthesize every spoken line and lay out the scene timeline.

Writes into the build directory:
  narrator.wav, kamla.wav   voice stems, already placed at their final times
  timeline.json             scene boundaries, subtitle cues, voicemail envelope
  voiceover_lines.txt       every spoken line by scene and speaker (for re-recording)

Voices come from Kokoro (local neural TTS, no API key): a Hindi male voice reading
English for the narrator, a Hindi female voice for Smt. Kamla Singh. If you record
real voices later, drop them in as narrator.wav / kamla.wav with the same timings.
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "build"
MODELS = HERE / "models"
RATE = 48000
NARRATOR_VOICE, NARRATOR_SPEED = "hm_omega", 1.08
KAMLA_VOICE, KAMLA_SPEED = "hf_beta", 0.8

# Scenes in order. Each "line" is one sentence: (caption, spoken text or None to
# speak the caption). "para" groups sentences that are read as one paragraph.
# lead = seconds before the first line, gap = pause between paragraphs,
# tail = seconds after the last line, min = shortest the scene may be.
SCENES = [
    dict(id="voicemail", title="Scene 1 — Cold open: the voicemail", min=22.0, lead=6.2, tail=3.2, gap=1.15,
         speaker="KAMLA", paras=[
             [("You killed my Rahul…", "आपने मेरे राहुल को मार दिया…")],
             [("He was coughing blood, and you sent him home without treating him.",
               "वो खून की खांसी कर रहा था, और आपने उसे बिना इलाज के घर भेज दिया।")],
             [("Two days… only two days.", "दो दिन… सिर्फ़ दो दिन।")],
             [("The Singh family will never forgive you.", "सिंह परिवार आपको कभी माफ़ नहीं करेगा।")],
         ],
         roman=["Aapne mere Rahul ko maar diya…",
                "Woh khoon ki khaansi kar raha tha, aur aapne usse bina ilaaj ke ghar bhej diya.",
                "Do din… sirf do din.",
                "Singh parivaar aapko kabhi maaf nahi karega."]),
    dict(id="title", title="Scene 2 — Title card", min=8.0, paras=[]),
    dict(id="kabir", title="Scene 3 — Kabir Rao", min=25.0, lead=1.4, tail=1.6, gap=0.55, paras=[
        [("Kabir Rao believes hospitals exist for the people who cannot pay.", None),
         ("That is why, five months ago, he chose Grace Loan Memorial.", None)],
        [("His days are filing, data entry and errands for whichever department needs a spare pair of hands.", None)],
        [("On Monday, the thirtieth of November, someone gives him one more dull job:", None),
         ("clear out a month of old voicemails.", None)],
        [("He has no idea it will put him at the centre of the biggest secret this hospital has ever kept.", None)],
    ]),
    dict(id="hospital", title="Scene 4 — The hospital", min=25.0, lead=1.2, tail=2.2, gap=0.55, paras=[
        [("From the outside, Grace Loan is everything Kabir hoped for.", None),
         ("A two-hundred-and-ten-bed hospital on Rajpur Road.", "A two hundred and ten bed hospital, on Rajpur Road."),
         ("A Director who says no patient is ever turned away for want of money.", None)],
        [("It is one of the few private hospitals on the government's State Pro Bono Care Scheme,",
          "It is one of the few private hospitals on the government's State Pro Bono Care Scheme,"),
         ("which pays a fixed amount for every poor patient it treats.", None)],
        [("Its website boasts of hundreds of free treatments.", None),
         ("On paper, it is a miracle.", None)],
    ]),
    dict(id="rahul", title="Scene 5 — Rahul Singh", min=28.0, lead=1.8, tail=3.0, gap=0.75, paras=[
        [("Rahul Singh was twelve.", None),
         ("He lived with his grandmother, who brought him to Grace Loan because she had heard it treated the poor for free.", None)],
        [("He had been coughing for weeks.", None), ("He was losing weight.", None),
         ("He had a fever every evening.", None)],
        [("In November he came to the hospital three times.", None), ("Always on a Monday.", None)],
        [("Two days after his last visit, Rahul died at home.", None)],
    ]),
    dict(id="question", title="Scene 6 — The question", min=18.0, lead=1.2, tail=2.6, gap=0.6, paras=[
        [("Kabir plays the message again.", None), ("And again.", None)],
        [("A hospital famous for free care, and a boy sent home to die.", None)],
        [("Somebody made that decision.", None), ("Kabir cannot let it go.", None)],
    ]),
    dict(id="people", title="Scene 7 — The people of Grace Loan", min=26.0, lead=3.0, tail=3.6, gap=0.9, paras=[
        [("Around him, thirty people keep this hospital running.", None),
         ("Doctors. Nurses. Finance. Billing. Operations.", "Doctors. Nurses. Finance. Billing. Operations.")],
        [("Every one of them had access.", None), ("Every one of them had reasons.", None)],
        [("Not all of them are innocent.", None)],
    ]),
    dict(id="clock", title="Scene 8 — The clock", min=14.0, lead=1.8, tail=2.4, gap=0.6, paras=[
        [("Whoever let Rahul die is about to walk away for good.", None)],
        [("Kabir doesn't have days.", None), ("He has hours.", None)],
    ]),
    dict(id="end", title="Scene 9 — Call to action / end card", min=15.0, paras=[]),
]
SENTENCE_GAP = 0.32
TARGET_MAX = 192.0  # keep Part A inside 3:15


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def trim(x, thresh=0.004):
    idx = np.flatnonzero(np.abs(x) > thresh)
    if not len(idx):
        return x
    a, b = max(0, idx[0] - int(0.02 * RATE)), min(len(x), idx[-1] + int(0.06 * RATE))
    return x[a:b]


def synthesize(tmp):
    import soundfile
    from kokoro_onnx import Kokoro
    kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
    clips = {}
    for si, sc in enumerate(SCENES):
        kamla = sc.get("speaker") == "KAMLA"
        for pi, para in enumerate(sc["paras"]):
            for li, (caption, spoken) in enumerate(para):
                key = f"s{si + 1}p{pi + 1}l{li + 1}"
                raw, out = tmp / f"{key}.raw.wav", tmp / f"{key}.wav"
                if kamla:
                    s, r = kokoro.create(spoken, voice=KAMLA_VOICE, speed=KAMLA_SPEED, lang="hi")
                    soundfile.write(str(raw), s, r, subtype="PCM_16")
                    # Older, shakier, crying: lower pitch, tremble, unsteady loudness.
                    af = (f"rubberband=pitch=0.93:formant=preserved,vibrato=f=6.2:d=0.22,"
                          f"tremolo=f=4.6:d=0.22,aresample={RATE}")
                else:
                    s, r = kokoro.create(spoken or caption, voice=NARRATOR_VOICE, speed=NARRATOR_SPEED, lang="en-gb")
                    soundfile.write(str(raw), s, r, subtype="PCM_16")
                    af = f"rubberband=pitch=0.96:formant=preserved,aresample={RATE}"
                run("ffmpeg", "-y", "-i", str(raw), "-af", af, "-ac", "1", "-sample_fmt", "s16", str(out))
                clips[key] = trim(read_wav(out))
    return clips


def layout(clips, squeeze=1.0):
    scenes, cues, t = [], [], 0.0
    for si, sc in enumerate(SCENES):
        start = t
        if sc["paras"]:
            t += sc["lead"]
            for pi, para in enumerate(sc["paras"]):
                if pi:
                    t += sc["gap"] * squeeze
                for li, (caption, _) in enumerate(para):
                    if li:
                        t += SENTENCE_GAP * squeeze
                    key = f"s{si + 1}p{pi + 1}l{li + 1}"
                    d = len(clips[key]) / RATE
                    cues.append(dict(id=key, scene=sc["id"], speaker=sc.get("speaker", "NARRATOR"),
                                     para=pi, start=round(t, 3), end=round(t + d, 3), text=caption))
                    t += d
            t += sc["tail"]
        t = max(t, start + sc["min"])
        scenes.append(dict(id=sc["id"], start=round(start, 3), end=round(t, 3)))
    return scenes, cues, t


def envelope(x, fps=30):
    hop = RATE // fps
    n = len(x) // hop
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    return [round(float(v), 3) for v in np.clip(rms / (rms.max() + 1e-9), 0, 1)]


def voiceover_text(scenes):
    lines = ["THE GRACE LOAN MEMORIAL CASE — Part A (opening) — voiceover lines",
             "Timings are where each line sits in the current cut (mm:ss.s). Record each line",
             "as its own take; Smt. Kamla Singh is in Hindi (Devanagari + romanised + English).", ""]
    for sc, placed in zip(SCENES, scenes):
        lines.append(f"== {sc['title']}  [{fmt(placed['start'])} – {fmt(placed['end'])}]")
        if not sc["paras"]:
            lines += ["   (no spoken lines — music / SFX and on-screen text only)", ""]
            continue
        speaker = "SMT. KAMLA SINGH (V.O., Hindi, crying)" if sc.get("speaker") == "KAMLA" else "NARRATOR (V.O.)"
        lines.append(f"   {speaker}")
        for pi, para in enumerate(sc["paras"]):
            for li, (caption, spoken) in enumerate(para):
                cue = next(c for c in CUES if c["id"] == f"s{SCENES.index(sc) + 1}p{pi + 1}l{li + 1}")
                if sc.get("speaker") == "KAMLA":
                    lines.append(f"   [{fmt(cue['start'])}] {spoken}")
                    lines.append(f"            {sc['roman'][pi]}")
                    lines.append(f"            EN: {caption}")
                else:
                    lines.append(f"   [{fmt(cue['start'])}] {caption}")
        lines.append("")
    return "\n".join(lines)


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


CUES = []


def main():
    global CUES
    tmp = OUT / "lines"
    tmp.mkdir(parents=True, exist_ok=True)
    clips = synthesize(tmp)

    squeeze = 1.0
    scenes, cues, total = layout(clips)
    while total > TARGET_MAX and squeeze > 0.7:
        squeeze -= 0.05
        scenes, cues, total = layout(clips, squeeze)
    CUES = cues

    n = int(total * RATE) + RATE
    stems = {"NARRATOR": np.zeros(n, np.float32), "KAMLA": np.zeros(n, np.float32)}
    for c in cues:
        x = clips[c["id"]]
        o = int(c["start"] * RATE)
        stems[c["speaker"]][o:o + len(x)] += x
    write_wav(OUT / "narrator.wav", stems["NARRATOR"])
    write_wav(OUT / "kamla.wav", stems["KAMLA"])

    timeline = dict(total=round(total, 3), scenes=scenes, cues=cues, kamla_env=envelope(stems["KAMLA"]))
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1, ensure_ascii=False))
    (OUT / "voiceover_lines.txt").write_text(voiceover_text(scenes), encoding="utf-8")

    print(f"total {total:.2f}s (squeeze {squeeze:.2f})")
    for s in scenes:
        print(f"  {s['start']:7.2f}-{s['end']:7.2f}  {s['id']}")


if __name__ == "__main__":
    main()
