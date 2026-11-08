"""Human-readable formatting for the quantities a ladder Short counts."""
import math

LY = 9.4607e15
YEAR = 365.25 * 86400
_SCALE = [(1e21, "sextillion"), (1e18, "quintillion"), (1e15, "quadrillion"), (1e12, "trillion"),
          (1e9, "billion"), (1e6, "million")]
_SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def _sig(x, d=3):
    """x rounded to d significant figures, without a trailing .0"""
    s = f"{float(f'{x:.{d}g}'):,.{max(0, d - 1 - int(math.floor(math.log10(abs(x)))) if x else 0)}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _named(x, unit=""):
    for v, name in _SCALE:
        if x >= v:
            return f"{_sig(x / v)} {name}{unit}"
    return f"{x:,.0f}{unit}"


def sci(x):
    e = int(math.floor(math.log10(x)))
    m = x / 10 ** e
    head = "" if abs(m - 1) < 5e-3 else f"{m:.3g} × "
    return f"{head}10{str(e).translate(_SUP)}"


def length(m):
    if m < 1e-4:
        return f"{m * 1e6:.0f} µm" if m >= 1e-6 else f"{m * 1e9:.1f} nm"
    if m < 1e-3:
        return f"{m * 1000:.1f} mm"
    if m < 0.01:
        return f"{m * 1000:.1f} mm".replace(".0 ", " ")
    if m < 0.1:
        return f"{m * 100:.1f} cm".replace(".0 ", " ")
    if m < 1:
        return f"{m * 100:.0f} cm"
    if m < 10:
        return f"{m:.1f} m".replace(".0 ", " ")
    if m < 1000:
        return f"{m:.0f} m"
    if m < 1e9:
        return f"{m / 1000:,.0f} km"
    if m < 0.1 * LY:
        return _named(m / 1000) + " km"
    y = m / LY
    if y < 10:
        return f"{y:.1f} light-years".replace(".0 ", " ")
    y = float(f"{y:.3g}")          # light-year figures rest on assumptions: 3 significant figures
    return f"{_named(y)} light-years"


def count(x):
    if x < 1e6:
        return f"{x:,.0f}"
    if x < 1e24:
        return _named(x)
    return sci(x)


def count_exact(x):
    return f"{int(round(x)):,}" if x < 1e21 else count(x)


def time(s):
    if s < 60:
        return f"{s:.0f} seconds" if s >= 2 else f"{s:.1f} seconds"
    if s < 3600:
        return f"{s / 60:.0f} minutes"
    if s < 86400:
        h, mnt = int(s // 3600), int(round((s % 3600) / 60))
        return f"{h} h {mnt:02d} min" if mnt else (f"{h} hour" if h == 1 else f"{h} hours")
    if s < 60 * 86400:
        return f"{s / 86400:.1f} days".replace(".0 ", " ")
    if s < 2 * YEAR:
        return f"{s / (30.44 * 86400):.0f} months"
    y = s / YEAR
    if y < 1e6:
        return f"{_sig(y)} years"
    return f"{_named(y)} years" if y < 1e24 else f"{sci(y)} years"


def mass(kg):
    if kg < 1:
        return f"{kg * 1000:.0f} g"
    if kg < 1000:
        return f"{_sig(kg)} kg"
    t = kg / 1000
    return f"{_sig(t)} tonnes" if t < 1e6 else f"{_named(t)} tonnes"


def clock(s):
    """Time of day from midnight, 24-hour: 00:00, 08:15"""
    m = int(round(s / 60))
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


FORMAT = {"clock": clock, "length": length, "count": count, "count_exact": count_exact, "time": time, "mass": mass}
