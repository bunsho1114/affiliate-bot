"""今日の候補から選んで Threads に投稿し、state/posted.json に記録する。

同じ商品は REPOST_DAYS 日のあいだ投稿しない。投稿直前に楽天から商品情報を取り直し、
売り切れやセール終了の商品、セール期間外の商品は飛ばす。
使い方: python -m bot.post [--count 4] [--dry-run]
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

from bot import compose, rakuten, threads

DAILY = "daily"
STATE = "state/posted.json"
REPOST_DAYS = 14
ACCOUNT = "ziyuunote1018"  # 投稿してよい Threads アカウント
JST = compose.JST


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return default


def recent_codes(posted, now):
    limit = now - dt.timedelta(days=REPOST_DAYS)
    return {code for code, v in posted.items() if dt.datetime.fromisoformat(v["at"]) >= limit}


def image(item):
    urls = item.get("mediumImageUrls") or []
    return urls[0].split("?")[0] + "?_ex=600x600" if urls else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="投稿せずに文面だけ表示する")
    ap.add_argument("--count", type=int, default=1, help="1回に投稿する件数")
    ap.add_argument("--gap", type=int, default=10, help="投稿と投稿のあいだの分数")
    ap.add_argument("--record-only", action="store_true",
                    help="Threads には投稿せず、今日の商品として記録だけする（投稿は手作業）")
    ap.add_argument("--min-since", type=int, default=0,
                    help="直前の投稿からこの分数が経っていなければ何もしない（遅れて動いた予定の二重投稿よけ）")
    args = ap.parse_args()

    if not args.dry_run and not args.record_only:
        # トークンが別のアカウントのものなら投稿しない（アカウントを切り替えたときの事故よけ）
        try:
            who = threads.username()
        except threads.ThreadsError as e:
            print(f"::error::Threads のアカウントを確かめられませんでした: {e}", flush=True)
            sys.exit(1)
        if who != ACCOUNT:
            print(f"::error::トークンが @{who} のものなので投稿しません（投稿先は @{ACCOUNT}）", flush=True)
            sys.exit(1)

    now = dt.datetime.now(JST)
    candidates = load(f"{DAILY}/candidates.json", [])
    copies = load(f"{DAILY}/copy.json", {})
    posted = load(STATE, {})
    skip = recent_codes(posted, now)
    if args.min_since and posted:
        prev = max(dt.datetime.fromisoformat(v["at"]) for v in posted.values())
        if now - prev < dt.timedelta(minutes=args.min_since):
            print(f"::notice::{prev:%H:%M} に投稿済みなので今回は投稿しません", flush=True)
            return

    # 同じ種類（楽天のジャンル）や同じショップの商品が続かないようにする。
    # まず直近24時間に出したジャンル・ショップを避け、それで足りなければ直前の1件とだけ違えばよい。
    genre_of = {c["itemCode"]: str(c["item"].get("genreId", "")) for c in candidates}
    history = sorted(((v["at"], (v.get("genre") or genre_of.get(code, ""))[:4], code.split(":")[0])
                      for code, v in posted.items()), reverse=True)
    day_ago = (now - dt.timedelta(hours=24)).isoformat(timespec="minutes")
    used = {(g, sh) for at, g, sh in history if at >= day_ago}
    last = history[0][1:] if history else None

    def kind(item):
        # 楽天のジャンル番号は近い種類ほど上4桁がそろう（牡蠣とカニ、など）ので、上4桁で種類を見る
        return str(item.get("genreId", ""))[:4], item.get("shopCode", "")

    def too_similar(item, strict):
        g, sh = kind(item)
        if strict:
            return any(g == ug or sh == ush for ug, ush in used)
        return last is not None and (g == last[0] or sh == last[1])

    done = 0
    for strict in (True, False):
        for c in candidates:
            code = c["itemCode"]
            if code in skip or too_similar(c["item"], strict):
                continue
            skip.add(code)
            try:
                item = rakuten.item(code)
            except rakuten.RakutenError as e:
                print(f"::warning::{e}", flush=True)
                item = None
            if not item or compose.score(item) == 0:
                print(f"::notice::{code} は売り切れかセール終了のようなので飛ばします", flush=True)
                continue
            if not compose.on_sale(item, dt.datetime.now(JST)):
                print(f"::notice::{code} はセール期間外（まだ始まっていない／終わった）なので飛ばします", flush=True)
                continue
            text = compose.compose(item, copies.get(code))
            print(text, flush=True)
            # 「今日の1件」ページが最新の価格で文章を作れるよう、取り直した商品情報で候補を上書きしておく
            c["item"] = item
            with open(f"{DAILY}/candidates.json", "w", encoding="utf-8") as f:
                json.dump(candidates, f, ensure_ascii=False, indent=1)
            if not args.dry_run:
                post_id = None
                if not args.record_only:
                    if done:
                        time.sleep(args.gap * 60)  # 続けて投稿すると宣伝ばかりに見えるので間をあける
                    try:
                        post_id = threads.publish(text, image(item))
                    except threads.ThreadsError as e:
                        print(f"::error::{code} を投稿できませんでした: {e}", flush=True)
                        continue
                posted[code] = {"at": now.isoformat(timespec="minutes"), "id": post_id,
                                "name": compose.clean_name(item.get("itemName", "")),
                                "genre": str(item.get("genreId", "")),
                                "url": post_id and threads.permalink(post_id)}
                os.makedirs(os.path.dirname(STATE), exist_ok=True)
                with open(STATE, "w", encoding="utf-8") as f:
                    json.dump(posted, f, ensure_ascii=False, indent=1)
                print(f"::notice::{'投稿しました' if post_id else '今日の商品に選びました'}: "
                      f"{posted[code]['url'] or posted[code]['name']}", flush=True)
            used.add(kind(item))
            last = kind(item)
            done += 1
            if done >= args.count:
                return

    if not done:
        print("::error::投稿できる候補がありませんでした", flush=True)
        sys.exit(1)
    print(f"::warning::候補が足りず {done} 件だけ投稿しました", flush=True)


if __name__ == "__main__":
    main()
