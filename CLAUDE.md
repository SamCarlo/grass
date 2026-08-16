# CLAUDE.md

Guidance for Claude Code when working in `games/kinetic/`.

## What this is

The `kinetic` branch of the grass repo (`github.com/SamCarlo/grass`, private). It is
`touch-grass.html` from `main` — the same endless grass survey — with webcam head tracking
added as a second controller. All original keyboard/mouse/touch controls are preserved
unchanged; head steering is purely additive.

**This is an experiment and belongs on the branch.** Do not merge it to `main` without
being asked; `main` is the plain games, and the head tracking is what is being tried out.

The game file is `touch-grass.html` renamed to `index.html` (so `serve.py` serves it at
`/`). Git sees the rename at 94% similarity, which is what keeps `git diff main..kinetic`
readable — **do not rename it again**, or the lineage stops being legible.

`descent.html` is inherited from `main` and is not part of this experiment; leave it alone.

Checked out as a git worktree at `games/kinetic`, alongside `main` at `games/Grass`. Both
are the same repository, so a commit here is a commit there. `git worktree list` shows the
pair.

See `README.md` for controls, tuning and the tracking design.

## Run

```bash
python3 serve.py          # http://localhost:1268/
```

`serve.py` exists solely because `getUserMedia` requires a secure origin — `file://` is not
one, `http://localhost` is. Do not "simplify" by telling anyone to open `index.html`
directly; the camera will not work.

## Structure

Single file, no build step, no package manager. `index.html` contains, in document order:

1. Styles, then all game markup (including `#cam`, the camera bay, and `#camCfg`, the
   console on the title card).
2. three.js r128, inlined and minified, as one ~600 KB line. **Never reformat it** — it
   makes every diff of this file useless. When grepping, exclude it.
3. A WebGL probe that sets `window.__tgReady`.
4. The head tracker: a self-contained IIFE exposing `window.KineticHead`. Classic script,
   not a module, so it evaluates *before* the game script — a `type="module"` block is
   deferred and would not exist yet when the game reads it.
5. The game, wrapped in `if (window.__tgReady) { … }`.

## The seam between tracker and game

The game holds `const HEAD = window.KineticHead` and **polls it**. It never awaits it,
imports from it, or assumes it exists. Keep it that way: if MediaPipe, the network or the
camera fails, the game must still be exactly the one it was branched from.

Game-side surface is four functions, all near the `HEAD STEERING` banner just above the
`LOOP` section:

- `headLive()` — tracking is up and trustworthy.
- `applyHeadLook(dt)` — called from `frame()` between `readKeys()` and `updatePlayer(dt)`.
  Adds `HEAD.yawRate * dt` to `input.look.x`, the same field the mouse writes, so head and
  mouse sum rather than fight. **Yaw only.**
- `headPitch()` — called from `updatePlayer`. Returns `HEAD.pitchOffset` in radians.
- `paintCamHud()` — called from `frame()` *above* the `mode !== 'playing'` early return, so
  the bay stays live on the menu, which is where you aim your chair.

## Two axes, two models — do not "unify" them

Yaw is unbounded and pitch is not, so they are deliberately different:

| | yaw / turn | pitch / tilt |
|---|---|---|
| model | **rate** (rad/s, integrated) | **absolute offset** (radians) |
| published as | `HEAD.yawRate` | `HEAD.pitchOffset` |
| consumed by | `applyHeadLook` → `input.look.x` | `headPitch(dt)` → `P.pitch` |
| on face loss | cut to zero | eased to level |
| filtered | once, at camera rate | despiked at camera rate, **reconstructed at display rate** |

A rate on the vertical parks the view at the sky whenever the player glances away; an
absolute angle on the horizontal caps them at how far they can physically twist. Both were
tried; this is the resolution.

The pitch offset is added in `updatePlayer` and **never written back into `input.look.y`**:

```js
input.look.y = clamp(input.look.y);                  // the mouse's, clamped on its own
P.pitch      = clamp(input.look.y + headPitch());    // head rides on top, per frame
```

Writing it back would make tilt accumulate frame over frame and pin the view at the clamp
within a second. There is a regression test for exactly this.

## Do not feed `HEAD.pitchOffset` straight to the camera

`headPitch(dt)` interpolates between the last two published samples, one camera interval
behind real time, then eases lightly. This is load-bearing, not polish. The tracker
publishes ~30 times a second and the game draws up to 144 times a second, so the raw value
holds for three or four frames and then jumps — visible, reported jerk. Yaw is immune
because integrating a rate low-passes it for free.

Filtering harder is the wrong fix: the time constant has to span a whole camera interval,
which costs lag proportionally. Interpolation is continuous by construction and measured
~35% cheaper in lag for the same smoothness. Numbers and method are in the README.

The mechanism needs three things kept intact:

- `HEAD.stamp` increments on **every** publish, including the face-lost easing in `decay()`.
  `headPitch` uses it to detect a genuinely new sample; if it stops moving, the
  interpolation saturates and holds.
- `HEAD.interval` is the *measured* detection gap, sampled only on frames that produced a
  face and windowed to 5–200 ms so a backgrounded tab cannot poison it. It sizes both the
  interpolation window and the ease floor.
- The ease tau floors at `interval * 0.6`, so dragging Steadiness to 0 cannot bring the
  steps back.

Both the game loop and the tracker loop are rAF/`requestVideoFrameCallback` driven, so
**neither runs in a hidden tab** — `HEAD.stamp` and `HEAD.fps` will sit still when testing
via automation. Pump frames with a screenshot, or verify the maths offline instead.

`pointerlockchange` no longer auto-pauses while `headLive()` — the original behaviour would
fire every time you looked away from the mouse.

## Sign conventions — get these right

- `input.look.x` **increasing = turning left.** From the game's own maths:
  `fwd = (-sin(yaw), 0, -cos(yaw))`, `rgt = (cos(yaw), 0, -sin(yaw))`, and `rgt` is what
  `D` strafes along, so `+X` is right at `yaw = 0` and rising yaw swings toward `-X`.
  Consistent with `look.x -= movementX` for the mouse.
- `input.look.y` / `P.pitch` **increasing = looking up**, consistent with
  `look.y -= movementY` for the mouse.
- `KineticHead.yawDeg` / `yawRate` **positive = turning to your left.**
- `KineticHead.pitchDeg` / `pitchOffset` **positive = chin up / looking up.**
- MediaPipe's head-pose matrix has ambiguous handedness, so its sign is **never assumed**.
  Each axis is locked at runtime against an image-space signal that is unambiguous — nose
  vs. the cheek midpoint for yaw, nose vs. the forehead–chin midpoint for pitch. Do not
  replace either with a hardcoded sign; see README for why.
- `opt.invert` is yaw only and `opt.invertPitch` is pitch only. They were one flag once;
  splitting them was deliberate.

## Testing without a webcam

Both of these were used to verify the current build and are worth repeating after changes:

- Stub the camera: override `navigator.mediaDevices.getUserMedia` to return
  `canvas.captureStream(30)`, then `await KineticHead.start()`. Exercises the CDN import,
  the wasm fileset, `FaceLandmarker` construction, the video wiring and the detection loop.
  No face is found, so it also covers the no-face path.
- Drive the game side directly: set `KineticHead.enabled/status/face` by hand with the
  detection loop stopped, then set `yawRate` (positive must turn **left**) or `pitchOffset`
  (positive must look **up**) and watch the view move.
- The pure maths — Euler decomposition, sign lock, both response curves, the no-accumulate
  property — is worth re-testing offline in node by copying the functions out; that is how
  the current curves were tuned.

Note that a background tab has `document.hidden === true` and rAF suspended, so the game
loop does not run; taking a screenshot pumps a few frames if you need them.
