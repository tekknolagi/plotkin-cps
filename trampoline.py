# Lean on Python refcounting to demonstrate trampoline structure lifetimes.

trampoline_id = 0

class Trampoline:
    def __init__(self, f):
        self.f = f
        global trampoline_id
        self.id = trampoline_id
        trampoline_id += 1
        print("alloc", self.id)

    def __call__(self):
        print("call", self.id)
        return self.f()

    def __del__(self):
        print("del", self.id)

def trampoline(f, *args):
    v = f(*args)
    while isinstance(v, Trampoline):
        v = v()
    return v

def fact_cps_thunked(n, cont):
    if n == 0:
        return cont(1)
    else:
        return Trampoline(lambda: fact_cps_thunked(
                         n - 1,
                         lambda value: Trampoline(lambda: cont(n * value))))

print(trampoline(fact_cps_thunked, 0, lambda x: x))
