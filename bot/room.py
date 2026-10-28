"""今日の1件を Threads・note・楽天ROOM に手で載せるためのページ（site/index.html）を作る。

その日の朝に選んだ商品を出す（まだ選んでいなければ候補の1位）。
note 用に、見出し画像の保存・タイトル/本文/ハッシュタグのコピー（記号つき・書式つき）を並べる。

GitHub Pages（https://bunsho1114.github.io/affiliate-bot/）で公開する。
使い方: python -m bot.room
"""
import datetime as dt
import html
import json
import os
import re
import urllib.parse

from bot import compose, note, post

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>今日の1件</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--text:#1d1d1f;--muted:#6b6b70;--accent:#1f6f5c;--line:#e3e1dc}
@media (prefers-color-scheme:dark){:root{--bg:#151515;--card:#222;--text:#f2f2f2;--muted:#a0a0a5;--accent:#5cc4a8;--line:#333}}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.7 system-ui,-apple-system,"Hiragino Sans","Yu Gothic UI",sans-serif}
main{max-width:680px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:8px 0 4px}
.lead{color:var(--muted);font-size:14px;margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 16px}
.label{color:var(--muted);font-size:12px;margin:0 0 8px}
.title{font-weight:700;margin:0 0 12px}
button,.btn{display:block;width:100%;box-sizing:border-box;margin:8px 0;padding:11px;border-radius:8px;border:1px solid var(--accent);background:transparent;color:var(--accent);font:600 14px/1.4 inherit;text-align:center;text-decoration:none;cursor:pointer}
.fill{background:var(--accent);color:#fff}
#eyeimg{width:100%;border-radius:6px;display:block}
#body h2{font-size:18px;margin:24px 0 8px}
#body p{margin:0 0 14px}
#body ul{margin:0 0 14px;padding-left:22px}
#body a{color:var(--accent);word-break:break-all}
textarea{width:100%;box-sizing:border-box;margin:8px 0;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:14px/1.5 inherit;resize:vertical}
.thumb{width:120px;height:120px;object-fit:cover;border-radius:8px}
</style></head><body><main>
<h1>今日の1件</h1>
<p class="lead">{{date}} 更新。<br>noteは、スマホならブラウザを「PC版サイト」表示にして「本文を選択する」→ 選ばれた部分を長押しして「コピー」→ noteに貼り付け。PCなら「書式つきでコピー」が便利です。</p>
{{cards}}
</main>
<script>
function done(b,t){var o=b.dataset.label||b.textContent;b.dataset.label=o;b.textContent=t||"コピーしました";setTimeout(function(){b.textContent=o},2000)}
function fallback(b,text){var t=document.createElement("textarea");t.value=text;t.setAttribute("readonly","");t.style.position="fixed";t.style.top="0";t.style.opacity="0";document.body.appendChild(t);t.focus();t.select();t.setSelectionRange(0,text.length);var ok=false;try{ok=document.execCommand("copy")}catch(x){}t.remove();
  if(ok){done(b)}else{done(b,"コピーできませんでした。文を長押しして手でコピーしてください")}}
function copyText(b,text){if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(text).then(function(){done(b)},function(){fallback(b,text)})}else{fallback(b,text)}}
document.querySelectorAll("[data-copy]").forEach(function(b){b.onclick=function(){var e=document.getElementById(b.dataset.copy);copyText(b,e.value!==undefined?e.value:e.textContent)}});
document.querySelectorAll("[data-select]").forEach(function(b){b.onclick=function(){var r=document.createRange();r.selectNodeContents(document.getElementById(b.dataset.select));var s=getSelection();s.removeAllRanges();s.addRange(r);done(b,"選択しました（長押しでコピー）")}});
document.querySelectorAll("[data-rich]").forEach(function(b){b.onclick=function(){var e=document.getElementById(b.dataset.rich);
  try{navigator.clipboard.write([new ClipboardItem({"text/html":new Blob([e.innerHTML],{type:"text/html"}),"text/plain":new Blob([e.innerText],{type:"text/plain"})})]).then(function(){done(b)},function(){done(b,"この端末ではできません。「本文を選択する」を使ってください")})}catch(x){done(b,"この端末ではできません。「本文を選択する」を使ってください")}}});
// 見出し画像（1280×670）をその場で描く
(function(){var d=window.EYE;if(!d)return;var c=document.createElement("canvas");c.width=1280;c.height=670;var g=c.getContext("2d");
  var F='"Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif';
  g.fillStyle="#173C35";g.fillRect(0,0,1280,670);g.fillStyle="#F5B731";g.fillRect(0,0,1280,100);
  g.textBaseline="middle";g.fillStyle="#1E3A34";g.font="900 44px "+F;g.fillText("楽天セール",56,52);
  var x=56+g.measureText("楽天セール").width+20;g.font="900 42px "+F;var w=g.measureText(d.band).width;
  g.fillStyle="#D9553B";g.fillRect(x-12,20,w+24,64);g.fillStyle="#fff";g.fillText(d.band,x,53);
  g.textBaseline="alphabetic";g.fillStyle="#fff";g.font="900 54px "+F;g.fillText(d.lead,56,215);
  var size=150;do{g.font="900 "+size+"px "+F;size-=4}while(g.measureText(d.main).width>860&&size>60);
  g.fillStyle="#F7C844";g.fillText(d.main,56,215+size+20);
  if(d.catch){var cs=64;do{g.font="900 "+cs+"px "+F;cs-=2}while(g.measureText(d.catch).width>1160&&cs>30);g.fillStyle="#fff";g.fillText(d.catch,56,500)}
  g.beginPath();g.arc(1080,230,130,0,7);g.fillStyle="#F7F4DC";g.fill();g.beginPath();g.arc(1080,230,120,0,7);g.fillStyle="#D9553B";g.fill();
  g.textAlign="center";g.fillStyle="#fff";g.font="900 32px "+F;g.fillText("みんなの評価",1080,200);g.font="900 64px "+F;g.fillText("★"+d.star,1080,275);g.textAlign="left";
  if(d.pill){g.font="900 36px "+F;var pw=g.measureText(d.pill).width;g.fillStyle="#F7F4DC";g.beginPath();g.roundRect(56,560,pw+56,64,32);g.fill();g.fillStyle="#173C35";g.fillText(d.pill,84,605)}
  var url=c.toDataURL("image/png");document.getElementById("eyeimg").src=url;var a=document.getElementById("eyesave");a.href=url;})();
</script>
</body></html>
"""

CARD = """<div class="card"><p class="label">画像を保存</p>
<a class="btn" id="eyesave" download="見出し画像.png">見出し画像を保存</a>
<a class="btn" href="{{img}}" target="_blank" rel="noopener">商品の画像を開く（Threads用・長押しで保存）</a></div>

<div class="card"><p class="label">タイトル</p><p class="title" id="ntitle">{{title}}</p>
<button data-copy="ntitle">タイトルをコピー</button></div>

<div class="card"><p class="label">見出し画像</p><img id="eyeimg" alt="見出し画像"></div>

<div class="card"><p class="label">本文</p>
<button data-select="body">本文を選択する（そのあと自分で「コピー」）</button>
<button data-copy="bodymd">本文を記号つき（##・**）でコピー</button>
<button data-rich="body">本文を書式つきでコピー（PC向け）</button>
<textarea id="bodymd" hidden>{{md}}</textarea>
<div id="body">{{html}}</div></div>

<div class="card"><p class="label">ハッシュタグ</p><p class="title" id="ntags">{{tags}}</p>
<button data-copy="ntags">ハッシュタグをコピー</button>
<a class="btn fill" href="https://note.com/notes/new" target="_blank" rel="noopener">noteを開く</a></div>

<div class="card"><p class="label">Threads の投稿文</p>
<img class="thumb" src="{{img}}" alt="">
<p class="label" style="margin-top:12px">① メイン投稿（画像をつけて投稿）</p>
<textarea id="th0" rows="8" readonly>{{th0}}</textarea>
<button data-copy="th0">メイン投稿をコピー</button>
<p class="label" style="margin-top:12px">② 自分の投稿に返信（1つめ）</p>
<textarea id="th1" rows="12" readonly>{{th1}}</textarea>
<button data-copy="th1">返信1をコピー</button>
<p class="label" style="margin-top:12px">③ ②にさらに返信（2つめ・楽天のリンク入り）</p>
<textarea id="th2" rows="8" readonly>{{th2}}</textarea>
<button data-copy="th2">返信2をコピー</button>
<a class="btn fill" href="https://www.threads.com/" target="_blank" rel="noopener">Threadsを開く</a></div>

<div class="card"><p class="label">楽天ROOM の紹介文</p>
<textarea id="room" rows="14" readonly>{{room}}</textarea>
<button data-copy="room">紹介文をコピー</button>
<a class="btn fill" href="{{room_url}}" target="_blank" rel="noopener">ROOMに追加</a></div>
<script>window.EYE={{eye}};</script>"""

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


def pick(candidates, now):
    """今朝選んだ商品（state の記録）を返す。無ければセール中の候補の1位。"""
    posted = post.load(post.STATE, {})
    today = [code for code, v in sorted(posted.items(), key=lambda kv: kv[1]["at"], reverse=True)
             if dt.datetime.fromisoformat(v["at"]).date() == now.date()]
    by_code = {c["itemCode"]: c for c in candidates}
    for code in today:
        if code in by_code:
            return by_code[code]
    return next((c for c in candidates if compose.on_sale(c["item"], now)), None)


def build():
    candidates = post.load(f"{post.DAILY}/candidates.json", [])
    copies = post.load(f"{post.DAILY}/copy.json", {})
    now = dt.datetime.now(post.JST)
    c = pick(candidates, now)
    cards = "<p>今日の商品はまだありません。</p>"
    if c:
        item, copy = c["item"], copies.get(c["itemCode"])
        a = note.article(item, copy, now)
        cards = fill(CARD, {
            "img": html.escape(post.image(item) or ""),
            "title": html.escape(a["title"]),
            "md": html.escape(a["md"]),
            "html": a["html"],
            "tags": html.escape(a["tags"]),
            "th0": html.escape(a["threads"][0]),
            "th1": html.escape(a["threads"][1]),
            "th2": html.escape(a["threads"][2]),
            "room": html.escape(room_comment(a)),
            "room_url": html.escape(ROOM_URL.format(code=urllib.parse.quote(c["itemCode"], safe=":"))),
            "eye": json.dumps(a["eye"], ensure_ascii=False).replace("</", "<\\/"),
        })
    return fill(PAGE, {"date": now.strftime("%-m月%-d日 %H:%M"), "cards": cards})


def main():
    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(build())


if __name__ == "__main__":
    main()
