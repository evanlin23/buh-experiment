#!/usr/bin/env python3
"""Spec -> finished, checked, packaged Short.

    python shorts/make.py shorts/specs/paper_12_folds.json            # render + QA + package
    python shorts/make.py shorts/specs/*.json --jobs 4                 # a batch
    python shorts/make.py shorts/specs/new_idea.json --review          # fast preview contact sheet only

Output per spec in renders/<slug>/: video.mp4, cover.png, sheet.png, qa.json, upload.md, upload.json.
A render is skipped when the spec and the engine are unchanged (use --force to redo).
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")   # one BLAS thread per worker; the workers are the parallelism

import argparse  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image  # noqa: E402

import package  # noqa: E402
import qa  # noqa: E402
from engine import DEFAULT_HANDLE, Video, render_stills, render_video  # noqa: E402
from ladder_short import LadderShort  # noqa: E402
from race_short import RaceShort  # noqa: E402
from reveal_short import RevealShort  # noqa: E402
from area_short import AreaShort  # noqa: E402

TEMPLATES = {"ladder": LadderShort, "race": RaceShort, "reveal": RevealShort, "area": AreaShort}


def scene_for(v, spec):
    return TEMPLATES[spec.get("template", "ladder")](v, spec)

PUBLISHED = os.path.join(HERE, "specs", "published.json")
SOURCES = ["engine.py", "ladder.py", "ladder_short.py", "race_short.py", "reveal_short.py", "area_short.py", "units.py"]


def load(paths):
    files = []
    for p in paths:
        files += sorted(glob.glob(os.path.join(p, "*.json"))) if os.path.isdir(p) else [p]
    out = []
    for f in files:
        if os.path.basename(f) == "published.json":
            continue
        with open(f) as fh:
            out.append((f, json.load(fh)))
    return out


def registry_problems(specs):
    """Every Short must be its own idea: no repeated slug, title or topic, and nothing already published."""
    everything = load([os.path.join(HERE, "specs")])
    published = json.load(open(PUBLISHED)) if os.path.exists(PUBLISHED) else []
    pub_topics = {p.get("topic", "").lower() for p in published}
    problems = []
    for path, s in specs:
        for key in ("slug", "topic"):
            same = [p for p, o in everything if o.get(key) == s.get(key) and os.path.abspath(p) != os.path.abspath(path)]
            if same:
                problems.append(f"{s['slug']}: {key} '{s.get(key)}' also used by {os.path.basename(same[0])}")
        title = s.get("package", {}).get("title", "").lower()
        if any(o.get("package", {}).get("title", "").lower() == title and os.path.abspath(p) != os.path.abspath(path)
               for p, o in everything):
            problems.append(f"{s['slug']}: duplicate title")
        if s.get("topic", "").lower() in pub_topics and not any(p.get("slug") == s["slug"] for p in published):
            problems.append(f"{s['slug']}: topic already published")
    return problems


def fingerprint(spec):
    h = hashlib.sha256(json.dumps(spec, sort_keys=True).encode())
    for f in SOURCES:
        h.update(open(os.path.join(HERE, f), "rb").read())
    return h.hexdigest()[:16]


def contact_sheet(paths, out, cols=8):
    ims = [Image.open(p).convert("RGB") for p in paths]
    w = 270
    ims = [im.resize((w, int(im.height * w / im.width))) for im in ims]
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 4), rows * (ims[0].height + 4)), (9, 7, 28))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * (w + 4), (i // cols) * (ims[0].height + 4)))
    sheet.save(out)


def make_one(path, spec, args):
    slug = spec["slug"]
    out = os.path.join(args.out, slug)
    os.makedirs(out, exist_ok=True)
    factory = lambda v: scene_for(v, spec)  # noqa: E731
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        scene = scene_for(Video(True, args.handle), spec)
        stills = render_stills(factory, tmp, scene.key_times, preview=True, handle=args.handle)
        contact_sheet(stills, os.path.join(out, "sheet.png"))
        if args.review:
            return dict(slug=slug, status="review", sheet=os.path.join(out, "sheet.png"), secs=time.time() - t0)
        cover_t = spec.get("cover", {}).get("t", scene.key_times[len(scene.key_times) // 2])
        cov = render_stills(factory, tmp, [cover_t], preview=args.preview, handle=args.handle, headline="hook")[0]
        shutil.copy(cov, os.path.join(out, "cover.png"))
    video = os.path.join(out, "video.mp4")
    fp = fingerprint(spec) + ("-preview" if args.preview else "") + args.handle
    man_path = os.path.join(out, "manifest.json")
    old = json.load(open(man_path)) if os.path.exists(man_path) else {}
    rendered = False
    if args.force or old.get("fingerprint") != fp or not os.path.exists(video):
        render_video(factory, video, preview=args.preview, handle=args.handle, jobs=args.jobs,
                     log=lambda s: print(f"[{slug}] {s.strip()}", flush=True))
        rendered = True
    res = qa.run(video, os.path.join(out, "qa.json"))
    full = scene_for(Video(args.preview, args.handle), spec)
    package.build(spec, full, out, "video.mp4", res)
    json.dump(dict(slug=slug, spec=os.path.relpath(path, HERE), fingerprint=fp, built=time.strftime("%Y-%m-%d %H:%M"),
                   qa_ok=res["ok"]), open(man_path, "w"), indent=1)
    return dict(slug=slug, status="PASS" if res["ok"] else "FAIL", secs=time.time() - t0, rendered=rendered,
                fails=[c["metric"] for c in res["checks"] if not c["ok"]], dur=res["metrics"]["duration_s"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="+", help="spec files or directories")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "renders"))
    ap.add_argument("--preview", action="store_true", help="540x960 render (fast check)")
    ap.add_argument("--review", action="store_true", help="only write the preview contact sheet")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--handle", default=DEFAULT_HANDLE)
    args = ap.parse_args()
    specs = load(args.specs)
    problems = registry_problems(specs)
    if problems:
        print("Registry problems (each Short must be a distinct idea):")
        for p in problems:
            print("  -", p)
        sys.exit(2)
    results = []
    for p, s in specs:
        try:
            results.append(make_one(p, s, args))
        except Exception as e:                      # one broken spec must not stop the batch
            import traceback
            traceback.print_exc()
            results.append(dict(slug=s.get("slug", p), status="ERROR", secs=0, fails=[f"{type(e).__name__}: {e}"], rendered=False))
    print("\nslug                         status  length  time   notes")
    for r in results:
        notes = r.get("sheet", "") if r["status"] == "review" else ("failed: " + ", ".join(r["fails"]) if r["fails"] else
                                                                     ("rendered" if r["rendered"] else "up to date"))
        print(f"{r['slug']:28s} {r['status']:6s}  {r.get('dur', 0):5.1f}s {r['secs']:5.0f}s  {notes}")
    for r in results:
        if r["status"] == "ERROR":
            print(f"  {r['slug']}: {r['fails'][0]}")
    sys.exit(0 if all(r["status"] in ("PASS", "review") for r in results) else 1)


if __name__ == "__main__":
    main()
