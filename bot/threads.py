"""Threads API で投稿する（自分のアカウントにテスターとして投稿）。"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.threads.net/v1.0"


class ThreadsError(Exception):
    pass


def _call(method, path, params):
    params = {**params, "access_token": os.environ["THREADS_ACCESS_TOKEN"]}
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{BASE}/{path}?{data.decode()}")
    else:
        req = urllib.request.Request(f"{BASE}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise ThreadsError(f"HTTP {e.code} {path}: {body}") from None


def _wait_ready(container_id):
    """画像つきの投稿は準備に時間がかかるので、使えるようになるまで待つ。"""
    for _ in range(12):
        status = _call("GET", container_id, {"fields": "status,error_message"})
        if status.get("status") == "FINISHED":
            return
        if status.get("status") in ("ERROR", "EXPIRED"):
            raise ThreadsError(f"投稿の準備に失敗: {status}")
        time.sleep(5)
    raise ThreadsError("投稿の準備が終わらなかった")


def publish(text, image_url=None):
    """投稿して投稿IDを返す。画像が使えなければ文字だけで投稿する。"""
    container = None
    if image_url:
        try:
            container = _call("POST", "me/threads", {
                "media_type": "IMAGE", "image_url": image_url, "text": text})["id"]
            _wait_ready(container)
        except ThreadsError as e:
            print(f"::warning::画像つきで投稿できなかったので文字だけにします: {e}", flush=True)
            container = None
    if container is None:
        container = _call("POST", "me/threads", {"media_type": "TEXT", "text": text})["id"]
        _wait_ready(container)
    return _call("POST", "me/threads_publish", {"creation_id": container})["id"]


def permalink(post_id):
    try:
        return _call("GET", post_id, {"fields": "permalink"}).get("permalink")
    except ThreadsError:
        return None
