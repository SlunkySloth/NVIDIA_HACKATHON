"""Narrate an actual browser capture using local eSpeak and FFmpeg."""
import argparse
import json
import subprocess
from pathlib import Path


def duration(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--espeak", default="espeak-ng")
    parser.add_argument("--voice", default="en-us")
    args = parser.parse_args()
    root = args.capture.resolve()
    captured = json.loads((root / "capture.json").read_text())
    mode = captured["mode"]
    parts, total = [], 0
    for index, scene in enumerate(captured["scenes"]):
        audio = root / f"narration-{index:02}.wav"
        speech = root / f"narration-{index:02}.txt"
        speech.write_text(scene["narration"])
        subprocess.run([args.espeak, "-v", args.voice, "-s", "175", "-w", str(audio), "-f", str(speech)], check=True)
        length = duration(audio) + 0.6
        available = scene["end"] - scene["start"]
        take = min(length, available)
        title = "ACTUAL LOCAL REFERENCE RUN | HUMAN-AUTHORED PATCH | NO INFERENCE" if mode == "reference" else "ACTUAL NVIDIA GENERATION | NEBIUS TOKEN FACTORY + SANDBOXES"
        if scene.get("compressed"):
            title += " | WAIT COMPRESSED"
        caption = root / f"caption-{index:02}.txt"
        caption.write_text(title)
        # The captured active-execution segment is shortened explicitly; other
        # segments are trimmed or held without inventing any UI or observations.
        filters = f"scale=1440:1000,pad=1440:1080:0:0:color=0x101a2a,tpad=stop_mode=clone:stop_duration={length},drawtext=textfile='{caption}':fontcolor=white:fontsize=20:x=24:y=1030"
        part = root / f"part-{index:02}.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(scene["start"]), "-t", str(take), "-i", str(root / "raw.webm"), "-i", str(audio), "-vf", filters, "-af", "apad", "-t", str(length), "-r", "25", "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(part)], check=True)
        parts.append(part)
        total += length
    if total >= 180:
        raise ValueError("Narrated demo must be less than three minutes; shorten the narration")
    listing = root / "parts.txt"
    listing.write_text("".join(f"file '{part.name}'\n" for part in parts))
    output = root / f"replaylab-{mode}-demo.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "1", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output)], check=True)
    metadata = {"mode": mode, "run_id": captured["run_id"], "video_seconds": duration(output), "actual_run_elapsed_seconds": captured["actual_run_elapsed_seconds"], "narration": "eSpeak NG generic synthetic English voice", "waiting_compressed": True, "public_upload": False}
    (root / "video-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"output": str(output), **metadata}, indent=2))


if __name__ == "__main__":
    main()
