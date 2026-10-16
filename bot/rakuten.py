"""楽天市場 商品検索API（openapi.rakuten.co.jp）からセール商品を取ってくる。"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
RANKING = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
# 楽天のアプリ登録で「許可されたWebサイト」に入れたドメイン。新APIはこれをRefererで確認する。
SITE = "https://bunsho1114.github.io/"


class RakutenError(Exception):
    pass


def _call(extra, endpoint=ENDPOINT):
    params = {
        "applicationId": os.environ["RAKUTEN_APP_ID"],
        "accessKey": os.environ["RAKUTEN_ACCESS_KEY"],
        "affiliateId": os.environ.get("RAKUTEN_AFFILIATE_ID", ""),
        "format": "json",
        "formatVersion": 2,
        **extra,
    }
    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Referer": SITE,
        "Origin": SITE.rstrip("/"),
        "User-Agent": "affiliatebot/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise RakutenError(f"HTTP {e.code} for {extra}: {body}") from None
    finally:
        time.sleep(1.2)  # 楽天APIは1秒に1回まで
    return data.get("Items", [])


def search(keyword, hits=30, page=1, sort="-reviewCount", min_price=1000):
    return _call({
        "keyword": keyword,
        "hits": hits,
        "page": page,
        "sort": sort,
        "minPrice": min_price,
        "availability": 1,
        "imageFlag": 1,
    })


def item(code):
    """商品コード（shop:12345）で今の商品情報を取り直す。売り切れなどで無ければ None。"""
    found = _call({"itemCode": code, "availability": 1})
    return found[0] if found else None


def ranking(pages=(1, 2, 3)):
    """楽天市場の総合ランキング上位（1ページ30件）の商品。"""
    items = []
    for page in pages:
        items += _call({"page": page}, RANKING)
    return items
