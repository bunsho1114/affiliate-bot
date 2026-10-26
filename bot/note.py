"""note の記事（タイトルと本文）を作る。note は自動投稿できないので、ページからコピーして貼る。"""
import datetime as dt

from bot import compose


def article(item, copy=None, now=None):
    """(タイトル, 本文) を返す。copy は Claude が書いた紹介文 {"hook", "points", "note"}。"""
    now = now or dt.datetime.now(compose.JST)
    if copy and compose._BANNED.search(copy.get("hook", "") + "".join(copy.get("points", [])) + copy.get("note", "")):
        copy = None
    name = compose.clean_name(item.get("itemName", ""), limit=60)
    sale = compose.label(item)
    cp = compose.coupon(item)
    price = int(item.get("itemPrice") or 0)
    avg = float(item.get("reviewAverage") or 0)
    cnt = int(item.get("reviewCount") or 0)
    pt = compose.points(item)
    link = compose.short_link(item)
    end = compose.sale_period(item, now)[1]

    title = f"【PR】{sale}｜{compose.clean_name(item.get('itemName', ''), limit=30)}"
    lines = ["※この記事はアフィリエイト広告（楽天アフィリエイト）を利用しています。", ""]
    if copy and copy.get("hook"):
        lines += [copy["hook"], ""]
    lines += ["■ 今日の商品", name, f"（{item.get('shopName', '')}）", ""]
    lines += ["■ セール情報", f"{sale}（ショップ表記）",
              f"価格：{price:,}円{'（クーポン適用前）' if cp else ''}（{now.month}/{now.day}時点）"]
    if end:
        week = "月火水木金土日"[end.weekday()]
        lines.append(f"期限：{end.month}/{end.day}({week}) {end.hour}:{end.minute:02d}まで（ショップ表記）")
    if pt:
        lines.append(f"ポイント{pt}倍")
    lines += ["", "■ みんなの評価", f"★{avg:.2f}（レビュー{cnt:,}件）", ""]
    good = copy["points"][:2] if copy and copy.get("points") else compose.features(item)
    if good:
        lines += ["■ ここがいい"] + [f"・{g}" for g in good] + [""]
    if copy and copy.get("note"):
        lines += [copy["note"], ""]
    lines += ["▼ 商品ページはこちら", link, "",
              "※価格・セール内容・在庫は変わることがあります。購入前に商品ページでご確認ください。", "",
              "#PR #楽天 #セール #お買い物"]
    return title, "\n".join(lines)
