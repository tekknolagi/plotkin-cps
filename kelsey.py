import unittest


GENSYM_COUNTER = iter(range(1000))


def gensym(stem="v"):
    return f"{stem}{next(GENSYM_COUNTER)}"


class UseGensym(unittest.TestCase):
    def setUp(self):
        global GENSYM_COUNTER
        GENSYM_COUNTER = iter(range(1000))


"""
Scheme grammar:
M ::= E
    | (E E*)
    | (if E M M)
    | (let ((x M)) M)
E ::= x | (+ E E) | ...
P ::= (lambda (x*) M)
where x are variables

To simplify the CPS algorithm the source language is restricted to allow
non-trivial expressions only in tail position or as the bound value in a let.
In an actual compiler the source program could be put in this form either by a
pre-pass or as part of a more complex CPS algorithm. We also assume that every
identifier is unique.

As we are not interested in interprocedural analysis we will treat each l_proc
as a separate program (here we depend on the assumption that explicit
environments have been introduced to take care of lexical scoping for any
nested l_proc's).
"""


def alphatise_(exp, env):
    match exp:
        case int(_):
            return exp
        case str(_):
            return env[exp]
        case [op, *args] if op in ("if", "+",):
            return [op, *(alphatise_(arg, env) for arg in args)]
        case ["let", [[x, value]], body]:
            name = gensym(x)
            return ["let", [[name, alphatise_(value, env)]],
                    alphatise_(body, {**env, x: name})]
        case ["lambda", [*args], body]:
            new_args = [gensym(arg) for arg in args]
            updates = dict(zip(args, new_args))
            return ["lambda", [new_args], alphatise_(body, {**env, **updates})]
        case list(_):
            return [alphatise_(e, env) for e in exp]
        case _:
            raise NotImplementedError(f"not implemented: {exp}")


def alphatise(exp):
    return alphatise_(exp, {})


class AlphatiseTests(UseGensym):
    def test_int(self):
        self.assertEqual(alphatise(5), 5)

    def test_add(self):
        self.assertEqual(alphatise_(["+", "a", "b"], {"a": "x", "b": "y"}),
                         ["+", "x", "y"])

    def test_name_not_in_env(self):
        with self.assertRaises(KeyError):
            alphatise_("x", {})

    def test_name_in_env(self):
        self.assertEqual(alphatise_("x", {"x": "y"}), "y")

    def test_if(self):
        exp = ["if", "a", "b", "c"]
        self.assertEqual(alphatise_(exp, {"a": "x", "b": "y", "c": "z"}),
                         ["if", "x", "y", "z"])

    def test_let_not_in_env(self):
        exp = ["let", [["x", 1]], "x"]
        self.assertEqual(alphatise_(exp, {}), ["let", [["x0", 1]], "x0"])

    def test_let_in_env(self):
        exp = ["let", [["x", 1]], "x"]
        self.assertEqual(alphatise_(exp, {"x": "a"}), ["let", [["x0", 1]], "x0"])

    def test_lambda_not_in_env(self):
        exp = ["lambda", ["x", "y"], "x"]
        self.assertEqual(alphatise_(exp, {}), ["lambda", [["x0", "y1"]], "x0"])

    def test_lambda_in_env(self):
        exp = ["lambda", ["x", "y"], "x"]
        self.assertEqual(alphatise_(exp, {"x": "a"}), ["lambda", [["x0", "y1"]], "x0"])

    def test_app(self):
        self.assertEqual(
           alphatise_(["f", "a", "b"], {"f": "g", "a": "x", "b": "y"}),
           ["g", "x", "y"],
        )


"""
CPS grammar:
M' ::= (E E* C)
     | (k E)
     | (if E M' M')
     | (let ((x E)) M')
     | (letrec ((x P')) M')
C ::= k | (l_cont (x) M')
P' ::= (l_proc (x* k) M') | (l_jump (x*) M')
where x, k are variables
"""


def V(exp):
    match exp:
        case ["lambda", [*args], body]:
            k = gensym("k")
            return ["l_proc", [*args, k], F(body, k)]
        case _:
            raise TypeError(f"not a procedure: {exp}")


def is_trivial(exp):
    return isinstance(exp, (int, str))


def F(exp, k):
    if isinstance(exp, list) and exp[0] == "+":
        assert all(is_trivial(arg) for arg in exp[1:]), "Arguments must be trivial"
    if isinstance(k, list):
        assert k[0] == "l_cont"
    else:
        assert isinstance(k, str)
    match exp:
        case int(_) | str(_) | ["+", *_] if isinstance(k, str):
            if k[0] == "$":
                # Letrec-bound jmp continuation
                return ["$jmp", k, exp]
            return ["$call-cont", k, exp]
        case int(_) | str(_) | ["+", *_]:
            _, [k_arg], k_body = k
            return ["let", [[k_arg, exp]], k_body]
        case ["let", [[x, value]], body]:
            # The paper just has a lambda, which is shorthand or a typo. The
            # continuation argument to F can only be a variable or l_cont.
            return F(value, ["l_cont", x, F(body, k)])
        case ["if", test, conseq, alt] if isinstance(k, str):
            return ["if", test, F(conseq, k), F(alt, k)]
        case ["if", test, conseq, alt]:
            _, [k_arg], k_body = k
            # $ indicates that it's bound by letrec, which is a terrible way to
            # do this, but I want to keep the function looking as similar to
            # Kelsey's paper as possible (for now). This is needed for the
            # function call case, which has two cases: 1) letrec-bound conts
            # and 2) other conts.
            kvar = gensym("$k")
            return ["letrec", [[kvar, ["l_jump", [k_arg], k_body]]],
                    ["if", test, F(conseq, kvar), F(alt, kvar)]]
        case [fn, *args] if isinstance(k, str) and k[0] == "$":
            # Letrec-bound jmp continuation
            v = gensym()
            assert is_trivial(fn), "Function must be trivial"
            assert all(is_trivial(arg) for arg in args), "Arguments must be trivial"
            # TODO(max): Convert to call to F to make sure this $jmp logic is
            # in one place?
            return ["let", [[v, exp]], ["$jmp", k, v]]
        case [fn, *args]:
            assert is_trivial(fn), "Function must be trivial"
            assert all(is_trivial(arg) for arg in args), "Arguments must be trivial"
            return [fn, *args, k]
        case _:
            raise NotImplementedError(f"not implemented: {exp}")


class CPSConversionTests(UseGensym):
    def test_int(self):
        self.assertEqual(F(42, "k"), ["$call-cont", "k", 42])
        self.assertEqual(F(42, ["l_cont", ["x"], "k_body"]),
                         ["let", [["x", 42]], "k_body"])

    def test_add(self):
        exp = ["+", 1, 2]
        self.assertEqual(F(exp, "k"), ["$call-cont", "k", exp])
        self.assertEqual(F(exp, ["l_cont", ["x"], "k_body"]),
                         ["let", [["x", exp]], "k_body"])

    def test_let(self):
        exp = ["let", [["x", 42]], ["+", "x", 1]]
        self.assertEqual(F(exp, "k"),
                         ["let", [["x", 42]], ["$call-cont", "k", ["+", "x", 1]]])

    def test_if(self):
        exp = ["if", 1, 2, 3]
        self.assertEqual(F(exp, "k"),
                         ["if", 1,
                          ["$call-cont", "k", 2],
                          ["$call-cont", "k", 3]])
        self.assertEqual(F(exp, ["l_cont", ["x"], "k_body"]),
                         ["letrec", [["$k0", ["l_jump", ["x"], "k_body"]]],
                          ["if", 1, ["$jmp", "$k0", 2], ["$jmp", "$k0", 3]]])

    def test_app_letrec_cont(self):
        exp = ["f", 1, 2]
        self.assertEqual(F(exp, "$k0"),
                         ["let", [["v0", ["f", 1, 2]]],
                          ["$jmp", "$k0", "v0"]])

    def test_app_cont(self):
        exp = ["f", 1, 2]
        self.assertEqual(F(exp, "k0"),
                         ["f", 1, 2, "k0"])
        self.assertEqual(F(exp, ["l_cont", ["x"], "k_body"]),
                         ["f", 1, 2, ["l_cont", ["x"], "k_body"]])

    def test_if_app(self):
        exp = ["if", 1, ["f", 2], ["g", 3]]
        self.assertEqual(F(exp, ["l_cont", ["x"], "k_body"]),
                         ["letrec", [["$k0", ["l_jump", ["x"], "k_body"]]],
                          ["if", 1,
                           ["let", [["v1", ["f", 2]]],
                            ["$jmp", "$k0", "v1"]],
                           ["let", [["v2", ["g", 3]]],
                            ["$jmp", "$k0", "v2"]]]])

    def test_lambda(self):
        exp = ["lambda", ["x"], ["+", "x", 1]]
        self.assertEqual(V(exp),
                         ["l_proc", ["x", "k0"],
                          ["$call-cont", "k0", ["+", "x", 1]]])


"""
SSA grammar:
P ::= proc(x*) { B L* }
L ::= l: I* B
I ::= x <- phi(E*);
B ::= x <- E; B
    | x <- E(E*); B
    | goto l_i
    | return E;
    | return E(E*);
    | if E then B else B
E ::= x | E + E | ...
where x are variables, l are labels

The l_jump's in the program are ignored when found by G. Each l_jump is instead
lifted up to become a labeled block in the SSA procedure. The arguments to the
l_jump's, which are also ignored by G, become the arguments to the phi function
that defines the value of the corresponding variable in the SSA program.
"""


# TODO(max): Collect the l_jump and their arguments and lift to blocks


def G(cps) -> list:
    match cps:
        case ["let", [[x, value]], body]:
            return [[x, "<-", value], *G(body)]
        case ["$call-cont", k, exp]:
            return [["return", exp]]
        case ["$jmp", k, exp]:
            return [["goto", k]]
        case ["if", test, conseq, alt]:
            return [["if", test, G(conseq), G(alt)]]
        case ["letrec", [*_], body]:
            return G(body)
        case _:
            raise NotImplementedError(f"not implemented: {cps}")


def Gproc(cps):
    match cps:
        case ["l_proc", [*args], body]:
            return ["proc", args, G(body)]
        case _:
            raise TypeError(f"not a procedure: {cps}")


def Gjump(j, cps):
    match cps:
        case ["l_jump", [*args], body]:
            raise NotImplementedError("l_jump not implemented")
        case _:
            raise TypeError(f"not a jump: {cps}")


class SSAConversionTests(unittest.TestCase):
    def test_let(self):
        cps = ["let", [["x", 42]], ["$call-cont", "k", ["+", "x", 1]]]
        self.assertEqual(G(cps), [
            ["x", "<-", 42],
            ["return", ["+", "x", 1]]
        ])

    def test_call_cont(self):
        cps = ["$call-cont", "k", 42]
        self.assertEqual(G(cps), [["return", 42]])

    def test_if(self):
        cps = ["if", 1, ["$call-cont", "k", 2], ["$call-cont", "k", 3]]
        self.assertEqual(G(cps), [["if", 1, [["return", 2]], [["return", 3]]]])

    def test_if_app(self):
        cps = F(["if", 1, ["f", 2], ["g", 3]], ["l_cont", ["x"], "k_body"])
        self.assertEqual(G(cps),
                         [["if", 1,
                           [["v1", "<-", ["f", 2]],
                            ["goto", "$k0"]],
                           [["v2", "<-", ["g", 3]],
                            ["goto", "$k0"]]]])

    def test_lambda(self):
        cps = ["l_proc", ["x", "k0"], ["$call-cont", "k0", ["+", "x", 1]]]
        self.assertEqual(Gproc(cps),
                         ["proc", ["x", "k0"], [
                             ["return", ["+", "x", 1]],
                         ]])


# TODO(max): Convert out of SSA with parallel assignments and emit C


if __name__ == "__main__":
    __import__("sys").modules["unittest.util"]._MAX_LENGTH = 999999999
    unittest.main()
