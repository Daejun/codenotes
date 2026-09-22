"""저장소를 codenotes에 opt-in시킨다.

hook은 `.codenotes/`가 없는 프로젝트에서 즉시 exit 0한다. 그래서 설치란 곧
이 디렉터리를 만드는 일이고, 지우면 그것이 곧 해제다.
"""
import json
import os

from . import config

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GITIGNORE = [".codenotes/state.json", ".codenotes/hook.log"]
GITATTR = ".codenotes/**/*.jsonl merge=union"

DEFAULT_CONFIG = {
    "budget_chars": 1200,      # PreToolUse로 주입할 최대 글자 수
    "why_max": 240,            # why 한 건의 상한 (불변식 7)
    "seen_cap": 5000,          # state.json이 기억할 tid 수
    "ask_missing": False,      # 이유가 빈 편집을 Stop에서 되묻는다 (모델 왕복 1회)
}


def settings_block(home=HERE):
    """`.claude/settings.json`에 넣을 hook 설정. 절대 경로로 이 체크아웃을 가리킨다."""
    def h(name, msg):
        return {"type": "command", "command": os.path.join(home, "hooks", name),
                "timeout": 15, "statusMessage": msg}
    return {"hooks": {
        "PreToolUse": [{"matcher": "Edit|Write",
                        "hooks": [h("pre_edit_recall.py", "codenotes recall")]}],
        "Stop": [{"hooks": [h("turn_capture.py", "codenotes capture")]}],
    }}


def append_lines(path, lines, header):
    """있는 파일에 없는 줄만 덧붙인다. 남의 설정을 덮지 않는다."""
    have = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            have = f.read()
    add = [l for l in lines if l not in have]
    if not add:
        return 0
    with open(path, "a", encoding="utf-8") as f:
        if have and not have.endswith("\n"):
            f.write("\n")
        f.write("\n# %s\n" % header if have else "# %s\n" % header)
        f.write("\n".join(add) + "\n")
    return len(add)


def merge_settings(path, block):
    """이미 있는 settings.json의 다른 hook을 지우지 않고 우리 것만 더한다."""
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None            # 못 읽는 설정을 덮어쓰지 않는다
    hooks = data.setdefault("hooks", {})
    for event, entries in block["hooks"].items():
        cur = hooks.setdefault(event, [])
        mine = json.dumps(entries, sort_keys=True)
        if any(json.dumps([e], sort_keys=True) == mine for e in cur):
            continue
        cur.extend(entries)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return data


def run(root, write_settings=True):
    root = os.path.abspath(root)
    out = []
    d = os.path.join(root, config.DIRNAME)
    os.makedirs(d, exist_ok=True)
    out.append(".codenotes/")

    cfg = os.path.join(d, "config.json")
    if not os.path.exists(cfg):
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=1)
            f.write("\n")
        out.append("config.json")

    if append_lines(os.path.join(root, ".gitignore"), GITIGNORE, "codenotes"):
        out.append(".gitignore")
    if append_lines(os.path.join(root, ".gitattributes"), [GITATTR], "codenotes"):
        out.append(".gitattributes")

    if write_settings:
        p = os.path.join(root, ".claude", "settings.json")
        if merge_settings(p, settings_block()) is None:
            out.append(".claude/settings.json (읽을 수 없어 건드리지 않음)")
        else:
            out.append(".claude/settings.json")
    return out
