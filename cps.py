import unittest


GENSYM_COUNTER = iter(range(1000))


def gensym(stem="v"):
    return f"{stem}{next(GENSYM_COUNTER)}"


def cps(exp, k):
    match exp:
        case int(_) | str(_):
            return [k, exp]
        case [op, x, y] if op in ["+", "-", "*", "/"]:
            vx = gensym()
            vy = gensym()
            return cps(x, ["cont", vx,
                           cps(y, ["cont", vy,
                                   [f"${op}", vx, vy, k]])])
        case ["lambda", arg, body]:
            vk = gensym("k")
            return [k, ["fun", [arg, vk], cps(body, vk)]]
        case ["if", cond, iftrue, iffalse]:
            vcond = gensym()
            vk = gensym("k")
            return [["cont", vk,
                       cps(cond, ["cont", vcond,
                                  ["$if", vcond,
                                   cps(iftrue, vk),
                                   cps(iffalse, vk)]]),
                     ], k]
        case [func, arg]:
            vfunc = gensym()
            varg = gensym()
            return cps(func, ["cont", vfunc,
                              cps(arg, ["cont", varg,
                                        [vfunc, varg, k]])])
    raise NotImplementedError("Not implemented")


class CPSTest(unittest.TestCase):
    def setUp(self):
        global GENSYM_COUNTER
        GENSYM_COUNTER = iter(range(1000))

    def test_int(self):
        self.assertEqual(cps(1, "k"), ["k", 1])

    def test_var(self):
        self.assertEqual(cps("x", "k"), ["k", "x"])

    def test_add(self):
        self.assertEqual(
            cps(["+", 1, 2], "k"),
            [["cont", "v0", [["cont", "v1", ["$+", "v0", "v1", "k"]], 2]], 1],
        )

    def test_lambda_id(self):
        self.assertEqual(
            cps(["lambda", "x", "x"], "k"),
            ["k", ["fun", ["x", "k0"], ["k0", "x"]]],
        )

    def test_if(self):
        self.assertEqual(
            cps(["if", 1, 2, 3], "k"),
            [['cont', 'k1', [['cont', 'v0', ['$if', 'v0', ['k1', 2], ['k1', 3]]], 1]], 'k']
        )

    def test_call(self):
        self.assertEqual(
            cps(["f", 1], "k"),
            [["cont", "v0", [["cont", "v1", ["v0", "v1", "k"]], 1]], "f"]
        )


if __name__ == "__main__":
    unittest.main()
