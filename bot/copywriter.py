"""商品説明から「買いたくなる紹介文」をAIで書く。

GitHub Actions に無料で付いている GitHub Models を使う（追加の鍵や料金は不要）。
失敗したときは None を返し、呼び出し側は機械的に拾った文にフォールバックする。
"""
import html
import json
import os
import re
import urllib.error
import urllib.request

ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL = os.environ.get("COPY_MODEL", "openai/gpt-4.1-mini")

SYSTEM = """あなたは楽天市場のセール商品をThreadsで紹介する、日本語のコピーライターです。
読んだ人が「これ欲しい」「今買わないと」と感じる、短くて具体的な紹介文を書きます。

必ず守るルール:
- 書いてよい事実は、渡された商品名・商品説明・価格・評価に書かれていることだけ。書かれていない機能や効果を作らない。
- 口コミや体験談をでっち上げない（「使ってみたら」「みんな絶賛」などは禁止）。
- 化粧品・健康食品・サプリ・家電などで、効果を断定・誇張しない（「シミが消える」「痩せる」「治る」「必ず」「絶対」は禁止）。
- 「最安値」「業界No.1」「どこよりも安い」など、根拠のない比較はしない。
- 価格や割引率、評価の数字は書かない（別の行で表示するため）。
- 絵文字・ハッシュタグ・URLは使わない。

書き方のコツ:
- 機能ではなく「使う人の生活がどう良くなるか」を書く（例: 大容量→毎日ためらわず使える）。
- 具体的な数字や素材など、商品説明にある具体的な情報を活かす。
- 誰向けの商品か、どんな場面で嬉しいかが一瞬で伝わるようにする。

出力は次のJSONだけ:
{"hook": "思わず手が止まる一言（20文字以内）", "points": ["魅力1（30文字以内）", "魅力2（30文字以内）"]}"""


def _caption(item, limit=1200):
    text = html.unescape(re.sub(r"<[^>]+>", " ", item.get("itemCaption", "")))
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def write(item, discount_label):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    user = (
        f"商品名: {item.get('itemName', '')}\n"
        f"商品説明: {_caption(item)}\n"
        f"セール: {discount_label}\n"
        f"評価: {item.get('reviewAverage')}（レビュー{item.get('reviewCount')}件）"
    )
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "temperature": 0.7,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    raw = ""
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read().decode("utf-8", "replace")
        content = json.loads(raw)["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        out = json.loads(content)
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError, IndexError) as e:
        if isinstance(e, urllib.error.HTTPError):
            detail = f"HTTP {e.code} " + e.read().decode("utf-8", "replace")[:300]
        else:
            detail = f"{e} / 応答: {raw[:300]!r}"
        print(f"::warning::紹介文のAI生成に失敗したので、商品説明から拾った文を使います: {detail}", flush=True)
        return None

    hook = str(out.get("hook", "")).strip()[:24]
    points = [str(p).strip()[:34] for p in out.get("points", []) if str(p).strip()][:2]
    if not hook or not points:
        return None
    return {"hook": hook, "points": points}
