"""note の記事（タイトル・本文・ハッシュタグ・見出し画像の文字）を作る。

note は自動投稿できないので、「今日の1件」ページからコピーして貼る。
本文は「問いかけ → 結論 → 絵文字つき見出し → ちょっと本音 → まとめ」の形で、
記号つき（## と **）と、そのまま貼れる書式つき（HTML）の両方を返す。
"""
import datetime as dt
import html
import re

from bot import compose

WEEK = "月火水木金土日"


def _short_count(cnt):
    return f"{cnt / 10000:.1f}万".replace(".0万", "万") if cnt >= 10000 else f"{cnt:,}"


def _end_text(end):
    return f"{end.month}/{end.day}({WEEK[end.weekday()]}) {end.hour}:{end.minute:02d}" if end else ""


def article(item, copy=None, now=None):
    """{"title", "md", "html", "tags", "eye", "threads"} を返す。

    copy は Claude が毎朝書く紹介文。使うのは hook / points / note と、
    記事用の short（短い商品名）/ q（書き出しの問いかけ）/ catch（見出し画像の一言）/ honne（ちょっと本音）/
    detail（Threads 返信1 用のくわしい説明）。
    """
    now = now or dt.datetime.now(compose.JST)
    copy = dict(copy or {})
    if compose._BANNED.search("".join(str(v) for v in copy.values())):
        print(f"::warning::note用の文に使えない表現があったので使いません: {copy}", flush=True)
        copy = {}
    name = compose.clean_name(item.get("itemName", ""), limit=36)
    short = copy.get("short") or compose.clean_name(item.get("itemName", ""), limit=16)
    sale = compose.label(item)
    cp = compose.coupon(item)
    price = int(item.get("itemPrice") or 0)
    avg = float(item.get("reviewAverage") or 0)
    cnt = int(item.get("reviewCount") or 0)
    pt = compose.points(item)
    link = compose.short_link(item)
    end = compose.sale_period(item, now)[1]
    good = copy.get("points", [])[:2] or compose.features(item)
    day = f"{now.month}/{now.day}"

    title = f"【PR】レビュー{_short_count(cnt)}件の{short}が{sale}！{copy.get('catch', '')}"

    md = []
    if copy.get("q"):
        md += [copy["q"], ""]
    md += [f"今日見つけたのは、**{short}**。",
           f"楽天で**レビュー{cnt:,}件・評価{avg:.2f}**の人気商品が、いま**{sale}**になっています（ショップ表記）。", "",
           "結論から言うと、**気になっていた人はセール中の今が狙い目**です！",
           "今回は、どんな商品なのか、どこがおトクなのかをまとめてみます。", ""]
    md += ["## 🛍️ どんな商品？", "", f"{name}（{item.get('shopName', '')}）", ""]
    md += [f"- {g}" for g in good] + [""]
    md += ["## 💰 どれくらいおトク？", "",
           f"- 割引：**{sale}**（ショップ表記）",
           f"- 価格：**{price:,}円**{'（クーポン適用前）' if cp else ''}（{day}時点）"]
    if end:
        md.append(f"- 期限：**{_end_text(end)}まで**（ショップ表記）")
    if pt:
        md.append(f"- ポイント：**{pt}倍**")
    md.append("")
    if end and end - now < dt.timedelta(hours=36):
        md += ["セールはもうすぐ終わるので、気になる方はお早めに。", ""]
    md += ["## ⭐ みんなの評価は？", "", f"**★{avg:.2f}（レビュー{cnt:,}件）**"]
    if avg >= 4.5 and cnt >= 3000:
        md.append(f"これだけの件数がついて{int(avg * 10) / 10:.1f}台というのは、かなりの高評価です。")
    else:
        md.append("たくさんの人に選ばれている商品です。")
    md.append("")
    if copy.get("honne"):
        md += ["## 💬 ちょっと本音", ""] + copy["honne"].split("\n") + [""]
    md += ["## 🌱 まとめ", "",
           f"- レビュー{_short_count(cnt)}件・★{avg:.2f}の{short}",
           f"- **{sale}**（ショップ表記）" + (f"、**{_end_text(end)}まで**" if end else "")]
    md += [f"- {g}" for g in good] + [""]
    if copy.get("note"):
        md += [copy["note"], ""]
    md += ["「気になるかも」と思った方は、まずは商品ページでチェックしてみてください😊", "",
           "▼ 商品ページはこちら", link, "",
           "参考になったら、スキやフォローをしてもらえると励みになります。", "",
           f"※価格・セール内容・在庫は{day}時点の情報です。変わることがあるので、購入前に商品ページでご確認ください。"]

    tag = re.sub(r"[\s・、。!！?？()（）〈〉\-]", "", short)
    tags = " ".join(f"#{t}" for t in dict.fromkeys(["PR", "楽天", "楽天セール", tag, "お買い物", "節約"]) if t)
    eye = {"band": sale + (f"　{_end_text(end)}まで" if end else ""), "lead": f"レビュー{_short_count(cnt)}件の",
           "main": short, "catch": copy.get("catch", ""), "star": f"{avg:.2f}", "pill": copy.get("hook", "")}
    # Threads 用：4つに分けたスレッド（それぞれ500文字まで）。URLは最後の返信3にだけ入れる
    # ① メイン投稿：フックと価値だけ ② 返信1：くわしい中身 ③ 返信2：まとめと案内 ④ 返信3：楽天のリンク
    main = ["【PR】" + (copy.get("q") or f"{short}が{sale}になっています！"), "",
            f"今日見つけたのは「{short}」。",
            f"レビュー{_short_count(cnt)}件・★{avg:.2f}の人気商品が、いま{sale}になっています（ショップ表記）。", ""]
    if copy.get("hook"):
        main.append(copy["hook"])
    main.append("どこがおトクなのか、続きで紹介します👇")
    r1 = [f"「{short}」がどんな商品か、くわしくまとめます。", "", "■ どんな商品？", f"{name}（{item.get('shopName', '')}）"]
    r1 += [f"・{g}" for g in good]
    if copy.get("detail"):
        r1 += [copy["detail"]]
    r1 += ["", "■ どれくらいおトク？", f"・割引：{sale}（ショップ表記）",
                                      f"・価格：{price:,}円{'（クーポン適用前）' if cp else ''}（{day}時点）"]
    if end:
        r1.append(f"・期限：{_end_text(end)}まで（ショップ表記）")
    if pt:
        r1.append(f"・ポイント{pt}倍")
    r1 += ["", "■ みんなの評価", f"★{avg:.2f}（レビュー{cnt:,}件）", md[md.index(f"**★{avg:.2f}（レビュー{cnt:,}件）**") + 1]]
    extra = []
    if copy.get("honne"):
        extra += ["", "■ ちょっと本音"] + copy["honne"].split("\n")
    if copy.get("note"):
        extra += ["", copy["note"]]
    while extra and len("\n".join(r1 + extra)) > compose.MAX_LEN:
        extra.pop()
    if len("\n".join(r1)) > compose.MAX_LEN and copy.get("detail"):
        r1.remove(copy["detail"])
    r2 = ["まとめると…", f"・レビュー{_short_count(cnt)}件・★{avg:.2f}の{short}",
          f"・{sale}（ショップ表記）" + (f"、{_end_text(end)}まで" if end else "")]
    if end and end - now < dt.timedelta(hours=36):
        r2 += ["", "セールはもうすぐ終わるので、気になる方はお早めに。"]
    r2 += ["", "※価格・在庫は変わることがあります", "",
           "くわしいまとめはプロフィールのリンク（note）から、商品ページはこの下の返信からどうぞ👇"]
    r3 = ["▶ 楽天で見る", link, "#PR"]
    threads = ["\n".join(main), "\n".join(r1 + extra), "\n".join(r2), "\n".join(r3)]
    return {"title": title, "md": "\n".join(md), "html": to_html(md), "tags": tags, "eye": eye,
            "threads": threads}


def to_html(lines):
    """記号つきの本文を、note にそのまま貼れる HTML にする（見出し・太字・箇条書き・リンクだけ）。"""
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', s)

    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(inline(p) for p in para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for line in lines:
        if line.startswith("## "):
            flush()
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("- "):
            if para:
                flush()
            items.append(line[2:])
        elif not line:
            flush()
        else:
            if items:
                flush()
            para.append(line)
    flush()
    return "\n".join(out)
