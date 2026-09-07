"""تولید لوگوی برنامه (app.ico) با Pillow.

یک آیکون تمیز و مدرن: مربع گِرد آبی با یک مانیتور سفید و چرخ‌دنده‌ی سرویس.
اجرا:  python assets/make_icon.py
خروجی: assets/app.ico  و  assets/app.png
"""
import os
import math
from PIL import Image, ImageDraw

SIZE = 512
PRIMARY = (37, 99, 235)      # #2563EB
PRIMARY_DK = (29, 78, 216)   # #1D4ED8
WHITE = (255, 255, 255)


def rounded_bg(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # پس‌زمینه‌ی گرادیانی عمودی از آبی روشن به تیره
    for y in range(size):
        t = y / size
        r = int(PRIMARY[0] * (1 - t) + PRIMARY_DK[0] * t)
        g = int(PRIMARY[1] * (1 - t) + PRIMARY_DK[1] * t)
        b = int(PRIMARY[2] * (1 - t) + PRIMARY_DK[2] * t)
        d.line([(0, y), (size, y)], fill=(r, g, b, 255))
    # ماسک گوشه‌گرد
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255
    )
    img.putalpha(mask)
    return img


def draw_gear(d, cx, cy, r_out, r_in, teeth, fill):
    pts = []
    for i in range(teeth * 2):
        ang = math.pi * i / teeth
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill=fill)


def build(size=SIZE):
    img = rounded_bg(size)
    d = ImageDraw.Draw(img)
    s = size

    # --- مانیتور ---
    mx0, my0 = int(s * 0.20), int(s * 0.24)
    mx1, my1 = int(s * 0.80), int(s * 0.60)
    d.rounded_rectangle([mx0, my0, mx1, my1], radius=int(s * 0.04), fill=WHITE)
    # صفحه‌ی داخل مانیتور (آبی)
    pad = int(s * 0.035)
    d.rounded_rectangle(
        [mx0 + pad, my0 + pad, mx1 - pad, my1 - pad],
        radius=int(s * 0.02), fill=PRIMARY,
    )
    # پایه و کف مانیتور
    d.rectangle([int(s * 0.46), my1, int(s * 0.54), int(s * 0.66)], fill=WHITE)
    d.rounded_rectangle(
        [int(s * 0.36), int(s * 0.66), int(s * 0.64), int(s * 0.70)],
        radius=int(s * 0.02), fill=WHITE,
    )

    # --- خطوط «لاگ» روی صفحه ---
    lx = mx0 + pad * 2
    for i, w in enumerate((0.34, 0.28, 0.20)):
        y = my0 + pad * 2 + int(i * s * 0.055)
        d.rounded_rectangle(
            [lx, y, lx + int(s * w), y + int(s * 0.022)],
            radius=int(s * 0.011), fill=WHITE,
        )

    # --- چرخ‌دنده‌ی سرویس (گوشه‌ی پایین-راست) ---
    gcx, gcy = int(s * 0.72), int(s * 0.72)
    draw_gear(d, gcx, gcy, int(s * 0.16), int(s * 0.115), 8, WHITE)
    d.ellipse(
        [gcx - int(s * 0.05), gcy - int(s * 0.05),
         gcx + int(s * 0.05), gcy + int(s * 0.05)],
        fill=PRIMARY_DK,
    )
    return img


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    img = build(SIZE)
    png = os.path.join(here, "app.png")
    ico = os.path.join(here, "app.ico")
    img.save(png)
    img.save(
        ico,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
               (128, 128), (256, 256)],
    )
    print("wrote", png)
    print("wrote", ico)


if __name__ == "__main__":
    main()
