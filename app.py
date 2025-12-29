import streamlit as st
import instaloader
import re
import os
import shutil

# ページ設定（スマホで見やすいように）
st.set_page_config(page_title="Insta Saver", page_icon="📸", layout="centered")

# スマホ向けのCSS調整（画像の余白とかを調整して見やすくするおまじない）
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

# Instaloader初期化
L = instaloader.Instaloader(
    download_pictures=True,
    download_videos=False, 
    download_video_thumbnails=False,
    download_geotags=False, 
    download_comments=False, 
    save_metadata=False,
    compress_json=False
)

# URL入力
url = st.text_input("URL", placeholder="https://www.instagram.com/p/...")

def get_shortcode(url):
    match = re.search(r'instagram\.com/p/([^/]+)', url)
    return match.group(1) if match else None

# エンターキーでも反応するようにフォーム化
with st.form("save_form"):
    submitted = st.form_submit_button("画像を表示する 🔍")

    if submitted and url:
        shortcode = get_shortcode(url)
        if not shortcode:
            st.error("URLを確認してね🥺")
        else:
            try:
                # ターゲットディレクトリ設定
                # os.makedirs(DOWNLOAD_DIR, exist_ok=True) # ここはループ外でやるべきだが、都度確認でもOK
                if not os.path.exists(DOWNLOAD_DIR):
                    os.makedirs(DOWNLOAD_DIR)

                target_dir = os.path.join(DOWNLOAD_DIR, shortcode)
                
                # 既存のキャッシュがあれば消す（常に最新を取得）
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                
                with st.spinner('画像を読み込んでるよ...'):
                    post = instaloader.Post.from_shortcode(L.context, shortcode)
                    
                    # Instaloaderのダウンロード実行
                    # target引数にパスを含めると誤動作するため、一時的にディレクトリ移動（バグ修正済ロジック）
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
                            
                            # widthを指定せず use_container_width=True にすると
                            # スマホの画面幅いっぱいに表示されてリッチに見えるよ
                            st.image(img_path, use_container_width=True)
                            
                            # 画像間の余白（スペーサー）
                            st.write("") 
                            st.write("")

            except Exception as e:
                st.error(f"エラー: {e}")
