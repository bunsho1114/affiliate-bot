"""セール商品を集めて点数順に並べ、投稿文の見本を作る（ステップ2：投稿はしない）。

使い方: python -m bot.main --preview 5
"""
import argparse
import json
import os
import sys

from bot import compose, rakuten

KEYWORDS = ["半額", "50%OFF", "40%OFF", "30%OFF", "タイムセール", "クーポンで"]


def collect():
    seen, items, errors = set(), [], []
    for kw in KEYWORDS:
        try:
            found = rakuten.search(kw)
        except rakuten.RakutenError as e:
            errors.append(str(e))
            continue
        for it in found:
            code = it.get("itemCode")
            if code and code not in seen:
                seen.add(code)
                items.append(it)
    return items, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=int, default=5, help="見本にする件数")
    args = ap.parse_args()

    items, errors = collect()
    ranked = sorted((i for i in items if compose.score(i) > 0), key=compose.score, reverse=True)

    out = [f"# 投稿文の見本（{len(items)}件取得、条件に合う商品 {len(ranked)}件）", ""]
    if errors:
        out += ["## エラー", ""] + [f"- `{e}`" for e in errors] + [""]
    for n, it in enumerate(ranked[: args.preview], 1):
        text = compose.compose(it)
        out += [f"## 見本{n}（{len(text)}文字、点数 {compose.score(it):.0f}）", "", "```", text, "```", ""]

    report = "\n".join(out)
    print(report)
    os.makedirs("out", exist_ok=True)
    with open("out/preview.md", "w", encoding="utf-8") as f:
        f.write(report)
    with open("out/candidates.json", "w", encoding="utf-8") as f:
        json.dump(ranked[:30], f, ensure_ascii=False, indent=1)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    if errors and not items:
        sys.exit(1)


if __name__ == "__main__":
    main()
