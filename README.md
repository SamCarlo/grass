# KINETIC

The `kinetic` branch of the grass repo: `touch-grass.html` from `main`, with the webcam
wired in as a second controller. Everything the original did, it still does — this only
adds a channel. It lives on a branch because the head movements are the experiment.

```bash
git diff main..kinetic -- index.html    # everything head tracking changed
git switch main                         # back to the original game
```

Git tracks `touch-grass.html → index.html` as a rename at 94% similarity, so the diff
against `main` stays readable rather than showing the file as new.

**Your head is the look stick.** Turn it left or right to steer; tilt it up or down to aim
vertically. The keyboard is untouched.

The two axes work differently on purpose:

- **Turn** drives a *rate*. Hold the turn and the view keeps rotating, so ~20° of head
  movement sweeps a full circle without you having to twist round.
- **Tilt** drives an *absolute angle*. Head tilt maps straight onto view pitch and lets go
  when you come back to level, so it cannot drift and never needs recentring. ~22° of tilt
  buys the whole 70° of look, because nobody wants to hold their neck back to see the sky.

A rate on the vertical would park the view at the ceiling every time you glanced at the
keyboard; an absolute angle on the horizontal would cap you at however far you can twist.

## Run it

```bash
cd ~/Documents/games/kinetic
python3 serve.py          # opens http://localhost:1268/
```

Then click **HEAD STEERING: OFF** on the title card and allow the camera.

`serve.py` is not optional if you want the camera. Browsers only hand over a webcam on a
secure origin, and a `file://` path is not one; `http://localhost` is. Opening `index.html`
directly still gives you the whole game, just with head steering permanently unavailable —
it says so on the card rather than failing silently.

The first camera start pulls ~12 MB of MediaPipe wasm and model weights from jsDelivr, so
it needs a network connection once. The browser caches it after that.

## Controls

| | |
|---|---|
| `W A S D` | Move |
| **head turn** | Steer left/right — the view follows and keeps turning |
| **head tilt** | Look up/down — comes back to level when you do |
| mouse | Look around — still live at the same time as the camera |
| `SHIFT` | Ski |
| `SPACE` | Thruster |
| `F` / click | Crack the whip |
| `H` | Head steering on/off, mid-run |
| `V` | Tilt axis on/off, leaving the turn axis running |
| `C` | Recentre — makes wherever you are sitting the new straight-ahead |
| `R` | Restart level |
| `ESC` | Pause |

Head and mouse coexist. Turn sums into the same accumulator the mouse writes; tilt rides on
top of whatever pitch the mouse has set, as an offset. So you can hold a head tilt and still
trim with the mouse, and neither one clobbers the other.

## Tuning

The title card has a **camera console**, grouped by axis.

**Turn — left / right**

- **Turn speed** — multiplier on how fast a given head angle rotates you.
- **Dead zone** (default 6°) — head movement smaller than this does nothing. Raise it if
  the view drifts while you are trying to sit still.
- **Full-turn angle** (default 26°) — the head angle that means "maximum speed". Lower it
  if you want to turn without moving much; raise it for finer control.

**Tilt — up / down**

- **Look reach** (default 70°) — how far up and down the view can go at full tilt.
- **Tilt for full** (default 22°) — how far you have to tilt your head to get there. This
  is the comfort dial: lower means less neck, at the cost of precision.
- **Dead zone** (default 4°) — smaller than the turn dead zone, because your head has far
  less vertical travel to spend.
- **Steadiness** (default 35 ms) — a light ease on top of the interpolation described
  below. It is already smooth at the default; raise it if your camera is slow or your
  lighting is poor, since both make the tracker's own output noisier.

**Both axes**

- **Turn smoothing** (default 70 ms) — lag traded against jitter, on the turn axis only.
- **TILT AXIS** — the vertical channel on or off. Also `V`.
- **INVERT TURN** / **INVERT TILT** — independent, see below.
- **CAMERA BAY** — the little preview panel, bottom right.
- **RECENTRE NOW** — same as pressing `C`.

At the defaults, 12° of head tilt gives you about 22° of view, and 20° gives about 59° —
gentle around level, decisive at the edges.

Settings and the on/off state persist in `localStorage` under `kinetic_head_v1`.

## The camera bay

Bottom-right panel, shown whenever tracking is on. The feed is mirrored, so it behaves like
a mirror: turn left and the needle goes left, tilt up and it goes up.

A crosshair tracks your head — the green vertical needle is the turn axis, the amber
horizontal one is tilt. The faint box around the centre is the two dead zones. Underneath,
one row per axis: which way you are steering and by how much. The tilt row reports the
*view* angle it is buying you, not your head angle, since that is the number you are
actually aiming with.

Top right of the feed is the camera's measured frame rate. This is the ceiling on how
smooth the tilt axis can be — see below — so it is worth a glance if the vertical ever
feels rough. It turns amber below 20 fps, which almost always means the room is too dark
and the webcam has dropped its rate to compensate. More light fixes it.

It also tells you when it cannot see you (`NO FACE`), when it is taking your centre
(`HOLD STILL`), and when the camera has faulted.

## How the head angle is worked out

MediaPipe's `FaceLandmarker` gives two useful things per frame: a 4×4 head-pose matrix, and
478 landmarks in image space.

The matrix gives a clean angle in degrees (`YXZ` Euler decomposition, yaw about Y), but its
handedness is a convention you have to guess at, and guessing wrong means the game steers
backwards.

So the sign is not guessed. The nose tip swings toward whichever side you turn to — that is
a fact about the image, not about anyone's matrix convention — so the horizontal offset of
landmark 1 (nose) from the midpoint of 234/454 (the cheek contours) gives an unambiguous
direction. A running correlation locks the matrix angle to agree with it. Whatever
handedness the matrix turns out to use, the output is positive when you turn to your left.

The vertical axis works the same way, correlated against the nose's offset from the
forehead–chin midpoint: the nose sits forward of the axis your head pitches about, so
tilting back lifts it in frame.

The one thing that defeats this is a camera driver that mirrors the feed in hardware, which
inverts the image-space signal too. That is what **INVERT TURN** and **INVERT TILT** are
for; they are separate because vertical is the one people hold opinions about.

Both angles then go through a dead zone, an eased response curve and exponential smoothing.
Turn comes out as a rate (`t^1.7`, up to 2.6 rad/s) that the game loop integrates into the
same accumulator the mouse writes. Tilt comes out as an absolute angle (`t^1.4`, up to the
look reach) that is added to the mouse's pitch fresh every frame and never written back —
which is precisely what stops it accumulating.

If the face is lost, both are held for 250 ms so one dropped frame is not a stutter. After
that the turn rate is simply cut, but the tilt angle is *eased* back to level rather than
dropped, because dropping it would snap the horizon. Easing also means reacquiring your
face blends in from wherever the view happens to be.

## Why the tilt axis is reconstructed at display rate

The tracker publishes a new tilt angle once per camera frame — thirty times a second, and
fewer in a dim room. The game draws sixty to a hundred and forty times a second. Handing
the camera the freshest value therefore holds the view perfectly still for three or four
frames and then snaps it several degrees, over and over. That reads as jerk, and it is
worse the *better* your monitor is: at 144 Hz with a 30 Hz camera the view moves on one
frame in five.

The turn axis never had this problem, which is the tell. A rate gets integrated by the game
loop, and integration is itself a low-pass filter; an absolute angle arrives with nothing
doing that job for it. The absolute mapping also multiplies the head angle by three to five
times on its way to a view angle, so any unevenness arrives magnified.

The fix is not to filter harder — that costs lag in proportion to the camera interval it
has to span. Instead the game keeps the last two samples and plays them back across the gap
between them, one camera interval behind real time. The motion in between is then
continuous by construction rather than by attenuation. A light ease on top rounds the
corner where one pair hands over to the next.

Measured against a perfectly reconstructed signal, this sits within about ten percent of
the smoothest motion the response curve allows, at ~63 ms of lag — where filtering alone
needed ~97 ms to reach the same smoothness. It also adapts: the interpolation window is
sized from the camera's *measured* rate, so a webcam that drops to 15 fps gets interpolated
over a wider gap instead of becoming twice as steppy.

## If it does not work

- **"A camera needs a secure page"** — you opened `index.html` as a file. Use `serve.py`.
- **Steering goes the wrong way** — **INVERT TURN** for left/right, **INVERT TILT** for
  up/down. They are independent.
- **View drifts when you sit still** — press `C` to recentre, and raise the dead zone.
- **Horizon sits permanently high or low** — your neutral was taken with your head tilted.
  Press `C` while sitting how you actually play.
- **Too twitchy / too sluggish** — full-turn angle first, turn speed second. For tilt, it
  is "tilt for full": raise it for precision, lower it for less neck movement.
- **Vertical feels jerky or steppy** — check the frame rate in the corner of the camera
  bay first. Below 20 fps the camera itself is the limit, and more light will do more than
  any slider. Otherwise raise **Steadiness**.
- **Tilt gets in the way** — press `V`. The turn axis keeps working.
- **`NO FACE`** — the bay shows what the camera sees. Usually light on your face, not
  behind you.
- **Camera is busy** — something else has the device.

Head steering failing never takes the game with it: every path falls back to keys and mouse.

## Layout

```
index.html   the whole game — three.js r128 inlined, no build step
serve.py     static server on :1268, only there to make the origin secure
LICENSE      MIT
```

Inside `index.html`, in document order: the game's markup, three.js, a WebGL probe, the
head tracker (`window.KineticHead`), then the game itself. The tracker is a standalone
IIFE that the game only ever polls — it never awaits it, and every read is guarded.

## License

MIT — see `LICENSE`. Fork it, gut it, ship it.

Two third-party pieces come with their own terms, neither of them changed by that:

- **three.js r128**, MIT, inlined into `index.html` as a single minified line. Its licence
  header sits at the top of that bundle and needs to stay there. Do not reformat the line —
  it makes every diff of this file useless.
- **MediaPipe Tasks-Vision**, Apache-2.0, fetched from jsDelivr at runtime along with the
  face-landmarker weights. Nothing from it is vendored here, so a fork inherits no
  obligations beyond Apache-2.0 if you choose to redistribute it yourself.

No analytics, no telemetry, no network calls beyond the MediaPipe CDN and the Google Fonts
stylesheet. The webcam frames are read into the tracker and never leave the page.
