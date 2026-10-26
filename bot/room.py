"""今日の1件を Threads と note に手で載せるためのページ（site/index.html）を作る。

その日の朝に選んだ商品を出す（まだ投稿していなければ候補の1位）。

GitHub Pages（https://bunsho1114.github.io/affiliate-bot/）で公開する。
使い方: python -m bot.room
"""
import datetime as dt
import html
import json
import os

from bot import compose, note, post

COUNT = 1

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>今日の1件</title>
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
.go{{background:var(--accent);color:#fff}}
h2{{font-size:15px;margin:16px 0 0}}
input{{width:100%;box-sizing:border-box;margin:8px 0;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:14px inherit}}
button{{background:transparent;color:var(--accent)}}
</style></head><body><main>
<h1>今日の1件</h1>
<p class="lead">{date} 更新。Threadsとnoteに、それぞれコピーして貼り付けてください。</p>
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
<h2>① Threads</h2>
<textarea id="th{n}" rows="10" readonly>{threads}</textarea>
<div class="btns"><button data-copy="th{n}">投稿文をコピー</button>
<a class="go" href="{img}" target="_blank" rel="noopener">画像を開く（長押しで保存）</a></div>
<div class="btns" style="margin-top:8px"><a class="go" href="https://www.threads.com/" target="_blank" rel="noopener">Threadsを開く</a></div>
<h2>② note</h2>
<input id="nt{n}" readonly value="{note_title}">
<div class="btns"><button data-copy="nt{n}">タイトルをコピー</button></div>
<textarea id="nb{n}" rows="12" readonly>{note_body}</textarea>
<div class="btns"><button data-copy="nb{n}">本文をコピー</button>
<a class="go" href="https://note.com/notes/new" target="_blank" rel="noopener">noteを開く</a></div>
</div>"""


def build():
    candidates = post.load(f"{post.DAILY}/candidates.json", [])
    copies = post.load(f"{post.DAILY}/copy.json", {})
    cards = []
    now = dt.datetime.now(post.JST)
    # 今朝 Threads に投稿した商品と同じものを出す
    posted = post.load(post.STATE, {})
    today = [code for code, v in sorted(posted.items(), key=lambda kv: kv[1]["at"], reverse=True)
             if dt.datetime.fromisoformat(v["at"]).date() == now.date()]
    by_code = {c["itemCode"]: c for c in candidates}
    picks = [by_code[code] for code in today if code in by_code]
    if not picks:
        picks = [c for c in candidates if compose.on_sale(c["item"], now)]
    for n, c in enumerate(picks[:COUNT]):
        item = c["item"]
        copy = copies.get(c["itemCode"])
        note_title, note_body = note.article(item, copy, now)
        cards.append(CARD.format(
            n=n,
            img=html.escape(post.image(item) or ""),
            name=html.escape(compose.clean_name(item.get("itemName", ""))),
            sale=html.escape(c["sale"]),
            price=f"{int(item.get('itemPrice') or 0):,}",
            threads=html.escape(compose.compose(item, copy, now)),
            note_title=html.escape(note_title),
            note_body=html.escape(note_body),
        ))
    date = now.strftime("%-m月%-d日 %H:%M")
    body = "\n".join(cards) or "<p>今日の商品はまだありません。</p>"
    return PAGE.format(date=date, cards=body)


def main():
    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(build())


if __name__ == "__main__":
    main()
