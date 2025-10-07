"""
全顧客の座標・距離を自動計算・更新
住所から座標を取得し、拠点からの距離を計算
"""
import sqlite3
from geocoding_distance import GeocodingService
import time

def update_all_customer_distances():
    """全顧客の座標・距離を自動更新"""

    print("\n" + "="*60)
    print("顧客座標・距離の自動計算")
    print("="*60 + "\n")

    geocoding_service = GeocodingService()
    conn = sqlite3.connect("estimate_system.db")
    cursor = conn.cursor()

    # 座標・距離が未設定の顧客を取得
    cursor.execute('''
        SELECT customer_id, company_name, address
        FROM customers
        WHERE latitude IS NULL OR longitude IS NULL OR distance_km IS NULL
    ''')

    customers_to_update = cursor.fetchall()

    if not customers_to_update:
        print("[INFO] すべての顧客に座標・距離が設定済みです")
        conn.close()
        return

    print(f"[検出] {len(customers_to_update)}件の顧客の座標・距離を計算します\n")

    success_count = 0
    error_count = 0

    for customer_id, company_name, address in customers_to_update:
        print(f"処理中: {company_name}")
        print(f"  住所: {address}")

        try:
            # 住所から座標を取得
            coordinates = geocoding_service.geocode_address(address)

            if coordinates:
                latitude, longitude = coordinates
                distance_km = geocoding_service.get_distance_from_base(latitude, longitude)

                # データベースを更新
                cursor.execute('''
                    UPDATE customers
                    SET latitude = ?, longitude = ?, distance_km = ?
                    WHERE customer_id = ?
                ''', (latitude, longitude, distance_km, customer_id))

                print(f"  ✅ 座標: ({latitude:.6f}, {longitude:.6f})")
                print(f"  ✅ 距離: {distance_km:.1f} km\n")
                success_count += 1

                # APIレート制限対策（1秒待機）
                time.sleep(1)

            else:
                print(f"  ❌ 座標の取得に失敗しました\n")
                error_count += 1

        except Exception as e:
            print(f"  ❌ エラー: {e}\n")
            error_count += 1

    conn.commit()
    conn.close()

    # 結果サマリー
    print("="*60)
    print("処理完了")
    print("="*60)
    print(f"\n成功: {success_count}件")
    print(f"失敗: {error_count}件\n")

    # 最終確認
    conn = sqlite3.connect("estimate_system.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN distance_km IS NOT NULL THEN 1 END) as with_distance
        FROM customers
    ''')

    total, with_distance = cursor.fetchone()
    print(f"総顧客数: {total}件")
    print(f"距離設定済み: {with_distance}件\n")

    # 顧客一覧を距離順に表示
    cursor.execute('''
        SELECT company_name, address, distance_km
        FROM customers
        ORDER BY distance_km
    ''')

    print("="*60)
    print("顧客一覧（距離順）")
    print("="*60 + "\n")

    for company_name, address, distance_km in cursor.fetchall():
        if distance_km is not None:
            print(f"{company_name}: {distance_km:.1f} km")
            print(f"  → {address}")
        else:
            print(f"{company_name}: 距離未設定")
            print(f"  → {address}")

    conn.close()

    print("\n" + "="*60)
    print("✅ 顧客座標・距離の更新が完了しました！")
    print("="*60 + "\n")

if __name__ == "__main__":
    update_all_customer_distances()
