"""Generate Arabic narration audio + beat timings from narration.json.

Outputs (src/audio/):
  <section>.wav     section narration track (44.1 kHz, pydub-processed)
  timings.json      {section: [beat_budget_seconds,...]} for the Manim scenes
  beats.json        {section: [[start_in_section, dur], ...]} for subtitle sync
  <section>.srt     burned-in Arabic subtitles (from the same narration text)
"""
import asyncio
import json
import os
import sys

from pydub import AudioSegment

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from arabic import normalize_arabic, wrap_2_lines  # noqa: E402

OUT = os.path.join(HERE, "audio")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(HERE, "narration.json"), encoding="utf-8") as f:
    CONTENT = json.load(f)
VOICE = CONTENT["voice"]
SECTIONS = CONTENT["sections"]

GAP = 0.30        # silence between beats inside a section
LEAD = 0.25       # lead-in silence before the first beat
TAIL = 0.45       # tail silence after the last beat
SRT_STEP = 0.001  # srt timestamp precision padding

try:
    import edge_tts

    HAVE_EDGE = True
except Exception:
    HAVE_EDGE = False


async def _edge_beat(text: str, path: str) -> bool:
    try:
        await edge_tts.Communicate(text, VOICE).save(path)
        return True
    except Exception as e:
        print(f"  edge-tts failed ({e.__class__.__name__}); trying gTTS")
        return False


def synth_beat(text: str, path: str) -> bool:
    """Synthesize one beat to <path>. Returns success."""
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return True  # cached
    if HAVE_EDGE and asyncio.run(_edge_beat(text, path)):
        return True
    try:
        from gtts import gTTS

        gTTS(text=text, lang="ar").save(path)
        return True
    except Exception as e:
        print(f"  gTTS failed too: {e}")
        return False


def to_segment(path: str) -> AudioSegment:
    """Normalize any TTS output to 44.1kHz mono pydub segment."""
    seg = AudioSegment.from_file(path)
    return seg.set_frame_rate(44100).set_channels(1)


def main() -> None:
    timings, beats = {}, {}
    for sec in SECTIONS:
        key = sec["key"]
        print(f"[{key}] synthesizing {len(sec['beats'])} beats…")
        pieces: list[AudioSegment] = []
        starts: list[list[float]] = []
        t = LEAD
        ok = True
        for i, beat in enumerate(sec["beats"]):
            raw = os.path.join(OUT, f"_{key}_{i:02d}.mp3")
            if not synth_beat(normalize_arabic(beat), raw):
                ok = False
                print(f"  !! beat {i} FAILED — aborting section")
                break
            seg = to_segment(raw)
            starts.append([t, seg.duration_seconds])
            pieces.append(seg)
            t += seg.duration_seconds + GAP
        if not ok:
            sys.exit(1)

        track = pieces[0]
        for p in pieces[1:]:
            track += AudioSegment.silent(duration=int(GAP * 1000)) + p
        track += AudioSegment.silent(duration=int(TAIL * 1000))
        wav = os.path.join(OUT, f"{key}.wav")
        track.export(wav, format="wav")

        budgets = [d + GAP for _, d in starts]
        timings[key] = [round(b, 2) for b in budgets]
        beats[key] = [[round(s, 2), round(d, 2)] for s, d in starts]
        print(f"  -> {wav}  ({track.duration_seconds:.1f}s)")

        # subtitles from the exact narration text
        srt_lines = []
        for i, beat in enumerate(sec["beats"]):
            s, d = beats[key][i]
            e = min(s + d + 0.5, track.duration_seconds)
            lines = wrap_2_lines(beat)
            srt_lines.append(
                f"{i + 1}\n{_ts(s)} --> {_ts(e)}\n" + "\n".join(lines) + "\n"
            )
        with open(os.path.join(OUT, f"{key}.srt"), "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

    with open(os.path.join(OUT, "timings.json"), "w", encoding="utf-8") as f:
        json.dump(timings, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "beats.json"), "w", encoding="utf-8") as f:
        json.dump(beats, f, ensure_ascii=False, indent=1)
    print("timings.json + beats.json written")


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


if __name__ == "__main__":
    main()
