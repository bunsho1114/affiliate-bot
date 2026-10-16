"""商品説明から「買いたくなる紹介文」をClaudeで書く。

GitHubの金庫に ANTHROPIC_API_KEY が入っているときだけ動く。
鍵がない・失敗した・断られたときは None を返し、呼び出し側は商品説明から拾った文に戻す。
"""
import html
import os
import re

import anthropic
from pydantic import BaseModel

MODEL = os.environ.get("COPY_MODEL") or "claude-opus-5-5"

SYSTEM = """あなたは楽天市場のセール商品をThreadsで紹介する、日本語のコピーライターです。
読んだ人が「これ欲しい」「今買っておきたい」と感じる、短くて具体的な紹介文を書きます。

必ず守るルール:
- 書いてよい事実は、渡された商品名・商品説明・セール情報・評価に書かれていることだけ。書かれていない機能や効果を作らない。
- 口コミや体験談をでっち上げない（「使ってみたら」「みんな絶賛」などは禁止）。
- 化粧品・健康食品・サプリ・家電などで、効果を断定・誇張しない（「シミが消える」「痩せる」「治る」「必ず」「絶対」は禁止）。
- 「最安値」「No.1」「どこよりも安い」など、根拠のない比較はしない。
- 価格・割引率・評価の数字は書かない（別の行で表示するため）。
- 絵文字・ハッシュタグ・URLは使わない。

書き方のコツ:
- 機能ではなく「使う人の生活がどう良くなるか」を書く（例: 大容量→毎日ためらわず使える）。
- 商品説明にある具体的な数字・素材・使う場面を活かす。
- 誰向けの商品か、どんな場面で嬉しいかが一瞬で伝わるようにする。

hook は思わず手が止まる一言（20文字以内）、points は魅力を2つ（それぞれ30文字以内）。"""


class Copy(BaseModel):
    hook: str
    points: list[str]


def _caption(item, limit=1500):
    text = html.unescape(re.sub(r"<[^>]+>", " ", item.get("itemCaption", "")))
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def write(item, discount_label):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    user = (
        f"商品名: {item.get('itemName', '')}\n"
        f"商品説明: {_caption(item)}\n"
        f"セール: {discount_label}\n"
        f"評価: {item.get('reviewAverage')}（レビュー{item.get('reviewCount')}件）"
    )
    try:
        response = anthropic.Anthropic().messages.parse(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": user}],
            output_format=Copy,
        )
    except anthropic.APIError as e:
        print(f"::warning::紹介文のAI生成に失敗したので、商品説明から拾った文を使います: {e}", flush=True)
        return None
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        print(f"::warning::紹介文のAI生成が途中で止まったので使いません（{response.stop_reason}）", flush=True)
        return None

    out = response.parsed_output
    hook = out.hook.strip()[:24]
    points = [p.strip()[:34] for p in out.points if p.strip()][:2]
    if not hook or not points:
        return None
    return {"hook": hook, "points": points}
