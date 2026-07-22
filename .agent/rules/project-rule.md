---
trigger: always_on
---

- 常に日本語で回答すること
- Windows版uvで管理している。Windows版uvのパスは `.env` の `WUV` から読むこと。スクリプト実行は `$(WUV) run python earth_photo_manager.pyw` または `make test` のように行うこと。
- .venvはWindows版uv専用とし、Codexは作成・更新・削除しないこと。CodexがWSL/Linux側で検証用の環境を必要とする場合は.venv-agentを使用してよい。ただしGUI起動、ビルド、実機動作確認はWindows版uvで行うこと。
- アプリ開発の基本格子は../sdvx_helperも参考にしてよい。
- プログラム本体はearth_photo_manager.pywである。srcに各モジュールを、misc内に単体検証やdb準備などの各種スクリプトを格納する。
- 実装プランのmarkdownも日本語で書いて
