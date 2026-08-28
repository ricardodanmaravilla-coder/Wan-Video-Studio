from pathlib import Path
import subprocess


def dims(aspect: str):
    if aspect == "9:16":
        return 540, 960
    if aspect == "1:1":
        return 720, 720
    return 960, 540


def generate_mock(prompt: str, output: Path, aspect: str = "16:9"):
    w, h = dims(aspect)
    vf = (
        f"drawtext=text='WAN VIDEO STUDIO':fontcolor=white:fontsize=38:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-35,"
        f"drawtext=text='SCENE TEST':fontcolor=white:fontsize=22:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+20"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x151922:s={w}x{h}:r=24:d=5",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", "5", str(output),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
