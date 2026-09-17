#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_assets.py —— 把 demo/shots/ 里的分步截图合成为两张展示用图：

  demo/shots/steps-overview.png   一页总览（2 列 × 5 行缩略图）
  demo/demo.gif                   逐步骤动图（README 可直接引用）

用法：python make_assets.py [--shots demo/shots] [--out demo]
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw, ImageFont

LABELS = {
    "01": "① 引用规则模版",
    "02": "② 选择媒体账号",
    "03": "③ 第 1 个广告户填完",
    "04": "③ 切换第 2 户 → 商品库被重置",
    "05": "③ 第 2 户重新填写",
    "06": "④ 未先清空 → 校验拦下",
    "07": "④ 先清空再写入 → 通过",
    "08": "⑤ 素材按商品ID检索取全",
    "09": "⑥ 生成计划草稿",
    "10": "⑥ 提交完成",
}


def font(size):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except Exception:
            continue
    return ImageFont.load_default()


def build_overview(files, out_path, cols=2, thumb_w=700, pad=18, label_h=38):
    thumbs = []
    for f in files:
        im = Image.open(f).convert("RGB")
        h = int(im.height * thumb_w / im.width)
        thumbs.append(im.resize((thumb_w, h), Image.LANCZOS))
    rows = (len(thumbs) + cols - 1) // cols
    cell_h = max(t.height for t in thumbs) + label_h + pad
    W = cols * thumb_w + (cols + 1) * pad
    H = rows * cell_h + (rows + 1) * pad
    canvas = Image.new("RGB", (W, H), (245, 246, 248))
    d = ImageDraw.Draw(canvas)
    fnt = font(20)
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = pad + c * (thumb_w + pad)
        y = pad + r * cell_h
        key = os.path.basename(files[i])[:2]
        d.rectangle([x - 1, y - 1, x + thumb_w, y + label_h - 6], fill=(255, 255, 255))
        d.text((x + 6, y + 6), LABELS.get(key, key), fill=(31, 35, 41), font=fnt)
        canvas.paste(t, (x, y + label_h))
    canvas.save(out_path, optimize=True)
    print("总览图:", out_path, canvas.size)
    return canvas.size


def build_gif(files, out_path, width=860, duration=1400):
    frames = []
    for f in files:
        im = Image.open(f).convert("RGB")
        h = int(im.height * width / im.width)
        im = im.resize((width, h), Image.LANCZOS)
        frames.append(im.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG))
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=True, disposal=2)
    size_mb = os.path.getsize(out_path) / 1048576
    print(f"动图: {out_path}  {len(frames)} 帧  {size_mb:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="shots")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.shots, "*.png")))
    files = [f for f in files if not os.path.basename(f).startswith("steps-overview")]
    if not files:
        print("未找到截图")
        return 1

    build_overview(files, os.path.join(args.shots, "steps-overview.png"))
    build_gif(files, os.path.join(args.out, "demo.gif"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
