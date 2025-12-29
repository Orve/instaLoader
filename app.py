import streamlit as st

# ページ設定
st.set_page_config(page_title="Insta Saver", page_icon="📸", layout="centered")

# スマホ向けのCSS調整
st.markdown("""
    <style>
        .stImage { margin-bottom: 20px; }
        .main-msg { text-align: center; font-weight: bold; font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

st.title("📸 Insta Saver")

# メンテナンス表示
st.warning("🚧 現在メンテナンス中です 🚧")
st.write("")
st.markdown("""
<div class="main-msg">
    Instagram側のアクセス制限に伴い、<br>
    現在システム調整を行っています。<br>
    <br>
    復旧までしばらくお待ちください🙇‍♂️
</div>
""", unsafe_allow_html=True)
st.write("")
st.info("※ 時間をおいてアクセスできるようになる場合もありますが、現在は不安定な状態です。")

# （コードはGit履歴に残っているため、ここでは削除して表示をクリアにします）
