"""今日の候補から1件選んで Threads に投稿し、state/posted.json に記録する。

同じ商品は REPOST_DAYS 日のあいだ投稿しない。投稿直前に楽天から商品情報を取り直し、
売り切れやセール終了の商品は飛ばす。
使い方: python -m bot.post [--dry-run]
"""
import argparse
import datetime as dt
import json
import os
import sys

from bot import compose, rakuten, threads

DAILY = "daily"
STATE = "state/posted.json"
REPOST_DAYS = 14
JST = dt.timezone(dt.timedelta(hours=9))


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
    args = ap.parse_args()

    now = dt.datetime.now(JST)
    candidates = load(f"{DAILY}/candidates.json", [])
    copies = load(f"{DAILY}/copy.json", {})
    posted = load(STATE, {})
    skip = recent_codes(posted, now)

    for c in candidates:
        code = c["itemCode"]
        if code in skip:
            continue
        try:
            item = rakuten.item(code)
        except rakuten.RakutenError as e:
            print(f"::warning::{e}", flush=True)
            item = None
        if not item or compose.score(item) == 0:
            print(f"::notice::{code} は売り切れかセール終了のようなので飛ばします", flush=True)
            continue
        text = compose.compose(item, copies.get(code))
        print(text, flush=True)
        if args.dry_run:
            return
        post_id = threads.publish(text, image(item))
        posted[code] = {"at": now.isoformat(timespec="minutes"), "id": post_id,
                        "name": compose.clean_name(item.get("itemName", "")),
                        "url": threads.permalink(post_id)}
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(posted, f, ensure_ascii=False, indent=1)
        print(f"::notice::投稿しました: {posted[code]['url'] or post_id}", flush=True)
        return

    print("::error::投稿できる候補がありませんでした", flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
