import streamlit as st
import instaloader
import re
import os

# ページ設定（ちょっとオシャレに）
st.set_page_config(page_title="Insta Saver", page_icon="📸")

st.title("📸 Insta Saver (Minimal)")
st.write("保存したい投稿のURLを貼ってね。")

# 保存先ディレクトリの準備
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Instaloaderのインスタンス化
L = instaloader.Instaloader(
    download_pictures=True,
    download_videos=False, 
    download_video_thumbnails=False,
    download_geotags=False, 
    download_comments=False, 
    save_metadata=False,
    compress_json=False
)

# URL入力欄
url = st.text_input("Instagram Post URL", placeholder="https://www.instagram.com/p/...")

def get_shortcode(url):
    """URLからショートコード（ID部分）を抽出する"""
    match = re.search(r'instagram\.com/p/([^/]+)', url)
    return match.group(1) if match else None

if st.button("保存する"):
    if not url:
        st.warning("URLを入力してね🥺")
    else:
        shortcode = get_shortcode(url)
        if not shortcode:
            st.error("URLの形式が違うみたい… 'instagram.com/p/...' の形式か確認してみて。")
        else:
            try:
                with st.spinner('画像を探しています...'):
                    # 投稿データを取得
                    post = instaloader.Post.from_shortcode(L.context, shortcode)
                    
                    # ターゲットディレクトリ（ID名）
                    target_dir = os.path.join(DOWNLOAD_DIR, shortcode)
                    
                    # Instaloaderのダウンロード実行
                    # target引数にパスを含めると誤動作するため、一時的にディレクトリ移動
                    current_dir = os.getcwd()
                    try:
                        os.chdir(DOWNLOAD_DIR)
                        L.download_post(post, target=shortcode)
                    finally:
                        os.chdir(current_dir)
                    
                    st.success(f"保存完了！✨")
                    st.caption(f"保存先: {target_dir}")
                    
                    # プレビュー表示（ローカル画像を使用）
                    # InstagramのCDNリンクは直接開けない場合があるため、保存したファイルを表示
                    import glob
                    image_files = glob.glob(os.path.join(target_dir, "*.jpg"))
                    
                    if image_files:
                        st.subheader("ダウンロードはこちら 👇")
                        for i, img_path in enumerate(image_files):
                            st.image(img_path, caption=f"Image {i+1}", use_container_width=True)
                            
                            # 画像ファイルをバイト列として読み込む
                            with open(img_path, "rb") as file:
                                btn = st.download_button(
                                    label=f"画像 {i+1} を保存",
                                    data=file,
                                    file_name=os.path.basename(img_path),
                                    mime="image/jpeg",
                                    key=f"download-btn-{i}"
                                )
                    else:
                        # 万が一ローカルファイルが見つからない場合はリモートURLを表示（以前の挙動）
                        st.image(post.url, caption="Preview (Remote - May fail)", use_container_width=True)

            except Exception as e:
                st.error(f"エラーが発生しちゃった: {e}")
                st.info("※非公開アカウントや、ログインが必要な投稿は取得できない場合があります。")
