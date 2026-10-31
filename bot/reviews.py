"""楽天のレビューページから、上位の候補の口コミ本文を少しだけ読んでくる。

楽天のAPIではレビュー本文が取れないので、商品ページからレビューページを探して1ページ目だけ読む。
アクセスは1日に数商品・数ページだけにして、間をあける。結果は daily/reviews.json に置き、
毎朝の紹介文づくり（WRITING.md）で「どんな声が多いか」の材料にする。
"""
import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read()
    for enc in ("utf-8", "euc-jp", "shift_jis"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def item_page(item):
    url = item.get("itemUrl", "")
    pc = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("pc")
    return pc[0] if pc else url


def review_url(page):
    m = re.search(r"https?://review\.rakuten\.co\.jp/item/1/(\d+_\d+)/", page)
    return m and f"https://review.rakuten.co.jp/item/1/{m.group(1)}/1.1/"


def texts(page):
    """レビュー本文を取り出す。ページに埋め込まれたJSONを優先し、無ければHTMLから拾う。"""
    out = []
    for m in re.finditer(r'"(?:reviewBody|body|reviewText|comment)"\s*:\s*"((?:[^"\\]|\\.){20,})"', page):
        try:
            out.append(json.loads(f'"{m.group(1)}"'))
        except ValueError:
            pass
    if not out:
        for m in re.finditer(r'<div[^>]*class="[^"]*review-body[^"]*"[^>]*>(.*?)</div>', page, re.S):
            out.append(html.unescape(re.sub(r"<[^>]+>", "", m.group(1))))
    seen, res = set(), []
    for t in (re.sub(r"\s+", " ", t).strip() for t in out):
        if len(t) >= 20 and t not in seen:
            seen.add(t)
            res.append(t[:400])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--debug", action="store_true", help="ページの一部を daily/reviews_debug.txt に残す")
    args = ap.parse_args()
    candidates = json.load(open("daily/candidates.json", encoding="utf-8"))
    result, debug = {}, []
    for c in candidates[:args.top]:
        code = c["itemCode"]
        try:
            page = get(item_page(c["item"]))
            time.sleep(3)
            url = review_url(page)
            if not url:
                print(f"::notice::{code} のレビューページが見つかりませんでした", flush=True)
                debug.append(f"== {code} item page (no review link)\n" + page[:3000])
                continue
            rpage = get(url)
            time.sleep(3)
            result[code] = {"url": url, "texts": texts(rpage)[:15]}
            print(f"::notice::{code}: 口コミ {len(result[code]['texts'])} 件", flush=True)
            if args.debug:
                i = rpage.find("review")
                debug.append(f"== {code} {url}\n" + rpage[:2000] + "\n...\n" + rpage[len(rpage)//2:len(rpage)//2+6000])
        except Exception as e:  # 口コミは無くても紹介文は書けるので、失敗しても止めない
            print(f"::warning::{code} の口コミを読めませんでした: {e}", flush=True)
    with open("daily/reviews.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    if args.debug:
        with open("daily/reviews_debug.txt", "w", encoding="utf-8") as f:
            f.write("\n\n".join(debug))


if __name__ == "__main__":
    main()
