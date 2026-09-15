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

scene_for() {
  case "$1" in
    intro) echo IntroSection ;;
    variables) echo VariablesSection ;;
    constants) echo ConstantsSection ;;
    functions) echo FunctionsSection ;;
    lambdas) echo LambdasSection ;;
    outro) echo OutroSection ;;
    *) echo "unknown section: $1" >&2; return 1 ;;
  esac
}
ALL="intro variables constants functions lambdas outro"
AV1=(-c:v libaom-av1 -b:v 0 -crf 40 -usage realtime -cpu-used 8 -row-mt 1 -tiles 8x2 -g 240 -pix_fmt yuv420p)

render() {
  local sec=$1 scene; scene=$(scene_for "$1")
  local ok=1
  if [[ -n $(ls "$FR" 2>/dev/null | head -1) ]]; then
    local last; last=$(ls "$FR" | sort | tail -1)
    [[ "$last" == ${scene}* ]] || ok=0
  else ok=0; fi
  if (( ok )); then echo "== render $sec: frames already present, skip =="; return 0; fi
  rm -rf "$FR"
  echo "== render $sec ($scene) =="
  $MANIM -qh --fps 60 --resolution 1920,1080 --format=png -g --disable_caching \
      src/manim_scenes.py "$scene" 2>&1 | tail -1
  echo "frames: $(ls "$FR" | wc -l)"
  echo "$scene" > "$OUT/.rendered_${sec}"
}

encode() {
  local sec=$1 scene; scene=$(scene_for "$1")
  if [[ -s "$OUT/${sec}_v.mp4" ]] && ffprobe -v error "$OUT/${sec}_v.mp4" >/dev/null 2>&1; then echo "== encode $sec: already done, skip =="; return 0; fi
  echo "== encode $sec (sequential resumable chunks) =="
  local nf; nf=$(ls "$FR" | wc -l)
  local nchunks=8 cs k start cnt
  cs=$(( (nf + nchunks - 1) / nchunks ))
  for ((k=0; k<nchunks; k++)); do
    start=$(( 1 + k*cs ))
    cnt=$(( nf - start + 1 ))
    (( cnt > cs )) && cnt=$cs
    if (( cnt <= 0 )); then break; fi
    local pf="$OUT/${sec}_part_$(printf '%02d' "$k").mp4"
    if [[ -s "$pf" ]] && ffprobe -v error "$pf" >/dev/null 2>&1 \
       && [[ $(ffprobe -v error -count_packets -select_streams v -show_entries stream=nb_read_packets -of csv=p=0 "$pf") == "$cnt" ]]; then
      echo "   chunk $k done"
      continue
    fi
    rm -f "$pf"
    echo "   chunk $k: frames $start..$((start+cnt-1))"
    ffmpeg -y -hide_banner -loglevel error -framerate 60 -start_number "$start" \
      -i "$FR/${scene}%04d.png" -frames:v "$cnt" "${AV1[@]}" -threads 48 -an \
      "$pf"
  done
  : > "$OUT/${sec}_parts.txt"
  for f in "$OUT/${sec}_part_"*.mp4; do echo "file '$(basename "$f")'" >> "$OUT/${sec}_parts.txt"; done
  ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$OUT/${sec}_parts.txt" \
    -c copy "$OUT/${sec}_v.mp4"
  rm -f "$OUT/${sec}_part_"*.mp4 "$OUT/${sec}_parts.txt"
}

mux() {
  local sec=$1
  if [[ -s "$OUT/${sec}.mp4" ]] && ffprobe -v error "$OUT/${sec}.mp4" >/dev/null 2>&1; then echo "== mux $sec: already done, skip =="; return 0; fi
  echo "== mux $sec =="
  ffmpeg -y -hide_banner -loglevel error -i "$OUT/${sec}_v.mp4" -i "$A/${sec}.wav" \
    -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart \
    "$OUT/${sec}.mp4"
  rm -f "$OUT/${sec}_v.mp4"
  rm -rf "$FR"
  ffprobe -v error -show_entries format=duration,size -of csv=p=0 "$OUT/${sec}.mp4"
}

concat() {
  if [[ -s "$OUT/manim_video_1080p60_av1.mp4" ]] && ffprobe -v error "$OUT/manim_video_1080p60_av1.mp4" >/dev/null 2>&1; then
    echo "== concat: already done, skip =="; return 0
  fi
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
    "$OUT/manim_video_1080p60_av1.mp4"
  ffprobe -v error -show_entries format=duration,size -of csv=p=0 "$OUT/manim_video_1080p60_av1.mp4"
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
