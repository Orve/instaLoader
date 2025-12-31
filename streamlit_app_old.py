import streamlit as st
import instaloader
import re
import os
import shutil

# ページ設定
st.set_page_config(page_title="Insta Saver", page_icon="📸", layout="centered")

# スマホ向けのCSS調整
st.markdown("""
    <style>
        .stImage { margin-bottom: 20px; }
        .stButton button { width: 100%; border-radius: 20px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("📸 Insta Saver")
st.caption("気に入った画像は **長押し** して保存してね👇")

# 保存先ディレクトリ
DOWNLOAD_DIR = "downloads"

# Instaloader初期化（User-Agent偽装）
# iPhoneの公式アプリからのアクセスに見せかける
USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 239.2.0.17.109'

L = instaloader.Instaloader(
    download_pictures=True,
    download_videos=False, 
    download_video_thumbnails=False,
    download_geotags=False, 
    download_comments=False, 
    save_metadata=False,
    compress_json=False,
    user_agent=USER_AGENT  # ここでUser-Agentを指定
)

# URL入力
url = st.text_input("URL", placeholder="https://www.instagram.com/p/...")

def get_shortcode(url):
    match = re.search(r'instagram\.com/p/([^/]+)', url)
    return match.group(1) if match else None

# エンターキーでも反応するようにフォーム化
with st.form("save_form"):
    submitted = st.form_submit_button("画像を表示する �")

    if submitted and url:
        shortcode = get_shortcode(url)
        if not shortcode:
            st.error("URLを確認してね🥺")
        else:
            try:
                # ターゲットディレクトリ設定
                if not os.path.exists(DOWNLOAD_DIR):
                    os.makedirs(DOWNLOAD_DIR)

                target_dir = os.path.join(DOWNLOAD_DIR, shortcode)
                
                # 既存のキャッシュがあれば消す（常に最新を取得）
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                
                with st.spinner('画像を読み込んでるよ...'):
                    # 取得処理
                    post = instaloader.Post.from_shortcode(L.context, shortcode)
                    
                    # 保存処理（ディレクトリ移動ハック）
                    current_dir = os.getcwd()
                    try:
                        os.chdir(DOWNLOAD_DIR)
                        L.download_post(post, target=shortcode)
                    finally:
                        os.chdir(current_dir)
                    
                    # 画像ファイルを取得してソート
                    images = sorted(
                        [f for f in os.listdir(target_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
                    )

                    if not images:
                        st.warning("画像が見つからなかった…動画のみかも？")
                    else:
                        st.success(f"{len(images)}枚の画像を見つけたよ✨")
                        st.divider() # 区切り線
                        
                        # 画像をループ表示
                        for img_file in images:
                            img_path = os.path.join(target_dir, img_file)
                            st.image(img_path, use_container_width=True)
                            st.write("") 
                            st.write("")

            except Exception as e:
                error_msg = str(e)
                # エラーハンドリング
                if "401 Unauthorized" in error_msg or "wait a few minutes" in error_msg:
                    st.warning("Instagramのアクセス制限がかかっちゃったみたい☕️\n\n短時間にたくさんアクセスすると一時的にブロックされることがあるよ。\n5〜10分くらいゆっくり休んでから、また試してみてね！")
                elif "404 Not Found" in error_msg:
                    st.error("投稿が見つからなかったよ🥺 URLが合ってるか、鍵垢じゃないか確認してみて。")
                elif "Login required" in error_msg:
                     st.warning("ログインが必要な投稿みたい🔒\n非公開アカウントや、一部の投稿はログインしないと見れない仕様だよ。")
                else:
                    st.error(f"エラーが発生しちゃった: {error_msg}")
