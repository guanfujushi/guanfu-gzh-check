#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号排版体检官 — 12 项形式检查，只查不改。

用法：
    python3 check_layout.py 文稿.md
    python3 check_layout.py 文稿.html --tag "观复的国学笔记"
    python3 check_layout.py 文稿.md --json

退出码：0 通过 / 1 有警告 / 2 有阻塞项
"""

import argparse
import json
import os
import re
import sys

BLOCK, WARN, INFO = "阻塞", "警告", "信息"

CJK = r"\u4e00-\u9fff"
CJK_PUNCT_FULL = "，。？！：；、"


def read_text(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def strip_tags(html):
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<br\s*/?>", "\n", txt, flags=re.I)
    txt = re.sub(r"</(p|div|h[1-6]|li|tr|section)>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = txt.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return txt


def paragraphs(text):
    out = []
    for blk in re.split(r"\n\s*\n", text):
        s = blk.strip()
        if s:
            out.append(s)
    return out


def body_len(text):
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", text)))


def check(path, tag=None):
    raw = read_text(path)
    is_html = path.lower().endswith((".html", ".htm"))
    text = strip_tags(raw) if is_html else raw
    paras = paragraphs(text)
    issues = []

    def add(level, item, detail, fix):
        issues.append({"level": level, "item": item, "detail": detail, "fix": fix})

    # 1 文首 AI 标识
    head = re.sub(r"\s", "", text[:400])
    if re.search(r"(本文由?AI|AI生成|内容由AI|人工智能生成|AI辅助生成)", head, re.I):
        add(BLOCK, "文首 AI 标识", "开头 400 字内出现 AI 生成声明",
            "删掉该行；AI 标识只留文末一处，开头贴 AI 标签读者会立刻划走")

    # 2 图注编号
    for m in re.finditer(r"图\s*[0-9一二三四五六七八九十]+\s*[：:、.]?", text):
        add(WARN, "图注编号", "出现「%s」" % m.group(0).strip(),
            "编号是内部稿痕迹，改成叙事性图注（一句话说画面里发生了什么）")
        break

    # 3 标题层级跳级（仅 Markdown）
    if not is_html:
        levels = [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s", text, re.M)]
        for i in range(1, len(levels)):
            if levels[i] - levels[i - 1] >= 2:
                add(WARN, "标题层级跳级", "从 H%d 直接跳到 H%d" % (levels[i - 1], levels[i]),
                    "中间补一级，或把后一级降成 H%d" % (levels[i - 1] + 1))
                break

    # 4 超长段落
    long_paras = [(i + 1, len(p)) for i, p in enumerate(paras) if len(p) > 200]
    if long_paras:
        idx, ln = max(long_paras, key=lambda x: x[1])
        add(WARN, "超长段落", "第 %d 段 %d 字（共 %d 段超 200 字）" % (idx, ln, len(long_paras)),
            "手机屏一段超过 5 行就眼累；在语义停顿处拆成 2–3 段")

    # 5 中英混排空格
    tight = re.findall(r"[%s][A-Za-z0-9]|[A-Za-z0-9][%s]" % (CJK, CJK), text)
    if len(tight) >= 3:
        add(INFO, "中英混排空格", "%d 处中英文紧贴未加空格" % len(tight),
            "中文与英文/数字之间留一个半角空格，观感立刻上一个档")

    # 6 半角标点混用
    halfw = re.findall(r"[%s][,\.\?!:;][%s]?" % (CJK, CJK), text)
    if len(halfw) >= 2:
        add(WARN, "半角标点", "%d 处中文里用了半角标点" % len(halfw),
            "改成全角「，。？！：；」；半角只留给英文与数字")

    # 7 连续空行
    if re.search(r"\n{4,}", text):
        add(INFO, "连续空行", "存在连续 3 个以上空行",
            "公众号后台会吃掉多余空行，留一个即可，免得样式忽宽忽窄")

    # 8 全角空格 / 行尾空格
    fw = text.count("\u3000")
    trail = len(re.findall(r"[ \t]+\n", text))
    if fw or trail:
        add(INFO, "空白字符", "全角空格 %d 个 / 行尾空格 %d 行" % (fw, trail),
            "全角空格在手机上宽度不可控，统一删掉；行尾空格一并清")

    # 9 品牌标签重复
    if tag:
        n = text.count(tag)
        if n >= 2:
            add(WARN, "品牌标签重复", "「%s」出现 %d 次" % (tag, n),
                "平台已自动标账号名，正文只留文末署名一处，重复=刷屏")

    # 10 图片缺 alt
    if is_html:
        imgs = re.findall(r"<img\b[^>]*>", raw, re.I)
        noalt = [t for t in imgs if not re.search(r"\balt\s*=\s*['\"][^'\"]+['\"]", t, re.I)]
        if noalt:
            add(INFO, "图片缺 alt", "%d 张图没有 alt 描述" % len(noalt),
                "补一句画面描述，图挂了也不至于全白，对无障碍也友好")

    # 11 裸露长链接
    for m in re.finditer(r"https?://[^\s\)\]]{60,}", text):
        add(INFO, "裸露长链接", "发现 %d 字符的裸链接" % len(m.group(0)),
            "改锚文本（如「点这里看原文」），长链接在手机端会折成三行")
        break

    # 12 字数与阅读时长
    n = body_len(text)
    minutes = max(1, round(n / 400))

    # 计分
    score = 100
    for it in issues:
        score -= {BLOCK: 15, WARN: 5, INFO: 1}[it["level"]]
    score = max(0, score)
    level_count = {
        BLOCK: sum(1 for i in issues if i["level"] == BLOCK),
        WARN: sum(1 for i in issues if i["level"] == WARN),
        INFO: sum(1 for i in issues if i["level"] == INFO),
    }
    return {
        "file": os.path.basename(path),
        "score": score,
        "issues": issues,
        "stats": {"chars": n, "minutes": minutes, "paragraphs": len(paras),
                  "avg_para": round(n / len(paras)) if paras else 0},
        "counts": level_count,
    }


def render(r):
    lines = []
    lines.append("════ 公众号排版体检报告 ════")
    lines.append("文件：%s      体检分：%d / 100" % (r["file"], r["score"]))
    lines.append("")
    if not r["issues"]:
        lines.append("全部通过 ✅ 可以粘进后台了。")
    for lv in (BLOCK, WARN, INFO):
        group = [i for i in r["issues"] if i["level"] == lv]
        if not group:
            continue
        lines.append("【%s】%d 项" % (lv, len(group)))
        for k, it in enumerate(group, 1):
            lines.append("  %s %s —— %s" % ("①②③④⑤⑥⑦⑧⑨⑩"[k - 1] if k <= 10 else "%d." % k, it["item"], it["detail"]))
            lines.append("     修法：%s" % it["fix"])
        lines.append("")
    s = r["stats"]
    lines.append("【信息】正文字数 %d 字 ｜ 预估阅读 %d 分 ｜ 段落 %d 段 ｜ 平均段长 %d 字"
                 % (s["chars"], s["minutes"], s["paragraphs"], s["avg_para"]))
    lines.append("════════════════════════")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="公众号排版体检官")
    ap.add_argument("path")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.path):
        print("找不到文件：%s" % a.path); sys.exit(2)
    r = check(a.path, a.tag)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else render(r))
    if r["counts"][BLOCK]:
        sys.exit(2)
    if r["counts"][WARN]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
