# Adapted from date code by Teemu Kalvas. https://github.com/tkalvas/date
# License: zero-clause BSD

def from_y_dy(y, dy):
    """(Year, day-in-year (zero = March 1st)) to internal day counter."""
    return 365*y + y//4 - y//100 + y//400 + dy

def from_gregorian(yg, mg, dg):
    """(Year, month, day) of Gregorian date to internal day counter."""
    y, my = divmod(12*yg + mg - 3, 12)
    return from_y_dy(y, (153*my + 2)//5 + dg - 1)

def workday(date):
    """Is this a work day according to Finnish rules (with new year eve
    defined as not a workday)?"""
    md = date.month, date.day
    # lauantai, sunnuntai
    if date.weekday() >= 5:
        return False
    # uusivuosi, loppiainen, vappu, itsenäisyyspäivä, joulu
    if md in [(12, 31), (1, 1), (1, 6), (5, 1), (12, 6), (12, 24), (12, 25), (12, 26)]:
        return False
    # juhannusaatto
    if date.weekday() == 4 and md >= (6, 19) and md <= (6, 25):
        return False
    day = from_gregorian(date.year, date.month, date.day)
    # pitkäperjantai, pääsiäismaanantai, helatorstai
    if day - easter(date.year) in [-2, 1, 39]:
        return False
    return True

def easter_internal(y):
    """Internal day counter of easter in year."""
    c = y//100 + 1
    g = y % 19
    e = (15 - 11*g + 3*c//4 - (5 + 8*c)//25) % 30
    return 4 + (from_y_dy(y, 20 + e - (e + g//11) // 29) + 3) // 7 * 7

easter_cache = {}

def easter(y):
    """Memoized version of easter calculation."""
    if y not in easter_cache:
        easter_cache[y] = easter_internal(y)
    return easter_cache[y]
