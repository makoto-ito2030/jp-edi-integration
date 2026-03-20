# JP向けEDI連携バッチ

## 目的
- 出荷CSVを生成し、JPサーバへPUTするバッチ
- JPサーバから追跡CSVを取得し、DB更新＋バックアップするバッチ

## ディレクトリ構成
```
./
├── bin/
│   ├── put_jp_edi.py               # PUTバッチ（出荷CSV→JP）
│   └── get_jp_track.py             # GETバッチ（追跡CSV→DB）
│
├── config/
│   ├── settings.ini                # PUT/GET共通の設定（gitignore対象）
│   └── settings.ini.dummy          # 設定ファイルのテンプレート
│
├── lib/
│   ├── clients/
│   │   ├── sftp_client.py          # SFTPクライアント
│   │   ├── s3_client.py            # S3クライアント
│   │   └── db_client.py            # DBクライアント（RDS/MySQL）
│   ├── lock_manager.py             # ロックファイルによる二重起動防止
│   └── get_jp_track/
│       ├── progress_manager.py     # GETバッチ進捗管理
│       ├── check_track_csv.py      # 追跡CSVフォーマットチェック
│       ├── parse_track_csv.py      # 追跡CSVパース・変換
│       └── insert_rows.py          # 重複チェック・バルクINSERTロジック
│
├── work/
│   ├── put_outbox/                 # PUT用 送信前CSV
│   ├── put_error/                  # PUT失敗CSV
│   ├── get_inbox/                  # GET用 取得した追跡CSV
│   ├── get_progress/               # GET処理中の進捗ファイル（処理済み行数・エラー行記録）
│
└── logs/
    ├── put_jp_edi_YYYYMM.log       # PUTバッチログ（月次）
    └── get_jp_track_YYYYMM.log     # GETバッチログ（月次）
```
※ `work/` と `logs/` はバッチ初回実行時に自動生成される

## 前提
- Python 3.x がインストール済み
- 依存パッケージがインストール済み（後述）
- JPのSFTP接続情報（ホスト、ポート、ユーザー、パスワード、ディレクトリ）が既知
- AWSの接続情報（S3バケット、RDSエンドポイント）が既知

## 依存パッケージ
```bash
pip install paramiko boto3 pymysql
```

## 設定ファイル
`config/settings.ini.dummy` をコピーして `config/settings.ini` を作成し、接続情報を記載する。

```bash
cp config/settings.ini.dummy config/settings.ini
```

```ini
[sftp]
host        = dummy-sftp-host.example.com
port        = 22
user        = dummy_user
password    = dummy_password
put_dir     = /edi/inbound
get_dir     = /edi/outbound

[s3]
bucket      = dummy-bucket-name
prefix      = edi/

[db]
host        = dummy-rds-endpoint.rds.amazonaws.com
port        = 3306
user        = dummy_user
password    = dummy_password
database    = dummy_database

[jp_edi]
biz_card_no         = 00000000000000000000000000000000  # ゆうびんビズカードお客さま番号（32桁）
shipper_name        = dummy_name                        # ご依頼主名
shipper_tel         = 0000000000                        # ご依頼主電話番号
shipper_postal_code = 0000000                           # ご依頼主郵便番号（7桁、ハイフンなし）
shipper_address     = dummy_address                     # ご依頼主住所

[feature]
s3_backup_enabled = true
sftp_get_enabled  = true
sftp_put_enabled  = true
```

## 実行方法と処理概要

### PUTバッチ
```bash
python -m bin.put_jp_edi
```
1. DBから出荷CSVを生成し、`work/put_outbox` に配置
2. `work/put_outbox` のCSVをSFTPでJPサーバへPUT
3. 成功時：S3へバックアップ、ローカルファイルを削除、`goods_hawb_ext.jp_download` を更新、ログに成功を出力
4. 失敗時：`work/put_error` へ移動、ログにエラーを出力して終了

再実行時はDBから再度CSVを生成する。`work/put_error` に残ったファイルはログと照合した原因調査用であり、再実行には使用しない。

### GETバッチ
```bash
python -m bin.get_jp_track
```
1. ロックファイル（`work/get_jp_track.lock`）で二重起動を防止
2. JPサーバから追跡CSVをSFTPで取得し、`work/get_inbox` に保存
3. 進捗ファイルを即時作成（サーバー障害時の再開に備える）
4. S3へバックアップ
5. フォーマットチェックを行い、NGファイルは `work/get_inbox/` に残してエラーをログに記録（修正後に再実行することで処理される）
6. CSVを解析し、`tracking_no + baggage_status + report_date` で重複チェック後に `logistic_track` テーブルへバルクINSERT（1,000件チャンク）
7. チャンクエラー時は1件ずつINSERTにフォールバック、エラー行は進捗ファイルに記録してスキップ
8. 完走後、エラーなし・S3バックアップOKなら進捗ファイルを削除、`get_inbox` のCSVを削除
9. 進捗ファイルが残っている場合は手動対応が必要（`work/get_progress/` を確認）

#### GETバッチ：サーバー障害時の再開
進捗ファイルは処理状況の把握およびサーバー障害時の再開に使用する。重複チェック（`tracking_no + baggage_status + report_date`）により再実行時の重複INSERTは防止されている。

処理中にサーバーが停止した場合、`work/get_inbox/` にCSVが残り、`work/get_progress/` に進捗ファイルが残る。再起動後にバッチを実行すると、進捗ファイルを読み込み処理済み行の次から自動的に再開する。

```json
{
  "source_file": "track_20260319.csv",   // 処理対象CSVファイル名
  "started_at": "2026/03/19 02:00:00",   // 処理開始日時
  "updated_at": "2026/03/19 02:00:45",   // 最終更新日時
  "s3_backup": "ok",                     // S3バックアップ成否（ok / ng）
  "format_check": "ok",                  // フォーマットチェック成否（ok / ng）
  "format_check_error": null,            // フォーマットエラー内容
  "total_rows": 50000,                   // CSV総行数
  "processed_rows": 30000,              // 処理済み行数
  "inserted_rows": 29980,               // INSERT済み行数
  "error_rows": {
    "count": 2,                          // エラー行数
    "rows": [
      {
        "row": 1234,                     // エラー行番号
        "tracking_no": "111122223333",   // 追跡番号
        "reason": "Duplicate entry..."  // エラー理由
      }
    ]
  }
}
```

## タスクスケジューラ

（後で記載）

## メール通知

（後で記載）

エラー時などに特定のアドレス宛にエラーメールを送信する。
