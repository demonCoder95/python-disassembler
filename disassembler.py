# This module contains code that implements a simple Python disassembler. It
# is based on the blog at:
# https://towardsdatascience.com/understanding-python-bytecode-e7edaae8734d
# Date: January 11, 2022

# To utilize some built-in disassembly functionality
import dis
# To process the marshalled PYC cache
import marshal
# to determine Python version
import sys

# Disassemble bytecode into opcode + oparg
def unpack_op(bytecode):
    extended_arg = 0
    # iterate over each 2 byte chunk of bytecode
    for i in range(0, len(bytecode), 2):
        # first byte is opcode
        opcode = bytecode[i]
        # detect if it is the type that takes arguments
        if opcode >= dis.HAVE_ARGUMENT:
            # extract the argument from the second byte
            # in case of extended arg, you can add it with bitwise OR
            oparg = bytecode[i+1] | extended_arg
            # see if the instruction has extended argument, and contain it
            # extended argument value is oparg * 256 in that case
            extended_arg = (oparg << 8) if opcode == dis.EXTENDED_ARG else 0
        else:
            # Otherwise, the instruction doesn't have any arg
            oparg = None
        # return a generator to be iterated upon
        yield(i, opcode, oparg)

# Map line numbers in source code to bytecode offsets using the code object
def find_linestarts(codeobj):
    # co_lnotab has the byte and line increments zipped together so, we can
    # unzip the lists with the colon operator
    # co_lnotab looks like: b_off1 l_off1 b_off2 l_off2 etc.
    # to extract b_off* only, we can do 0::2 
    # to extract l_off* only, we can do 1::2
    # this extracts all the bytecode/linenum increments 
    byte_increments = codeobj.co_lnotab[0::2]
    line_increments = codeobj.co_lnotab[1::2]
    
    # offset of first byte is 0
    byte = 0
    # offset of the first line number is in co_firstlineno attribute
    line = codeobj.co_firstlineno
    # store the offset of first instruction
    linestart_dict = {byte: line}

    # iterate over each value of increment
    for byte_incr, line_incr in zip(byte_increments, line_increments):
        # add the increment value to get byte offset of next bytecode
        byte += byte_incr
        # line increments are signed integers, so values greater than or
        # equal to 0x80 (128) are to be interpreted as negative values,
        # so we subtract 256 from the value to make it a negative value.
        if line_incr >= 0x80:
            line_incr -= 0x100
        line += line_incr
        linestart_dict[byte] = line
    return linestart_dict

# determine what is the 'value' of the argument depending on the type of
# instruction in the bytecode
def get_argvalue(offset, codeobj, opcode, oparg):
    # get all the metadata lists from the Code object
    constants = codeobj.co_consts
    varnames = codeobj.co_varnames
    names = codeobj.co_names
    cell_names = codeobj.co_cellvars + codeobj.co_freevars

    # starting value of the argument
    argval = None

    # check for string literal type
    if opcode in dis.hasconst:
        if constants is not None:
            argval = constants[oparg]
            if type(argval) == str or argval == None:
                argval = repr(argval)
    # check for 'name' type (a symbol for function/object/variable etc.)
    elif opcode in dis.hasname:
        if names is not None:
            argval = names[oparg]
    # check for 'relative jump' type, where arg value represents the offset
    # to jump to, so it's value if current offset + 2 (instruction size) +
    # argument value (number of bytes to jump).
    elif opcode in dis.hasjrel:
        argval = offset + 2 + oparg
        argval = "to " + repr(get_argvalue)
    # check for 'local' variables
    elif opcode in dis.haslocal:
        if varnames is not None:
            argval = varnames[oparg]
    # check for 'comparison' operators
    elif opcode in dis.hascompare:
        argval = dis.cmp_op[oparg]
    # check for free variables
    elif opcode in dis.hasfree:
        if cell_names is not None:
            argval = cell_names[oparg]
    
    return argval

# find all offsets in the bytecode which are jump targets
def find_labels(codeobj):
    # get the bytecode of compiled code
    bytecode = codeobj.co_code
    # initiate the empty list
    labels = []
    # iterate over every op in the bytecode
    for offset, opcode, oparg in unpack_op(bytecode):
        # check for relative jump instructions
        if opcode in dis.hasjrel:
            label = offset + 2 + oparg
        # check for absolute jump instructions
        elif opcode in dis.hasjabs:
            label = oparg
        # ignore when instructions are not jump instructions
        else:
            continue
        # store the label if it doesn't already exist
        if label not in labels:
            labels.append(label)
    return labels

# disassemble bytecode into instructions
def disassemble(c):
    # Check for type of the argument 'c' which should be a code object
    if not (hasattr(c, 'co_code')):
        raise TypeError("The argument should be a code object.")
    # initialize empty code objects list. function calls are code objects
    # themselves, so their references can be stored here to further
    # disassemble the code, recursively
    code_objects = []
    # determine all the line starts to print
    linestarts = find_linestarts(c)
    # determine all the jump targets to print
    labels = find_labels(c)
    # extract the bytecode of the parent code object
    bytecode = c.co_code
    # handle extended arguments
    # extended_arg = 0
    # iterate on each op in the bytecode
    for offset, opcode, oparg in unpack_op(bytecode):
        # determine the argument value
        argvalue = get_argvalue(offset, c, opcode, oparg)
        # check if the argument is a function call and has its own 'co_code'
        # section
        if hasattr(argvalue, 'co_code'):
            code_objects.append(argvalue)
        # determine the line number of this instruction
        line_start = linestarts.get(offset, None)
        # create format string for the disassembly
        dis_text = "{0:4}{1:2}{2:5} {3:<22} {4:3} {5}".format(
            str(line_start or ''),
            ">>" if offset in labels else "",
            offset, dis.opname[opcode],
            oparg if oparg is not None else "",
            "(" + str(argvalue) + ")" if argvalue is not None else ''
        )
        # add extra line to all non-zero line numbers + offset numbers
        if (line_start and offset):
            print()
        # print the disassembly string literal
        print(dis_text)
    # iteratively process all the child code objects as well, in the bytecode
    for oc in code_objects:
        print("\nDisassembly of {}:\n".format(oc))
        disassemble(oc)

def disassemble_pyc(filename):
    header_size = 8
    if sys.version_info >= (3, 6):
        header_size = 12
    if sys.version_info >= (3, 7):
        header_size = 16
    with open(filename, 'rb') as f:
        metadata = f.read(header_size)
        code_obj = marshal.load(f)
        disassemble(code_obj)