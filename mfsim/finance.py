"""XIRR, without scipy (importing scipy.optimize alone costs ~38 MB of RAM)."""

from __future__ import annotations

import math
from datetime import date

XIRR_LOW, XIRR_HIGH = -0.9999, 50.0


def brentq(f, xa: float, xb: float, xtol: float = 2e-12, rtol: float = 8.881784197001252e-16,
           maxiter: int = 100) -> float:
    """Brent's root finder, a line-for-line port of scipy.optimize.brentq (same defaults),
    so XIRRs match what the scipy version computed. Raises ValueError when f(xa) and f(xb)
    have the same sign and RuntimeError when it doesn't converge, like scipy."""
    xpre, xcur = xa, xb
    xblk = fblk = spre = scur = 0.0
    fpre, fcur = f(xpre), f(xcur)
    if fpre * fcur > 0:
        raise ValueError("f(a) and f(b) must have different signs")
    if fpre == 0:
        return xpre
    if fcur == 0:
        return xcur
    for _ in range(maxiter):
        if fpre != 0 and fcur != 0 and math.copysign(1, fpre) != math.copysign(1, fcur):
            xblk, fblk = xpre, fpre
            spre = scur = xcur - xpre
        if abs(fblk) < abs(fcur):
            xpre, xcur, xblk = xcur, xblk, xcur
            fpre, fcur, fblk = fcur, fblk, fcur
        delta = (xtol + rtol * abs(xcur)) / 2
        sbis = (xblk - xcur) / 2
        if fcur == 0 or abs(sbis) < delta:
            return xcur
        if abs(spre) > delta and abs(fcur) < abs(fpre):
            if xpre == xblk:
                stry = -fcur * (xcur - xpre) / (fcur - fpre)  # interpolate
            else:
                dpre = (fpre - fcur) / (xpre - xcur)  # extrapolate
                dblk = (fblk - fcur) / (xblk - xcur)
                stry = -fcur * (fblk * dblk - fpre * dpre) / (dblk * dpre * (fblk - fpre))
            if 2 * abs(stry) < min(abs(spre), 3 * abs(sbis) - delta):
                spre, scur = scur, stry  # good short step
            else:
                spre = scur = sbis  # bisect
        else:
            spre = scur = sbis  # bisect
        xpre, fpre = xcur, fcur
        if abs(scur) > delta:
            xcur += scur
        else:
            xcur += delta if sbis > 0 else -delta
        fcur = f(xcur)
    raise RuntimeError("failed to converge")


def xirr(cashflows: list[float], dates: list[date]) -> float | None:
    """Annualised return of dated cashflows (negative = money in, positive = money out).
    None, not an exception, when there's no sign change or no root in [-99.99%, 5000%]:
    callers must handle None."""
    if len(cashflows) < 2:
        return None
    if not any(c > 0 for c in cashflows) or not any(c < 0 for c in cashflows):
        return None
    base = min(dates)
    years = [(d - base).days / 365.0 for d in dates]

    def npv(r: float) -> float:
        return sum(cf / (1 + r) ** t for cf, t in zip(cashflows, years))

    try:
        return brentq(npv, XIRR_LOW, XIRR_HIGH, maxiter=2000)
    except Exception:
        return None
