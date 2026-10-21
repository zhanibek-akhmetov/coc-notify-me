"""Тест API-скриптов без сети: компилируются и понятно сообщают, если нет ключа или тега.

Скрипты копируются во временную папку, чтобы не подхватить локальный coc_api_key.txt.
Запуск: python tests/test_api_tools.py
"""
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "api-tools")
SCRIPTS = {  # скрипт: аргументы, без которых он должен вежливо остановиться
    "coc_war.py": [],
    "coc_war_hunt.py": [],
    "coc_warlog_year.py": [],
    "coc_tag.py": [],
}
failed = []


def check(cond, what, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + what + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failed.append(what)


work = tempfile.mkdtemp()
for name in SCRIPTS:
    shutil.copy(os.path.join(TOOLS, name), work)
env = {k: v for k, v in os.environ.items() if k != "COC_API_KEY"}
env["PYTHONIOENCODING"] = "utf-8"


def run(name, args, extra_env=None):
    return subprocess.run([sys.executable, os.path.join(work, name)] + args, cwd=work, capture_output=True,
                          text=True, encoding="utf-8", env={**env, **(extra_env or {})}, timeout=60)


for name in SCRIPTS:
    print(f"{name}:")
    try:
        py_compile.compile(os.path.join(TOOLS, name), doraise=True)
        check(True, "компилируется")
    except py_compile.PyCompileError as e:
        check(False, "компилируется", str(e))
        continue
    r = run(name, [])
    out = (r.stdout + r.stderr).strip()
    check(r.returncode != 0 and "Traceback" not in out and ("ключ" in out.lower() or "COC_API_KEY" in out),
          "без ключа — понятное сообщение, а не падение", out[-300:])

for name in ("coc_tag.py", "coc_warlog_year.py", "coc_war.py"):
    r = run(name, [], {"COC_API_KEY": "dummy"})
    out = (r.stdout + r.stderr).strip()
    check(r.returncode != 0 and "Traceback" not in out, f"{name}: с ключом, но без тега — подсказка по запуску",
          out[-300:])

print("\nИТОГ:", "всё работает ✅" if not failed else f"ОШИБКИ: {failed}")
sys.exit(1 if failed else 0)
