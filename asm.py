"""Usage:
   registers: r0, r1, r2, ... r15. (r16 is stack pointer) 
   label: define label with `Label(name)`, then use `tag(label_object)` to label an instruction
          use `ref(label_object)` to refer to label
   instructions: for example, instruction `mov`, use it like `mov(B, r1, r2)`, `B` is the modifier,
                 where you could use B(byte, 8 bit), S(short, 16bit), D(dword, 32 bit), Q(qword, bit)
"""

import struct
import ctypes

def size2modifier(size):
    global inses
    if size == 64:
        mod = 64
    elif size == 32:
        mod = 48
    elif size == 16:
        mod = 32
    elif size == 8:
        mod = 16
    else:
        raise Exception('invalid size {} for instruction mov at #{}'.format(size, len(inses)))
    return mod

def pack64(s):
    return struct.pack('<Q', s)

def pack32(s):
    return struct.pack('<I', s)

def pack16(s):
    return struct.pack('<H', s)

def pack8(s):
    return struct.pack('<B', s)

def signed2unsigned(x, size):
    if size == 8:
        return ctypes.c_uint8(x).value
    elif size == 16:
        return ctypes.c_uint16(x).value
    elif size == 32:
        return ctypes.c_uint32(x).value
    elif size == 64:
        return ctypes.c_uint64(x).value

def pack(val, size):
    if size == 64:
        return pack64(val)
    elif size == 32:
        return pack32(val)
    elif size == 16:
        return pack16(val)
    elif size == 8:
        return pack8(val)

class Reg:
    def __init__(self, name):
        r = int(name[1:])
        assert r <= 0x11, 'reg is only 0 - {}'.format(0x11)
        self.name = name
        self.num = r

    def make(self, size):
        return pack8(self.num)

    def __str__(self):
        return self.name

class Mem:
    def __init__(self, addr):
        self.addr = addr

    def make(self, size):
        if type(self.addr) is Imm:
            return self.addr.make(size)
        elif type(self.addr) is Reg:
            return self.addr.make(size)
    
    def __str__(self):
        return 'Mem({})'.format(self.addr)

class StackMem:
    def __init__(self, addr):
        self.addr = addr
    
    def make(self):
        return self.addr.make(size) 

    def __str__(self):
        return 'StackMem({})'.format(self.addr)

class Imm:
    def __init__(self, val):
        self.val = val

    def make(self, size):
        return pack(self.val, size)

    def __str__(self):
        return 'Imm({})'.format(hex(self.val))

class LabelRef:
    def __init__(self, name):
        self.name = name

    def make(self, size):
        # temp value
        return pack(0, size)

    def __str__(self):
        return 'L:{}'.format(self.name)

class Label:
    def __init__(self, name):
        self.name = name
        self.use_sites = []
        self.def_site = None
        self.resolved = None

    def tag(self, def_site):
        self.def_site = def_site

    def make(self, code):
        return b''

    def ref(self, ins_idx):
        self.use_sites.append(ins_idx)
        return LabelRef(self.name)

    def resolve(self):
        global inses
        byte_offset = 0
        for i in range(self.def_site):
            byte_offset += len(inses[i].bytecode)
        self.resolved = byte_offset

    def rewrite(self):
        global inses
        for use in self.use_sites:
            offset = 0
            for i in range(use + 1):
                offset += len(inses[i].bytecode)
            ins = inses[use]
            dis = self.resolved - offset
            ins.dest = Imm(signed2unsigned(self.resolved - offset, ins.size))
            ins.make(ins.CODE)

class Exit:
    CODE = 0
    def __init__(self):
        self.bytecode = bytes([self.CODE])

    def make(self, code):
        return self.bytecode

    def __str__(self):
        return "exit"

def binop_mode(dest, src, size):
    if type(dest) is Reg and type(src) is Reg:
        mode = 0
    elif type(dest) is Reg and type(src) is Mem:
        if type(src.addr) is Imm:
            mode = 1
        elif type(src.addr) is Reg:
            mode = 0xc
    elif type(dest) is Mem and type(src) is Reg:
        if type(dest.addr) is Reg:
            mode = 0xb
        elif type(dest) is Imm:
            mode = 2
    elif type(dest) is Reg and type(src) is StackMem:
        if type(src.addr) is Imm:
            mode = 3
        elif type(src.addr) is Reg:
            mode = 0xe
    elif type(dest) is StackMem and type(src) is Reg:
        if type(dest.addr) is Imm:
            mode = 4
        elif type(dest.addr) is Reg:
            mode = 0xd
    elif type(dest) is Reg and type(src) is Imm:
        mode = 5
    return mode | size2modifier(size)


class BinOp:
    def __init__(self, dest, src, size):
        self.dest = dest
        self.src = src
        self.size = size
        self.bytecode = None

    def make(self, code):
        mode = binop_mode(self.dest, self.src, self.size)
        self.bytecode = bytes([code])
        self.bytecode += bytes([mode])
        self.bytecode += self.dest.make(self.size)
        self.bytecode += self.src.make(self.size)
        return self.bytecode

    def __str__(self):
        return '{} {}, {}'.format(type(self).__name__, self.dest, self.src)

class Mov(BinOp):
    CODE = 1

class Add(BinOp):
    CODE = 2
    
class Sub(BinOp):
    CODE = 3

class Mul(BinOp):
    CODE = 4

class Div(BinOp):
    CODE = 5

class Mod(BinOp):
    CODE = 6

class Xor(BinOp):
    CODE = 7

class Or(BinOp):
    CODE = 8

class And(BinOp):
    CODE = 9

class Shl(BinOp):
    CODE = 10

class Shr(BinOp):
    CODE = 11

def unop_mode(dest, size):
    if type(dest) is Reg:
        mode = 6
    elif type(dest) is Imm:
        mode = 7
    elif type(dest) is Mem:
        mode = 8
    elif type(dest) is LabelRef:
        # NOTE: relative jump only
        mode = 7

    return mode | size2modifier(size)
    
class UnOp:
    def __init__(self, dest, size):
        self.dest = dest
        self.size = size
        self.bytecode = None
        self.resolved = None

    def make(self, code):
        mode = unop_mode(self.dest, self.size)
        
        self.bytecode = bytes([code])
        self.bytecode += bytes([mode])
        self.bytecode += self.dest.make(self.size)
        return self.bytecode

    def __str__(self):
        return '{} {}'.format(type(self).__name__, self.dest)

class Not(UnOp):
    CODE = 12

class Pop(UnOp):
    CODE = 13

class Push(UnOp):
    CODE = 14

class Call(UnOp):
    CODE = 0x10

class Ret:
    CODE = 0x11

    def make(self, code):
        self.bytecode = bytes([code])
    def __str__(self):
        return "ret"

class Cmp(BinOp):
    CODE = 0x12

class Jmp(UnOp):
    CODE = 0x13

class Je(UnOp):
    CODE = 0x14

class Jne(UnOp):
    CODE = 0x15
    
class Jg(UnOp):
    CODE = 0x16

class Jl(UnOp):
    CODE = 0x18

class Jge(UnOp):
    CODE = 0x19
    
class Ja(UnOp):
    CODE = 0x1a
    
class Jnbe(UnOp):
    CODE = 0x1b
    
class Jb(UnOp):
    CODE = 0x1c
    
class Jc(UnOp):
    CODE = 0x1d

inses = []
bytecodes = []
labels = []



Q = 64
D = 32
S = 16
B = 8

BINOPS = [
    'mov',
    'add',
    'sub',
    'mul',
    'div',
    'mod',
    'xor',
    'or',
    'and',
    'shl',
    'shr',
    'cmp',
]
def binop_ins(insname, mod, x, y):
    global inses
    class_name = insname.capitalize()
    inses.append(globals()[class_name](x, y, mod))

for op in BINOPS:
    def inner(op):
        globals()[op] = lambda mod, x, y: binop_ins(op, mod, x, y)
    inner(op)


UOPS = [
    'push',
    'pop',
    'nop',
    'jmp',
    'call',
    'je',
    'jne',
    'jg',
    'jl',
    'jge',
    'ja',
    'jnbe',
    'jb',
    'jc'
]

def uop_ins(insname, mod, x):
    global inses
    class_name = insname.capitalize()
    inses.append(globals()[class_name](x, mod))

for op in UOPS:
    def inner(op):
        globals()[op] = lambda mod, x: uop_ins(op, mod, x)
    inner(op)

NOOPS = [
    'exit'
    'ret'
]

def exit():
    global inses
    inses.append(Exit())

def ret():
    global inses
    inses.append(Ret())

def tag(label):
    global inses, labels
    #inses.append(label.tag(len(inses)))
    label.tag(len(inses))
    labels.append(label)

def ref(label):
    global inses
    return label.ref(len(inses))


def assemble():
    global inses, labels

    # phase 1: generate inses without label resolved
    for ins in inses:
        ins.make(ins.CODE)

    # phase 2: resolve labels
    for label in labels:
        label.resolve()

    # phase 3: adjust bytecodes
    for label in labels:
        label.rewrite()

    # phase 4: propagate all bytecode

    bytecode = b''
    for ins in inses:
        print(len(bytecode), ins)
        bytecode += ins.bytecode
    return bytecode

for i in range(0x11 + 1):
    name = 'r{}'.format(i)
    globals()[name] = Reg(name)



def main_bubble():
    loop = Label('loop')
    

    big_loop = Label('big_loop')
    loop = Label('loop')
    skip = Label('skip')

    mov(B, r8, Imm(8))
    mov(B, r0, Imm(100))
    mov(B, r7, Imm(1))

    tag(big_loop)
    xor(Q, r1, r1)
    mov(Q, r2, r8)
    
    tag(loop)
    mov(Q, r3, Mem(r1))
    mov(Q, r4, Mem(r2))
    cmp(Q, r3, r4)

    jl(B, ref(skip))
    mov(Q, Mem(r1), r4)
    mov(Q, Mem(r2), r3)

    tag(skip)
    add(Q, r1, r8)
    add(Q, r2, r8)
    cmp(S, r2, Imm(800))

    jl(B, ref(loop)) 
    sub(Q, r0, r7)

    jg(B, ref(big_loop))

    exit()


    with open('test_asm', 'wb') as f:
        f.write(assemble())

def main_quicksort():

    # call convention
    # r0: ret
    # r1-r2: args

    quicksort = Label("quicksort")
    end_qsort = Label("end_qsort")
    loop_check = Label("loop_check")
    loop_begin = Label("loop_begin")
    loop1_end = Label("loop1_end")
    loop1_begin = Label("loop1_begin")
    loop2_end = Label("loop2_end")
    loop2_begin = Label("loop2_begin")

    # quicksort(0, 800-1)
    mov(S, r1, Imm(0))
    mov(S, r2, Imm((100-1)*8))
    call(B, ref(quicksort))
    exit()

    tag(quicksort)
    # r1: left, r2: right
    # r11: low, r12: high
    # r0: pivot
    # r4: array[low]
    # r5: array[high]

    # if left < right: ret
    cmp(S, r1, r2)
    jge(B, ref(end_qsort))
    # pivot = array[left]
    mov(Q, r0, Mem(r1))
    # low = left
    mov(S, r11, r1)
    # high = right
    mov(S, r12, r2)

    jmp(B, ref(loop_check))
    tag(loop_begin)

    tag(loop1_begin)
    mov(Q, r5, Mem(r12))
    cmp(Q, r5, r0)
    jl(B, ref(loop1_end))
    cmp(S, r11, r12)
    jge(B, ref(loop1_end))
    sub(S, r12, Imm(8))
    jmp(B, ref(loop1_begin))
    tag(loop1_end)
    mov(Q, Mem(r11), r5)

    tag(loop2_begin)
    mov(Q, r4, Mem(r11))
    cmp(Q, r4, r0)
    jg(B, ref(loop2_end))
    cmp(S, r11, r12)
    jge(B, ref(loop2_end))
    add(S, r11, Imm(8))
    jmp(B, ref(loop2_begin))
    tag(loop2_end)
    mov(Q, Mem(r12), r4)

    tag(loop_check)
    cmp(S, r11, r12)
    jl(B, ref(loop_begin))

    # array[low] = pivot
    mov(Q, Mem(r11), r0)
    # qsort(left, low-1)
    push(S, r2)
    push(S, r11)
    mov(S, r2, r11)
    sub(S, r2, Imm(8))
    call(B, ref(quicksort))
    # qsort(low+1, right)
    pop(S, r1)
    add(S, r1, Imm(8))
    pop(S, r2)
    call(B, ref(quicksort))

    tag(end_qsort)
    ret()


    with open("payload", "wb") as f:
        f.write(assemble())


if __name__ == "__main__":
    main_quicksort()