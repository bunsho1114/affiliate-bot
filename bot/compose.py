"""商品データから割引率を読み取り、Threads用の投稿文（500文字以内）を作る。"""
import html
import math
import re

MAX_LEN = 500

_PCT = re.compile(r"(最大)?\s*(\d{1,2})\s*[%％]\s*(?:OFF|オフ|off|Off)")
_YEN_OFF = re.compile(r"(最大)?\s*([\d,]{2,7})\s*円\s*(?:OFF|オフ|off|引き|引)")
_POINT = re.compile(r"ポイント\s*(\d{1,2})\s*倍")
_TAG = re.compile(r"<[^>]+>")
_BRACKETS = re.compile(r"[【\[［〔(（<＜《][^】\]］〕)）>＞》]{0,40}[】\]］〕)）>＞》]")


def discount(item):
    """商品名から割引の表記を読み取る。(割引率%, 「最大」付きか) を返す。読めなければ None。"""
    name = item.get("itemName", "")
    best = None
    for m in _PCT.finditer(name):
        pct = int(m.group(2))
        if 10 <= pct <= 90 and (best is None or pct > best[0]):
            best = (pct, bool(m.group(1)))
    # 「2本目半額」「2点目半額」のような条件付きは割引とみなさない
    half = re.search(r"(?<![本個点枚着足目])(最大)?半額", name)
    if half and not re.search(r"\d+\s*[本個点枚着足]目\s*半額", name) and (best is None or best[0] < 50):
        best = (50, bool(half.group(1)))
    price = item.get("itemPrice") or 0
    for m in _YEN_OFF.finditer(name):
        yen = int(m.group(2).replace(",", ""))
        if price and 0 < yen < price * 3:
            pct = round(yen / (price + yen) * 100)
            if 10 <= pct <= 90 and (best is None or pct > best[0]):
                best = (pct, bool(m.group(1)))
    return best


def points(item):
    m = _POINT.search(item.get("itemName", ""))
    if m:
        return int(m.group(1))
    rate = item.get("pointRate") or 1
    return rate if rate >= 5 else None


def score(item):
    d = discount(item)
    if not d:
        return 0
    pct, is_max = d
    avg = float(item.get("reviewAverage") or 0)
    cnt = int(item.get("reviewCount") or 0)
    # 80%超の割引表記は元値の根拠が怪しいことが多いので除外する
    if avg < 4.0 or cnt < 30 or pct > 80:
        return 0
    s = pct * avg * math.log10(cnt)
    return s * (0.7 if is_max else 1.0)


_NOISE = re.compile(
    r"＼[^／]*／|\\[^/]*/|楽天(ランキング|市場)?\s*\d+位|ランキング\s*\d+位|\d+冠|"
    r"(最大)?\d{1,2}\s*[%％]\s*(OFF|オフ)|半額(セール)?|\d+\s*[%％]?\s*クーポン|クーポン(利用|使用)?で?|"
    r"P\s*\d+倍|ポイント\s*\d+倍|[\d,]+\s*円(OFF|オフ|引き)?|送料無料|あす楽|即納|セール|SALE|sale|"
    r"\d{4}年(間|度)|\d+\s*[本個点枚]目|[0-9]+%"
)


def clean_name(name, limit=42):
    name = _BRACKETS.sub(" ", name)
    name = _NOISE.sub(" ", name)
    name = re.sub(r"[【】\[\]［］〔〕＼／&＆+＋|｜]", " ", name)
    name = re.sub(r"[★☆◆◇■□●○♪！!※]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name if len(name) <= limit else name[:limit].rstrip() + "…"


def features(item, n=2):
    text = html.unescape(_TAG.sub(" ", item.get("itemCaption", "")))
    text = re.sub(r"https?://\S+", " ", text)
    parts = re.split(r"[。\n\r]|・|■|●|◆|★|【|】", text)
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" 　:：-")
        p = re.sub(r"^(商品説明|商品詳細|商品紹介|特徴|ポイント)\s*[:：]?\s*", "", p)
        if p.startswith(("※", "*", "＊")) or re.match(r"^[^ ]{1,8}[:：]", p):
            continue
        if 8 <= len(p) <= 40 and not re.search(
            r"送料|注意|ご了承|返品|発送|お届け|配送|メール|当店|在庫|JAN|型番|価格|メーカー希望|予告なく|クーポン|"
            r"ポイント|レビュー|ランキング|保証|交換|問い合わせ|品番|サイズ|カラー|原材料|内容量|生産国|製造|"
            r"振込|支払|決済|詳細は|こちら|→|あす楽|ギフト対応|のし", p) and len(re.findall(r"[ぁ-んァ-ヶ一-龯]", p)) >= len(p) * 0.4:
            if p not in out:
                out.append(p)
        if len(out) >= n:
            break
    return out


def headline(pct, is_max):
    if pct >= 50 and not is_max:
        return f"今なら{pct}%OFF！" if pct != 50 else "今なら半額！"
    return f"{'最大' if is_max else ''}{pct}%OFFのセール中"


def compose(item):
    pct, is_max = discount(item)
    avg = float(item.get("reviewAverage") or 0)
    cnt = int(item.get("reviewCount") or 0)
    price = int(item.get("itemPrice") or 0)
    pt = points(item)
    link = item.get("affiliateUrl") or item.get("itemUrl")

    lines = [f"【PR】{headline(pct, is_max)}", clean_name(item.get("itemName", "")), ""]
    lines.append(f"💰 {'最大' if is_max else ''}{pct}%OFF（ショップ表記）／投稿時点 {price:,}円")
    lines.append(f"⭐ 評価{avg:.2f}（レビュー{cnt:,}件）")
    if pt:
        lines.append(f"🎁 ポイント{pt}倍")
    for f in features(item):
        lines.append(f"✔ {f}")
    tail = ["", "▶ 楽天で見る", link, "※価格・在庫は変わることがあります"]

    text = "\n".join(lines + tail)
    while len(text) > MAX_LEN and len(lines) > 4:
        lines.pop()
        text = "\n".join(lines + tail)
    return text
