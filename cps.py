import unittest


GENSYM_COUNTER = iter(range(1000))


def gensym():
    return f"v{next(GENSYM_COUNTER)}"


def cps(exp, k):
    match exp:
        case int(_) | str(_):
            return [k, exp]
        case [op, x, y] if op in ["+", "-", "*", "/"]:
            vx = gensym()
            vy = gensym()
            return cps(x, ["cont", vx,
                           cps(y, ["cont", vy,
                                   [op, vx, vy, k]])])
        case ["lambda", arg, body]:
            raise NotImplementedError("Not implemented")
        case ["if", cond, iftrue, iffalse]:
            raise NotImplementedError("Not implemented")
        case [func, arg]:
            raise NotImplementedError("Not implemented")
    raise NotImplementedError("Not implemented")


class CPSTest(unittest.TestCase):
    def test_int(self):
        self.assertEqual(cps(1, "k"), ["k", 1])

    def test_var(self):
        self.assertEqual(cps("x", "k"), ["k", "x"])

    def test_add(self):
        self.assertEqual(
            cps(["+", 1, 2], "k"),
            [["lambda", "v0", [["lambda", "v1", ["+", "v0", "v1", "k"]], 2]], 1],
        )


if __name__ == "__main__":
    unittest.main()
