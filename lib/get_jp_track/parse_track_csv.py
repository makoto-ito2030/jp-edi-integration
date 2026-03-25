"""lib/get_jp_track/parse_track_csv.py - Parse V6 tracking CSV.

Body record columns:
  0: 削除区分, 1: 郵便分類コード, 2: 郵便分類名称, 3: 追跡番号,
  4: 顧客側管理番号, 5: 状態発生日時(YYYYMMDDhhmm), 6: 取扱店コード,
  7: 取扱店名, 8: ステータスコード(4桁=コード2桁+補助2桁), 9: 付加日付,
  10: 引受日時, 11: 引受店コード, 12: 引受店名,
  13: 顧客コード①, 14: 顧客コード②, 15: サイズ情報, 16: 予備
"""

import csv
from datetime import datetime

DATETIME_FORMAT = "%Y%m%d%H%M"

# ステータスコード(4桁) → 状態名
# key: ステータスコード2桁 + 補助コード2桁
STATUS_MAP = {
    "1101": "引受",
    "1102": "引受 大口",
    "1106": "委託引受",
    "1107": "再差出",
    "110E": "引受確定（予約運用）",
    "110F": "引受確定（確定運用）",
    "110G": "予約運用（書留受領証）",
    "1210": "局内受取",
    "1213": "委託引渡",
    "1214": "通過",
    "1215": "無集配送付",
    "1216": "コンビニ引渡",
    "1217": "はこぽす等入庫",
    "1483": "車船輸送 品名未記載",
    "1484": "車船輸送 具体的品名なし",
    "1485": "車船輸送 品名から危険物と判断",
    "1486": "車船輸送 外装から危険物と判断",
    "1487": "車船輸送 外装に危険物表示あり",
    "1488": "車船輸送 Ｘ線検査で発見",
    "3000": "到着",
    "5001": "持出",
    "5002": "持出 大口",
    "5130": "不在 持ち戻り",
    "5131": "不在 代人配達",
    "5132": "不在 指定場所",
    "5133": "不在 ムツ",
    "5201": "配達完了",
    "5231": "配達完了 代人配達",
    "5232": "配達完了 指定場所",
    "5234": "配達完了 返還完了",
    "5235": "配達完了 委託先",
    "5236": "配達完了 受取",
    "5337": "窓口交付",
    "5338": "局内交付",
    "6048": "不在留置",
    "6049": "保管 私書箱",
    "6050": "保管 局留",
    "6077": "保管 指示待ち",
    "6081": "保管 棚入",
    "6082": "保管 棚出",
    "6099": "保管 その他",
    "6151": "転送 受取場所変更",
    "6152": "転送 転居",
    "6153": "転送 あて名変更",
    "6154": "転送 嘱託回送",
    "6155": "転送 海外転送",
    "6179": "転送 その他",
    "6244": "返還 汚損・き損",
    "6256": "返還 期間経過",
    "6257": "返還 転送期間経過",
    "6258": "返還 たずねあたらず",
    "6259": "返還 あて名不完全",
    "6260": "返還 棟室番号無",
    "6261": "返還 受取拒絶",
    "6262": "返還 取り戻し",
    "6263": "返還 転送不要",
    "6264": "返還 転居先不明",
    "6265": "返還 返還不要",
    "6266": "返還 返還不能",
    "6276": "返還 長期不在",
    "6279": "返還 その他",
    "6367": "配達希望",
    "6368": "転送希望",
    "6369": "保管期間延長",
    "6370": "取り戻し希望",
    "6371": "返還取り消し",
    "6372": "留置希望",
    "6378": "初回配達希望",
    "6379": "初回転送希望",
    "6380": "初回留置希望",
    "6473": "配達予定 休業日",
    "6474": "配達予定 災害",
    "6475": "配達予定 業務都合",
    "6479": "配達予定 その他",
    "9039": "誤送（その他の理由）",
    "9040": "誤転送",
    "9041": "誤返還",
    "9042": "誤配",
    "9043": "郵便番号誤打鍵",
    "9044": "汚損・き損",
    "9045": "破損補修",
    "9046": "誤送（仕分番号違い）",
    "9047": "問い合わせ",
    "9079": "その他",
}


def parse_csv(filepath):
    """
    Parse V6 CSV and return list of tuples for logistic_track INSERT.
    Skips header record (row 0) and deletion records (削除区分=1).
    Returns: list of tuple (tracking_no, report_date, shipping_club, baggage_status,
                            store_nm_in_charge, create_time, update_time)
    """
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, encoding="shift-jis", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header record
        for row in reader:
            # Skip deletion records
            if row[0].strip() == "1":
                continue

            tracking_no        = row[3].strip()
            shipping_club      = row[2].strip()
            report_date        = datetime.strptime(row[5].strip(), DATETIME_FORMAT).strftime("%Y-%m-%d %H:%M:%S")
            store_nm_in_charge = row[7].strip()
            status_code        = row[8].strip()
            baggage_status     = STATUS_MAP.get(status_code, status_code)

            rows.append((
                tracking_no,
                report_date,
                shipping_club,
                baggage_status,
                store_nm_in_charge,
                now,  # create_time
                now,  # update_time
            ))
    return rows
