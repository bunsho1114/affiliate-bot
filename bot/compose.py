"""商品データから割引率を読み取り、Threads用の投稿文（500文字以内）を作る。"""
import datetime as dt
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


def coupon(item):
    """クーポン利用が条件の割引か（商品名に「クーポン」があれば条件付きとみなす）。"""
    return "クーポン" in item.get("itemName", "")


JST = dt.timezone(dt.timedelta(hours=9))
# 投稿を見た人が買う時間が残るよう、終わりまでこれより短いセールは投稿しない
MIN_LEFT = dt.timedelta(minutes=30)

_D = r"(\d{1,2})[/月](\d{1,2})日?(?:\s*[(（][^)）]{1,3}[)）])?\s*"  # 10/17(土) / 10月17日
_T = r"(\d{1,2})(?:[:：時](\d{2})?分?)"                              # 9:59 / 21時
_RANGE = re.compile(_D + _T + r"?\s*(?:[~～〜]|から|より)\s*(?:" + _D + r")?" + _T + r"?\s*(?:まで|迄)?")
_HOURS = re.compile(_D + _T + r"\s*(?:から|より)\s*(\d{1,2})\s*時間限定")
_UNTIL = re.compile(_D + _T + r"?\s*(?:まで|迄)")
_DAY = re.compile(_D + r"(?:\d{1,2}[:：時]\d{0,2}\s*)?(?:限定|のみ|当日)")


def _at(now, month, day, hour=None, minute=None, end=False):
    """月日（年なし）を now に近い年の日時にする。時刻が無ければその日の始まり／終わり。"""
    if hour is None:
        hour, minute = (23, 59) if end else (0, 0)
    year = now.year
    if int(month) == 1 and now.month == 12:
        year += 1
    elif int(month) == 12 and now.month == 1:
        year -= 1
    try:
        return dt.datetime(year, int(month), int(day), min(int(hour), 23), int(minute or 0), tzinfo=JST)
    except ValueError:
        return None


def sale_period(item, now):
    """セール期間 (開始, 終了) を返す。分からない側は None。
    楽天APIのタイムセール時刻（startTime/endTime）を優先し、無ければ商品名の期間表記を読む。"""
    def api(key):
        try:
            return dt.datetime.strptime(item.get(key) or "", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        except ValueError:
            return None
    start, end = api("startTime"), api("endTime")
    if start or end:
        return start, end
    name = item.get("itemName", "")
    m = _HOURS.search(name)
    if m:
        s = _at(now, *m.group(1, 2, 3, 4))
        return s, s and s + dt.timedelta(hours=int(m.group(5)))
    m = _RANGE.search(name)
    if m:
        mo1, d1, h1, mi1, mo2, d2, h2, mi2 = m.groups()
        s = _at(now, mo1, d1, h1, mi1)
        e = _at(now, mo2 or mo1, d2 or d1, h2, mi2, end=True)
        if s and e and e < s:  # 「10/15 0:00〜23:59」のように日付が省略された同じ日
            e = None
        return s, e
    m = _UNTIL.search(name)
    if m:
        return None, _at(now, *m.groups(), end=True)
    m = _DAY.search(name)
    if m:
        return _at(now, *m.groups()), _at(now, *m.groups(), end=True)
    return None, None


def on_sale(item, now):
    """今セール中か。期間が書かれていなければ商品名の表記を信じて True。"""
    start, end = sale_period(item, now)
    if start and now < start:
        return False
    if end and now > end - MIN_LEFT:
        return False
    return True


def points(item):
    m = _POINT.search(item.get("itemName", ""))
    if m:
        return int(m.group(1))
    rate = item.get("pointRate") or 1
    return rate if rate >= 5 else None


# 効果をうたいやすく薬機法・景品表示法で危ない商品は扱わない
_RISKY = re.compile(r"ダイエット|サプリ|痩身|脂肪|育毛|発毛|医薬品|精力")
# 「2点で半額」のような、まとめ買いが条件の割引
_BUNDLE = re.compile(r"\d+\s*[点個本枚箱袋着足セット]\s*(以上)?\s*(で|購入|買い|ご購入)|まとめ買い|対象.{0,6}\d+点")


def score(item, ranked=None):
    """売れ筋ほど高い点。ranked は楽天ランキングに入っている商品コードの集合（あれば加点）。"""
    d = discount(item)
    if not d:
        return 0
    pct, is_max = d
    avg = float(item.get("reviewAverage") or 0)
    cnt = int(item.get("reviewCount") or 0)
    # 売れ筋だけに絞る：評価4.3以上・レビュー1000件以上・30%以上引き。
    # 80%超の割引表記は元値の根拠が怪しいことが多く、まとめ買い条件の割引は分かりにくいので除外する
    if avg < 4.3 or cnt < 1000 or pct < 30 or pct > 80 or _BUNDLE.search(item.get("itemName", "")) \
            or _RISKY.search(item.get("itemName", "")):
        return 0
    # 売れている量（レビュー件数）を一番重く、割引率は控えめに効かせる
    s = avg * math.log10(cnt) ** 2 * math.sqrt(pct)
    if ranked and item.get("itemCode") in ranked:
        s *= 1.5
    return s * (0.7 if is_max else 1.0)

_NOISE = re.compile(
    r"\d{1,2}[/月]\d{1,2}日?\s*([(（][^)）]{1,3}[)）])?\s*(\d{1,2}[:：時]\d{0,2}\s*)?(まで|迄|から|より|限定)?|\d{1,2}[:：]\d{2}\s*(まで|迄)|＼[^／]*／|\\[^/]*/|楽天(ランキング|市場)?\s*\d+位|ランキング\s*\d+位|\d+冠|"
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
            r"振込|支払|決済|詳細は|こちら|→|あす楽|ギフト対応|のし|お願い|ご確認|申し上げ|ください|商品内容|解凍", p) and len(re.findall(r"[ぁ-んァ-ヶ一-龯]", p)) >= len(p) * 0.4:
            if p not in out:
                out.append(p)
        if len(out) >= n:
            break
    return out


def headline(pct, is_max, cp=False):
    if cp:
        return f"クーポンで{'最大' if is_max else ''}{'半額' if pct == 50 and not is_max else f'{pct}%OFF'}！"
    if pct >= 50 and not is_max:
        return f"今なら{pct}%OFF！" if pct != 50 else "今なら半額！"
    return f"{'最大' if is_max else ''}{pct}%OFFのセール中"


_BANNED = re.compile(r"最安|No\.?1|ナンバーワン|絶対|必ず|治る|治す|消える|痩せ|若返|効く|保証|万能|奇跡")


def label(item):
    pct, is_max = discount(item)
    return f"{'クーポン利用で' if coupon(item) else ''}{'最大' if is_max else ''}{pct}%OFF"


def compose(item, copy=None, now=None):
    """copy: Claudeが書いた紹介文 {"hook": str, "points": [str, str]}。無ければ商品説明から拾う。"""
    pct, is_max = discount(item)
    avg = float(item.get("reviewAverage") or 0)
    cnt = int(item.get("reviewCount") or 0)
    price = int(item.get("itemPrice") or 0)
    pt = points(item)
    link = item.get("affiliateUrl") or item.get("itemUrl")

    if copy and (not copy.get("hook") or not copy.get("points")
                 or _BANNED.search(copy["hook"] + "".join(copy["points"]))):
        print(f"::warning::紹介文に使えない表現があったので使いません: {copy}", flush=True)
        copy = None

    cp = coupon(item)
    lines = [f"【PR】{headline(pct, is_max, cp)}"]
    if copy:
        lines.append(copy["hook"][:24])
    lines += ["", clean_name(item.get("itemName", ""))]
    lines.append(f"💰 {label(item)}（ショップ表記）／投稿時点 {price:,}円{'（クーポン適用前）' if cp else ''}")
    end = sale_period(item, now or dt.datetime.now(JST))[1]
    if end:
        week = "月火水木金土日"[end.weekday()]
        lines.append(f"⏰ {end.month}/{end.day}({week}) {end.hour}:{end.minute:02d}まで（ショップ表記）")
    lines.append(f"⭐ 評価{avg:.2f}（レビュー{cnt:,}件）")
    if pt:
        lines.append(f"🎁 ポイント{pt}倍")
    for f in (copy["points"][:2] if copy else features(item)):
        lines.append(f"✔ {f}")
    tail = ["", "▶ 楽天で見る", link, "※価格・在庫は変わることがあります"]

    text = "\n".join(lines + tail)
    while len(text) > MAX_LEN and len(lines) > 4:
        lines.pop()
        text = "\n".join(lines + tail)
    return text
