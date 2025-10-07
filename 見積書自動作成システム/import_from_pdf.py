"""
見積書PDFファイルから顧客・商品情報を抽出してデータベースに登録
"""
import pdfplumber
import sqlite3
import glob
import re
from pathlib import Path

class PDFEstimateImporter:
    """見積書PDFファイルからデータをインポート"""

    def __init__(self, db_name="estimate_system.db"):
        self.db_name = db_name
        self.conn = None
        self.cursor = None

    def connect(self):
        """データベースに接続"""
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()

    def _safe_print(self, message):
        """安全にメッセージを出力"""
        try:
            print(message)
        except UnicodeEncodeError:
            safe_message = message.encode('cp932', errors='replace').decode('cp932')
            print(safe_message)

    def extract_text_from_pdf(self, pdf_path):
        """PDFからテキストを抽出"""
        text_lines = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_lines.extend(text.split('\n'))
        except Exception as e:
            self._safe_print(f"[エラー] PDF読み込み失敗: {e}")
            return []

        return text_lines

    def parse_pdf_estimate(self, pdf_path):
        """PDFから見積情報を解析"""
        customer_name = None
        address = None
        products = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        lines = text.split('\n')

                        for i, line in enumerate(lines):
                            # 顧客名を抽出（宛先行から）
                            if '宛先' in line:
                                # 「宛先」の次の行から会社名を探す
                                for j in range(i + 1, min(i + 5, len(lines))):  # 最大4行先まで確認
                                    next_line = lines[j].strip()

                                    # 空行やご担当者様などをスキップ
                                    if not next_line or 'ご担当' in next_line or '発行元' in next_line:
                                        continue

                                    # 会社名のパターンをチェック
                                    company_keywords = ['株式会社', '有限会社', '合同会社', '一般社団法人', '財団法人', '社団法人', '医療法人']
                                    if any(keyword in next_line for keyword in company_keywords):
                                        customer_name = next_line
                                        break

                            # 作業場所から住所を抽出
                            if '作業場所' in line:
                                # 「作業場所:」の後ろの住所を抽出
                                address_match = re.search(r'作業場所[︓:：\s]+(.+)', line)
                                if address_match:
                                    address = address_match.group(1).strip()
                                # 次の行も住所の可能性がある（改行されている場合）
                                elif i + 1 < len(lines):
                                    next_line = lines[i + 1].strip()
                                    if next_line and not any(x in next_line for x in ['作業日', '作業名', '項目']):
                                        address = next_line

                    # テーブルから商品情報を抽出
                    tables = page.extract_tables()
                    for table in tables:
                        if not table:
                            continue

                        # ヘッダー行を確認
                        header = table[0] if table else []
                        if not any('品名' in str(cell) for cell in header if cell):
                            continue

                        # データ行を処理
                        for row in table[1:]:  # ヘッダーをスキップ
                            if len(row) < 4:  # 最低限必要なカラム数
                                continue

                            # カラム: [項目, 品名・仕様, 数量, 単位, 単価, 金額]
                            try:
                                product_name = row[1] if len(row) > 1 else None
                                quantity_str = row[2] if len(row) > 2 else None
                                unit = row[3] if len(row) > 3 else '個'
                                price_str = row[4] if len(row) > 4 else None

                                if not product_name or not price_str:
                                    continue

                                # 商品名のクリーニング
                                product_name = product_name.replace('\n', ' ').strip()

                                # 単価の抽出
                                price_cleaned = re.sub(r'[￥¥,円]', '', str(price_str))
                                try:
                                    base_price = int(float(price_cleaned))
                                except ValueError:
                                    continue

                                # 商品を追加
                                products.append({
                                    'name': product_name,
                                    'unit': unit,
                                    'base_price': base_price
                                })

                            except Exception as e:
                                self._safe_print(f"  行の解析エラー: {e}")
                                continue

        except Exception as e:
            self._safe_print(f"[エラー] PDF解析失敗: {e}")
            return None

        return {
            'customer_name': customer_name,
            'address': address,
            'products': products
        }

    def import_customer(self, customer_name, address):
        """顧客をデータベースに登録"""
        if not customer_name:
            return None

        # 既存チェック
        self.cursor.execute('SELECT customer_id FROM customers WHERE company_name = ?', (customer_name,))
        existing = self.cursor.fetchone()

        if existing:
            self._safe_print(f"  [スキップ] 顧客は既に登録済み: {customer_name}")
            return existing[0]

        # 新規登録
        self.cursor.execute('''
            INSERT INTO customers (company_name, address, phone, email)
            VALUES (?, ?, ?, ?)
        ''', (customer_name, address, '', ''))

        customer_id = self.cursor.lastrowid
        self._safe_print(f"  [登録] 顧客: {customer_name}")
        return customer_id

    def import_product(self, product_name, unit, base_price):
        """商品をデータベースに登録"""
        if not product_name or base_price <= 0:
            return None

        # 既存チェック
        self.cursor.execute('SELECT product_id, base_price FROM products WHERE product_name = ?', (product_name,))
        existing = self.cursor.fetchone()

        if existing:
            existing_id, current_price = existing
            if base_price > current_price:
                self.cursor.execute('''
                    UPDATE products SET base_price = ?, unit = ? WHERE product_id = ?
                ''', (base_price, unit, existing_id))
                self._safe_print(f"  [更新] 商品: {product_name} ({current_price:,}円 -> {base_price:,}円)")
            else:
                self._safe_print(f"  [スキップ] 商品は既に登録済み: {product_name}")
            return existing_id

        # カテゴリを推測
        category = self._guess_category(product_name)

        # 新規登録
        self.cursor.execute('''
            INSERT INTO products (product_name, product_category, base_price, unit)
            VALUES (?, ?, ?, ?)
        ''', (product_name, category, base_price, unit))

        product_id = self.cursor.lastrowid
        self._safe_print(f"  [登録] 商品: {product_name} [{category}] - {base_price:,}円 / {unit}")
        return product_id

    def _guess_category(self, product_name):
        """商品名からカテゴリを推測"""
        categories = {
            'IT・開発': ['開発', 'システム', 'プログラム', 'API', 'サーバー', 'クラウド', 'SaaS', 'アプリ', 'Web', 'データベース', 'db', 'テスト', 'レビュー', '設計'],
            'ネットワーク': ['ルーター', 'スイッチ', 'Wi-Fi', 'LAN', 'ネットワーク', 'ケーブル', 'HDMI'],
            'ハードウェア': ['パソコン', 'PC', 'サーバ', 'モニター', 'プリンター', '複合機', 'タブレット', 'ノートPC', 'Laptop'],
            'サービス': ['保守', 'メンテナンス', '作業', '支援', 'サポート', 'プラン', 'ライセンス', 'オンサイト', '運用'],
            'ソフトウェア': ['Office', 'Microsoft', 'Google', 'Workspace', 'ソフトウェア', 'アプリケーション'],
            '家電': ['冷蔵庫', '洗濯機', 'エアコン', '電子レンジ', 'テレビ'],
            '家具': ['テーブル', '椅子', 'デスク', 'チェア', '棚'],
        }

        product_lower = product_name.lower()

        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword.lower() in product_lower:
                    return category

        return 'その他'

    def import_all_pdfs(self, pattern="pdf_estimates/*.pdf"):
        """すべてのPDFファイルをインポート"""
        files = glob.glob(pattern)

        if not files:
            self._safe_print(f"PDFファイルが見つかりません: {pattern}")
            return

        self._safe_print(f"\n=== PDFファイルから顧客・商品をインポート ===")
        self._safe_print(f"対象ファイル: {len(files)}件\n")

        customers_imported = 0
        products_imported = 0

        for filepath in files:
            self._safe_print(f"\n処理中: {filepath}")

            data = self.parse_pdf_estimate(filepath)

            if not data:
                self._safe_print("  [警告] PDF解析に失敗しました")
                continue

            # 顧客を登録
            if data['customer_name']:
                self.import_customer(data['customer_name'], data['address'])
                customers_imported += 1

            # 商品を登録
            for product in data['products']:
                self.import_product(
                    product['name'],
                    product['unit'],
                    product['base_price']
                )
                products_imported += 1

        self.conn.commit()

        self._safe_print(f"\n\n=== インポート完了 ===")
        self._safe_print(f"処理ファイル数: {len(files)}件")
        self._safe_print(f"顧客データ処理: {customers_imported}件")
        self._safe_print(f"商品データ処理: {products_imported}件")

        # データベース状態を表示
        self.cursor.execute('SELECT COUNT(*) FROM customers')
        total_customers = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM products')
        total_products = self.cursor.fetchone()[0]

        self._safe_print(f"\n[データベース状態]")
        self._safe_print(f"顧客総数: {total_customers}件")
        self._safe_print(f"商品総数: {total_products}件")

    def close(self):
        """データベース接続を閉じる"""
        if self.conn:
            self.conn.close()

def main():
    """メイン処理"""
    importer = PDFEstimateImporter()

    try:
        importer.connect()

        # pdf_estimatesフォルダ内のPDFファイルをインポート
        importer.import_all_pdfs("pdf_estimates/*.pdf")

    finally:
        importer.close()

if __name__ == "__main__":
    main()
