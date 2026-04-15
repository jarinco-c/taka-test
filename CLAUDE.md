# 手書き文字認識アプリ

## プロジェクト概要
手書き文書（PDF・画像）をClaude Vision APIでテキスト化するWebアプリ。

## 現在の状態
- ブランチ: `claude/handwriting-recognition-app-GTXUp`
- OCRエンジン: Claude API（claude-opus-4-6）
- EasyOCRは精度不足のため却下済み

## 経緯・決定事項
- EasyOCR → Claude API に変更（手書き表形式の精度が段違い）
- 社内ルール未整備のため現時点では個人APIキーで運用
- GWSチームのGemini手動運用と比較して精度は同等、使い勝手は上
- 将来的にAPIの社内申請が通ったら社内展開予定

## 今後の拡張候補
- Excelダウンロード機能
- 300ページ一括処理（SSE or Batch API）
- Anthropic Batch API対応（コスト半額）

## 起動方法
```powershell
# venv有効化
venv\Scripts\Activate.ps1

# APIキー設定
$env:ANTHROPIC_API_KEY="sk-ant-..."

# 起動
uvicorn app:app --reload
```

## ファイル構成
```
app.py           # FastAPIバックエンド
requirements.txt # 依存ライブラリ
static/index.html # フロントエンド
仕様書.md         # システム仕様書
```
