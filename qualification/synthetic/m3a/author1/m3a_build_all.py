#!/usr/bin/env python3
"""Build and verify driver (author 1). Runs the five generators twice into two scratch folders, requires identical
sha256 for every dataset, writes the datasets into the target folder, runs the self-check and the mutation runner and
writes the manifest. Usage: m3a_build_all.py [TARGET_DIR]   (default: the folder of this script). Own processes only."""
import hashlib, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAMS = ["surface", "delta25", "tenors", "coverage", "american"]
FILES = (["m3a_cases_%s.json" % f for f in FAMS] + ["gen_m3a_%s.py" % f for f in FAMS] +
         ["m3a_oracle.py", "m3a_scen.py", "m3a_ref.py", "m3a_selfcheck.py", "m3a_mutants.py", "m3a_build_all.py",
          "MUTATION_RESULTS.txt", "AUTHORING_NOTES.md", "STATUS.md"])


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def gen(out):
    os.makedirs(out, exist_ok=True)
    for f in FAMS:
        subprocess.run([sys.executable, os.path.join(HERE, "gen_m3a_%s.py" % f), "--out", out], check=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), stdout=subprocess.DEVNULL)


def main(argv):
    target = os.path.abspath(argv[1]) if len(argv) > 1 else HERE
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        gen(t1)
        gen(t2)
        for f in FAMS:
            n = "m3a_cases_%s.json" % f
            a, b = sha(os.path.join(t1, n)), sha(os.path.join(t2, n))
            print("determinism %-26s %s %s" % (n, a[:16], "SAME" if a == b else "DIFFERENT"))
            if a != b:
                return 1
        gen(target)
    import m3a_selfcheck, m3a_mutants
    rc = m3a_selfcheck.main(target)
    rc2 = m3a_mutants.main(["x", target, os.path.join(target, "MUTATION_RESULTS.txt")])
    if rc or rc2:
        return 1
    lines = []
    for f in FILES:
        p = os.path.join(target, f)
        if os.path.exists(p):
            lines.append("%s  %s\n" % (sha(p), f))
    open(os.path.join(target, "MANIFEST.sha256"), "w", newline="\n").write("".join(lines))
    print("manifest files:", len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
