# Contributing to Multi-Platform Instagram Downloader Bot

このプロジェクトへの貢献を歓迎します！

## 開発環境のセットアップ

1. リポジトリをフォークしてクローン
```bash
git clone https://github.com/your-username/instagram-downloader-bot.git
cd instagram-downloader-bot
```

2. Python仮想環境を作成
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 依存関係をインストール
```bash
pip install -r requirements.txt
```

4. 環境変数を設定
```bash
cp .env.example .env
# .envファイルを編集して必要な値を設定
```

## コーディング規約

### Python Style Guide
- [PEP 8](https://www.python.org/dev/peps/pep-0008/)に従う
- 変数名・関数名：snake_case
- クラス名：PascalCase
- 定数：UPPER_SNAKE_CASE

### コードフォーマッター
```bash
# Black を使用
pip install black
black .
```

### リンター
```bash
# Flake8 を使用
pip install flake8
flake8 .
```

## プルリクエストのプロセス

1. 新しい機能/修正用のブランチを作成
```bash
git checkout -b feature/your-feature-name
```

2. 変更をコミット（わかりやすいメッセージで）
```bash
git commit -m "feat: add new feature"
```

### コミットメッセージ規約
- `feat:` 新機能
- `fix:` バグ修正
- `docs:` ドキュメント変更
- `style:` コードスタイルの変更
- `refactor:` リファクタリング
- `test:` テスト追加・修正
- `chore:` ビルドプロセス・補助ツール変更

3. ブランチをプッシュ
```bash
git push origin feature/your-feature-name
```

4. プルリクエストを作成

## テスト

### ユニットテストの実行
```bash
python -m pytest tests/
```

### 新機能のテスト
- 新しい機能には必ずテストを追加してください
- テストカバレッジは80%以上を維持

## バグレポート

バグを見つけた場合は、以下の情報を含めてIssueを作成してください：

1. **環境情報**
   - OS
   - Pythonバージョン
   - 依存ライブラリのバージョン

2. **再現手順**
   - 詳細なステップ

3. **期待される動作**

4. **実際の動作**

5. **エラーログ**（あれば）

## 機能リクエスト

新機能のアイデアがある場合は、Issueで提案してください：

1. **機能の概要**
2. **ユースケース**
3. **実装案**（あれば）

## セキュリティ

セキュリティの脆弱性を発見した場合は、公開Issueではなく、直接メンテナーに連絡してください。

## ライセンス

貢献されたコードは、プロジェクトのMITライセンスに従います。

## 質問・サポート

質問がある場合は、Discussionsセクションを利用するか、Issueを作成してください。

ありがとうございます！ 🙏