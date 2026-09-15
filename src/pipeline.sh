#!/bin/bash
# 4K60 AV1 pipeline: Manim per-frame PNGs -> libaom-av1 CQ -> concat + chapters
# Usage: src/pipeline.sh render|encode|mux|concat|all [section ...]
set -euo pipefail
cd "$(dirname "$0")/.."
MANIM=~/.venvs/manim/bin/manim
PY=~/.venvs/manim/bin/python
A=src/audio
OUT=out
FR=media/images/manim_scenes
mkdir -p "$OUT"

declare -A SCENE=(
  [intro]=IntroSection [variables]=VariablesSection [constants]=ConstantsSection
  [functions]=FunctionsSection [lambdas]=LambdasSection [outro]=OutroSection
)
ALL="intro variables constants functions lambdas outro"
AV1=(-c:v libaom-av1 -b:v 0 -crf 32 -cpu-used 8 -row-mt 1 -tile-columns 4 -g 240 -pix_fmt yuv420p)

render() {
  local sec=$1 scene=${SCENE[$1]}
  rm -rf "$FR"
  echo "== render $sec ($scene) =="
  $MANIM -qh --fps 60 --resolution 3840,2160 --format=png -g --disable_caching \
      src/manim_scenes.py "$scene" 2>&1 | tail -1
  echo "frames: $(ls "$FR" | wc -l)"
}

encode() {
  local sec=$1 scene=${SCENE[$1]}
  echo "== encode $sec =="
  ffmpeg -y -hide_banner -loglevel error -framerate 60 \
    -i "$FR/${scene}%04d.png" "${AV1[@]}" -an "$OUT/${sec}_v.mp4"
}

mux() {
  local sec=$1
  echo "== mux $sec =="
  ffmpeg -y -hide_banner -loglevel error -i "$OUT/${sec}_v.mp4" -i "$A/${sec}.wav" \
    -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart \
    "$OUT/${sec}.mp4"
  rm -f "$OUT/${sec}_v.mp4"
  rm -rf "$FR"
  ffprobe -v error -show_entries format=duration,size -of csv=p=0 "$OUT/${sec}.mp4"
}

concat() {
  : > "$OUT/list.txt"
  for sec in $ALL; do echo "file '${sec}.mp4'" >> "$OUT/list.txt"; done
  "$PY" - <<'PYEOF'
import json, subprocess
secs = ["intro", "variables", "constants", "functions", "lambdas", "outro"]
c = json.load(open("src/narration.json", encoding="utf-8"))
titles = {s["key"]: s["chapter"] for s in c["sections"]}
lines = [";FFMETADATA1", "title=" + c["video_title"]]
start = 0.0
for k in secs:
    d = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", f"out/{k}.mp4"]).strip())
    lines += ["[CHAPTER]", "TIMEBASE=1/1000",
              f"START={int(start*1000)}", f"END={int((start+d)*1000)}",
              f"title={titles[k]}"]
    start += d
open("out/chapters.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
PYEOF
  ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$OUT/list.txt" \
    -i "$OUT/chapters.txt" -map 0 -map_metadata 1 -c copy -movflags +faststart \
    "$OUT/manim_video_4k60_av1.mp4"
  ffprobe -v error -show_entries format=duration,size -of csv=p=0 "$OUT/manim_video_4k60_av1.mp4"
}

step() { render "$1"; encode "$1"; mux "$1"; }

case "${1:-all}" in
  render) shift; for s in "$@"; do render "$s"; done ;;
  encode) shift; for s in "$@"; do encode "$s"; done ;;
  mux)    shift; for s in "$@"; do mux "$s"; done ;;
  concat) concat ;;
  all)    for s in $ALL; do step "$s"; done; concat ;;
  *)      step "$1" ;;
esac
