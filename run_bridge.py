import subprocess
import time
import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

def run_python_app():
    print("🚀 Starting OneDrive-Telegram Bridge...")
    return subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        cwd=ROOT_DIR,
        env=os.environ.copy()
    )

def main():
    processes = []
    try:
        py_proc = run_python_app()
        processes.append(py_proc)
        
        print("\n✅ Bridge is running!")
        print("   - API: http://localhost:8080")
        print("\nPress Ctrl+C to stop.\n")
        
        while True:
            # Check if processes are still running
            for p in processes:
                if p.poll() is not None:
                    print(f"\n⚠️ Process {p.args} exited with code {p.returncode}")
                    return
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
    finally:
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("👋 Done.")

if __name__ == "__main__":
    main()
