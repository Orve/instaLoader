import logging
import requests
import json
from typing import Optional, Dict, Any, Union, List

from core.config import RAPID_API_KEY, RAPID_API_HOST

# ログ設定
logger = logging.getLogger(__name__)

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

def process_instagram_url(text: str) -> Optional[Dict[str, Any]]:
    """
    テキスト内のInstagram URLを検出し、RapidAPIを使用してメディア情報を取得する。
    複数メディア（カルーセル投稿）に対応。
    
    Args:
        text (str): ユーザーからの入力テキスト
        
    Returns:
        Optional[Dict[str, Any]]: 取得成功時は以下の辞書を返す。失敗時またはURLが含まれない場合はNone。
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
        logger.info(f"RapidAPI Response: {json.dumps(data, ensure_ascii=False)[:500]}...")  # 最初の500文字のみログ

        # --- メディア情報の抽出 ---
        media_list = _extract_media_info(data)
        
        if not media_list:
            logger.error(f"No media URLs found in response")
            return None
        
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
        
        logger.info(f"Extracted {len(media_list)} media items from Instagram post")
        logger.info(f"Media types: {[m['type'] for m in media_list]}")
        
        return result

    except Exception as e:
        logger.error(f"Error in process_instagram_url: {e}")
        return None