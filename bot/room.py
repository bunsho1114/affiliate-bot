"""楽天ROOMに手で追加するための「今日のリスト」ページ（site/index.html）を作る。

GitHub Pages（https://bunsho1114.github.io/affiliate-bot/）で公開する。
使い方: python -m bot.room
"""
import datetime as dt
import html
import json
import os
import urllib.parse

from bot import compose, post

COUNT = 5
ROOM_URL = "https://room.rakuten.co.jp/mix?itemcode={code}&scid=we_room_upc60"

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>今日のROOMリスト</title>
<style>
:root{{--bg:#f6f5f2;--card:#fff;--text:#1d1d1f;--muted:#6b6b70;--accent:#bf0000;--line:#e3e1dc}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--card:#222;--text:#f2f2f2;--muted:#a0a0a5;--accent:#ff5a5a;--line:#333}}}}
body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Hiragino Sans","Yu Gothic UI",sans-serif}}
main{{max-width:640px;margin:0 auto;padding:16px}}
h1{{font-size:20px;margin:8px 0 4px}}
.lead{{color:var(--muted);font-size:14px;margin:0 0 16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:0 0 14px}}
.top{{display:flex;gap:12px}}
.top img{{width:96px;height:96px;object-fit:cover;border-radius:8px;flex:none}}
.name{{font-weight:600;font-size:15px}}
.sale{{color:var(--accent);font-weight:700;font-size:14px}}
textarea{{width:100%;box-sizing:border-box;margin:10px 0 8px;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:14px/1.5 inherit;resize:vertical}}
.btns{{display:flex;gap:8px;flex-wrap:wrap}}
.btns a,.btns button{{flex:1;min-width:120px;text-align:center;padding:10px;border-radius:8px;font:600 14px inherit;text-decoration:none;cursor:pointer;border:1px solid var(--accent)}}
.room{{background:var(--accent);color:#fff}}
button{{background:transparent;color:var(--accent)}}
</style></head><body><main>
<h1>今日のROOMリスト</h1>
<p class="lead">{date} 更新。紹介文をコピーしてから「ROOMに追加」を押し、貼り付けて投稿してください。</p>
{cards}
</main>
<script>
document.querySelectorAll("button[data-copy]").forEach(function(b){{
  b.addEventListener("click",function(){{
    var t=document.getElementById(b.dataset.copy);
    navigator.clipboard.writeText(t.value).then(function(){{b.textContent="コピーしました";}},function(){{t.select();document.execCommand("copy");b.textContent="コピーしました";}});
  }});
}});
</script>
</body></html>
"""

CARD = """<div class="card">
<div class="top"><img src="{img}" alt="" loading="lazy">
<div><div class="name">{name}</div><div class="sale">{sale}（ショップ表記）／{price}円</div></div></div>
<textarea id="t{n}" rows="5" readonly>{comment}</textarea>
<div class="btns"><button data-copy="t{n}">紹介文をコピー</button>
<a class="room" href="{room}" target="_blank" rel="noopener">ROOMに追加</a></div>
</div>"""


def comment(c, copy):
    lines = []
    if copy:
        lines.append(copy["hook"])
        lines += [f"✔ {p}" for p in copy["points"][:2]]
    else:
        lines += [f"✔ {p}" for p in compose.features(c["item"])]
    lines.append(f"{c['sale']}（ショップ表記）")
    lines.append("#PR #楽天セール")
    return "\n".join(lines)


def build():
    candidates = post.load(f"{post.DAILY}/candidates.json", [])
    copies = post.load(f"{post.DAILY}/copy.json", {})
    cards = []
    for n, c in enumerate(candidates[:COUNT]):
        item = c["item"]
        cards.append(CARD.format(
            n=n,
            img=html.escape(post.image(item) or ""),
            name=html.escape(compose.clean_name(item.get("itemName", ""))),
            sale=html.escape(c["sale"]),
            price=f"{int(item.get('itemPrice') or 0):,}",
            comment=html.escape(comment(c, copies.get(c["itemCode"]))),
            room=html.escape(ROOM_URL.format(code=urllib.parse.quote(c["itemCode"], safe=":"))),
        ))
    date = dt.datetime.now(post.JST).strftime("%-m月%-d日 %H:%M")
    body = "\n".join(cards) or "<p>今日の候補はまだありません。</p>"
    return PAGE.format(date=date, cards=body)


def main():
    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(build())


if __name__ == "__main__":
    main()
