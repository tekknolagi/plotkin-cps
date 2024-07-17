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
            return cps(x, ["cont", [vx],
                           cps(y, ["cont", [vy],
                                   [f"${op}", vx, vy, k]])])
        case ["lambda", [arg], body]:
            vk = gensym("k")
            return [k, ["fun", [arg, vk], cps(body, vk)]]
        case ["if", cond, iftrue, iffalse]:
            vcond = gensym()
            vk = gensym("k")
            return [["cont", [vk],
                       cps(cond, ["cont", [vcond],
                                  ["$if", vcond,
                                   cps(iftrue, vk),
                                   cps(iffalse, vk)]]),
                     ], k]
        case [func, arg]:
            vfunc = gensym()
            varg = gensym()
            return cps(func, ["cont", [vfunc],
                              cps(arg, ["cont", [varg],
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
            [["cont", ["v0"], [["cont", ["v1"], ["$+", "v0", "v1", "k"]], 2]], 1],
        )

    def test_add_nested(self):
        self.assertEqual(
            cps(["+", 1, ["+", 2, 3]], "k"),
            [["cont", ["v0"],
              [["cont", ["v2"],
                [["cont", ["v3"],
                  ["$+", "v2", "v3", ["cont", ["v1"], ["$+", "v0", "v1", "k"]]]],
                 3]],
               2]],
             1]
        )

    def test_sub(self):
        self.assertEqual(
            cps(["-", 1, 2], "k"),
            [["cont", ["v0"], [["cont", ["v1"], ["$-", "v0", "v1", "k"]], 2]], 1],
        )

    def test_lambda_id(self):
        self.assertEqual(
            cps(["lambda", ["x"], "x"], "k"),
            ["k", ["fun", ["x", "k0"], ["k0", "x"]]],
        )

    def test_if(self):
        self.assertEqual(
            cps(["if", 1, 2, 3], "k"),
            [["cont", ["k1"], [["cont", ["v0"], ["$if", "v0", ["k1", 2], ["k1", 3]]], 1]], "k"]
        )

    def test_if_nested_cond(self):
        self.assertEqual(
            cps(["if", ["if", 1, 2, 3], ["+", 4, 4], ["+", 5, 5]], "k"),
            # (+ 4 4) and (+ 5 5) are not duplicated
            [["cont", ["k1"],
              [["cont", ["k7"],
                [["cont", ["v6"],
                  ["$if", "v6", ["k7", 2], ["k7", 3]]], 1]],
               ["cont", ["v0"],
                ["$if", "v0",
                 [["cont", ["v2"],
                   [["cont", ["v3"],
                     ["$+", "v2", "v3", "k1"]], 4]], 4],
                 [["cont", ["v4"],
                   [["cont", ["v5"],
                     ["$+", "v4", "v5", "k1"]], 5]], 5]]]]],
             "k"]
        )

    def test_call(self):
        self.assertEqual(
            cps(["f", 1], "k"),
            [["cont", ["v0"], [["cont", ["v1"], ["v0", "v1", "k"]], 1]], "f"]
        )


def reify(k):
    rv = gensym()
    return ["cont", [rv], k(rv)]


def cps_pyfunc(exp, k):
    match exp:
        case int(_) | str(_) | ["lambda", _, _]:
            return k(cps_trivial(exp))
        case [op, x, y] if op in ["+", "-", "*", "/"]:
            return cps_pyfunc(x, lambda vx:
                        cps_pyfunc(y, lambda vy:
                            [f"${op}", vx, vy, reify(k)]))
        case [f, e]:
            return cps_pyfunc(f, lambda vf:
                        cps_pyfunc(e, lambda ve:
                             [vf, ve, reify(k)]))
        case ["if", cond, iftrue, iffalse]:
            return cps_pyfunc(cond, lambda vcond:
                                [f"$if", vcond,
                                 cps_pyfunc(iftrue, k),
                                 cps_pyfunc(iffalse, k)])
    raise NotImplementedError((exp, k))


def dedup(cont, k):
    if isinstance(cont, str):
        return k(cont)
    return [reify(k), cont]


def cps_cont(exp, c):
    match exp:
        case int(_) | str(_) | ["lambda", _, _]:
            return [c, cps_trivial(exp)]
        case [op, x, y] if op in ["+", "-", "*", "/"]:
            return cps_pyfunc(x, lambda vx:
                        cps_pyfunc(y, lambda vy:
                            [f"${op}", vx, vy, c]))
        case [f, e]:
            return cps_pyfunc(f, lambda vf:
                        cps_pyfunc(e, lambda ve:
                            [vf, ve, c]))
        case ["if", cond, iftrue, iffalse]:
            return dedup(c, lambda vc:
                         cps_pyfunc(cond, lambda vcond:
                             [f"$if", vcond,
                              cps_cont(iftrue, vc),
                              cps_cont(iffalse, vc)]))
    raise NotImplementedError((exp, c))


def cps_trivial(exp):
    match exp:
        case ["lambda", [var], expr]:
            k = gensym("k")
            return ["fun", [var, k], cps_cont(expr, k)]
        case str(_) | int(_):
            return exp
    raise NotImplementedError(exp)


class MetaCPSTest(unittest.TestCase):
    def setUp(self):
        global GENSYM_COUNTER
        GENSYM_COUNTER = iter(range(1000))

    def test_int(self):
        self.assertEqual(cps_cont(1, "k"), ["k", 1])

    def test_var(self):
        self.assertEqual(cps_cont("x", "k"), ["k", "x"])

    def test_add(self):
        self.assertEqual(
            cps_cont(["+", 1, 2], "k"),
            ["$+", 1, 2, "k"]
        )

    def test_add_nested(self):
        self.assertEqual(
            cps_cont(["+", 1, ["+", 2, 3]], "k"),
            ["$+", 2, 3, ["cont", ["v0"], ["$+", 1, "v0", "k"]]]
        )

    def test_sub(self):
        self.assertEqual(
            cps_cont(["-", 1, 2], "k"),
            ["$-", 1, 2, "k"]
        )

    def test_lambda_id(self):
        self.assertEqual(
            cps_cont(["lambda", ["x"], "x"], "k"),
            ["k", ["fun", ["x", "k0"], ["k0", "x"]]]
        )

    def test_if(self):
        self.assertEqual(
            cps_cont(["if", 1, 2, 3], "k"),
            ["$if", 1, ["k", 2], ["k", 3]]
        )

    def test_if_cont_is_not_duplicated(self):
        v = gensym()
        k = ["cont", [v], ["print", v]]
        self.assertEqual(
            cps_cont(["if", 1, 2, 3], k),
            [["cont", ["v1"], ["$if", 1, ["v1", 2], ["v1", 3]]],
             ["cont", ["v0"], ["print", "v0"]]]
        )

    def test_if_nested_cond(self):
        self.assertEqual(
            cps_cont(["if", ["if", 1, 2, 3], ["+", 4, 4], ["+", 5, 5]], "k"),
            # TODO(max): Figure out what to do about the code duplication of
            # the iftrue and iffalse
            ["$if", 1,
             ["$if", 2, ["$+", 4, 4, "k"], ["$+", 5, 5, "k"]],
             ["$if", 3, ["$+", 4, 4, "k"], ["$+", 5, 5, "k"]]]
        )

    def test_call(self):
        self.assertEqual(
            cps_cont(["f", 1], "k"),
            ["f", 1, "k"]
        )


def triv(cps, env):
    match cps:
        case int(_):
            return cps
        case str(_):
            return env[cps]
        case ["fun", [argname, kname], body]:
            return cps
        case ["cont", [argname], body]:
            return cps
        case FunctionType():
            return cps
    raise NotImplementedError(cps)


def unpack_func(func):
    match func:
        case ["fun", [argname, kname], body]:
            return argname, kname, body
    raise NotImplementedError(func)


def unpack_cont(cont):
    match cont:
        case ["cont", [argname], body]:
            return argname, body
    raise NotImplementedError(cont)


def apply_cont(cont, arg, env):
    match cont:
        case ["cont", [argname], body]:
            interp(body, {**env, argname: arg})
            return
        case FunctionType():
            cont(arg)
            return
    raise NotImplementedError(cont)


def interp(cps, env):
    match cps:
        case ["$+", x, y, k]:
            varg = triv(x, env) + triv(y, env)
            apply_cont(triv(k, env), varg, env)
            return
        case ["$-", x, y, k]:
            varg = triv(x, env) - triv(y, env)
            apply_cont(triv(k, env), varg, env)
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
            apply_cont(vcont, varg, env)
            return
        case [func, arg, k]:
            vfunc = triv(func, env)
            varg = triv(arg, env)
            vk = triv(k, env)
            if isinstance(vfunc, FunctionType):
                vfunc(varg, env, vk)
                return
            argname, kname, body = unpack_func(vfunc)
            interp(body, {**env, argname: varg, kname: vk})
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

    def test_add_nested(self):
        _set, _get = self._return()
        interp(["$+", 1, 2, ["cont", ["v0"], ["$+", "v0", 3, "k"]]], {"k": _set})
        self.assertEqual(_get(), 6)

    def test_sub(self):
        _set, _get = self._return()
        interp(["$-", 1, 2, "k"], {"k": _set})
        self.assertEqual(_get(), -1)

    def test_sub_nested(self):
        _set, _get = self._return()
        interp(["$-", 1, 2, ["cont", ["v0"], ["$-", "v0", 3, "k"]]], {"k": _set})
        self.assertEqual(_get(), -4)

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
        exp = [["cont", ["v0"], [["cont", ["v1"], ["v0", "v1", "k"]], 1]], "f"]
        interp(exp, {"f": lambda x, env, k: apply_cont(k, x+1, env), "k": _set})
        self.assertEqual(_get(), 2)

    def test_call_reentrant(self):
        _set, _get = self._return()
        exp = [["cont", ["v0"], [["cont", ["v1"], ["v0", "v1", "k"]], 1]], "f"]
        interp(exp, {"f": lambda x, env, k: apply_cont(k, x+1, env),
                     "k": ["cont", ["x"], [_set, "x"]]})
        self.assertEqual(_get(), 2)


class EndToEndTests(unittest.TestCase):
    @staticmethod
    def _return():
        result = None
        def _set(x):
            nonlocal result
            result = x
        def _get():
            return result
        return _set, _get

    def _interp(self, exp):
        cps0 = cps(exp, "k")
        cps1 = cps_cont(exp, "k")
        _set0, _get0 = self._return()
        interp(cps0, {"k": _set0})
        _set1, _get1 = self._return()
        interp(cps1, {"k": _set1})
        res0 = _get0()
        res1 = _get1()
        self.assertEqual(res0, res1)
        return res0

    def test_int(self):
        self.assertEqual(self._interp(1), 1)

    def test_add(self):
        self.assertEqual(self._interp(["+", 1, 2]), 3)

    def test_add_nested(self):
        self.assertEqual(self._interp(["+", 1, ["+", 2, 3]]), 6)

    def test_if_true(self):
        self.assertEqual(self._interp(["if", 1, 2, 3]), 2)

    def test_if_false(self):
        self.assertEqual(self._interp(["if", 0, 2, 3]), 3)

    def test_call_lambda_id(self):
        self.assertEqual(self._interp([["lambda", ["x"], "x"], 123]), 123)

    def test_call_lambda_add(self):
        exp = [[["lambda", ["x"], ["lambda", ["y"], ["+", "x", "y"]]], 3], 4]
        self.assertEqual(self._interp(exp), 7)


if __name__ == "__main__":
    __import__("sys").modules["unittest.util"]._MAX_LENGTH = 999999999
    unittest.main()
