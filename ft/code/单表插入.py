# load_csv_to_db.py
import csv
import pymysql

DB = dict(host='10.0.0.4', port=3316, user='delay_user',
          password='T7#mK9$vQ!x2@pL&nR5*wE8sY^a4FbN', database='delay_data', charset='utf8mb4')

CSV_FILE = 'delay_total_20251029.csv'
conn = pymysql.connect(**DB)
with conn:
    with conn.cursor() as cur:
        sql = """
        INSERT INTO delay_total (ID, ts, Delay_ms, Exchange, Calc_Date, category)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          Delay_ms = VALUES(Delay_ms),
          created_at = NOW()
        """
        with open(CSV_FILE, encoding='utf-8') as f:
            rows = [r[:6] for r in csv.reader(f)][1:]  # 6 列正好对应 6 个 %s
            cur.executemany(sql, rows)
        conn.commit()
print(f'已导入 {len(rows)} 条记录')