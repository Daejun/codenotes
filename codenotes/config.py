"""프로젝트 root 판정과 제외 규칙."""
import json
import os

DIRNAME = ".codenotes"

# 디렉터리 이름이 이것이면 그 아래 전부 제외.
SKIP_DIRS = {".git", ".codenotes", ".testrepos", "node_modules", "__pycache__",
             ".venv", "venv", "logs", "build", "dist"}
# 확장자로 제외 — 빌드 산출물, 바이너리, note 자신.
SKIP_SUFFIX = (".o", ".ko", ".so", ".a", ".pyc", ".pyo", ".jsonl", ".lock",
               ".png", ".jpg", ".pdf", ".zip", ".tar", ".gz")
# 생성 파일. <mod>.mod.c 같은 것.
SKIP_TAIL = (".mod.c",)

DEFAULTS = {"budget_chars": 1200, "why_max": 240, "seen_cap": 5000,
            "ask_missing": False}


def find_root(start):
    """start에서 위로 올라가며 .codenotes/를 가진 디렉터리를 찾는다. 없으면 None."""
    p = os.path.abspath(start or ".")
    while True:
        if os.path.isdir(os.path.join(p, DIRNAME)):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def load(root):
    """기본값 < .codenotes/config.json < plugin userConfig 순으로 덮는다.

    plugin으로 설치하면 userConfig 값이 hook 프로세스에 CLAUDE_PLUGIN_OPTION_<KEY>로 온다.
    저장소 설정보다 사용자 설정이 우선이다.
    """
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(root, DIRNAME, "config.json"), encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    for key in DEFAULTS:
        raw = os.environ.get("CLAUDE_PLUGIN_OPTION_" + key.upper())
        if raw is None:
            continue
        low = raw.strip().lower()
        if low in ("true", "false"):
            cfg[key] = low == "true"
        else:
            try:
                cfg[key] = int(raw)
            except ValueError:
                cfg[key] = raw
    return cfg


def relativize(root, path):
    """root 안의 상대 경로. 밖이면 None."""
    if not path:
        return None
    ap = os.path.abspath(path)
    rt = os.path.abspath(root)
    if ap == rt or not ap.startswith(rt + os.sep):
        return None
    return ap[len(rt) + 1:]


def excluded(root, rel):
    """제외 규칙. 이유 문자열을 돌려주고, 통과면 None."""
    if rel is None:
        return "outside-root"
    parts = rel.split(os.sep)
    for d in parts[:-1]:
        if d in SKIP_DIRS:
            return "skip-dir:" + d
    if rel.endswith(SKIP_SUFFIX):
        return "skip-suffix"
    if rel.endswith(SKIP_TAIL):
        return "generated"
    # 중첩 git 저장소 — 여기는 시험 대상이지 작업 트리가 아니다.
    cur = os.path.join(root, os.path.dirname(rel))
    while os.path.abspath(cur) != os.path.abspath(root):
        if os.path.isdir(os.path.join(cur, ".git")):
            return "nested-repo"
        nxt = os.path.dirname(cur)
        if nxt == cur:
            break
        cur = nxt
    return None
