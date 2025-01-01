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


def F(exp, k):
    if isinstance(exp, list) and exp[0] == "+":
        assert all(isinstance(arg, (int,str)) for arg in exp[1:]), "Arguments must be trivial"
    match exp:
        case int(_) | str(_) | ["+", *_] if isinstance(k, str):
            return [k, exp]
        case int(_) | str(_) | ["+", *_]:
            assert k[0] == "l_cont", "Expected continuation in E"
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
            assert k[0] == "l_cont", "Expected continuation in if"
            _, [k_arg], k_body = k
            kvar = gensym("k")
            return ["letrec", [[kvar, ["l_jump", [k_arg], k_body]]],
                    ["if", test, F(conseq, kvar), F(alt, kvar)]]
        case _:
            raise NotImplementedError(f"not implemented: {exp}")


class CPSConversionTests(unittest.TestCase):
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
                         ["letrec", [["k0", ["l_jump", ["x"], "k_body"]]],
                          ["if", 1, ["k0", 2], ["k0", 3]]])


if __name__ == "__main__":
    unittest.main()
