import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
#!/usr/bin/env python3
"""Builds the test corpus: real RISC-V firmware (.bin/.hex), native code and data files.

Run:  python3 mnemo_corpus.py        -> fills ./corpus/ and writes corpus/MANIFEST.csv
"""
import os, random, struct, subprocess, glob, math

HERE = os.path.dirname(os.path.abspath(__file__))  # This holds the folder of this script
SRC = os.path.join(HERE, "..", "c_files")              # This holds the C sources for the firmware
OUT = os.path.join(HERE, "..", "test_files")                  # This holds the generated corpus files
CC = "riscv64-unknown-elf-gcc"                      # This holds the cross compiler name
OBJCOPY = "riscv64-unknown-elf-objcopy"             # This holds the objcopy tool name
RAM_IMAGE = 32 * 1024                               # This holds the RAM size used for the memory image files


def run(cmd):
    """Runs one shell command and stops with a clear error if it fails."""
    subprocess.run(cmd, check=True)  # Run the command and raise on a non-zero exit


def build_firmware(manifest):
    """Compiles every C app at -O2 and -Os and emits .bin, .hex and a zero padded RAM image."""
    apps = [c for c in sorted(glob.glob(os.path.join(SRC, "*.c"))) if not c.endswith("libc.c")]  # App sources only
    for c in apps:  # Visit each C source
        name = os.path.splitext(os.path.basename(c))[0]    # Take the app name from the file name
        for opt in ("O2", "Os"):                           # Build two optimisation levels
            tag = f"fw_{name}_{opt}"                       # Build the corpus file stem
            elf = os.path.join(OUT, tag + ".elf")          # Path of the intermediate ELF
            run([CC, "-march=rv32im", "-mabi=ilp32", f"-{opt}", "-nostdlib", "-ffreestanding",
                 "-T", os.path.join(SRC, "link.ld"), os.path.join(SRC, "start.S"), os.path.join(SRC, "libc.c"), c, "-lgcc", "-o", elf])  # Compile and link
            run([OBJCOPY, "-O", "binary", elf, os.path.join(OUT, tag + ".bin")])   # Raw binary image
            run([OBJCOPY, "-O", "ihex", elf, os.path.join(OUT, tag + ".hex")])     # Intel HEX text image
            raw = open(os.path.join(OUT, tag + ".bin"), "rb").read()               # Read the binary back
            ram = raw + bytes(RAM_IMAGE - len(raw))                                # Pad with zeros to the whole RAM
            open(os.path.join(OUT, tag + "_ram32k.bin"), "wb").write(ram)          # Save the full memory image
            os.remove(elf)                                                         # Drop the ELF, it is not a corpus file
            manifest.append((tag + ".bin", "firmware", "RISC-V rv32im binary, code+rodata+data"))
            manifest.append((tag + ".hex", "hex_text", "Intel HEX text of the same image"))
            manifest.append((tag + "_ram32k.bin", "ram_image", "binary padded with zeros to a 32 KB RAM"))


def build_bundle(manifest):
    """Links every app into one larger firmware, as a real product image holds many modules."""
    apps = [c for c in sorted(glob.glob(os.path.join(SRC, "*.c"))) if not c.endswith("libc.c")]  # App sources only
    names = [os.path.splitext(os.path.basename(c))[0] for c in apps]  # App names
    driver = os.path.join(OUT, "_driver.c")                           # Generated main that calls every app
    open(driver, "w").write("".join(f"int app_{n}(void);\n" for n in names) + "int main(void){ " + " ".join(f"app_{n}();" for n in names) + " for(;;); }\n")
    for opt in ("O2", "Os"):                                          # Two optimisation levels
        objs = []                                                     # Object files for this level
        for c, n in zip(apps, names):                                 # Compile each app with a renamed main
            o = os.path.join(OUT, f"_{n}_{opt}.o")
            run([CC, "-march=rv32im", "-mabi=ilp32", f"-{opt}", "-ffreestanding", "-fno-builtin", f"-Dmain=app_{n}", "-c", c, "-o", o])
            objs.append(o)
        tag = f"fw_bundle_{opt}"                                      # Corpus file stem
        elf = os.path.join(OUT, tag + ".elf")                         # Intermediate ELF
        run([CC, "-march=rv32im", "-mabi=ilp32", f"-{opt}", "-nostdlib", "-ffreestanding", "-T", os.path.join(SRC, "link.ld"),
             os.path.join(SRC, "start.S"), os.path.join(SRC, "libc.c"), driver] + objs + ["-lgcc", "-o", elf])  # Link everything
        run([OBJCOPY, "-O", "binary", elf, os.path.join(OUT, tag + ".bin")])  # Raw binary
        run([OBJCOPY, "-O", "ihex", elf, os.path.join(OUT, tag + ".hex")])    # Intel HEX
        raw = open(os.path.join(OUT, tag + ".bin"), "rb").read()               # Read binary back
        open(os.path.join(OUT, tag + "_ram32k.bin"), "wb").write(raw + bytes(RAM_IMAGE - len(raw)))  # Padded RAM image
        manifest.append((tag + ".bin", "firmware", "all apps linked into one RISC-V image"))
        manifest.append((tag + ".hex", "hex_text", "Intel HEX text of the bundle"))
        manifest.append((tag + "_ram32k.bin", "ram_image", "bundle padded with zeros to a 32 KB RAM"))
        for tmp in objs + [elf]:                                       # Clean intermediates
            os.remove(tmp)
    os.remove(driver)


def build_native(manifest):
    """Takes slices of real x86-64 programs from this machine as native code samples."""
    for path in ("/bin/ls", "/bin/bash", "/usr/bin/python3"):  # Candidate native programs
        real = os.path.realpath(path)                          # Follow symlinks
        if not os.path.exists(real):                           # Skip when missing
            continue
        blob = open(real, "rb").read()                         # Read the whole program
        mid = len(blob) // 3                                   # Start a third in, inside the code
        tag = "native_" + os.path.basename(real)[:10] + ".bin"  # Corpus file name
        open(os.path.join(OUT, tag), "wb").write(blob[mid:mid + 48 * 1024])  # Save a 48 KB slice
        manifest.append((tag, "native", "x86-64 program slice"))


def build_data(manifest):
    """Creates deterministic data files of the kinds a processor keeps in memory."""
    rnd = random.Random(2026)  # Fixed seed so results repeat

    # IMU sensor stream as text, like the fakeimu file used with compengine.
    lines = ["ax,ay,az,gx,gy,gz"]  # CSV header line
    ax = ay = az = 0               # Slowly drifting values
    for i in range(1600):          # 1600 samples
        ax += rnd.randint(-3, 3); ay += rnd.randint(-3, 3); az += rnd.randint(-2, 2)  # Random walk
        lines.append(f"{ax},{ay},{16384+az},{int(40*math.sin(i/30))},{int(25*math.cos(i/50))},{rnd.randint(-4,4)}")  # One row
    open(os.path.join(OUT, "data_imu.csv"), "w").write("\n".join(lines))   # Write the CSV
    manifest.append(("data_imu.csv", "data_text", "IMU samples as text"))

    # The same kind of samples as packed int16 binary.
    buf = bytearray()  # Collects the packed samples
    for i in range(8000):  # 8000 six-axis samples would be big, use 4 axes
        buf += struct.pack("<hhhh", int(1000*math.sin(i/40)) + rnd.randint(-6, 6), int(800*math.cos(i/55)) + rnd.randint(-6, 6),
                           16384 + rnd.randint(-10, 10), rnd.randint(-3, 3))  # One sample
    open(os.path.join(OUT, "data_imu_i16.bin"), "wb").write(bytes(buf[:48 * 1024]))
    manifest.append(("data_imu_i16.bin", "data_bin", "packed int16 sensor samples"))

    # Table of pointers into a 64 KB region, like a heap of linked objects.
    ptrs = b"".join(struct.pack("<I", 0x20000000 + 16 * rnd.randint(0, 4095)) for _ in range(8192))
    open(os.path.join(OUT, "data_pointers.bin"), "wb").write(ptrs)
    manifest.append(("data_pointers.bin", "data_bin", "array of 32-bit pointers"))

    # Small counters and flags, mostly zero (typical .data and .bss).
    ints = b"".join(struct.pack("<I", rnd.choice([0, 0, 0, 0, 1, 2, 3, 255, rnd.randint(0, 1000)])) for _ in range(12288))
    open(os.path.join(OUT, "data_counters.bin"), "wb").write(ints)
    manifest.append(("data_counters.bin", "data_bin", "mostly small 32-bit integers"))

    # Float32 signal (sine plus noise).
    fl = b"".join(struct.pack("<f", math.sin(i / 20) + rnd.gauss(0, 0.01)) for i in range(12288))
    open(os.path.join(OUT, "data_float32.bin"), "wb").write(fl)
    manifest.append(("data_float32.bin", "data_bin", "float32 samples"))

    # English-like ASCII text from files on this machine, if any.
    text = b""
    for f in ("/usr/share/common-licenses/GPL-3", "/usr/share/common-licenses/Apache-2.0"):
        if os.path.exists(f):
            text += open(f, "rb").read()
    if text:
        open(os.path.join(OUT, "data_text.txt"), "wb").write(text[:48 * 1024])
        manifest.append(("data_text.txt", "data_text", "English text (license files)"))

    # Incompressible and all-zero controls.
    open(os.path.join(OUT, "ctrl_random.bin"), "wb").write(bytes(rnd.getrandbits(8) for _ in range(32 * 1024)))
    manifest.append(("ctrl_random.bin", "control", "random bytes, must not shrink"))
    open(os.path.join(OUT, "ctrl_zeros.bin"), "wb").write(bytes(32 * 1024))
    manifest.append(("ctrl_zeros.bin", "control", "all zeros, best case"))


def main():
    """Builds everything and writes the manifest."""
    os.makedirs(OUT, exist_ok=True)  # Make sure the output folder exists
    for old in glob.glob(os.path.join(OUT, "*")):  # Clear old files for a clean rebuild
        os.remove(old)
    manifest = []                    # Collects (file, kind, description)
    build_firmware(manifest)         # Real firmware
    build_bundle(manifest)           # Larger linked image
    build_native(manifest)           # Native code
    build_data(manifest)             # Data files
    with open(os.path.join(OUT, "MANIFEST.csv"), "w") as f:  # Write the manifest
        f.write("file,kind,description\n")
        for row in manifest:
            f.write(",".join(row[:2]) + "," + '"' + row[2] + '"\n')
    print(f"{len(manifest)} files in {OUT}")


if __name__ == "__main__":
    main()
