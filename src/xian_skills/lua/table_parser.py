"""Minimal parser for the decompiled config_lua/*.lua data files.

The decompiler emits files shaped like:

    local __rt_1 = { ... }
    local __rt = createtable and createtable(N, 0) or {}
    __rt[1] = { ... }
    local <name> = { [id] = { ... }, ... }
    local __default_values = { ... }
    return <name>

Only table constructors, scalars and references to previously defined
`__rt_N` / `__rt[N]` locals appear inside the data, so a small
recursive-descent parser is enough. Shared sub-tables are returned as the
*same* Python object, which mirrors the Lua aliasing and lets callers group
identical structures by `id()`.
"""

import io
import re

TOKEN_RE = re.compile(r"""
    (?P<ws>\s+|--[^\n]*)
  | (?P<str>"(?:[^"\\]|\\.)*")
  | (?P<num>-?(?:0[xX][0-9a-fA-F]+|\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+|\d+(?:[eE][-+]?\d+)?))
  | (?P<name>[^\W\d]\w*)
  | (?P<punct>==|~=|<=|>=|\.\.|[{}\[\]=,;().:<>+\-*/#%])
""", re.X)

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "a": "\a", "b": "\b"}


def tokenize(src):
    pos, n = 0, len(src)
    out = []
    while pos < n:
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise SyntaxError("cannot tokenize at %d: %r" % (pos, src[pos:pos + 40]))
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        out.append((kind, m.group()))
    out.append(("eof", ""))
    return out


def unquote(s):
    body = s[1:-1]
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt.isdigit():
                j = i + 1
                while j < len(body) and body[j].isdigit() and j - i <= 3:
                    j += 1
                out.append(chr(int(body[i + 1:j])))
                i = j
                continue
            out.append(ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


class Parser(object):
    def __init__(self, src):
        self.toks = tokenize(src)
        self.i = 0
        self.env = {}      # local name -> value
        self.rt = {}       # __rt[N] -> value

    # -- token helpers ---------------------------------------------------
    def peek(self, k=0):
        return self.toks[self.i + k]

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, kind, val=None):
        k, v = self.peek()
        if k == kind and (val is None or v == val):
            self.i += 1
            return v
        return None

    def expect(self, kind, val=None):
        got = self.accept(kind, val)
        if got is None:
            raise SyntaxError("expected %s %r, got %r at tok %d" %
                              (kind, val, self.peek(), self.i))
        return got

    # -- grammar ---------------------------------------------------------
    def parse_chunk(self):
        """Execute the statements we care about; return the value of `return X`."""
        while True:
            k, v = self.peek()
            if k == "eof":
                return None
            if k == "name" and v == "local":
                self.next()
                name = self.expect("name")
                self.expect("punct", "=")
                self.env[name] = self.parse_expr_or_skip()
                continue
            if k == "name" and v == "return":
                self.next()
                return self.parse_value()
            # __rt[N] = value
            if k == "name" and self.peek(1)[1] == "[":
                base = self.next()[1]
                self.expect("punct", "[")
                idx = self.parse_value()
                self.expect("punct", "]")
                self.expect("punct", "=")
                val = self.parse_expr_or_skip()
                if base == "__rt":
                    self.rt[idx] = val
                continue
            # anything else (if/do/for/setmetatable ...) -> skip statement
            self.skip_statement()

    def parse_expr_or_skip(self):
        """Parse a value, tolerating expressions such as
        `createtable and createtable(1652, 0) or {}`."""
        start = self.i
        try:
            val = self.parse_value()
        except SyntaxError:
            self.i = start
            self.skip_statement()
            return None
        # trailing `and`/`or`/call noise -> fall back to the last table literal
        while True:
            k, v = self.peek()
            if k == "name" and v in ("and", "or"):
                self.next()
                val = self.parse_expr_or_skip()
                continue
            if k == "punct" and v == "(":
                self.skip_balanced("(", ")")
                continue
            break
        return val

    def parse_value(self):
        k, v = self.peek()
        if k == "str":
            self.next()
            return unquote(v)
        if k == "num":
            self.next()
            if re.match(r"^-?\d+$", v):
                return int(v)
            if v.lower().startswith("0x") or v.lower().startswith("-0x"):
                return int(v, 16)
            return float(v)
        if k == "punct" and v == "{":
            return self.parse_table()
        if k == "name":
            if v == "true":
                self.next()
                return True
            if v == "false":
                self.next()
                return False
            if v == "nil":
                self.next()
                return None
            # reference: name or name[idx]
            self.next()
            if self.accept("punct", "["):
                idx = self.parse_value()
                self.expect("punct", "]")
                if v == "__rt":
                    return self.rt.get(idx)
                base = self.env.get(v)
                return base.get(idx) if isinstance(base, dict) else None
            return self.env.get(v)
        raise SyntaxError("unexpected token %r at %d" % ((k, v), self.i))

    def parse_table(self):
        self.expect("punct", "{")
        arr, hsh = [], {}
        while True:
            if self.accept("punct", "}"):
                break
            # [key] = value
            if self.accept("punct", "["):
                key = self.parse_value()
                self.expect("punct", "]")
                self.expect("punct", "=")
                hsh[key] = self.parse_value()
            elif self.peek()[0] == "name" and self.peek(1)[1] == "=" and \
                    self.peek(1)[0] == "punct":
                key = self.next()[1]
                self.expect("punct", "=")
                hsh[key] = self.parse_value()
            else:
                arr.append(self.parse_value())
            if not (self.accept("punct", ",") or self.accept("punct", ";")):
                self.expect("punct", "}")
                break
        if arr and not hsh:
            return arr
        if arr:
            for i, x in enumerate(arr, 1):
                hsh[i] = x
        return hsh

    # -- crude statement skipping ---------------------------------------
    def skip_balanced(self, open_t, close_t):
        self.expect("punct", open_t)
        depth = 1
        while depth:
            k, v = self.next()
            if k == "eof":
                return
            if v == open_t:
                depth += 1
            elif v == close_t:
                depth -= 1

    def skip_statement(self):
        depth = 0
        while True:
            k, v = self.peek()
            if k == "eof":
                return
            if k == "name" and v in ("end", "return") and depth == 0:
                if v == "end":
                    self.next()
                return
            if v in "{([":
                depth += 1
            elif v in "})]":
                depth -= 1
            self.next()
            if depth <= 0 and self.peek()[0] == "name" and \
                    self.peek()[1] in ("local", "return"):
                return


KEY2IDX_RE = re.compile(r"local\s+key2idx\s*=\s*\{([^}]+)\}", re.S)
KEY2IDX_PAIR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)")


def extract_key2idx(src):
    """Pull the packed-column map from a temple_part*.lua `local key2idx = {...}` block."""
    m = KEY2IDX_RE.search(src)
    if not m:
        return {}
    return {k: int(v) for k, v in KEY2IDX_PAIR_RE.findall(m.group(1))}


def _deepcopy(obj):
    if isinstance(obj, dict):
        return {k: _deepcopy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deepcopy(v) for v in obj]
    return obj


def apply_default_values(tbl, defaults):
    """Materialize `setmetatable(v, {__index = __default_values})` for every row dict.

    For temple_refresh-style tables the rows themselves get the defaults. For
    temple_refresh_new-style tables (temple_id -> list/dict of spawn entries)
    defaults are applied to each spawn entry.
    """
    if not defaults or tbl is None:
        return tbl

    def fill(row):
        if not isinstance(row, dict):
            return
        for k, v in defaults.items():
            if k not in row:
                row[k] = _deepcopy(v)

    def looks_like_entry_bucket(row):
        if not isinstance(row, dict) or not row:
            return False
        if not all(isinstance(k, int) for k in row.keys()):
            return False
        sample = next((v for v in row.values() if isinstance(v, dict)), None)
        return bool(sample) and any(
            k in sample for k in ("id", "type", "temple", "init_amount", "reward", "level")
        )

    if isinstance(tbl, list):
        for row in tbl:
            fill(row)
        return tbl

    if isinstance(tbl, dict):
        for row in tbl.values():
            if looks_like_entry_bucket(row):
                for child in row.values():
                    fill(child)
            else:
                fill(row)
    return tbl


def unpack_key2idx(tbl, key2idx):
    """Expand packed numeric temple rows into named-key dicts via key2idx.

    Decompiled rows may arrive as a Python list (dense 1..n array constructor)
    or as a dict with integer keys (sparse `[k]=v` constructors). Both are
    handled; list index 0 maps to Lua slot 1.
    """
    if not key2idx or not isinstance(tbl, dict):
        return tbl
    idx2key = {idx: name for name, idx in key2idx.items()}
    out = {}
    for tid, row in tbl.items():
        items = []
        if isinstance(row, list):
            items = list(enumerate(row, 1))
        elif isinstance(row, dict):
            items = list(row.items())
        else:
            out[tid] = row
            continue
        named = {}
        for idx, val in items:
            if val is None:
                continue
            if isinstance(idx, int) and idx in idx2key:
                named[idx2key[idx]] = _deepcopy(val)
            elif isinstance(idx, str):
                named[idx] = _deepcopy(val)
            elif isinstance(idx, int):
                named["_idx_%d" % idx] = _deepcopy(val)
        out[tid] = named
    return out


def load(path, apply_defaults=False, unpack_packed=False):
    with io.open(path, encoding="utf-8", errors="replace") as handle:
        src = handle.read()
    if src.startswith("\ufeff"):
        src = src[1:]
    p = Parser(src)
    ret = p.parse_chunk()
    if ret is None:
        # `return <name>` may have been swallowed; fall back to the biggest local
        cands = [(len(v), k, v) for k, v in p.env.items()
                 if isinstance(v, dict) and not k.startswith("__rt")]
        cands.sort()
        ret = cands[-1][2] if cands else None

    defaults = p.env.get("__default_values")
    key2idx = extract_key2idx(src) if unpack_packed else {}

    if apply_defaults and defaults is not None:
        ret = _deepcopy(ret)
        apply_default_values(ret, defaults)
    if unpack_packed and key2idx:
        ret = unpack_key2idx(ret, key2idx)

    p.defaults = defaults
    p.key2idx = key2idx
    return ret, p
