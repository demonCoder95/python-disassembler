# practicing Python disassembly
from dis import dis
from disassembler import disassemble, disassemble_pyc
from py_compile import compile

s = '''
a = 5
b = 'text'
def f(x):
    return x
f(5)
'''
# c = compile(s, '', 'exec')

# closures and nonlocal variables
s2 = '''
def f(x):
    z = 3
    t = 5
    def g(y):
        return t * x + y
    return g
a = 5
b = 1
h = f(a)
'''
# t is not in f.co_varnames because it's not a local variable of the function
# f. It's rather, a nonlocal variable, and is used by the closure g.
# x is included because it's the function's argument.

# testing the disassembler module
s = '''a=0
while a < 10:
    print(a)
    a += 1
'''
# c = compile(s, "", "exec")
# disassemble(c)  # the built-in dis.dis() method does the same work!

# c = compile("source.py", "source_cache.pyc")
# print(c)

disassemble_pyc("source_cache.pyc")