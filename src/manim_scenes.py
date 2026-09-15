"""Arabic 4K/60fps Manim explainer: variables, constants, functions, lambdas.

Render (4K/60):
  manim -qh --fps 60 --resolution 3840,2160 src/manim_scenes.py IntroSection ...
"""
import json
import os
import sys

import numpy as np
from manim import (
    BOLD,
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Arrow,
    Code,
    FadeIn,
    FadeOut,
    GrowArrow,
    LaggedStart,
    Rectangle,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
    config,
    there_and_back,
)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from arabic import normalize_arabic  # noqa: E402

# ---------------------------------------------------------------- palette
PURPLE = "#4B0082"        # user-required background
CODE_BG = "#141414"       # black code box
GUTTER_BG = "#3A3A3A"     # رصاصي line-number strip
GUTTER_FG = "#FFFFFF"
ACCENT = "#7CFF8F"        # light-green titles
ARROW_C = "#FFC83D"
BOX_STROKE = "#606070"

KUFI = "Noto Kufi Arabic"
NASKH = "Noto Naskh Arabic"
MONO = "DejaVu Sans Mono"

W, H = config.frame_width, config.frame_height   # 14.222 x 8 at 16:9
FS = 48.0                                        # Manim's default font size

# layout spec (fractions of the frame, per user request)
MARGIN_TOP = 0.10 * H
MARGIN_SIDE_HDR = 0.10 * W
HDR_DESC_GAP = 0.45          # natural gap: title <-> description (one object)
HDR_BOX_GAP = 0.10 * H       # exactly 10% header -> code box (not 25%)
BOX_MARGIN_X = 0.15 * W
BOX_MARGIN_BOT = 0.15 * H
SUB_CLEAR = 0.62             # clearance above the bottom subtitle strip

BOX_W = W - 2 * BOX_MARGIN_X

# ---------------------------------------------------------------- content
with open(os.path.join(HERE, "narration.json"), encoding="utf-8") as _f:
    CONTENT = json.load(_f)
SECTIONS = {s["key"]: s for s in CONTENT["sections"]}


def _load_timings() -> dict[str, list[float]]:
    p = os.path.join(HERE, "audio", "timings.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if isinstance(v, list)}
    return {}


TIMINGS = _load_timings()


class ArabicBase(Scene):
    """Shared plumbing: bottom subtitle strip + narration-aware budgets."""

    section_key: str = ""

    def setup(self):
        self.camera.background_color = PURPLE
        self._beats = [normalize_arabic(b) for b in SECTIONS[self.section_key]["beats"]]
        self._budgets = TIMINGS.get(self.section_key) or [4.0] * len(self._beats)
        self._sub: Text | None = None

    # ---------------------------------------------------------- subtitles
    def _subtitle(self, idx: int) -> float:
        """Swap in the bottom subtitle strip. Returns seconds spent."""
        used = 0.0
        old, self._sub = self._sub, None
        text = self._beats[idx]
        words = text.split(" ")
        if len(words) > 7:  # two short lines read better at the bottom
            mid = (len(words) + 1) // 2
            text = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
        sub = Text(text, font=NASKH, font_size=FS * 0.46, color="#FFFFFF",
                   line_spacing=0.5)
        sub.set_z_index(50)
        sub.move_to([0, -H / 2 + sub.height / 2 + 0.20, 0])
        if old is not None:
            self.play(FadeOut(old, run_time=0.3))
            used += 0.3
        self._sub = sub
        self.play(FadeIn(sub, run_time=0.4))
        return used + 0.4

    def _drop_sub(self) -> None:
        if self._sub is not None:
            self.play(FadeOut(self._sub, run_time=0.4))
            self._sub = None

    def _beat(self, i: int) -> float:
        """Narration budget (seconds) for beat i."""
        return float(self._budgets[i]) if i < len(self._budgets) else 4.0


class TitleSection(ArabicBase):
    """Intro / outro: centered green title + white description."""

    def setup(self):
        super().setup()
        sec = SECTIONS[self.section_key]
        self.title = Text(sec["title"], font=KUFI, weight=BOLD,
                          font_size=FS * 1.30, color=ACCENT, line_spacing=0.7)
        self.desc = Text(sec["subtitle"], font=NASKH, font_size=FS * 0.62,
                         color="#FFFFFF", line_spacing=0.65)
        self.desc.next_to(self.title, DOWN, buff=0.55)
        self.block = VGroup(self.title, self.desc).move_to(UP * 0.7)

    def construct(self):
        t0 = self._beat(0)
        rt = max(0.8, min(2.0, t0 - 0.8))
        self.play(FadeIn(self.title, scale=1.22), run_time=rt)
        used = rt + self._subtitle(0)
        self.wait(max(0.15, t0 - used))

        t1 = self._beat(1)
        rt1 = max(0.8, min(1.8, t1 - 0.8))
        self.play(FadeIn(self.desc, shift=DOWN * 1.2), run_time=rt1)
        used = rt1 + self._subtitle(1)
        self.wait(max(0.15, t1 - used))

        for i in range(2, len(self._beats)):
            used = self._subtitle(i)
            self.wait(max(0.15, self._beat(i) - used))

        self._drop_sub()
        self.play(FadeOut(self.title), FadeOut(self.desc), run_time=0.8)
        self.wait(0.4)


class IntroSection(TitleSection):
    section_key = "intro"


class OutroSection(TitleSection):
    section_key = "outro"


class CodeSection(ArabicBase):
    """Header (top-right) + large numbered black code box + gold arrow."""

    section_key: str = ""

    # ---------------------------------------------------------------- setup
    def setup(self):
        super().setup()
        sec = SECTIONS[self.section_key]

        # header object: big green title, white one-line description
        self.title = Text(sec["chapter"], font=KUFI, weight=BOLD,
                          font_size=FS * 1.40, color=ACCENT)
        self.desc = Text(sec["desc"], font=NASKH, font_size=FS * 0.62,
                         color="#FFFFFF")
        self.desc.next_to(self.title, DOWN, buff=HDR_DESC_GAP)
        self.header = VGroup(self.title, self.desc)
        self.header.move_to([
            W / 2 - MARGIN_SIDE_HDR - self.header.width / 2,
            H / 2 - MARGIN_TOP - self.header.height / 2,
            0,
        ])

        self._build_codebox(sec["code"]["lines"])

        self._arrow: Arrow | None = None
        self._box_in = False

    def _build_codebox(self, lines: list[str]) -> None:
        joined = "\n".join(lines)
        # Pango merges lam-alef into one glyph, which breaks Code/Paragraph's
        # 1-char-per-submobject mapping -> reword comments to avoid it.
        for bad in ("لا", "لأ", "لإ", "لآ"):
            if bad in joined:
                raise ValueError(
                    f"code comments must not contain lam-alef ligature {bad!r}"
                )
        code = Code(
            code_string="\n".join(lines),
            language="python",
            formatter_style="monokai",
            background="rectangle",
            add_line_numbers=True,
            line_numbers_from=1,
            paragraph_config={
                "font": MONO,
                "font_size": 34,
                "line_spacing": 0.5,
            },
        )
        code.set_z_index(5)
        zone_top = self.header.get_bottom()[1] - HDR_BOX_GAP
        zone_bot = -H / 2 + BOX_MARGIN_BOT + SUB_CLEAR
        zone_h = zone_top - zone_bot
        # the box must FILL the free zone: scale up to the 70% width,
        # then clamp so it never exceeds the vertical zone
        code.scale(BOX_W * 0.995 / code.width)
        if code.height > zone_h:
            code.scale(zone_h / code.height)
        box_cy = (zone_top + zone_bot) / 2
        code.move_to([0, box_cy, 0])

        bg_rect, nums, body = code.submobjects
        bg_rect.set_opacity(0)  # we draw our own frame + gutter

        gutter = Rectangle(
            width=nums.width + 0.70, height=code.height + 0.42,
            fill_color=GUTTER_BG, fill_opacity=1.0, stroke_width=0,
        ).move_to([nums.get_center()[0], box_cy, 0]).set_z_index(1)

        frame = RoundedRectangle(
            corner_radius=0.12,
            width=code.width + 0.55, height=code.height + 0.42,
            fill_color=CODE_BG, fill_opacity=1.0,
            stroke_color=BOX_STROKE, stroke_width=2.5,
        ).move_to([0, box_cy, 0]).set_z_index(0)

        nums.set_color(GUTTER_FG).set_z_index(6)
        body.set_z_index(5)

        # hide everything; rows/numbers appear while "typing"
        for row in body:
            for g in row:
                g.set_opacity(0)
        for n in nums:
            n.set_opacity(0)
        self._pending_nums = set(range(len(body)))  # gutter numbers not yet shown

        self.box = VGroup(frame, gutter)          # enters from mid-screen
        self.body = body                          # typed rows (added separately)
        self.nums = nums                          # line numbers
        self.box_cy = box_cy

    # ------------------------------------------------------------ helpers
    def _line_y(self, i: int) -> float:
        row = self.body[i]
        if len(row) == 0:
            return float(self.nums[i].get_center()[1])
        return float(np.mean([g.get_center()[1] for g in row]))

    def _arrow_anims(self, line_1based: int) -> list:
        """Create/move the gold arrow so its tip points at a code line."""
        i = line_1based - 1
        y = self._line_y(i)
        tip = np.array([self.box.get_left()[0] + 0.15, y, 0.0])
        start = tip + LEFT * 1.35

        def _make(s, e):
            return Arrow(s, e, buff=0, stroke_width=10, color=ARROW_C,
                         max_tip_length_to_length_ratio=0.38,
                         max_stroke_width_to_length_ratio=12)

        if self._arrow is None:
            self._arrow = _make(start, tip)
            self._arrow.set_z_index(30)
            return [GrowArrow(self._arrow)]
        return [self._arrow.animate.put_start_and_end_on(start, tip)]

    def _arrow_pulse(self) -> list:
        return [self._arrow.animate(rate_func=there_and_back).scale(1.25)]

    def _reveal(self, line_idx: int, total_rt: float) -> list:
        """Letter-by-letter reveal of one real (syntax-colored) code line."""
        anims: list = []
        row = [g for g in self.body[line_idx] if g.width > 1e-4]
        row.sort(key=lambda g: g.get_center()[0])   # visual left->right order
        num = self.nums[line_idx]
        n = len(row)
        if n == 0:  # blank line: only its number fades in
            if line_idx in self._pending_nums:
                anims.append(FadeIn(num, run_time=0.25))
                self._pending_nums.discard(line_idx)
            return anims
        seg = 0.22
        lag = (total_rt - seg) / (seg * (n - 1)) if n > 1 else 0.0
        lag = float(np.clip(lag, 0.02, 0.97))
        anims.append(LaggedStart(
            *[FadeIn(g, run_time=seg) for g in row],
            lag_ratio=lag, run_time=total_rt,
        ))
        if line_idx in self._pending_nums:
            anims.append(FadeIn(num, run_time=0.3))
            self._pending_nums.discard(line_idx)
        return anims

    def _type_lines(self, lines: list[int], avail: float) -> float:
        """Reveal the given lines (plus skipped blank lines' numbers)."""
        used = 0.0
        last = -1
        for l in lines:
            # blank lines jumped over: fade their numbers in so the
            # gutter stays a continuous 1, 2, 3, ...
            for k in range(last + 1, l):
                if len([g for g in self.body[k] if g.width > 1e-4]) == 0:
                    if k in self._pending_nums:
                        self.play(FadeIn(self.nums[k], run_time=0.2))
                        self._pending_nums.discard(k)
                        used += 0.2
            last = l
            chars = len([g for g in self.body[l] if g.width > 1e-4])
            if chars == 0:  # the requested line itself is blank
                if l in self._pending_nums:
                    self.play(FadeIn(self.nums[l], run_time=0.2))
                    self._pending_nums.discard(l)
                    used += 0.2
                continue
            per = max(0.8, (avail - used) / (len(lines) + 1))
            per = min(per, 0.14 * max(chars, 4) + 0.45)  # natural typing speed
            anims = self._reveal(l, per)
            if anims:
                self.play(*anims)
                used += per
        return used

    # ---------------------------------------------------------- construct
    def construct(self):
        sched = self.schedule()
        for i, step in enumerate(sched):
            budget = self._beat(i)
            kind = step["kind"]
            used = 0.0

            # static build-ins
            if kind == "title":
                rt = max(0.8, min(1.4, budget * 0.4))
                self.play(FadeIn(self.title, shift=LEFT * 1.8), run_time=rt)
                used += rt
            elif kind == "desc_box":
                rt = max(0.8, min(1.2, budget * 0.3))
                if not self._box_in:
                    # box starts at mid-screen (y=0), rises, settles, fading in
                    self.add(self.box)
                    self.play(FadeIn(self.desc),
                              FadeIn(self.box, shift=UP * (-self.box_cy)),
                              run_time=rt)
                    self._box_in = True
                else:
                    self.play(FadeIn(self.desc), run_time=rt)
                used += rt

            used += self._subtitle(i)

            # arrow first (viewer sees the target), then the typing
            if kind in ("desc_box", "type", "pulse", "point") and "arrow" in step:
                arr = self._arrow_anims(step["arrow"] + 1)
                self.play(*arr, run_time=0.45)
                used += 0.45
            if kind == "pulse" and self._arrow is not None:
                self.play(*self._arrow_pulse(), run_time=0.5)
                used += 0.5
            if kind in ("desc_box", "type"):
                used += self._type_lines(step.get("lines", []),
                                         max(0.5, budget - used - 0.2))

            self.wait(max(0.15, budget - used))

        # outro of the section
        self.wait(0.3)
        self._drop_sub()
        outs = [FadeOut(self.header), FadeOut(self.box),
                FadeOut(self.body), FadeOut(self.nums)]
        if self._arrow is not None:
            outs.append(FadeOut(self._arrow))
        self.play(*outs, run_time=0.8)
        self.wait(0.4)

    def schedule(self) -> list[dict]:
        return SCHEDULES[self.section_key]


# per-beat animation schedule (0-based code line indices)
SCHEDULES: dict[str, list[dict]] = {
    "variables": [
        {"kind": "title"},
        {"kind": "desc_box", "lines": [0, 1], "arrow": 1},
        {"kind": "type", "lines": [2], "arrow": 2},
        {"kind": "type", "lines": [4], "arrow": 4},
        {"kind": "pulse", "arrow": 4},
        {"kind": "type", "lines": [6, 7], "arrow": 6},
    ],
    "constants": [
        {"kind": "title"},
        {"kind": "desc_box", "lines": [0, 1], "arrow": 1},
        {"kind": "type", "lines": [2], "arrow": 2},
        {"kind": "type", "lines": [4], "arrow": 4},
        {"kind": "type", "lines": [6, 7, 8], "arrow": 7},
    ],
    "functions": [
        {"kind": "title"},
        {"kind": "desc_box", "lines": [0, 1], "arrow": 1},
        {"kind": "type", "lines": [2, 3], "arrow": 3},
        {"kind": "type", "lines": [5], "arrow": 5},
        {"kind": "pulse", "arrow": 5},
        {"kind": "type", "lines": [6, 7], "arrow": 7},
    ],
    "lambdas": [
        {"kind": "title"},
        {"kind": "desc_box", "lines": [0, 1], "arrow": 1},
        {"kind": "pulse", "arrow": 1},
        {"kind": "type", "lines": [3], "arrow": 3},
        {"kind": "type", "lines": [5, 6, 7], "arrow": 6},
    ],
}


class VariablesSection(CodeSection):
    section_key = "variables"


class ConstantsSection(CodeSection):
    section_key = "constants"


class FunctionsSection(CodeSection):
    section_key = "functions"


class LambdasSection(CodeSection):
    section_key = "lambdas"
