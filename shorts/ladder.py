"""Scale-ladder kit: neon landmark icons drawn at true size, and a log-zoom camera.

Every landmark is defined in metres, so the on-screen comparison is always to scale,
and its label is generated from the same number that sizes it (the 25M-view
reference Short had labels lagging one drawing behind; this makes that impossible).
"""
import math

from engine import C, lerp


class LogCamera:
    """Maps world metres to screen pixels. The visible world height H_world is
    interpolated in log space, so zooming from 1 m to 10 km is smooth and constant-rate."""

    def __init__(self, ground_y=1240, x0=540, screen_h=900):
        self.ground_y, self.x0, self.screen_h = ground_y, x0, screen_h
        self.world_h = 1.0

    def set_height(self, metres):
        self.world_h = max(1e-9, metres)

    def zoom_between(self, h0, h1, u):
        self.world_h = math.exp(lerp(math.log(h0), math.log(h1), u))

    @property
    def k(self):  # pixels per metre
        return self.screen_h / self.world_h

    def pt(self, x_m, y_m):
        return (self.x0 + x_m * self.k, self.ground_y - y_m * self.k)


# Real heights (m). Landmarks used as rungs; each icon is drawn inside a unit box
# (width w * height, height 1) and scaled by its true height.
LANDMARKS = {
    "grain": dict(h=0.004, label="Grain of wheat", sub="4 mm"),
    "rice": dict(h=0.006, label="Grain of rice", sub="6 mm"),
    "coin": dict(h=0.0243, label="Coin", sub="2.4 cm"),
    "card": dict(h=0.0856, label="Bank card", sub="8.6 cm"),
    "a4": dict(h=0.297, label="A4 sheet", sub="29.7 cm"),
    "spoon": dict(h=0.17, label="Teaspoon", sub="17 cm"),
    "bucket": dict(h=0.35, label="Bucket", sub="35 cm"),
    "person": dict(h=1.75, label="You", sub="1.75 m"),
    "car": dict(h=1.5, label="Car", sub="1.5 m"),
    "truck": dict(h=4.0, label="Truck", sub="4 m"),
    "house": dict(h=10.0, label="House", sub="10 m"),
    "silo": dict(h=40.0, label="Grain silo", sub="40 m"),
    "pisa": dict(h=57.0, label="Tower of Pisa", sub="57 m"),
    "pyramid": dict(h=139.0, label="Great Pyramid", sub="139 m"),
    "eiffel": dict(h=330.0, label="Eiffel Tower", sub="330 m"),
    "burj": dict(h=828.0, label="Burj Khalifa", sub="828 m"),
    "everest": dict(h=8849.0, label="Mount Everest", sub="8,849 m"),
}


def icon(f, kind, cam, x_m, color=C["mint"], a=1.0, width=4):
    """Draw a landmark of its true height with its left foot at world x = x_m."""
    h = LANDMARKS[kind]["h"]
    P = lambda u, v: cam.pt(x_m + u * h, v * h)       # unit-box coordinates -> screen
    L = lambda pts: f.line([P(*p) for p in pts], color, width, a)
    if kind == "person":
        f.circle(*P(0.12, 0.9), 0.1 * h * cam.k, color, width, a)
        L([(0.12, 0.8), (0.12, 0.42)]); L([(0.0, 0.0), (0.12, 0.42), (0.24, 0.0)]); L([(-0.02, 0.62), (0.12, 0.72), (0.26, 0.62)])
    elif kind == "car":
        L([(0, .25), (0, .6), (.35, .62), (.55, 1.0), (1.35, 1.0), (1.6, .62), (1.95, .58), (1.95, .25), (0, .25)])
        f.circle(*P(.45, .2), .2 * h * cam.k, color, width, a); f.circle(*P(1.5, .2), .2 * h * cam.k, color, width, a)
    elif kind == "truck":
        L([(0, .15), (0, 1), (1.6, 1), (1.6, .15), (0, .15)]); L([(1.6, .15), (1.6, .6), (1.95, .6), (2.2, .35), (2.2, .15), (1.6, .15)])
        for u in (.3, 1.25, 1.95):
            f.circle(*P(u, .1), .1 * h * cam.k, color, width, a)
    elif kind == "house":
        L([(0, 0), (0, .6), (.5, 1), (1, .6), (1, 0), (0, 0)]); L([(.4, 0), (.4, .3), (.6, .3), (.6, 0)])
    elif kind == "silo":
        L([(0, 0), (0, .85), (.15, 1), (.35, 1), (.5, .85), (.5, 0)]); L([(0, .85), (.5, .85)])
        for v in (.25, .5):
            L([(0, v), (.5, v)])
    elif kind == "pisa":
        for i in range(6):
            dx = 0.05 * i
            L([(dx, i / 6), (dx + .3, i / 6)])
        L([(0, 0), (.25, 1), (.55, 1), (.3, 0)])
    elif kind == "pyramid":
        L([(0, 0), (.8, 1), (1.6, 0)]); L([(.8, 1), (1.05, 0)])
    elif kind == "eiffel":
        L([(0, 0), (.17, .35), (.22, .6), (.25, 1), (.28, .6), (.33, .35), (.5, 0)])
        L([(.1, .2), (.4, .2)]); L([(.18, .4), (.32, .4)]); L([(.14, .2), (.25, .3), (.36, .2)])
    elif kind == "burj":
        L([(0, 0), (.04, .45), (.07, .72), (.09, .85), (.1, 1), (.11, .85), (.13, .72), (.16, .45), (.2, 0)])
    elif kind == "everest":
        L([(-1.2, 0), (-.5, .55), (-.3, .45), (0, 1), (.35, .62), (.55, .7), (1.3, 0)])
        L([(-.12, .78), (0, .86), (.1, .8), (.2, .74)])
    elif kind == "spoon":
        f.circle(*P(.11, .82), .1 * h * cam.k, color, width, a); L([(.11, .72), (.11, 0)])
    elif kind == "bucket":
        L([(0, 1), (.12, 0), (.68, 0), (.8, 1)]); L([(0, 1), (.8, 1)])
    elif kind == "rice":
        f.circle(*P(.2, .5), .0, color, width, a)
        pts = [(.2 + .2 * math.cos(th), .5 + .5 * math.sin(th)) for th in [i * math.pi / 12 for i in range(25)]]
        L(pts)
    elif kind == "coin":
        f.circle(*P(.5, .5), .5 * h * cam.k, color, width, a)
        f.circle(*P(.5, .5), .38 * h * cam.k, color, max(1, width - 2), a * 0.6)
    elif kind == "card":
        L([(0, 0), (0, 1), (.63, 1), (.63, 0), (0, 0)])
        L([(.1, .78), (.26, .78), (.26, .66), (.1, .66), (.1, .78)])
        L([(.1, .22), (.5, .22)])
    elif kind == "a4":
        L([(0, 0), (0, 1), (.707, 1), (.707, 0), (0, 0)])
        for v in (.78, .66, .54, .42):
            L([(.12, v), (.59, v)])
    elif kind == "grain":
        f.circle(*P(.5, .5), .5 * h * cam.k, color, width, a)
    return P


def mound(f, cam, x_m, height_m, color=C["warm"], a=1.0, slope=0.47, width=5, fill=0.10):
    """A conical pile (angle of repose ~25 deg, tan = 0.47) seen side-on, apex at x_m."""
    r = height_m / slope
    pts = [cam.pt(x_m - r, 0), cam.pt(x_m, height_m), cam.pt(x_m + r, 0)]
    f.poly(pts, color, width, a, fill=fill)
    return r
