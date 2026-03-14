# logistic_track テーブル更新仕様書 (1)

---

## 概要

日本郵便からSFTP経由で取得した追跡情報CSVを解析し、`logistic_track` テーブルに書き込む。

- **対象商品**：ゆうパックのみ（ゆうパケットは将来対応）
- **実行タイミング**：毎日 13:05 / 18:05 / 23:55 にCSV取得後に実行

---

## 1. 入力ファイル定義

カンマ区切り・ヘッダあり（1行目は列名行）。

| # | カラム名 | サンプル値 |
|---|---------|-----------|
| 1 | 追跡番号 | `494735708622` |
| 2 | 取扱局／支店名 | `堺金岡郵便局` |
| 3 | 取扱日時 | `2023/12/23 06:34:21` |
| 4 | ステータスコード | `30` |
| 5 | ステータス | `到着` |

---

## 2. テーブル定義

| カラム名 | 型 | NULL | 備考 |
|---------|-----|------|------|
| `id` | bigint | NO | PK・自動採番 |
| `tracking_no` | varchar(50) | NO | 追跡番号 |
| `report_date` | datetime | YES | 状態発生日時 |
| `shipping_club` | varchar(255) | YES | 配送業者名 |
| `baggage_status` | varchar(255) | YES | 荷物ステータス |
| `track_type` | int | YES | トラック種別 |
| `store_nm_in_charge` | varchar(255) | YES | 担当店舗名 |
| `create_time` | datetime | YES | 作成日時 |
| `update_time` | datetime | YES | 更新日時 |
| `create_user_id` | bigint | YES | 作成ユーザID |
| `update_user_id` | bigint | YES | 更新ユーザID |
| `url` | varchar(200) | YES | |
| `sign_type` | varchar(25) | YES | |
| `remark` | varchar(200) | YES | |

---

## 3. マッピング定義

| DBカラム | 入力元 | 変換内容 |
|---------|--------|---------|
| `id` | - | 自動採番 |
| `tracking_no` | 追跡番号 | そのまま |
| `report_date` | 取扱日時 | `YYYY/MM/DD HH:mm:ss` → datetime型 |
| `shipping_club` | - | `"日本郵便"` 固定 |
| `baggage_status` | ステータス | そのまま |
| `track_type` | - | NULL |
| `store_nm_in_charge` | 取扱局／支店名 | そのまま |
| `create_time` | - | `NOW()`（INSERT時） |
| `update_time` | - | `NOW()`（INSERT時） |
| `create_user_id` | - | NULL |
| `update_user_id` | - | NULL |
| `url` | - | NULL |
| `sign_type` | - | NULL |
| `remark` | - | NULL |

---

## 4. バリデーション

### ファイルチェック（全行処理前）

| チェック対象 | 条件 | NGの場合 |
|------------|------|---------|
| カラム数 | 5カラム全て揃っていること | 処理中断 |

### 行チェック（1行ずつ）

V6仕様書より全項目必須のため、いずれかがNULL・空文字の場合は処理中断。

| チェック対象 | 条件 |
|------------|------|
| 追跡番号 | NULL・空文字でないこと |
| 取扱局／支店名 | NULL・空文字でないこと |
| 取扱日時 | `YYYY/MM/DD HH:mm:ss` 形式であること |
| ステータスコード | NULL・空文字でないこと |
| ステータス | NULL・空文字でないこと |

---

## 5. 確認事項 (済)

| # | 確認事項 |
|---|---------|
| 1 | `track_type` はNULLのままでよいか<br>　→ 開発課に確認したところNULLで問題ない |
| 2 | `create_user_id` / `update_user_id` の値（NULLでよいか）<br>　→ 開発課に確認したところNULLで問題ない |

---

## 参考資料

| ファイル名 | 用途 |
|-----------|------|
| `追跡情報提供サービスV6.doc` | ファイルフォーマット・ステータスコード定義（別紙7・9） |
| `発生した追跡情報.xlsx` | 追跡情報のサンプルデータ |
| `IDN0062_01__SFTP_企業間通信確認票_v2_0.xlsx` | 入力ファイル形式（CSV）・取得スケジュールの根拠 |
