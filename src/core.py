

"""
BUBU
"""

import re
import sys
import operator as op
from functools import reduce




_verbose_tokenrepr = False

def pair(L):
    pairs = []
    s, e = 0, 2
    for _ in range(len(L)//2):
        pairs.append(L[s:e])
        s += 2
        e += 2
    return pairs


def group_case_clauses(clauses, g):
    if clauses:
        g.append(clauses[:2])
        return group_case_clauses(clauses[2:], g)
    return g

HIGHER_ORDER_FUNCTIONS = ("call", "map")
# def ishigherorder(tok): return tok.label in HIGHER_ORDER_FUNCTIONS
SINGLE_NAMING_BLOCK_BUILDERS = ("block","defun", )
NONNAMING_BLOCK_BUILDERS = ("case","call")
LEXICAL_BLOCK_BUILDERS = ("block", "defun", "define", "fn", )
MULTIPLE_VALUE_BINDERS = ("defvar", "define")

def is_multiple_value_binder(tok): return tok.label in MULTIPLE_VALUE_BINDERS

def is_singlename_builder(tok): return tok.label in SINGLE_NAMING_BLOCK_BUILDERS

def is_lexenv_builder(tok): return tok.label in LEXICAL_BLOCK_BUILDERS

######### builtin functions
def sub(*args): return reduce(op.sub, args) if args else 0
def mul(*args): return reduce(op.mul, args) if args else 1
def floordiv(*args): return reduce(op.floordiv, args)
def truediv(*args): return reduce(op.truediv, args)
def add(*args): return sum(args)
def eq(*args): return args.count(args[0]) == len(args)
def pret(thing):
    """Prints and returns the thing."""
    print(thing)
    return thing
def list_(*args): return list(args)
def map_(fn, *args): return list(map(fn, *args))

def builtin_funcs():
    return {
        "*": mul, "+": add, "-": sub, "=": eq, 
        "//": floordiv, "/": truediv,
        "pret": pret,
        "list": list_, "map": map_
    }

class Env:
    def __init__(self, parenv=None):
        self.funcs = builtin_funcs()
        self.vars = {}
        self.consts = {}
        self.parenv = parenv
        
    def isfunc(self, tok): return tok.label in self.funcs
    
    def resolve_token(self, tok):
        if tok.label.startswith("'"): # return the function object
            return self.funcs[tok.label[1:]]
        else:
            try:
                return self.funcs[tok.label]
            except KeyError:
                try:
                    return self.vars[tok.label]
                except KeyError:
                    try:
                        return self.consts[tok.label]
                    except KeyError:
                        return self.parenv.resolve_token(tok)
    
    def isblockbuilder(self, tok):
        if tok.label in self.funcs:
            return True
        else:
            if self.parenv:
                return self.parenv.isblockbuilder(tok)
            else:
                return tok.label in SINGLE_NAMING_BLOCK_BUILDERS + \
                    NONNAMING_BLOCK_BUILDERS + MULTIPLE_VALUE_BINDERS + \
                    HIGHER_ORDER_FUNCTIONS + LEXICAL_BLOCK_BUILDERS
    
    def getenv(self, s):
        if s in self.funcs or s in self.vars or s in self.consts:
            return self
        elif self.parenv:
            return self.parenv.getenv(s)
        else:
            raise KeyError
            
            
class Token:
    def __init__(self, label="_TOPLEVEL", start=-1, end=sys.maxsize, line=-1):
        self.label = label
        self.start = start
        self.end = end
        self.line = line
    
    def __repr__(self):
        if _verbose_tokenrepr:
            return f"{self.label}.L{self.line}.S{self.start}"
        else:
            return f"{self.label}"


class Function:
    
    def __init__(self, params, body, enclosing_env):
        self.params = params
        self.body = body
        self.enclosing_env = enclosing_env
    
    def __call__(self, *args):
        assert (len(self.params) == len(args)), f"function expected {len(self.params)} arguments, but got {len(args)}"
        e = Env(self.enclosing_env)
        e.vars.update(zip(self.params, args))
        for expr in self.body[:-1]:
            eval_(expr, e)
        return eval_(self.body[-1], e)




# decimal numbers
# DECPATT = r"[+-]?((\d+(\.\d*)?)|(\.\d+))"
STRPATT = re.compile(r'"[^"]*"')
# def tokenize_source(src):
    # """
    # """
    # src = src.strip()
    # str_matches = list(STRPATT.finditer(src))
    # spans = [m.span() for m in str_matches]
    # indices = [0] + [i for s in spans for i in s] + [len(src)]
    # tokens = []
    # for x in list(zip(indices[:-1], indices[1:])):
        # if x in spans: # str match?
            # tokens.append(src[x[0]:x[1]])
        # else:
            # tokens.extend(src[x[0]:x[1]].replace(LPAR, f" {LPAR} ").replace(RPAR, f" {RPAR} ").split())
    # return tokens

def lines(src): return src.strip().splitlines()

def tokenize_source(src):
    toks = []
    for i, line in enumerate(lines(src)):
        # for match in re.finditer(r"([*=+-]|\w+|{})".format(DECPATT), line):
        for match in re.finditer(r"\S+", line):
            toks.append(Token(label=match.group(), start=match.start(), end=match.end(), line=i)
            )
    return toks




def token_isin_block(tk, bl):
    """Is tk inside of the kw's block?"""
    return tk.start > bl.kw.start and tk.line >= bl.kw.line



class Block:
    counter = 0
    def __init__(self, kw, env):
        self.kw = kw
        self.cont = [self.kw]
        self.env = env
        self.nth = Block.counter
        Block.counter += 1
    
    def __repr__(self): return f"B{self.nth}"
    def append(self, t): self.cont.append(t)


def ast(parsed_block, tree=[]):
    for x in parsed_block.cont:
        if isinstance(x, Token):
            tree.append(x)
        else: # Block?
            tree.append(ast(x, []))
    return tree



def bottom_rightmost_enclosing_block(enclosing_blocks):
    # Find the max line
    maxline = max(enclosing_blocks, key=lambda b: b.kw.line).kw.line
    # all bottommost blocks
    bottommost_blocks = [b for b in enclosing_blocks if b.kw.line == maxline]
    # return the rightmost of them
    return max(bottommost_blocks, key=lambda b: b.kw.start)

# global env has no parent env
toplevelenv = Env()
toplevelblock = Block(kw=Token(), env=toplevelenv)

###########################
###########################
# The listify is passed to eval
def parse(toks):
    """Converts tokens of the source file to an AST of Tokens/Blocks"""
    nametok = None
    enclosingblock = toplevelblock
    blocktracker = [enclosingblock]
    
    for i, t in enumerate(toks):
        # make a block??
        if enclosingblock.env.isblockbuilder(t):
            if is_lexenv_builder(t):
                B = Block(t, Env(enclosingblock.env)) # give it a new env
            else:
                B = Block(t, enclosingblock.env)
            blocktracker.append(B)

        # Monitor next coming token
        if is_singlename_builder(t): # eg defun
            nametok = toks[i+1]
            
        enclosing_blocks = [b for b in blocktracker if token_isin_block(t, b)]
        enclosingblock = bottom_rightmost_enclosing_block(enclosing_blocks)
        enclosingblock.append(B if enclosingblock.env.isblockbuilder(t) else t)
        
        # if enclosing_blocks: # If there are some enclosing blocks (Is this not always true?????????)
            # if enclosingblock.env.isblockbuilder(t):
                # enclosingblock.append(B)
            # else:
                # enclosingblock.append(t)
        # Adding to Env
        try:
            if t.label == nametok.label:
                # Create placeholders, so that the parser knows about these names while parsing
                # coming tokens.
                # The actual bindings to the objects happen later during evaluation.
                if toks[i-1].label == "define":
                    toplevelblock.env.funcs[t.label] = None
                elif toks[i-1].label == "funlet":
                    enclosingblock.env.funcs[t.label] = None
                elif toks[i-1].label == "block":
                    pass
                elif toks[i-1].label == "map": 
                    pass
                    
                nametok = None
        # If nametok is None
        except AttributeError: pass
    return toplevelblock
    # try:
        # return blocktracker[0]
    # except IndexError: # If there was no kw, no blocks have been built
        # pass


def eval_(x, e):
    if isinstance(x, Block): # think of a Block as list!

        car, cdr = x.kw, x.cont[1:]
        # car, cdr = x.kw, x.cont
        if car.label == "_TOPLEVEL": # start processing the rest
            for i in cdr[:-1]:
                eval_(i, e)
            return eval_(cdr[-1], e)
            
        elif car.label == "case":
            pass
            # for pred, form in group_case_clauses(x.cont, []):
                # if evaltoplevel(pred, e): return evaltoplevel(form, e)
            # return False
        
        # elif car.label == "defvar":
            # assert all([isinstance(a, Block) for a in cdr[1:]])
            # for bind in cdr: # bind is a Block
                # _, vartok, val = bind.cont
                # # Nicht im toplevelenv??? es ist defvar!
                # x.env.vars[vartok.label] = eval_(val, bind.env)
            # return vartok
        
        # Higher order functions
        elif car.label == "call": # call a function object
            fn, *args = cdr
            return eval_(fn, e)(*[eval_(a, e) for a in args])
        
        elif car.label == "map":
            fn, *args = cdr
            return e.funcs["map"](eval_(fn, e), *[eval_(a, e) for a in args])

        elif car.label == "fn": # create a function object
            # the first block is a block of params
            paramsblock, *exprs = cdr
            params = paramsblock.cont[1:]
            return Function([p.label for p in params], exprs, e)
        
        elif e.isfunc(car):
            # return e.funcs[car.label](*[eval_(b, e) for b in cdr])
            # print(car,cdr)
            return eval_(car, e)(*[eval_(b, e) for b in cdr])
        
        else:
            raise SyntaxError(f"{(x, x.cont)} not known")
    
    else: # x is a Token
        try:
            return int(x.label)
        except ValueError:
            try:
                return float(x.label)
            except ValueError:
                return e.resolve_token(x)


def evalsrc(src):
    with open(src, "r") as s:
        # print(s.read())
        print(eval_(parse(tokenize_source(s.read())), toplevelenv))



# def repl(prompt='lis.py> '):
    # "A prompt-read-eval-print loop."
    # while True:
        # val = eval(parse(raw_input(prompt)))
        # if val is not None: 
            # print(schemestr(val))

# def schemestr(exp):
    # "Convert a Python object back into a Scheme-readable string."
    # if isinstance(exp, List):
        # return '(' + ' '.join(map(schemestr, exp)) + ')' 
    # else:
        # return str(exp)

# toks = tokenize_source(s)
# print(STRPATT.findall(s))
# print(parse(toks))
# print(ast(parse(toks)))
# eval_(parse(toks), toplevelenv)