"""
AI見積書生成システム - データベース設計と初期セットアップ
SQLiteを使用したデータベース構築
"""
import sqlite3
from datetime import datetime

class EstimateDatabase:
    def __init__(self, db_name="estimate_system.db"):
        self.db_name = db_name
        self.conn = None
        self.cursor = None

    def connect(self):
        """データベースに接続"""
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        print(f"[OK] データベースに接続しました: {self.db_name}")

    def create_tables(self):
        """テーブルを作成"""

        # 顧客情報テーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            company_name_kana TEXT,
            postal_code TEXT,
            address TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            distance_km REAL,
            phone TEXT,
            email TEXT,
            contact_person TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        ''')

        # 商品マスタテーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            product_category TEXT,
            description TEXT,
            base_price INTEGER,
            unit TEXT DEFAULT '個',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        ''')

        # 見積履歴テーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS estimates (
            estimate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            estimate_date TEXT DEFAULT (datetime('now', 'localtime')),
            contract_count INTEGER DEFAULT 1,
            total_amount INTEGER NOT NULL,
            status TEXT DEFAULT 'draft',
            sales_person TEXT,
            notes TEXT,
            sent_at TEXT,
            approved_at TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
        ''')

        # 見積明細テーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS estimate_details (
            detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
            estimate_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (estimate_id) REFERENCES estimates(estimate_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
        ''')

        self.conn.commit()
        print("[OK] テーブルを作成しました")

    def insert_sample_products(self):
        """サンプル商品データを挿入"""
        sample_products = [
            ('冷蔵庫', '家電', '業務用冷蔵庫の配送', 50000, '台', None),
            ('洗濯機', '家電', '業務用洗濯機の配送', 30000, '台', None),
            ('テーブル', '家具', 'オフィステーブルの配送', 15000, '台', None),
            ('椅子', '家具', 'オフィスチェアの配送', 8000, '脚', None),
            ('段ボール箱', '梱包資材', '引越し用段ボール', 300, '個', None),
            ('エアコン', '家電', '業務用エアコンの配送・設置', 80000, '台', '設置費用含む'),
            ('什器', '備品', '店舗什器の配送', 25000, '台', None),
            ('金庫', '備品', '業務用金庫の配送', 100000, '台', '重量物のため要確認'),
        ]

        self.cursor.executemany('''
            INSERT INTO products (product_name, product_category, description, base_price, unit, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_products)
        self.conn.commit()
        print(f"[OK] サンプル商品データを{len(sample_products)}件挿入しました")

    def insert_sample_customer(self):
        """サンプル顧客データを挿入"""
        sample_customers = [
            ('株式会社サンプル商事', 'カブシキガイシャサンプルショウジ', '100-0001', '東京都千代田区千代田1-1-1', None, None, None, '03-1234-5678', 'sample@example.com', '山田太郎'),
            ('テスト株式会社', 'テストカブシキガイシャ', '530-0001', '大阪府大阪市北区梅田1-1-1', None, None, None, '06-1234-5678', 'test@example.com', '佐藤花子'),
        ]

        self.cursor.executemany('''
            INSERT INTO customers (company_name, company_name_kana, postal_code, address, latitude, longitude, distance_km, phone, email, contact_person)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_customers)
        self.conn.commit()
        print(f"[OK] サンプル顧客データを{len(sample_customers)}件挿入しました")

    def display_tables(self):
        """テーブル一覧を表示"""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = self.cursor.fetchall()
        print("\n[データベース内のテーブル]")
        for table in tables:
            print(f"  - {table[0]}")

    def close(self):
        """データベース接続を閉じる"""
        if self.conn:
            self.conn.close()
            print("\n[OK] データベース接続を閉じました")

def main():
    """メイン処理"""
    db = EstimateDatabase()

    try:
        db.connect()
        db.create_tables()
        # サンプルデータは挿入しない（PDFからインポートするため）
        # db.insert_sample_products()
        # db.insert_sample_customer()
        db.display_tables()
    finally:
        db.close()

if __name__ == "__main__":
    main()
