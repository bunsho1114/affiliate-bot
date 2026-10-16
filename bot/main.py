"""セール商品を集めて点数順に並べ、候補と投稿文の見本を daily/ に書き出す。

daily/copy.json に Claude が書いた紹介文があれば使う（毎朝の予定タスクが書く）。
使い方: python -m bot.main --preview 5
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys

from bot import compose, post, rakuten

KEYWORDS = ["半額", "50%OFF", "40%OFF", "30%OFF", "タイムセール", "クーポンで"]
DAILY = "daily"


def collect():
    seen, items, errors = set(), [], []
    # 1日12件投稿しても候補が尽きないよう、各キーワード2ページ分（60件）を見る
    for kw, page in ((kw, page) for kw in KEYWORDS for page in (1, 2)):
        try:
            found = rakuten.search(kw, page=page)
        except rakuten.RakutenError as e:
            errors.append(str(e))
            print(f"::error::{e}", flush=True)
            continue
        for it in found:
            code = it.get("itemCode")
            if code and code not in seen:
                seen.add(code)
                items.append(it)
    return items, errors


def load_copy():
    try:
        with open(f"{DAILY}/copy.json", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def slim(item):
    """Claudeが紹介文を書くのに必要な情報だけにする。"""
    caption = html.unescape(re.sub(r"<[^>]+>", " ", item.get("itemCaption", "")))
    return {
        "itemCode": item["itemCode"],
        "itemName": item.get("itemName", ""),
        "itemCaption": re.sub(r"\s+", " ", caption).strip()[:1500],
        "sale": compose.label(item),
        "itemPrice": item.get("itemPrice"),
        "reviewAverage": item.get("reviewAverage"),
        "reviewCount": item.get("reviewCount"),
        "item": item,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=int, default=5, help="見本にする件数")
    ap.add_argument("--candidates", type=int, default=10, help="紹介文を書いてもらう候補の件数")
    args = ap.parse_args()

    items, errors = collect()
    # 楽天ランキングに入っている商品は売れ筋なので候補に加え、点も上げる
    try:
        top = rakuten.ranking()
        print(f"::notice::楽天ランキング {len(top)}件を取得", flush=True)
    except rakuten.RakutenError as e:
        print(f"::warning::楽天ランキングを取れなかったのでランキング加点なしで選びます: {e}", flush=True)
        top = []
    ranked_codes = {i.get("itemCode") for i in top}
    seen = {i["itemCode"] for i in items}
    items += [i for i in top if i.get("itemCode") and i["itemCode"] not in seen]

    def points_of(i):
        return compose.score(i, ranked_codes)

    now = dt.datetime.now(post.JST)
    # 最近 Threads に投稿した商品は候補から外す
    skip = post.recent_codes(post.load(post.STATE, {}), now)
    # セールが終わった商品も外す（これから始まる商品は残し、投稿のときに始まっていれば使う）
    ended = {i["itemCode"] for i in items
             if (end := compose.sale_period(i, now)[1]) and end - compose.MIN_LEFT < now}
    ranked = sorted((i for i in items
                     if points_of(i) > 0 and i["itemCode"] not in skip | ended),
                    key=points_of, reverse=True)
    copies = load_copy()

    out = [f"# 投稿文の見本（{len(items)}件取得、条件に合う商品 {len(ranked)}件）", ""]
    if errors:
        out += ["## エラー", ""] + [f"- `{e}`" for e in errors] + [""]
    for n, it in enumerate(ranked[: args.preview], 1):
        copy = copies.get(it["itemCode"])
        text = compose.compose(it, copy)
        src = "Claudeの紹介文" if copy else "商品説明から抽出"
        out += [f"## 見本{n}（{len(text)}文字、{src}）", "", "```", text, "```", ""]

    report = "\n".join(out)
    print(report)
    os.makedirs(DAILY, exist_ok=True)
    with open(f"{DAILY}/preview.md", "w", encoding="utf-8") as f:
        f.write(report)
    with open(f"{DAILY}/candidates.json", "w", encoding="utf-8") as f:
        json.dump([slim(i) for i in ranked[: args.candidates]], f, ensure_ascii=False, indent=1)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    if errors and not items:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        # ログは読めないことがあるので、エラーの中身を注記として残す
        print("::error::" + traceback.format_exc().replace("\n", "%0A"), flush=True)
        raise
