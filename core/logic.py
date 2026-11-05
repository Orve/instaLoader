import logging
import re
import time

import requests
from typing import Optional, Dict, Any, Union, List

from core.config import RAPID_API_KEY, RAPID_API_HOST, RAPID_API_TIMEOUT

# ログ設定
logger = logging.getLogger(__name__)

# 投稿ID（shortcode）の抽出用。ログには URL 全体ではなく shortcode のみを残す
# （クエリ付き URL には共有用トークン等が含まれ得るため）。
_SHORTCODE_RE = re.compile(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)")


def _extract_shortcode(text: str) -> Optional[str]:
    """テキスト中の Instagram 投稿 URL から shortcode を取り出す。"""
    match = _SHORTCODE_RE.search(text)
    return match.group(1) if match else None

def _find_all_urls(obj: Union[Dict[str, Any], List[Any]], collected_urls: Optional[List[str]] = None) -> List[str]:
    """
    レスポンスJSONから全てのメディアURLを再帰的に探索するヘルパー関数。
    カルーセル投稿の複数画像・動画に対応。
    
    Args:
        obj: 探索対象の辞書またはリスト
        collected_urls: 収集済みのURLリスト（再帰処理用）
        
    Returns:
        見つかった全てのURL文字列のリスト
    """
    if collected_urls is None:
        collected_urls = []
    
    if isinstance(obj, dict):
        # パターンA: 'medias' リストがある場合（複数メディアの可能性大）
        if 'medias' in obj and isinstance(obj['medias'], list):
            for media_item in obj['medias']:
                _find_all_urls(media_item, collected_urls)
            return collected_urls
        
        # パターンB: 直接的なメディアURL
        for key in ['video_url', 'download_url', 'media', 'thumbnail', 'cover', 'thumb', 'url']:
            if key in obj and isinstance(obj[key], str) and obj[key].startswith('http'):
                # InstagramのHTMLページURLは除外
                if "instagram.com/p/" in obj[key] or "instagram.com/reel/" in obj[key]:
                    continue
                # 重複を避ける
                if obj[key] not in collected_urls:
                    collected_urls.append(obj[key])
        
        # パターンC: ネストされている場合
        for key in ['body', 'data', 'results', 'items', 'carousel_media', 'edges']:
            if key in obj:
                _find_all_urls(obj[key], collected_urls)
                
    elif isinstance(obj, list):
        for item in obj:
            _find_all_urls(item, collected_urls)
            
    return collected_urls

def _find_url(obj: Union[Dict[str, Any], List[Any]]) -> Optional[str]:
    """
    レスポンスJSONから最初のメディアURLを探索するヘルパー関数。
    後方互換性のために残す。
    
    Args:
        obj: 探索対象の辞書またはリスト
        
    Returns:
        見つかったURL文字列、またはNone
    """
    urls = _find_all_urls(obj)
    return urls[0] if urls else None

def _extract_media_info(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    APIレスポンスから詳細なメディア情報を抽出する。
    
    Args:
        data: APIレスポンスのJSON
        
    Returns:
        メディア情報のリスト。各要素は以下の構造：
        {
            "url": str,           # メディアURL
            "type": "image" | "video",  # メディアタイプ
            "thumbnail": str | None     # サムネイルURL（動画の場合）
        }
    """
    media_list = []
    
    # mediasリストがある場合（最も一般的なパターン）
    if 'medias' in data and isinstance(data['medias'], list):
        for media in data['medias']:
            media_info = {
                "url": None,
                "type": "image",
                "thumbnail": None
            }
            
            # メディアURLの取得
            if isinstance(media, dict):
                # 動画チェック
                if 'video_url' in media:
                    media_info["url"] = media['video_url']
                    media_info["type"] = "video"
                    # サムネイルも取得
                    if 'thumbnail' in media:
                        media_info["thumbnail"] = media['thumbnail']
                    elif 'thumb' in media:
                        media_info["thumbnail"] = media['thumb']
                elif 'download_url' in media:
                    media_info["url"] = media['download_url']
                elif 'url' in media and not ("instagram.com/p/" in media['url'] or "instagram.com/reel/" in media['url']):
                    media_info["url"] = media['url']
                
                # タイプ判定の追加ロジック
                if media_info["url"]:
                    if ".mp4" in media_info["url"] or "video" in str(media).lower():
                        media_info["type"] = "video"
                    
                    media_list.append(media_info)
    
    # mediasがない場合は従来の方法でURLを探す
    if not media_list:
        urls = _find_all_urls(data)
        for url in urls:
            media_info = {
                "url": url,
                "type": "video" if ".mp4" in url else "image",
                "thumbnail": None
            }
            media_list.append(media_info)
    
    return media_list

def fetch_instagram_media(text: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    テキスト内のInstagram URLを検出し、RapidAPIを使用してメディア情報を取得する。
    複数メディア（カルーセル投稿）に対応。

    ログは段階別（url_detect / config / api / parse / extract）に、
    request_id（rid）と shortcode のみで記録する。URL 全体・レスポンス本文・
    署名付きメディア URL はログに残さない。

    Args:
        text (str): ユーザーからの入力テキスト
        request_id (str): Webhook から追跡するためのリクエストID（任意）

    Returns:
        Dict[str, Any]: 処理結果を表す辞書。いずれの形式でも例外は送出しない。
            成功時: {"status": "ok", "result": {メディア情報の辞書}}
            URLが含まれない場合: {"status": "no_url"}
            取得失敗時: {"status": "failed", "reason": <理由>, "http_status": <int|None>}
                理由は api_key_missing / timeout / request_error / http_error /
                parse_error / no_media / extract_error のいずれか。
            成功時の result の構造:
            {
                "type": "single" | "carousel",  # 投稿タイプ
                "media_count": int,              # メディア数
                "media_list": [                  # メディアのリスト
                    {
                        "url": str,
                        "type": "image" | "video",
                        "thumbnail": str | None
                    },
                    ...
                ],
                # 後方互換性のため以下も保持
                "media_url": str,       # 最初のメディアURL
                "preview_url": str      # 最初のプレビューURL
            }
    """
    rid = request_id or "-"
    shortcode = _extract_shortcode(text)

    # --- 段階1: URL検出 ---
    if "instagram.com/p/" not in text and "instagram.com/reel/" not in text:
        logger.info("rid=%s stage=url_detect result=not_found", rid)
        return {"status": "no_url"}
    logger.info("rid=%s stage=url_detect result=ok shortcode=%s", rid, shortcode)

    # --- 段階2: 設定確認 ---
    if not RAPID_API_KEY:
        logger.error("rid=%s stage=config result=error reason=api_key_missing", rid)
        return {"status": "failed", "reason": "api_key_missing", "http_status": None}

    # --- 段階3: RapidAPI 通信 ---
    url = f"https://{RAPID_API_HOST}/download"
    querystring = {"url": text}
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": RAPID_API_HOST
    }

    started = time.monotonic()
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=RAPID_API_TIMEOUT)
    except requests.Timeout:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.error(
            "rid=%s stage=api result=timeout elapsed_ms=%d timeout_s=%s shortcode=%s",
            rid, elapsed_ms, RAPID_API_TIMEOUT, shortcode,
        )
        return {"status": "failed", "reason": "timeout", "http_status": None}
    except requests.RequestException as e:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.error(
            "rid=%s stage=api result=request_error error_type=%s elapsed_ms=%d shortcode=%s",
            rid, type(e).__name__, elapsed_ms, shortcode,
        )
        return {"status": "failed", "reason": "request_error", "http_status": None}

    elapsed_ms = int((time.monotonic() - started) * 1000)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error(
            "rid=%s stage=api result=http_error status=%s elapsed_ms=%d shortcode=%s",
            rid, response.status_code, elapsed_ms, shortcode,
        )
        return {"status": "failed", "reason": "http_error", "http_status": response.status_code}
    logger.info(
        "rid=%s stage=api result=ok status=%s elapsed_ms=%d shortcode=%s",
        rid, response.status_code, elapsed_ms, shortcode,
    )

    # --- 段階4: レスポンス解析 ---
    # 本文はログに残さない（署名付きメディア URL が含まれ得るため）。
    # 代わりにトップレベルのキー名だけを記録する。
    try:
        data = response.json()
    except ValueError:
        logger.error("rid=%s stage=parse result=json_error shortcode=%s", rid, shortcode)
        return {"status": "failed", "reason": "parse_error", "http_status": response.status_code}

    top_keys = sorted(data.keys()) if isinstance(data, dict) else [f"<{type(data).__name__}>"]
    logger.info("rid=%s stage=parse result=ok top_keys=%s", rid, ",".join(top_keys))

    # --- 段階5: メディア抽出 ---
    # 想定外の応答形状でも呼び出し側（Webhook ハンドラ）を落とさないよう、
    # 抽出時の例外はここで捕捉して失敗として記録する。
    try:
        media_list = _extract_media_info(data)
    except Exception as e:
        logger.error(
            "rid=%s stage=extract result=error error_type=%s shortcode=%s",
            rid, type(e).__name__, shortcode,
        )
        return {"status": "failed", "reason": "extract_error", "http_status": response.status_code}

    if not media_list:
        logger.error(
            "rid=%s stage=extract result=no_media top_keys=%s shortcode=%s",
            rid, ",".join(top_keys), shortcode,
        )
        return {"status": "failed", "reason": "no_media", "http_status": response.status_code}

    media_types = [m["type"] for m in media_list]
    logger.info(
        "rid=%s stage=extract result=ok count=%d types=%s shortcode=%s",
        rid, len(media_list), ",".join(media_types), shortcode,
    )

    # 結果の構築
    result: Dict[str, Any] = {
        "type": "carousel" if len(media_list) > 1 else "single",
        "media_count": len(media_list),
        "media_list": media_list
    }

    # 後方互換性のため、最初のメディアの情報も含める
    first_media = media_list[0]
    result["media_url"] = first_media["url"]
    result["preview_url"] = first_media["thumbnail"] or first_media["url"]

    # 従来のtypeフィールド（最初のメディアのタイプ）
    result["media_type"] = first_media["type"]

    return {"status": "ok", "result": result}


def process_instagram_url(text: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    後方互換用のラッパー。成功時はメディア情報の辞書、失敗時・URLなしの場合は None を返す。

    失敗理由の区別が必要な呼び出し側は fetch_instagram_media を使うこと。
    """
    outcome = fetch_instagram_media(text, request_id=request_id)
    if outcome.get("status") == "ok":
        return outcome["result"]
    return None


def failure_message(reason: Optional[str]) -> str:
    """
    取得失敗を利用者へ伝える文言を、失敗理由に応じて返す（LINE / Discord 共通）。

    理由を断定しすぎない文言にする。特に http_error は、準センシティブ帯
    （外部参照が制限されている投稿）で観測された応答だが、一般的な上流障害でも
    起こり得るため「可能性」として伝える。
    """
    if reason == "http_error":
        return (
            "この投稿は取得できませんでした🙏\n"
            "Instagram側で外部からの取得が制限されている投稿の可能性があります。"
        )
    if reason in ("timeout", "request_error"):
        return (
            "取得に失敗しました🙇‍♂️\n"
            "一時的な問題の可能性があります。少し時間をおいて、もう一度送ってみてください。"
        )
    return "この投稿は取得できませんでした🙏"