"""tinybasic.py (screen) - the Tiny BASIC editor, runner and display.

The interpreter works in a fixed **240x135** coordinate space and this screen
scales it up for the window. That split is deliberate: a fixed space means a
program draws the same picture wherever it runs, and only the pixels get bigger.

Scaling is by an **integer factor** chosen to fit the panel, so a one-pixel
PSET becomes a crisp NxN block rather than a blurred smear, and the 240x135
aspect is preserved with the result centered.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import Screen, COL_ACCENT2, COL_MUTED, COL_TEXT
from ...engine import tinybasic as TB

SAMPLE = """10 REM Tiny BASIC
20 CLS
30 FOR I = 0 TO 11
40 LINE 120, 67, 120 + 100 * COS(I * 30), 67 + 100 * SIN(I * 30), 3
50 NEXT
60 CIRCLE 120, 67, 60, 5
70 CIRCLE 120, 67, 30, 2
80 TEXT 86, 4, "ORBITDECK BASIC"
90 SHOW
100 PRINT "Drew a ", 12, "-spoke rosette."
110 REM Live data is available too - try:
120 REM   SATSEL 0 : PRINT "AZ=", SATAZ, " EL=", SATEL
130 REM   FOR I=0 TO NSAT-1 : SATSEL I : PRINT SATNOR : NEXT
140 END
"""


class TinyBasicScreen(Screen):
    REPORT_TITLE = "Tiny BASIC"

    def build(self):
        self.header("Tiny BASIC")

        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Button(bar, text="Run", command=self._run).pack(side="left")
        ttk.Button(bar, text="Stop / Clear",
                   command=self._clear).pack(side="left", padx=6)
        ttk.Button(bar, text="Open\u2026",
                   command=self._open).pack(side="left", padx=(16, 2))
        ttk.Button(bar, text="Save\u2026", command=self._save).pack(side="left")
        ttk.Button(bar, text="Sample",
                   command=self._sample).pack(side="left", padx=6)
        ttk.Button(bar, text="Print screen\u2026",
                   command=self._report).pack(side="right", padx=4)
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel",
                  wraplength=520).pack(side="left", padx=12)

        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        left = ttk.Frame(body, style="TFrame")
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Program", style="TLabel").pack(anchor="w")
        self.editor = tk.Text(left, height=16, width=46, undo=True,
                              bg="#0d1117", fg=COL_TEXT,
                              insertbackground=COL_TEXT,
                              font=("DejaVu Sans Mono", 10),
                              relief="flat", highlightthickness=1,
                              highlightbackground=COL_MUTED)
        self.editor.pack(fill="both", expand=True, pady=(2, 6))
        self.editor.insert("1.0", SAMPLE)

        ttk.Label(left, text="Output", style="TLabel").pack(anchor="w")
        self.console = tk.Text(left, height=7, width=46, state="disabled",
                               bg="#0d1117", fg=COL_ACCENT2,
                               font=("DejaVu Sans Mono", 10),
                               relief="flat", highlightthickness=1,
                               highlightbackground=COL_MUTED)
        self.console.pack(fill="both", expand=False, pady=2)

        right = ttk.Frame(body, style="TFrame")
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(right, text="Display  (240 \u00d7 135)",
                  style="TLabel").pack(anchor="w")
        self.canvas = tk.Canvas(right, bg="#000000", highlightthickness=1,
                                highlightbackground=COL_MUTED, width=480,
                                height=270)
        self.canvas.pack(fill="both", expand=True, pady=2)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        ttk.Label(right, text="The drawing canvas is 240 \u00d7 135 with ten "
                              "colors. The display scales by a whole number "
                              "of pixels, so edges stay crisp at any window "
                              "size.",
                  style="Muted.TLabel", wraplength=420).pack(anchor="w",
                                                             pady=(4, 0))
        self._ops = []

    # ---- running ---------------------------------------------------------
    def _run(self):
        src = self.editor.get("1.0", "end")
        prog = TB.Program(src)
        wanted = prog.input_prompts()
        values = []
        if wanted:
            # INPUT is collected BEFORE the run: the interpreter never
            # re-enters the event loop with a live program on the stack.
            for name in wanted:
                v = _ask_number(self.frame, name)
                if v is None:
                    self.info.set("Run canceled.")
                    return
                values.append(v)
        try:
            from ...engine.basichost import BasicHost
            vm = TB.Interpreter(prog, inputs=values,
                                host=BasicHost(self.store),
                                file_dir=_program_dir()).run()
        except TB.BasicError as exc:
            self._write_console("?%s" % exc)
            self.info.set(str(exc))
            return
        except Exception as exc:                    # pragma: no cover
            self._write_console("?internal error: %s" % str(exc)[:120])
            self.info.set("internal error")
            return
        self._write_console("\n".join(vm.out) if vm.out else "(no output)")
        self._ops = vm.gfx
        self._redraw()
        self.info.set("Ran %d statement(s); %d graphics call(s)."
                      % (vm.steps, len(vm.gfx)))

    def _clear(self):
        self._ops = []
        self._write_console("")
        self._redraw()
        self.info.set("")

    def _write_console(self, text):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.insert("1.0", text)
        self.console.configure(state="disabled")

    # ---- display ---------------------------------------------------------
    def _geometry(self):
        """Integer scale factor and centering offsets for the current canvas.

        A whole-number scale keeps a single-pixel PSET a crisp square; a
        fractional one would leave some pixels a row taller than their
        neighbors.
        """
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        scale = max(1, min(w // TB.GFX_W, h // TB.GFX_H))
        ox = (w - TB.GFX_W * scale) // 2
        oy = (h - TB.GFX_H * scale) // 2
        return scale, ox, oy

    def _redraw(self):
        self.canvas.delete("all")
        s, ox, oy = self._geometry()
        # Everything is clipped to the 240x135 canvas. Drawing outside it is
        # simply not possible in this dialect, so a program that runs off the
        # edge is clipped rather than spilling across the panel.
        clip = (ox, oy, ox + TB.GFX_W * s, oy + TB.GFX_H * s)
        # the canvas edge, so a program can see where its bounds are
        self.canvas.create_rectangle(ox, oy, ox + TB.GFX_W * s,
                                     oy + TB.GFX_H * s,
                                     outline="#243040", fill="#000000")

        def X(v):
            return ox + float(v) * s

        def Y(v):
            return oy + float(v) * s

        def color(i):
            i = int(i)
            return TB.PALETTE[i] if 0 <= i < len(TB.PALETTE) else "#ffffff"

        def inside(*items):
            """Keep only what falls within the 240x135 canvas."""
            for item in items:
                self.canvas.addtag_withtag("gfx", item)

        for op in self._ops:
            a = op.args
            if op.op == "cls":
                self.canvas.create_rectangle(ox, oy, ox + TB.GFX_W * s,
                                             oy + TB.GFX_H * s,
                                             outline="", fill="#000000")
            elif op.op == "pset":
                # a scaled pixel is a filled square, not a dot
                inside(self.canvas.create_rectangle(
                    X(a[0]), Y(a[1]), X(a[0]) + s, Y(a[1]) + s,
                    outline="", fill=color(a[2])))
            elif op.op == "line":
                inside(self.canvas.create_line(
                    X(a[0]) + s / 2, Y(a[1]) + s / 2,
                    X(a[2]) + s / 2, Y(a[3]) + s / 2,
                    fill=color(a[4]), width=max(1, s)))
            elif op.op == "circle":
                r = float(a[2]) * s
                cx, cy = X(a[0]) + s / 2, Y(a[1]) + s / 2
                inside(self.canvas.create_oval(
                    cx - r, cy - r, cx + r, cy + r,
                    outline=color(a[3]), width=max(1, s)))
            elif op.op == "text":
                # Scale the point size with the display so text keeps its
                # proportion to the drawing.
                inside(self.canvas.create_text(
                    X(a[0]), Y(a[1]), anchor="nw", text=op.text or "",
                    fill="#ffffff",
                    font=("DejaVu Sans Mono", max(6, 4 * s))))

        # Clip: drop anything drawn entirely off the canvas, and mask the
        # overhang of anything crossing the edge.
        for item in self.canvas.find_withtag("gfx"):
            x1, y1, x2, y2 = self.canvas.bbox(item) or (0, 0, 0, 0)
            if x2 < clip[0] or x1 > clip[2] or y2 < clip[1] or y1 > clip[3]:
                self.canvas.delete(item)
        self._mask(clip)

    def _mask(self, clip):
        """Cover anything that spills past the canvas edge.

        Tk canvas items cannot be clipped directly, so the overhang is painted
        over in the panel background.
        """
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        bg = "#0d1117"
        x1, y1, x2, y2 = clip
        for box in ((0, 0, w, y1), (0, y2, w, h),
                    (0, 0, x1, h), (x2, 0, w, h)):
            if box[2] > box[0] and box[3] > box[1]:
                self.canvas.create_rectangle(*box, outline="", fill=bg)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#243040")

    # ---- files -----------------------------------------------------------
    def _sample(self):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", SAMPLE)
        self.info.set("Loaded the sample program.")

    def _open(self):
        path = filedialog.askopenfilename(
            parent=self.frame, title="Open a BASIC program",
            filetypes=[("BASIC", "*.bas"), ("Text", "*.txt"), ("All", "*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as exc:
            messagebox.showerror("Open", str(exc)[:200], parent=self.frame)
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.info.set("Opened %s" % path)

    def _save(self):
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension=".bas",
            filetypes=[("BASIC", "*.bas")], title="Save the program")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", "end"))
        except Exception as exc:
            messagebox.showerror("Save", str(exc)[:200], parent=self.frame)
            return
        self.info.set("Saved %s" % path)

    def _report(self):
        from ..reports import save_report_dialog
        src = self.editor.get("1.0", "end").rstrip()
        out = self.console.get("1.0", "end").rstrip()
        save_report_dialog(
            self, "tinybasic", title="Tiny BASIC",
            sections=[("Program", "text", src or "(empty)"),
                      ("Output", "text", out or "(none)")])


def _program_dir():
    """Where FOPEN writes. One directory, so a program cannot reach the disk."""
    import os
    d = os.path.join(os.path.expanduser("~"), ".orbitdeck", "basic")
    os.makedirs(d, exist_ok=True)
    return d


def _ask_number(parent, name):
    """Ask for one INPUT value before the run starts."""
    from tkinter import simpledialog
    return simpledialog.askfloat("INPUT", "Value for %s:" % name,
                                 parent=parent)
