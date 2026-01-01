
import logging
import requests
import json
from typing import Optional, Dict, Any, Union, List

from core.config import RAPID_API_KEY, RAPID_API_HOST

# ログ設定
logger = logging.getLogger(__name__)

def _find_url(obj: Union[Dict[str, Any], List[Any]]) -> Optional[str]:
    """
    レスポンスJSONからメディアURLを再帰的に探索するヘルパー関数。
    
    Args:
        obj: 探索対象の辞書またはリスト
        
    Returns:
        見つかったURL文字列、またはNone
    """
    if isinstance(obj, dict):
        # パターンA: このAPI特有の 'medias' リストがある場合（ここが本命）
        if 'medias' in obj and isinstance(obj['medias'], list) and len(obj['medias']) > 0:
            return _find_url(obj['medias'][0])

        # パターンB: キー名探索
        # 'url' は投稿ページ自体のURLが入っていることがあるので優先度を下げる
        # サムネイル系のキー（thumbnail, cover, thumb）も対象に追加
        for key in ['video_url', 'download_url', 'media', 'thumbnail', 'cover', 'thumb', 'url']:
            if key in obj and isinstance(obj[key], str) and obj[key].startswith('http'):
                # ★重要: Instagramの投稿URLそのもの（HTML）は除外する
                if "instagram.com/p/" in obj[key] or "instagram.com/reel/" in obj[key]:
                    continue
                return obj[key]

        # パターンC: ネストされている場合（body, data, resultsなど）
        for key in ['body', 'data', 'results', 'items', '0']:
            if key in obj:
                res = _find_url(obj[key])
                if res: return res
                
    elif isinstance(obj, list) and len(obj) > 0:
        for item in obj:
            res = _find_url(item)
            if res: return res
            
    return None

def process_instagram_url(text: str) -> Optional[Dict[str, Any]]:
    """
    テキスト内のInstagram URLを検出し、RapidAPIを使用してメディア情報を取得する。
    
    Args:
        text (str): ユーザーからの入力テキスト
        
    Returns:
        Optional[Dict[str, Any]]: 取得成功時は以下の辞書を返す。失敗時またはURLが含まれない場合はNone。
            {
                "type": "video" | "image",
                "media_url": str,
                "preview_url": str
            }
    """
    # InstagramのURLが含まれているかチェック
    if "instagram.com/p/" not in text and "instagram.com/reel/" not in text:
        return None

    if not RAPID_API_KEY:
        logger.error("RAPID_API_KEY is not set.")
        return None

    try:
        # --- RapidAPI呼び出しロジック ---
        url = f"https://{RAPID_API_HOST}/download"
        querystring = {"url": text}
        headers = {
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": RAPID_API_HOST
        }

        logger.info(f"Fetching media from RapidAPI for URL: {text}")
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"RapidAPI Response: {data}")

        # --- レスポンス解析 ---
        media_url = _find_url(data)

        # メディアURLが見つからなかった場合
        if not media_url:
            logger.error(f"Media URL extraction failed. Response data: {json.dumps(data)}")
            return None

        result: Dict[str, Any] = {
            "media_url": media_url,
            "type": "image",  # デフォルト
            "preview_url": media_url # デフォルト
        }

        # 動画か画像かの判定
        if ".mp4" in media_url or "video" in str(data).lower():
            result["type"] = "video"
            
        # プレビュー画像のURL探索
        # json内からサムネイルを探す
        preview_url = _find_url({k: v for k, v in data.items() if 'thumb' in k or 'cover' in k})
        
        # それでもなければ、data直下のthumbnailを明示的にチェック
        if not preview_url and isinstance(data, dict):
            preview_url = data.get('thumbnail')

        if preview_url:
            result["preview_url"] = preview_url
        elif result["type"] == "video":
            # 動画でプレビューがない場合はプレースホルダー
             result["preview_url"] = "https://via.placeholder.com/1024x1024.png?text=No+Preview"

        logger.info(f"Extracted data: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in process_instagram_url: {e}")
        return None
