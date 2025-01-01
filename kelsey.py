import unittest


GENSYM_COUNTER = iter(range(1000))


def gensym(stem="v"):
    return f"{stem}{next(GENSYM_COUNTER)}"


"""
Scheme grammar:
M ::=   E
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


"""
CPS grammar:
M' ::=   (E E* C)
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
            raise RuntimeError(f"not a procedure: {exp}")


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
            return [k, exp]
        case int(_) | str(_) | ["+", *_]:
            _, [k_arg], k_body = k
            return ["let", [[k_arg, exp]], k_body]
        case ["let", [[x, value]], body]:
            # TODO(max): Double check l_cont is right. The paper just has a
            # lambda, which doesn't seem right--C is only either l_cont or
            # l_jump.
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
            # Letrec-bound continuation
            v = gensym()
            assert is_trivial(fn), "Function must be trivial"
            assert all(is_trivial(arg) for arg in args), "Arguments must be trivial"
            return ["let", [[v, exp]], ["jmp", k, v]]
        case [fn, *args]:
            assert is_trivial(fn), "Function must be trivial"
            assert all(is_trivial(arg) for arg in args), "Arguments must be trivial"
            return [fn, *args, k]
        case _:
            raise NotImplementedError(f"not implemented: {exp}")


class UseGensym(unittest.TestCase):
    def setUp(self):
        global GENSYM_COUNTER
        GENSYM_COUNTER = iter(range(1000))


class CPSConversionTests(UseGensym):
    def test_int(self):
        self.assertEqual(F(42, "k"), ["k", 42])
        self.assertEqual(F(42, ["l_cont", ["x"], "k_body"]),
                         ["let", [["x", 42]], "k_body"])

    def test_add(self):
        exp = ["+", 1, 2]
        self.assertEqual(F(exp, "k"), ["k", exp])
        self.assertEqual(F(exp, ["l_cont", ["x"], "k_body"]),
                         ["let", [["x", exp]], "k_body"])

    def test_let(self):
        exp = ["let", [["x", 42]], ["+", "x", 1]]
        self.assertEqual(F(exp, "k"),
                         ["let", [["x", 42]], ["k", ["+", "x", 1]]])

    def test_if(self):
        exp = ["if", 1, 2, 3]
        self.assertEqual(F(exp, "k"), ["if", 1, ["k", 2], ["k", 3]])
        self.assertEqual(F(exp, ["l_cont", ["x"], "k_body"]),
                         ["letrec", [["$k0", ["l_jump", ["x"], "k_body"]]],
                          ["if", 1, ["$k0", 2], ["$k0", 3]]])

    def test_app_letrec_cont(self):
        exp = ["f", 1, 2]
        self.assertEqual(F(exp, "$k0"),
                         ["let", [["v0", ["f", 1, 2]]],
                          ["jmp", "$k0", "v0"]])

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
                            ["jmp", "$k0", "v1"]],
                           ["let", [["v2", ["g", 3]]],
                            ["jmp", "$k0", "v2"]]]])

    def test_lambda(self):
        exp = ["lambda", ["x"], ["+", "x", 1]]
        self.assertEqual(V(exp),
                         ["l_proc", ["x", "k0"], ["k0", ["+", "x", 1]]])


if __name__ == "__main__":
    unittest.main()
