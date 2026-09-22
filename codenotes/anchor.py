"""편집이 걸린 symbol을 판정하고, 파일이 바뀐 뒤에 다시 찾는다.

줄 번호는 힌트일 뿐 식별자가 아니다. 해석 순서는 CLAUDE.md에 있다.
tree-sitter도 ctags도 쓰지 않는다 — hook이 편집마다 도는 경로라 import 비용이 곧 장애다.
"""
import ast
import hashlib
import os
import re

C_LIKE = {".c", ".h", ".cc", ".cpp", ".hpp", ".cxx", ".hh",
          ".java", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".cs"}
KEYWORDS = {"if", "for", "while", "switch", "do", "else", "return", "sizeof", "catch"}
NAME = re.compile(r"([A-Za-z_]\w*)\s*\(")
# simhash 해밍 거리 상한. 실측 — 참쌍(같은 함수, 본문 변경) 거리는 중앙값 7 / 90분위 17,
# 남과의 거리는 10분위 17 / 중앙값 22. 12는 참쌍 대부분을 담고 남을 거의 배제하는 지점이다.
SIM_MAX = 12


def lang_of(rel):
    ext = os.path.splitext(rel or "")[1].lower()
    if ext == ".py":
        return "py"
    if ext in C_LIKE:
        return "c"
    return None


def normalize(body):
    """공백을 접는다. 들여쓰기만 바뀐 편집에 anchor가 흔들리지 않게."""
    return " ".join((body or "").split())


def body_hash(body):
    return hashlib.sha1(normalize(body).encode("utf-8")).hexdigest()[:6]


def simhash(body, bits=64):
    """개명 탐지용 유사도 지문. 본문을 레코드에 담을 수 없어서 16자로 줄인 것이다."""
    toks = normalize(body).split()
    grams = [" ".join(toks[i:i + 3]) for i in range(max(len(toks) - 2, 1))] or [""]
    v = [0] * bits
    for g in grams:
        h = int(hashlib.md5(g.encode("utf-8")).hexdigest()[:16], 16)
        for b in range(bits):
            v[b] += 1 if (h >> b) & 1 else -1
    out = 0
    for b in range(bits):
        if v[b] > 0:
            out |= (1 << b)
    return "%016x" % out


def hamming(a, b):
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 64


# ---- symbol 추출 ----

def _py_symbols(text):
    try:
        tree = ast.parse(text)
    except Exception:
        return []
    lines = text.split("\n")
    out = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                end = getattr(child, "end_lineno", child.lineno)
                kind = "cls" if isinstance(child, ast.ClassDef) else "fn"
                out.append({"sym": name, "kind": kind, "start": child.lineno, "end": end,
                            "body": "\n".join(lines[child.lineno - 1:end])})
                walk(child, name + ".")
    walk(tree, "")
    return out


def _c_symbols(text):
    """커널 C 관례 — 0열에서 시작하는 정의, 0열 여는 중괄호, 0열 닫는 중괄호."""
    lines = text.split("\n")
    n = len(lines)
    out = []
    i = 0
    while i < n:
        ln = lines[i]
        at_col0 = bool(ln) and not ln[0].isspace()
        opens = ln.startswith("{") or (at_col0 and ln.rstrip().endswith("{"))
        if not opens:
            i += 1
            continue
        # 시그니처 — 여는 줄 자신이거나, 위로 거슬러 모은 줄들
        if ln.startswith("{"):
            j = i - 1
            sig = []
            while j >= 0:
                prev = lines[j].rstrip()
                if not prev or prev.endswith((";", "}", "*/", ":")) or prev.startswith("#"):
                    break
                sig.insert(0, prev)
                j -= 1
            start = j + 1
        else:
            sig = [ln.rstrip().rstrip("{").rstrip()]
            start = i
        if not sig:
            i += 1
            continue
        cand = [m for m in NAME.findall(" ".join(sig)) if m not in KEYWORDS]
        if not cand:
            i += 1
            continue
        # 닫는 중괄호 찾기
        k = i + 1
        while k < n and not lines[k].startswith("}"):
            k += 1
        if k >= n:
            i += 1
            continue
        out.append({"sym": cand[-1], "kind": "fn", "start": start + 1, "end": k + 1,
                    "body": "\n".join(lines[start:k + 1])})
        i = k + 1
    return out


def symbols(text, rel):
    lang = lang_of(rel)
    if lang == "py":
        return _py_symbols(text)
    if lang == "c":
        return _c_symbols(text)
    return []


def enclosing(syms, span):
    """바뀐 줄 범위를 품는 symbol 중 가장 안쪽 것.

    두 개 이상에 걸치면 symbol이 아니라 파일 단위 변경이다 — None을 돌려준다.
    새 파일 Write가 첫 함수에 잘못 걸리던 것이 이 규칙으로 잡힌다.
    """
    if not span:
        return None
    lo, hi = span
    inside = [s for s in syms if s["start"] <= lo and hi <= s["end"]]
    if inside:
        return min(inside, key=lambda s: s["end"] - s["start"])
    touched = [s for s in syms if not (hi < s["start"] or s["end"] < lo)]
    return touched[0] if len(touched) == 1 else None


def make(text, rel, span):
    """편집 후 내용에서 anchor를 만든다."""
    s = enclosing(symbols(text, rel), span)
    if not s:
        return {"sym": None, "kind": "file", "hash": None, "lines": span}
    return {"sym": s["sym"], "kind": s["kind"], "hash": body_hash(s["body"]),
            "sig": simhash(s["body"]), "lines": [s["start"], s["end"]]}


# ---- 재해석: 파일이 바뀐 뒤 note를 다시 찾는다 ----

def resolve(text, rel, anchor, deep=False):
    """(stage, symbol|None). stage 1~4는 CLAUDE.md의 해석 순서.

    deep=False면 3단계(개명 탐지)를 건너뛴다. 실측에서 3단계는 anchor 14,856건 중
    2건(0.013%)만 건졌고 파일 전체에 simhash를 돌려야 한다 — 편집마다 도는 경로에 둘 것이 아니다.
    doctor와 rebind에서만 deep=True로 부른다.
    """
    if not anchor or anchor.get("kind") == "file" or not anchor.get("sym"):
        return 0, None
    syms = symbols(text, rel)
    want_hash = anchor.get("hash")
    if want_hash:
        for s in syms:                                   # 1. 내용 그대로 — 이동해도 따라간다
            if body_hash(s["body"]) == want_hash:
                return 1, s
    for s in syms:                                       # 2. 이름 — 본문만 바뀐 경우
        if s["sym"] == anchor["sym"]:
            return 2, s
    sig = anchor.get("sig") if deep else None            # 3. 파일 전수 유사도 — 개명 탐지
    if sig:
        best, dist = None, 65
        for s in syms:
            d = hamming(sig, simhash(s["body"]))
            if d < dist:
                best, dist = s, d
        if best and dist <= SIM_MAX:
            return 3, best
    return 4, None                                       # 4. 유실
