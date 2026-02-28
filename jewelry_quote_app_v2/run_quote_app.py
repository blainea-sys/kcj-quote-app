import sys
import subprocess
from pathlib import Path

def find_app_py() -> Path:
    exe_dir = Path(sys.executable).resolve().parent
    meipass = Path(getattr(sys, "_MEIPASS", exe_dir)).resolve()

    candidates = [
        exe_dir / "app.py",
        exe_dir / "_internal" / "app.py",
        meipass / "app.py",
        meipass / "_internal" / "app.py",
    ]
    for p in candidates:
        if p.exists():
            return p
    for root in [exe_dir, meipass]:
        for p in root.rglob("app.py"):
            return p
    raise FileNotFoundError(f"Could not find app.py near {exe_dir} or {meipass}")

def main():
    app_path = find_app_py()
    base_dir = app_path.parent
    (base_dir / "output").mkdir(exist_ok=True)
    (base_dir / "assets").mkdir(exist_ok=True)
    (base_dir / "quotes").mkdir(exist_ok=True)

    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.port=8501",
    ]
    subprocess.run(cmd, cwd=str(base_dir), check=False)

if __name__ == "__main__":
    main()
