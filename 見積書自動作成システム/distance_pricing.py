"""
距離別価格調整機能
商品ごとに距離に応じて見積価格を自動調整
"""
import sqlite3
from typing import Dict, Optional

DB_NAME = "estimate_system.db"

class DistancePricingService:
    """距離別価格調整サービス"""

    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name

    def add_distance_coefficient_column(self):
        """商品テーブルに距離係数カラムを追加"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            # 既にカラムが存在するかチェック
            cursor.execute("PRAGMA table_info(products)")
            columns = [col[1] for col in cursor.fetchall()]

            if "distance_coefficient" not in columns:
                cursor.execute('''
                    ALTER TABLE products ADD COLUMN distance_coefficient REAL DEFAULT 0.0
                ''')
                conn.commit()
                print("[OK] 距離係数カラムを追加しました")
            else:
                print("[INFO] 距離係数カラムは既に存在します")

            # 調整タイプカラムも追加
            cursor.execute("PRAGMA table_info(products)")
            columns = [col[1] for col in cursor.fetchall()]

            if "price_adjustment_type" not in columns:
                cursor.execute('''
                    ALTER TABLE products ADD COLUMN price_adjustment_type TEXT DEFAULT 'fixed'
                ''')
                conn.commit()
                print("[OK] 価格調整タイプカラムを追加しました")
            else:
                print("[INFO] 価格調整タイプカラムは既に存在します")

        except Exception as e:
            print(f"[エラー] カラム追加失敗: {e}")
        finally:
            conn.close()

    def set_product_distance_coefficient(self, product_id: int, coefficient: float,
                                        adjustment_type: str = 'distance_proportional'):
        """
        商品の距離係数を設定

        Args:
            product_id: 商品ID
            coefficient: 距離係数（例: 0.02 = 1kmあたり基本価格の2%加算）
            adjustment_type: 調整タイプ
                - 'fixed': 固定価格（距離による変動なし）
                - 'distance_proportional': 距離比例（距離が遠いほど高くなる）
                - 'distance_discount': 距離割引（距離が遠いほど安くなる）
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE products
                SET distance_coefficient = ?, price_adjustment_type = ?
                WHERE product_id = ?
            ''', (coefficient, adjustment_type, product_id))
            conn.commit()

            if cursor.rowcount > 0:
                print(f"[OK] 商品ID {product_id} の距離係数を設定しました: {coefficient} ({adjustment_type})")
            else:
                print(f"[警告] 商品ID {product_id} が見つかりません")

        except Exception as e:
            print(f"[エラー] 設定失敗: {e}")
        finally:
            conn.close()

    def calculate_adjusted_price(self, product_id: int, base_price: int,
                                 distance_km: float, quantity: int = 1) -> Dict:
        """
        距離調整後の価格を計算

        Args:
            product_id: 商品ID
            base_price: 基本単価
            distance_km: 距離 (km)
            quantity: 数量

        Returns:
            調整後の価格情報
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT distance_coefficient, price_adjustment_type
            FROM products
            WHERE product_id = ?
        ''', (product_id,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            # デフォルト（調整なし）
            total = base_price * quantity
            return {
                'base_price': base_price,
                'adjusted_price': base_price,
                'adjustment_amount': 0,
                'total_amount': total,
                'adjustment_type': 'fixed',
                'distance_km': distance_km
            }

        coefficient, adjustment_type = result

        # 調整額を計算
        adjustment_amount = 0

        if adjustment_type == 'fixed':
            # 固定価格（調整なし）
            adjusted_price = base_price

        elif adjustment_type == 'distance_proportional':
            # 距離比例（遠いほど高い）
            adjustment_amount = int(base_price * coefficient * distance_km)
            adjusted_price = base_price + adjustment_amount

        elif adjustment_type == 'distance_discount':
            # 距離割引（遠いほど安い）
            adjustment_amount = -int(base_price * coefficient * distance_km)
            adjusted_price = base_price + adjustment_amount

        else:
            # 不明な調整タイプ
            adjusted_price = base_price

        # 価格は0以下にならない
        adjusted_price = max(adjusted_price, 0)

        total_amount = adjusted_price * quantity

        return {
            'base_price': base_price,
            'adjusted_price': adjusted_price,
            'adjustment_amount': adjustment_amount,
            'total_amount': total_amount,
            'adjustment_type': adjustment_type,
            'distance_km': distance_km,
            'coefficient': coefficient
        }

    def get_product_pricing_info(self, product_id: int) -> Optional[Dict]:
        """商品の価格設定情報を取得"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT product_name, base_price, unit, distance_coefficient, price_adjustment_type
            FROM products
            WHERE product_id = ?
        ''', (product_id,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'product_name': result[0],
                'base_price': result[1],
                'unit': result[2],
                'distance_coefficient': result[3] or 0.0,
                'price_adjustment_type': result[4] or 'fixed'
            }

        return None

    def set_category_distance_coefficient(self, category: str, coefficient: float,
                                          adjustment_type: str = 'distance_proportional'):
        """
        カテゴリ全体に距離係数を一括設定

        Args:
            category: 商品カテゴリ
            coefficient: 距離係数
            adjustment_type: 調整タイプ
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE products
                SET distance_coefficient = ?, price_adjustment_type = ?
                WHERE product_category = ?
            ''', (coefficient, adjustment_type, category))
            conn.commit()

            print(f"[OK] カテゴリ '{category}' の{cursor.rowcount}件の商品に距離係数を設定しました")

        except Exception as e:
            print(f"[エラー] 設定失敗: {e}")
        finally:
            conn.close()

def auto_setup_all_products():
    """全商品に距離係数を自動設定"""
    service = DistancePricingService()

    print("\n" + "="*60)
    print("商品カテゴリ別 距離係数自動設定")
    print("="*60 + "\n")

    # 1. カラム追加
    service.add_distance_coefficient_column()

    # 2. 商品カテゴリ別に距離係数を設定
    print("\n=== カテゴリ別距離係数の設定 ===\n")

    # カテゴリごとの設定（係数が大きいほど距離の影響が大きい）
    category_settings = {
        # 重量物・配送コストが高いもの
        '家電': (0.03, 'distance_proportional', '重い家電製品は配送コストが高い'),
        '家具': (0.025, 'distance_proportional', '大型家具は配送・設置コストが高い'),
        'ハードウェア': (0.02, 'distance_proportional', 'PC・モニター等の配送コスト'),

        # 訪問・作業が必要なサービス
        'サービス': (0.015, 'distance_proportional', '訪問・作業サービスは距離に応じてコスト増'),

        # 中程度の影響
        'ネットワーク': (0.01, 'distance_proportional', 'ネットワーク機器の設置・設定作業'),
        'その他': (0.01, 'distance_proportional', 'その他商品'),

        # 距離の影響が少ないもの
        'IT・開発': (0.005, 'distance_proportional', 'リモート対応可能だが一部訪問あり'),
        'ソフトウェア': (0.0, 'fixed', 'ライセンス・オンライン納品のため距離無関係'),
    }

    for category, (coefficient, adj_type, description) in category_settings.items():
        print(f"カテゴリ: {category}")
        print(f"  係数: {coefficient} ({adj_type})")
        print(f"  理由: {description}")
        service.set_category_distance_coefficient(category, coefficient, adj_type)
        print()

    # 3. 設定結果を確認
    print("\n" + "="*60)
    print("設定完了サマリー")
    print("="*60 + "\n")

    conn = sqlite3.connect(service.db_name)
    cursor = conn.cursor()

    # カテゴリ別統計
    cursor.execute('''
        SELECT
            product_category,
            COUNT(*) as count,
            AVG(distance_coefficient) as avg_coefficient,
            price_adjustment_type
        FROM products
        GROUP BY product_category, price_adjustment_type
        ORDER BY product_category
    ''')

    print("カテゴリ別設定状況:")
    for row in cursor.fetchall():
        category, count, avg_coef, adj_type = row
        print(f"  {category}: {count}件 (係数: {avg_coef:.3f}, {adj_type})")

    # 全体統計
    cursor.execute('SELECT COUNT(*) FROM products WHERE distance_coefficient > 0')
    distance_enabled = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM products')
    total_products = cursor.fetchone()[0]

    print(f"\n距離調整有効: {distance_enabled}/{total_products}件")

    conn.close()

    print("\n" + "="*60)
    print("✅ 全商品の距離係数設定が完了しました！")
    print("="*60 + "\n")

def show_price_examples():
    """価格計算例を表示"""
    service = DistancePricingService()

    print("\n" + "="*60)
    print("距離別価格シミュレーション")
    print("="*60 + "\n")

    # サンプル商品で計算
    examples = [
        (1, "ハードウェア商品例", 50000),
        (10, "サービス商品例", 100000),
        (20, "家電商品例", 200000),
    ]

    distances = [0, 5, 10, 20, 50]

    for product_id, product_name, base_price in examples:
        print(f"\n【{product_name}: ¥{base_price:,}】")
        print("-" * 60)
        print(f"{'距離':>6} | {'調整後価格':>12} | {'調整額':>12} | {'調整率':>8}")
        print("-" * 60)

        for distance in distances:
            result = service.calculate_adjusted_price(product_id, base_price, distance, 1)
            if result:
                adjusted = result['adjusted_price']
                adjustment = result['adjustment_amount']
                rate = (adjustment / base_price * 100) if base_price > 0 else 0
                print(f"{distance:4}km | ¥{adjusted:>10,} | ¥{adjustment:>+10,} | {rate:>+6.1f}%")

def main():
    """メイン処理"""
    auto_setup_all_products()
    show_price_examples()

if __name__ == "__main__":
    main()
