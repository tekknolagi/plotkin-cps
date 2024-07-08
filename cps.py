import unittest
from types import FunctionType


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


def triv(cps, env):
    match cps:
        case int(_):
            return cps
        case str(_):
            return env[cps]
        case ["fun", [argname, kname], body]:
            return cps
        case ["cont", argname, body]:
            return cps
    raise NotImplementedError(cps)


def unpack_func(func):
    match func:
        case ["fun", [argname, kname], body]:
            return argname, kname, body
    raise NotImplementedError(func)


def unpack_cont(cont):
    match cont:
        case ["cont", argname, body]:
            return argname, body
    raise NotImplementedError(cont)


def interp(cps, env):
    match cps:
        case ["$+", x, y, k]:
            triv(k, env)(triv(x, env) + triv(y, env))
            return
        case ["fun", [arg, k], body]:
            raise NotImplementedError(cps)
        case ["$if", cond, iftrue, iffalse]:
            vcond = triv(cond, env)
            if vcond:
                interp(iftrue, env)
            else:
                interp(iffalse, env)
            return
        case [cont, arg]:
            vcont = triv(cont, env)
            varg = triv(arg, env)
            if isinstance(vcont, FunctionType):
                vcont(varg)
                return
            argname, body = unpack_cont(vcont)
            interp(body, {**env, argname: varg})
            return
        case [func, arg, k]:
            vfunc = triv(func, env)
            varg = triv(arg, env)
            if isinstance(vfunc, FunctionType):
                vfunc(varg, triv(k, env))
                return
            argname, kname, body = unpack_func(vfunc)
            interp(body, {**env, argname: varg, kname: k})
            return
    raise NotImplementedError(cps)


class CPSInterpTests(unittest.TestCase):
    @staticmethod
    def _return():
        result = None
        def _set(x):
            nonlocal result
            result = x
        def _get():
            return result
        return _set, _get

    def test_ret(self):
        _set, _get = self._return()
        interp(["k", 1], {"k": _set})
        self.assertEqual(_get(), 1)

    def test_add(self):
        _set, _get = self._return()
        interp(["$+", 1, 2, "k"], {"k": _set})
        self.assertEqual(_get(), 3)

    def test_lambda_id(self):
        _set, _get = self._return()
        interp(["k", ["fun", ["x", "k0"], ["k0", "x"]]], {"k": _set})
        self.assertEqual(_get(), ["fun", ["x", "k0"], ["k0", "x"]])

    def test_if_true(self):
        _set, _get = self._return()
        interp(["$if", 1, ["k1", 2], ["k1", 3]], {"k1": _set})
        self.assertEqual(_get(), 2)

    def test_if_false(self):
        _set, _get = self._return()
        interp(["$if", 0, ["k1", 2], ["k1", 3]], {"k1": _set})
        self.assertEqual(_get(), 3)

    def test_call(self):
        _set, _get = self._return()
        exp = [["cont", "v0", [["cont", "v1", ["v0", "v1", "k"]], 1]], "f"]
        interp(exp, {"f": lambda x, k: k(x + 1), "k": _set})
        self.assertEqual(_get(), 2)


if __name__ == "__main__":
    unittest.main()
