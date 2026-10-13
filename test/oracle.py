"""Independent integer arithmetic contract; no RTL parsing or simulator imports."""
def signed(value, bits=24):
    value %= 2 ** bits
    return value - 2 ** bits if value >= 2 ** (bits - 1) else value


def mac(acc, a, b):
    exact = acc + signed(a, 8) * signed(b, 8)
    return signed(exact), not -(2 ** 23) <= exact < 2 ** 23


def requant(acc, shift, mode, unsigned=False):
    value = (acc + (2 ** (shift - 1) if shift else 0)) // (2 ** shift)
    if unsigned:
        return max(0, min(255, value))
    return max(0 if mode == 1 else -128, min(127, value))
