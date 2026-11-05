"""今日の5件を楽天ROOMに手で載せるためのページ（site/index.html）を作る。

その日の朝に選んだ商品を出す（まだ選んでいなければセール中の候補の上から）。
1件ごとに、ROOM に貼る紹介文のコピーと「ROOMに追加」ボタンを並べる（note と Threads はやめた 2026-11-06）。

GitHub Pages（https://bunsho1114.github.io/affiliate-bot/）で公開する。
使い方: python -m bot.room
"""
import datetime as dt
import html
import os
import re
import urllib.parse

from bot import compose, note, post

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>今日の楽天ROOM</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--text:#1d1d1f;--muted:#6b6b70;--accent:#bf0000;--line:#e3e1dc}
@media (prefers-color-scheme:dark){:root{--bg:#151515;--card:#222;--text:#f2f2f2;--muted:#a0a0a5;--accent:#ff6b6b;--line:#333}}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.7 system-ui,-apple-system,"Hiragino Sans","Yu Gothic UI",sans-serif}
main{max-width:680px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:8px 0 4px}
.lead{color:var(--muted);font-size:14px;margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 16px}
.head{display:flex;gap:12px;align-items:flex-start;margin:0 0 8px}
.no{flex:none;width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;text-align:center;line-height:28px}
.title{font-weight:700;margin:0}
.meta{color:var(--muted);font-size:13px;margin:2px 0 0}
button,.btn{display:block;width:100%;box-sizing:border-box;margin:8px 0;padding:11px;border-radius:8px;border:1px solid var(--accent);background:transparent;color:var(--accent);font:600 14px/1.4 inherit;text-align:center;text-decoration:none;cursor:pointer}
.fill{background:var(--accent);color:#fff}
textarea{width:100%;box-sizing:border-box;margin:8px 0;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:14px/1.5 inherit;resize:vertical}
.thumb{width:88px;height:88px;object-fit:cover;border-radius:8px;flex:none}
</style></head><body><main>
<h1>今日の楽天ROOM（{{count}}件）</h1>
<p class="lead">{{date}} 更新。<br>1件ずつ「紹介文をコピー」→「ROOMに追加」で開いた画面に貼り付けて投稿してください。</p>
{{cards}}
</main>
<script>
function done(b,t){var o=b.dataset.label||b.textContent;b.dataset.label=o;b.textContent=t||"コピーしました";setTimeout(function(){b.textContent=o},2000)}
function fallback(b,text){var t=document.createElement("textarea");t.value=text;t.setAttribute("readonly","");t.style.position="fixed";t.style.top="0";t.style.opacity="0";document.body.appendChild(t);t.focus();t.select();t.setSelectionRange(0,text.length);var ok=false;try{ok=document.execCommand("copy")}catch(x){}t.remove();
  if(ok){done(b)}else{done(b,"コピーできませんでした。文を長押しして手でコピーしてください")}}
function copyText(b,text){if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(text).then(function(){done(b)},function(){fallback(b,text)})}else{fallback(b,text)}}
document.querySelectorAll("[data-copy]").forEach(function(b){b.onclick=function(){copyText(b,document.getElementById(b.dataset.copy).value)}});
</script>
</body></html>
"""

CARD = """<div class="card"><div class="head"><span class="no">{{no}}</span>
<img class="thumb" src="{{img}}" alt=""><div><p class="title">{{name}}</p><p class="meta">{{meta}}</p></div></div>
<textarea id="room{{no}}" rows="10" readonly>{{room}}</textarea>
<button data-copy="room{{no}}">紹介文をコピー</button>
<a class="btn fill" href="{{room_url}}" target="_blank" rel="noopener">ROOMに追加</a></div>"""

COUNT = 5  # 1日に載せる件数
ROOM_URL = "https://room.rakuten.co.jp/mix?itemcode={code}&scid=we_room_upc60"


ROOM_MAX = 500  # ROOM の紹介文は500字まで
ROOM_DROP = ("【まとめ】", "結論から", "【ちょっと本音】", "セールはもうすぐ", "今回は", "【みんなの評価は？】")


def room_comment(article):
    """note の記事を、ROOM に貼れる飾りなしの文にする（リンクやnote向けの一言は外す）。"""
    lines = []
    for line in article["md"].split("\n"):
        if line.startswith("http") or line.startswith("▼") or "スキやフォロー" in line or "商品ページでチェック" in line:
            continue
        line = line.replace("**", "")
        if line.startswith("## "):
            line = "【" + line[3:].split(" ", 1)[-1] + "】"
        elif line.startswith("- "):
            line = "・" + line[2:]
        if line or (lines and lines[-1] and not lines[-1].startswith("【")):
            lines.append(line)
    blocks = "\n".join(lines).strip().split("\n\n") + [article["tags"]]
    # 長いときは、ほかと重なる部分から順に外す
    for head in ROOM_DROP:
        if len("\n\n".join(blocks)) <= ROOM_MAX:
            break
        blocks = [b for b in blocks if not b.startswith(head)]
    while len("\n\n".join(blocks)) > ROOM_MAX and len(blocks) > 3:
        blocks.pop(-3)  # 最後の注意書きとハッシュタグは残す
    text = "\n\n".join(blocks)
    return text


def fill(template, values):
    """{{名前}} を値に置き換える（CSSやJSの { } と % にぶつからないように format は使わない）。"""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)


def picks(candidates, now, count=COUNT):
    """今朝選んだ商品（state の記録）を選んだ順に返す。無ければセール中の候補の上から。"""
    posted = post.load(post.STATE, {})
    today = [code for code, v in sorted(posted.items(), key=lambda kv: kv[1]["at"])
             if dt.datetime.fromisoformat(v["at"]).date() == now.date()]
    by_code = {c["itemCode"]: c for c in candidates}
    chosen = [by_code[code] for code in today if code in by_code]
    if not chosen:
        chosen = [c for c in candidates if compose.on_sale(c["item"], now)]
    return chosen[:count]


def build():
    candidates = post.load(f"{post.DAILY}/candidates.json", [])
    copies = post.load(f"{post.DAILY}/copy.json", {})
    now = dt.datetime.now(post.JST)
    chosen = picks(candidates, now)
    cards = []
    for no, c in enumerate(chosen, 1):
        item, copy = c["item"], copies.get(c["itemCode"])
        a = note.article(item, copy, now)  # ROOM の紹介文は記事の文面から作る
        meta = f"{compose.label(item)}・{int(item.get('itemPrice') or 0):,}円・★{float(item.get('reviewAverage') or 0):.2f}"
        cards.append(fill(CARD, {
            "no": str(no),
            "img": html.escape(post.image(item) or ""),
            "name": html.escape((copy or {}).get("name") or compose.clean_name(item.get("itemName", ""), limit=36)),
            "meta": html.escape(meta),
            "room": html.escape(room_comment(a)),
            "room_url": html.escape(ROOM_URL.format(code=urllib.parse.quote(c["itemCode"], safe=":"))),
        }))
    return fill(PAGE, {"date": now.strftime("%-m月%-d日 %H:%M"), "count": str(len(chosen)),
                       "cards": "\n".join(cards) or "<p>今日の商品はまだありません。</p>"})


def main():
    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(build())


if __name__ == "__main__":
    main()
