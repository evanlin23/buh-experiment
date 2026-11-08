"""Upload packaging from a spec: upload.md (paste-ready) and upload.json (machine-readable).

The step table in the description is computed from the same q(n) the video draws, so
the numbers in the description always match the numbers on screen.
"""
import json
import os

CHANNEL = "@packedbuh"

SETTINGS = [
    ("Audience", "No, it's not made for kids", "'Made for kids' turns off comments and most recommendations"),
    ("Altered or synthetic content", "No", "Code-rendered abstract animation; nothing realistic"),
    ("Category", "Education", ""),
    ("Comments", "On", ""),
    ("Audio", "Keep the original",
     "Every note is generated. A library track would take a revenue share and invite claims on cross-posts"),
    ("Cover", "Upload cover.png, or pick the frame at {cover_t}", ""),
]


def description(spec, scene):
    pk = spec["package"]
    fmt = pk.get("step_format", "{n}: {q} ({note})")
    steps = [fmt.format(**{**scene.fields_for(int(n)), "note": note}) for n, note in pk.get("steps", {}).items()]
    lines = []
    for line in pk["description"]:
        lines.extend(steps if line == "{steps}" else [line])
    lines += ["", pk.get("question", "Which number surprised you most? 👇"), "",
              " ".join("#" + h for h in pk.get("hashtags", []))]
    return "\n".join(lines)


def build(spec, scene, out_dir, video="video.mp4", qa=None):
    pk = spec["package"]
    cover_t = spec.get("cover", {}).get("t", 0)
    desc = description(spec, scene)
    data = dict(
        slug=spec["slug"], channel=CHANNEL, video=video, cover="cover.png",
        duration_s=round(scene.duration, 2),
        youtube=dict(title=pk["title"], alt_titles=pk.get("alt_titles", []), description=desc,
                     pinned_comment=pk.get("pinned", ""), tags=pk.get("tags", []),
                     made_for_kids=False, altered_content=False, category="Education"),
        tiktok=pk.get("tiktok", ""), reels=pk.get("reels", ""),
        sources=pk.get("sources", []), qa_ok=None if qa is None else qa["ok"],
    )
    with open(os.path.join(out_dir, "upload.json"), "w") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)

    mmss = f"0:{int(cover_t):02d}"
    md = [f"# {pk['title']} ({CHANNEL})", "",
          f"- `{video}`: 1080×1920, {scene.duration:.1f} s",
          f"- `cover.png`: the frame at {mmss}"]
    if qa:
        m = qa["metrics"]
        md.append(f"- QA {'PASS' if qa['ok'] else 'FAIL'}: dead air {m['dead_air_s']} s, still {m['still_share']:.0%}, "
                  f"loop seam {m['loop_seam']}, {m['lufs']} LUFS")
    md += ["", "## YouTube Shorts", "", f"**Title:** {pk['title']}", ""]
    if pk.get("alt_titles"):
        md += ["Alternates (for cross-posts, or a later test):"] + [f"- {t}" for t in pk["alt_titles"]] + [""]
    md += ["**Description:**", "", "```", desc, "```", "", "**Pinned comment:**", "", "```", pk.get("pinned", ""), "```", "",
           "**Settings:**", "", "| Setting | Value | Why |", "|---|---|---|"]
    md += [f"| {a} | {b.format(cover_t=mmss)} | {c} |" for a, b, c in SETTINGS]
    if pk.get("tags"):
        md += [f"| Tags (optional) | {', '.join(pk['tags'])} | |"]
    md += ["", "## Cross-posts", "",
           "TikTok pays only for videos over 1 minute, so post there for reach. The video carries only our own handle.", ""]
    if pk.get("tiktok"):
        md += ["**TikTok:**", "", "```", pk["tiktok"], "```", ""]
    if pk.get("reels"):
        md += ["**Instagram Reels:**", "", "```", pk["reels"], "```", ""]
    if pk.get("sources"):
        md += ["## Sources", ""] + [f"- {s}" for s in pk["sources"]]
    with open(os.path.join(out_dir, "upload.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")
    return data
