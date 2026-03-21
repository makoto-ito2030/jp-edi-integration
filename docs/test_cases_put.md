# PUTテストケース

---

## 前提

- DBは実DB（またはテスト用DB）を使用する
- 各テスト実行前に `work/put_outbox/` / `work/put_backup/` / `work/put_error/` をクリアする
- SFTP送信が不要なテストは `sftp_put_enabled = false` に設定して実行する
- S3バックアップが不要なテストは `s3_backup_enabled = false` に設定して実行する

---

## 正常系

1. **対象レコードがある場合、CSVが生成され `put_outbox/` に配置される**
   - 前提: 送信対象レコードがDBに存在する（`jp_download = 0` または未登録）、`sftp_put_enabled = false`、`s3_backup_enabled = false`
   - 操作: バッチ実行
   - 期待: `put_outbox/` にCSVが生成される / ログに `Generated CSV` が出力される

2. **SFTP送信が成功した場合、CSVが `put_backup/` へ移動する**
   - 前提: 送信対象レコードがDBに存在する、`s3_backup_enabled = false`
   - 操作: バッチ実行
   - 期待: `put_outbox/` のCSVが `put_backup/` へ移動する / `put_outbox/` にCSVが残らない / ログに `sent. Moved to put_backup` が出力される

3. **SFTP送信成功後、`goods_hawb_ext.jp_download` が `1` に更新される**
   - 前提: 送信対象レコードがDBに存在する、`s3_backup_enabled = false`
   - 操作: バッチ実行
   - 期待: 送信したレコードの `goods_hawb_ext.jp_download` が `1` になっている / ログに `jp_download updated` が出力される

4. **S3バックアップが成功した場合、`put_backup/` からCSVが削除される**
   - 前提: 送信対象レコードがDBに存在する
   - 操作: バッチ実行
   - 期待: `put_backup/` のCSVがS3にアップロードされる / `put_backup/` からCSVが削除される / ログに `backed up to S3 and deleted` が出力される

5. **`put_backup/` に前回残ったCSVが次回起動時にS3リトライされる**
   - 前提: `put_backup/` にCSVが残っている状態（前回S3バックアップ失敗を想定）、送信対象レコードはDBに存在しない（`jp_download = 1`）
   - 操作: バッチ実行
   - 期待: `put_backup/` のCSVがS3にアップロードされる / `put_backup/` からCSVが削除される

6. **対象レコードがない場合、何もせず正常終了する**
   - 前提: 送信対象レコードがDBに存在しない（全件 `jp_download = 1`）
   - 操作: バッチ実行
   - 期待: CSVが生成されない / ログに `No records to send.` が出力される / 終了コード0

7. **`sftp_put_enabled = false` の場合、CSV生成のみ行われSFTP送信はスキップされる**
   - 前提: 送信対象レコードがDBに存在する、`sftp_put_enabled = false`、`s3_backup_enabled = false`
   - 操作: バッチ実行
   - 期待: `put_outbox/` にCSVが生成される / SFTPは実行されない / ログに `SFTP upload skipped` が出力される

8. **`s3_backup_enabled = false` の場合、S3バックアップがスキップされる**
   - 前提: 送信対象レコードがDBに存在する、`s3_backup_enabled = false`
   - 操作: バッチ実行
   - 期待: SFTP送信は正常に行われる / S3はアップロードされない / `put_backup/` にCSVが残る / ログに `S3 backup skipped` が出力される

---

## CSV生成系

9. **生成されたCSVのファイル名が `put_filename_template` のタイムスタンプ置換形式になっている**
   - 前提: 送信対象レコードがDBに存在する、`sftp_put_enabled = false`、`s3_backup_enabled = false`
   - 操作: バッチ実行後、`put_outbox/` のCSVファイル名を確認
   - 期待: `put_filename_template` の `0000000000000`（13桁）が実行時刻の `YYYYMMDDHHMMSS` に置換されたファイル名になっている

10. **生成されたCSVが50カラム・CRLF・UTF-8（BOMなし）になっている**
    - 前提: 送信対象レコードがDBに存在する、`sftp_put_enabled = false`、`s3_backup_enabled = false`
    - 操作: バッチ実行後、`put_outbox/` のCSVを確認
    - 期待: 各行が50カラムのカンマ区切り / 改行コードがCRLF / 文字コードがUTF-8（BOMなし） / ヘッダ行なし

11. **1行目が `DENKAKUTEI,,,101,` で始まる**
    - 前提: 10番と同じ
    - 期待: No.1が `DENKAKUTEI`、No.2・3がブランク、No.4が `101` になっている

12. **`jp_download` 更新後に再実行した場合、CSVに対象レコードが含まれない**
    - 前提: 4番実行済み（`jp_download = 1` に更新済み）
    - 操作: バッチ再実行
    - 期待: 対象レコードが0件となり `No records to send.` で終了する

13. **フィールドに禁則文字が含まれる場合、除去されてCSVに出力される**
    - 前提: `consignee_name` にタブ文字や改行が含まれるレコードをDBに用意する
    - 操作: バッチ実行（`sftp_put_enabled = false`）
    - 期待: CSVの該当フィールドから禁則文字が除去されている

14. **サイズが計算できないレコード（全フィールドが0）がある場合、No.27がブランクで警告メールが送信される**
    - 前提: `length = 0`, `width = 0`, `height = 0` のレコードをDBに用意する
    - 操作: バッチ実行
    - 期待: No.27がブランクで出力される / 警告メールが1件送信される

15. **サイズコードの境界値が正しく計算される**
    - 前提: 各サイズ閾値の境界値レコードをDBに用意する、`sftp_put_enabled = false`
    - 操作: バッチ実行後、CSVのNo.27を確認
    - 期待: 3辺合計と対応するサイズコードが以下の通りになっている

    | 3辺合計 | 期待するサイズコード |
    |---------|----------------------|
    | 60cm以下 | `060` |
    | 61cm | `080` |
    | 80cm以下 | `080` |
    | 81cm | `100` |
    | 100cm以下 | `100` |
    | 101cm | `120` |
    | 120cm以下 | `120` |
    | 121cm | `140` |
    | 140cm以下 | `140` |
    | 141cm | `160` |
    | 160cm以下 | `160` |
    | 161cm | `170` |
    | 170cm以下 | `170` |
    | 171cm以上 | `170` |

16. **サイズが170cm超のレコードがある場合、No.27が `170` になり警告メールは送信されない**
    - 前提: 3辺合計が170cm超（例: 60+60+60=180）のレコードをDBに用意する
    - 操作: バッチ実行（`sftp_put_enabled = false`）
    - 期待: No.27が `170` で出力される / 警告メールは送信されない

---

## エラー系

17. **SFTPエラー時にCSVが `put_error/` へ移動し終了する**
    - 前提: SFTPの接続情報を意図的に誤った設定にする
    - 操作: バッチ実行
    - 期待: CSVが `put_error/` へ移動する / `put_outbox/` にCSVが残らない / エラーログが出力される / エラーメールが送信される / 終了コード1

18. **DB接続エラー時にエラーメールが送信され終了する**
    - 前提: DBの接続情報を意図的に誤った設定にする
    - 操作: バッチ実行
    - 期待: CSVが生成されない / エラーメールが送信される / 終了コード1

19. **S3バックアップ失敗時に `put_backup/` にファイルが残り、次回起動時にリトライされる**
    - 前提: S3の接続情報を意図的に誤った設定にする（SFTP送信は成功する設定）
    - 操作: バッチ実行
    - 期待: CSVが `put_backup/` に残る / 次回バッチ起動時にS3バックアップがリトライされる

20. **設定ファイルが存在しない場合、エラーメールが送信され終了する**
    - 前提: `config/settings.ini` を削除または別名にリネームする
    - 操作: バッチ実行
    - 期待: エラーメールが送信される（件名: `[ERROR] put_jp_edi: configuration error`） / 終了コード1

21. **`mail_enabled = false` の場合、エラー発生時もメールが送信されない**
    - 前提: DBの接続情報を意図的に誤った設定にする、`mail_enabled = false`
    - 操作: バッチ実行
    - 期待: エラーログが出力される / メールは送信されない / 終了コード1

---

## 二重起動防止

22. **バッチ実行中に同じバッチを起動しようとした場合、二重起動が防止されメールが送信される**
    - 前提: ロックファイル（`work/put_jp_edi.lock`）が存在する状態
    - 操作: バッチ実行
    - 期待: 即座に終了する / ログに `Another process is running` が出力される / エラーメールが送信される（件名: `[ERROR] put_jp_edi: lock file exists`）

23. **バッチが正常終了した後、ロックファイルが削除される**
    - 前提: 送信対象レコードがDBに存在する
    - 操作: バッチ実行・完了
    - 期待: `work/put_jp_edi.lock` が存在しない

24. **バッチが異常終了した後、ロックファイルが残り手動削除後に再実行可能になる**
    - 操作: バッチ実行中にプロセスを `kill -9` で強制終了
    - 期待: `work/put_jp_edi.lock` が残る / そのまま再実行すると `Another process is running` で終了 / ロックファイルを手動削除すると再実行可能になる
