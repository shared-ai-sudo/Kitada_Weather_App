"""
価格予測モデル - 回帰分析による見積金額の予測
既存の見積書データを使用して機械学習モデルを訓練
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import pickle
import os

class PricePredictionModel:
    """価格予測モデルクラス"""

    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.label_encoders = {}
        self.feature_columns = []
        self.model_path = "price_prediction_model.pkl"

    def prepare_data(self, df: pd.DataFrame) -> tuple:
        """
        データの前処理

        Args:
            df: 見積書データのDataFrame

        Returns:
            (X, y) 特徴量とターゲット
        """
        # データのコピーを作成
        data = df.copy()

        # 金額から数値のみを抽出（カンマや通貨記号を除去）
        if '金額' in data.columns:
            # クォーテーションマークと通貨記号、カンマを除去
            data['金額_数値'] = data['金額'].astype(str).str.replace('"', '').str.replace(',', '').str.replace('円', '').str.replace('¥', '').str.replace('￥', '').str.strip()
            data['金額_数値'] = pd.to_numeric(data['金額_数値'], errors='coerce')

        # 数量の数値変換
        if '数量' in data.columns:
            data['数量_数値'] = pd.to_numeric(data['数量'].astype(str).str.replace(',', ''), errors='coerce')

        # カテゴリカル変数のエンコーディング
        categorical_columns = ['品名・仕様', '見積会社']
        for col in categorical_columns:
            if col in data.columns:
                le = LabelEncoder()
                data[f'{col}_encoded'] = le.fit_transform(data[col].astype(str))
                self.label_encoders[col] = le

        # 特徴量の選択
        feature_cols = []
        if '数量_数値' in data.columns:
            feature_cols.append('数量_数値')
        if '品名・仕様_encoded' in data.columns:
            feature_cols.append('品名・仕様_encoded')
        if '見積会社_encoded' in data.columns:
            feature_cols.append('見積会社_encoded')

        self.feature_columns = feature_cols

        # 欠損値を除去
        data = data.dropna(subset=feature_cols + ['金額_数値'])

        X = data[feature_cols]
        y = data['金額_数値']

        return X, y

    def train(self, csv_file: str = '見積書データ.csv'):
        """
        モデルの訓練

        Args:
            csv_file: 訓練データのCSVファイルパス
        """
        if not os.path.exists(csv_file):
            print(f"[エラー] データファイルが見つかりません: {csv_file}")
            return

        # データ読み込み
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"[OK] データ読み込み完了: {len(df)}件")

        # データ準備
        X, y = self.prepare_data(df)
        print(f"[OK] 特徴量: {self.feature_columns}")
        print(f"[OK] 訓練データ数: {len(X)}件")

        # 訓練データとテストデータに分割
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # モデル訓練
        print("\n[処理中] モデルを訓練しています...")
        self.model.fit(X_train, y_train)

        # 予測と評価
        y_pred = self.model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        print("\n=== モデル評価結果 ===")
        print(f"平均絶対誤差 (MAE): {mae:,.0f}円")
        print(f"二乗平均平方根誤差 (RMSE): {rmse:,.0f}円")
        print(f"決定係数 (R2): {r2:.3f}")

        # 特徴量の重要度
        feature_importance = pd.DataFrame({
            '特徴量': self.feature_columns,
            '重要度': self.model.feature_importances_
        }).sort_values('重要度', ascending=False)

        print("\n=== 特徴量の重要度 ===")
        print(feature_importance.to_string(index=False))

        # モデルを保存
        self.save_model()

    def predict(self, product_name: str, quantity: int, company: str = None, distance_km: float = None) -> float:
        """
        価格を予測

        Args:
            product_name: 商品名
            quantity: 数量
            company: 見積会社名（オプション）
            distance_km: 距離（km）（オプション、将来的に使用）

        Returns:
            予測価格
        """
        # 特徴量を準備
        features = {}

        # 数量
        features['数量_数値'] = quantity

        # 商品名のエンコード
        if '品名・仕様' in self.label_encoders:
            le = self.label_encoders['品名・仕様']
            try:
                features['品名・仕様_encoded'] = le.transform([product_name])[0]
            except ValueError:
                # 未知の商品名の場合はデフォルト値
                features['品名・仕様_encoded'] = 0

        # 会社名のエンコード
        if company and '見積会社' in self.label_encoders:
            le = self.label_encoders['見積会社']
            try:
                features['見積会社_encoded'] = le.transform([company])[0]
            except ValueError:
                features['見積会社_encoded'] = 0
        else:
            features['見積会社_encoded'] = 0

        # DataFrameに変換
        X = pd.DataFrame([features], columns=self.feature_columns)

        # 予測
        predicted_price = self.model.predict(X)[0]

        return predicted_price

    def save_model(self):
        """モデルを保存"""
        model_data = {
            'model': self.model,
            'label_encoders': self.label_encoders,
            'feature_columns': self.feature_columns
        }

        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"\n[OK] モデルを保存しました: {self.model_path}")

    def load_model(self):
        """モデルを読み込み"""
        if not os.path.exists(self.model_path):
            print(f"[エラー] モデルファイルが見つかりません: {self.model_path}")
            return False

        with open(self.model_path, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.label_encoders = model_data['label_encoders']
        self.feature_columns = model_data['feature_columns']

        print(f"[OK] モデルを読み込みました: {self.model_path}")
        return True

def main():
    """メイン処理"""
    predictor = PricePredictionModel()

    # モデルの訓練
    print("=== 価格予測モデルの訓練 ===\n")
    predictor.train()

    # テスト予測
    print("\n\n=== テスト予測 ===")
    if predictor.label_encoders:
        # 最初の商品名を使ってテスト
        first_product = list(predictor.label_encoders['品名・仕様'].classes_)[0]
        test_quantity = 5

        predicted_price = predictor.predict(first_product, test_quantity)
        print(f"商品名: {first_product}")
        print(f"数量: {test_quantity}")
        print(f"予測価格: {predicted_price:,.0f}円")

if __name__ == "__main__":
    main()
