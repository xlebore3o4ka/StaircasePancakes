import os
import sys
import shutil
import subprocess
import glob


def find_gcc():
    for name in ("gcc", "gcc.exe", "x86_64-w64-mingw32-gcc"):
        p = shutil.which(name)
        if p:
            return p
    if os.name == "nt":
        cands = [
            r"C:\msys64\ucrt64\bin\gcc.exe",
            r"C:\msys64\mingw64\bin\gcc.exe",
            r"C:\msys64\mingw32\bin\gcc.exe",
            r"C:\mingw64\bin\gcc.exe",
            r"C:\mingw32\bin\gcc.exe",
            r"C:\TDM-GCC-64\bin\gcc.exe",
        ]
        for c in cands:
            if os.path.isfile(c):
                return c
    return None


def print_install_hint():
    if os.name == "nt":
        print("""
Windows -- install MSYS2 (https://www.msys2.org/):
  In 'MSYS2 UCRT64' shell:
    pacman -S mingw-w64-ucrt-x86_64-gcc
""")
    else:
        print("""
Linux:  sudo apt install build-essential
""")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    args = sys.argv[1:]

    if "--clean" in args:
        for f in glob.glob("libraries/*.dll") + glob.glob("libraries/*.so"):
            os.remove(f)
        print("cleaned")

    gcc = find_gcc()
    if not gcc:
        print("error: gcc not found", file=sys.stderr)
        print_install_hint()
        return 1
    print(f"gcc: {gcc}")

    env = os.environ.copy()
    env["PATH"] = os.path.dirname(gcc) + os.pathsep + env.get("PATH", "")

    if "--shared" not in args:
        print("usage: python build.py --shared")
        print("  builds libraries/light.dll (and light.so on linux)")
        return 0

    os.makedirs("libraries", exist_ok=True)
    out_name = "light.dll" if os.name == "nt" else "light.so"
    out = os.path.join("libraries", out_name)
    cmd = [gcc, "-shared", "-O2", "-fPIC", "-Isrc", "-o", out,
           "src/camera.c", "src/light.c", "-lm"]
    if os.name == "nt":
        cmd.append("-Wl,--export-all-symbols")
    print("LINK", out)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        if r.stdout: print(r.stdout)
        if r.stderr: print(r.stderr)
        print(f"error: link failed (exit {r.returncode})", file=sys.stderr)
        return r.returncode
    print(f"OK -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
