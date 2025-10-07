"""
住所から座標取得・距離計算機能
- 国税庁 法人番号システムAPI: 企業名から住所を取得
- 国土地理院API: 住所から座標を取得
- 距離計算: ダイキョウクリーン様の拠点との距離を計算
"""
import requests
import json
import math
from typing import Optional, Tuple

class GeocodingService:
    """ジオコーディングと距離計算を行うサービスクラス"""

    # ダイキョウクリーン様の拠点座標（仮の値、実際の座標に置き換えてください）
    BASE_LATITUDE = 35.6812
    BASE_LONGITUDE = 139.7671

    def __init__(self):
        self.houjin_api_url = "https://api.houjin-bangou.nta.go.jp/4/name"
        self.geocoding_api_url = "https://msearch.gsi.go.jp/address-search/AddressSearch"

    def search_company_address(self, company_name: str) -> Optional[dict]:
        """
        国税庁APIで企業名から住所を検索

        Args:
            company_name: 企業名

        Returns:
            企業情報の辞書 (法人番号、所在地など)
        """
        try:
            params = {
                'id': '1',  # アプリケーションID（要取得）
                'name': company_name,
                'mode': '2',  # 前方一致
            }

            response = requests.get(self.houjin_api_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if 'corporations' in data and len(data['corporations']) > 0:
                    corp = data['corporations'][0]
                    return {
                        'corporate_number': corp.get('corporateNumber'),
                        'name': corp.get('name'),
                        'address': corp.get('prefectureName', '') + corp.get('cityName', '') + corp.get('streetNumber', ''),
                        'postal_code': corp.get('postCode'),
                    }
            else:
                print(f"[警告] 国税庁API呼び出しエラー: {response.status_code}")
                return None

        except Exception as e:
            print(f"[エラー] 企業情報取得に失敗: {e}")
            return None

    def geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        """
        国土地理院APIで住所から座標を取得

        Args:
            address: 住所文字列

        Returns:
            (緯度, 経度) のタプル
        """
        try:
            params = {
                'q': address
            }

            response = requests.get(self.geocoding_api_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if len(data) > 0:
                    geometry = data[0].get('geometry', {})
                    coordinates = geometry.get('coordinates', [])
                    if len(coordinates) >= 2:
                        # 地理院APIは [経度, 緯度] の順で返す
                        longitude = coordinates[0]
                        latitude = coordinates[1]
                        return (latitude, longitude)
            else:
                print(f"[警告] ジオコーディングAPI呼び出しエラー: {response.status_code}")
                return None

        except Exception as e:
            print(f"[エラー] 座標取得に失敗: {e}")
            return None

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        2点間の直線距離を計算（ヒュベニの公式）

        Args:
            lat1, lon1: 地点1の緯度・経度
            lat2, lon2: 地点2の緯度・経度

        Returns:
            距離（km）
        """
        # 緯度経度をラジアンに変換
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # 平均緯度
        lat_avg = (lat1_rad + lat2_rad) / 2

        # 地球の楕円体パラメータ（GRS80）
        a = 6378137.0  # 赤道半径（m）
        b = 6356752.314140  # 極半径（m）
        e2 = (a**2 - b**2) / a**2  # 離心率の2乗

        # 子午線・卯酉線曲率半径
        M = a * (1 - e2) / ((1 - e2 * math.sin(lat_avg)**2)**(3/2))
        N = a / math.sqrt(1 - e2 * math.sin(lat_avg)**2)

        # 距離計算
        delta_lat = lat1_rad - lat2_rad
        delta_lon = lon1_rad - lon2_rad

        distance = math.sqrt((delta_lat * M)**2 + (delta_lon * N * math.cos(lat_avg))**2)

        return distance / 1000  # kmに変換

    def get_distance_from_base(self, latitude: float, longitude: float) -> float:
        """
        拠点からの距離を計算

        Args:
            latitude: 対象地点の緯度
            longitude: 対象地点の経度

        Returns:
            拠点からの距離（km）
        """
        return self.calculate_distance(
            self.BASE_LATITUDE, self.BASE_LONGITUDE,
            latitude, longitude
        )

def main():
    """テスト用のメイン関数"""
    service = GeocodingService()

    print("=== 住所から座標取得・距離計算のテスト ===\n")

    # テスト1: 住所から座標を取得
    test_address = "東京都千代田区千代田1-1"
    print(f"[テスト1] 住所: {test_address}")
    coordinates = service.geocode_address(test_address)

    if coordinates:
        lat, lon = coordinates
        print(f"  緯度: {lat}, 経度: {lon}")

        # 距離を計算
        distance = service.get_distance_from_base(lat, lon)
        print(f"  拠点からの距離: {distance:.2f} km\n")
    else:
        print("  座標の取得に失敗しました\n")

    # テスト2: 企業名から住所を検索（国税庁APIはアプリケーションIDが必要）
    # test_company = "株式会社サンプル"
    # print(f"[テスト2] 企業名: {test_company}")
    # company_info = service.search_company_address(test_company)
    # if company_info:
    #     print(f"  住所: {company_info['address']}")

    print("\n[注意] 国税庁APIを使用する場合は、アプリケーションIDの取得が必要です")
    print("詳細: https://www.houjin-bangou.nta.go.jp/webapi/")

if __name__ == "__main__":
    main()
