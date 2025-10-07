"""
AI見積書生成システム - Flaskアプリケーション
Webインターフェースを提供し、各機能を統合
"""
from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import json
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from database_setup import EstimateDatabase
from geocoding_distance import GeocodingService
from price_prediction import PricePredictionModel
from estimate_generator import EstimateGenerator
from import_from_pdf import PDFEstimateImporter
from distance_pricing import DistancePricingService

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# アップロードフォルダを作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# サービスの初期化
geocoding_service = GeocodingService()
price_predictor = PricePredictionModel()
estimate_generator = EstimateGenerator()
distance_pricing_service = DistancePricingService()

# 価格予測モデルをロード
try:
    price_predictor.load_model()
except:
    print("[警告] 価格予測モデルが読み込めません。モデルを訓練してください。")

DB_NAME = "estimate_system.db"

def get_db_connection():
    """データベース接続を取得"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """トップページ"""
    return render_template('index.html')

@app.route('/test')
def test():
    """API接続テストページ"""
    return render_template('test.html')

@app.route('/api/customers', methods=['GET'])
def get_customers():
    """顧客一覧を取得"""
    conn = get_db_connection()
    customers = conn.execute('SELECT * FROM customers').fetchall()
    conn.close()

    return jsonify([dict(row) for row in customers])

@app.route('/api/products', methods=['GET'])
def get_products():
    """商品一覧を取得"""
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()

    return jsonify([dict(row) for row in products])

@app.route('/api/customer', methods=['POST'])
def add_customer():
    """新規顧客を登録"""
    data = request.json

    company_name = data.get('company_name')
    address = data.get('address')
    phone = data.get('phone')
    email = data.get('email')

    # 住所から座標を取得
    coordinates = geocoding_service.geocode_address(address)

    latitude = None
    longitude = None
    distance_km = None

    if coordinates:
        latitude, longitude = coordinates
        distance_km = geocoding_service.get_distance_from_base(latitude, longitude)

    # データベースに登録
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO customers (company_name, address, latitude, longitude, distance_km, phone, email)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (company_name, address, latitude, longitude, distance_km, phone, email))

    customer_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'customer_id': customer_id,
        'distance_km': distance_km
    })

@app.route('/api/predict_price', methods=['POST'])
def predict_price():
    """価格を予測"""
    data = request.json

    product_name = data.get('product_name')
    quantity = int(data.get('quantity', 1))

    try:
        predicted_price = price_predictor.predict(product_name, quantity)
        return jsonify({
            'success': True,
            'predicted_price': int(predicted_price)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/generate_estimate', methods=['POST'])
def generate_estimate():
    """見積書を生成"""
    data = request.json

    customer_id = data.get('customer_id')
    items = data.get('items')  # [{'name': '', 'quantity': '', 'unit': '', 'unit_price': '', 'amount': ''}, ...]
    notes = data.get('notes', '')

    # 顧客情報を取得
    conn = get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE customer_id = ?', (customer_id,)).fetchone()

    if not customer:
        return jsonify({'success': False, 'error': '顧客が見つかりません'})

    # 見積番号を生成
    estimate_number = f"EST-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 見積書をデータベースに保存
    total_amount = sum(item['amount'] for item in items)

    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO estimates (customer_id, estimate_date, total_amount, status, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (customer_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), total_amount, 'draft', notes))

    estimate_id = cursor.lastrowid

    # 見積明細を保存
    for item in items:
        # 商品IDを取得（商品名から検索）
        product = conn.execute('SELECT product_id FROM products WHERE product_name = ?', (item['name'],)).fetchone()
        product_id = product['product_id'] if product else None

        cursor.execute('''
            INSERT INTO estimate_details (estimate_id, product_id, quantity, unit_price, amount, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (estimate_id, product_id, item['quantity'], item['unit_price'], item['amount'], item.get('notes', '')))

    conn.commit()
    conn.close()

    # PDFを生成
    pdf_path = estimate_generator.generate_estimate(
        customer_name=customer['company_name'],
        customer_address=customer['address'],
        items=items,
        estimate_number=estimate_number,
        notes=notes
    )

    return jsonify({
        'success': True,
        'estimate_id': estimate_id,
        'estimate_number': estimate_number,
        'pdf_path': pdf_path
    })

@app.route('/api/estimates', methods=['GET'])
def get_estimates():
    """見積一覧を取得"""
    conn = get_db_connection()
    estimates = conn.execute('''
        SELECT e.*, c.company_name
        FROM estimates e
        JOIN customers c ON e.customer_id = c.customer_id
        ORDER BY e.created_at DESC
    ''').fetchall()
    conn.close()

    return jsonify([dict(row) for row in estimates])

@app.route('/api/upload_pdf', methods=['POST'])
def upload_pdf():
    """PDFファイルをアップロードして顧客・商品を登録"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'ファイルが選択されていません'})

    file = request.files['file']

    if file.filename == '':
        return jsonify({'success': False, 'error': 'ファイルが選択されていません'})

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'PDFファイルを選択してください'})

    try:
        # ファイルを保存
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # PDFから情報を抽出
        importer = PDFEstimateImporter(DB_NAME)
        importer.connect()

        data = importer.parse_pdf_estimate(filepath)

        if not data:
            importer.close()
            return jsonify({'success': False, 'error': 'PDFの解析に失敗しました'})

        customers_added = 0
        products_added = 0

        # 顧客を登録
        if data['customer_name']:
            customer_id = importer.import_customer(data['customer_name'], data['address'])
            if customer_id:
                customers_added = 1

        # 商品を登録
        for product in data['products']:
            product_id = importer.import_product(
                product['name'],
                product['unit'],
                product['base_price']
            )
            if product_id:
                products_added += 1

        importer.conn.commit()
        importer.close()

        # アップロードファイルを削除
        os.remove(filepath)

        return jsonify({
            'success': True,
            'customers_added': customers_added,
            'products_added': products_added,
            'customer_name': data.get('customer_name'),
            'total_products': len(data['products'])
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calculate_distance_price', methods=['POST'])
def calculate_distance_price():
    """距離による価格調整を計算"""
    data = request.json

    product_id = data.get('product_id')
    base_price = data.get('base_price')
    distance_km = data.get('distance_km', 0)
    quantity = data.get('quantity', 1)

    try:
        result = distance_pricing_service.calculate_adjusted_price(
            product_id=product_id,
            base_price=base_price,
            distance_km=distance_km,
            quantity=quantity
        )

        return jsonify({
            'success': True,
            'result': result
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/set_product_distance_coefficient', methods=['POST'])
def set_product_distance_coefficient():
    """商品の距離係数を設定"""
    data = request.json

    product_id = data.get('product_id')
    coefficient = data.get('coefficient', 0.0)
    adjustment_type = data.get('adjustment_type', 'distance_proportional')

    try:
        distance_pricing_service.set_product_distance_coefficient(
            product_id=product_id,
            coefficient=coefficient,
            adjustment_type=adjustment_type
        )

        return jsonify({
            'success': True,
            'message': f'商品ID {product_id} の距離係数を {coefficient} に設定しました'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/set_category_distance_coefficient', methods=['POST'])
def set_category_distance_coefficient():
    """カテゴリの距離係数を一括設定"""
    data = request.json

    category = data.get('category')
    coefficient = data.get('coefficient', 0.0)
    adjustment_type = data.get('adjustment_type', 'distance_proportional')

    try:
        distance_pricing_service.set_category_distance_coefficient(
            category=category,
            coefficient=coefficient,
            adjustment_type=adjustment_type
        )

        return jsonify({
            'success': True,
            'message': f'カテゴリ "{category}" の距離係数を {coefficient} に設定しました'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/product_pricing_info/<int:product_id>', methods=['GET'])
def get_product_pricing_info(product_id):
    """商品の価格設定情報を取得"""
    try:
        info = distance_pricing_service.get_product_pricing_info(product_id)

        if info:
            return jsonify({
                'success': True,
                'info': info
            })
        else:
            return jsonify({
                'success': False,
                'error': '商品が見つかりません'
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def check_and_setup_data():
    """起動時にデータをチェックし、不足していれば自動セットアップ"""
    import sqlite3
    import glob
    import os

    print("\n" + "="*60)
    print("システム起動前チェック")
    print("="*60 + "\n")

    # データベースの存在確認
    if not os.path.exists(DB_NAME):
        print("[!] データベースが見つかりません")
        print("[*] データベースを初期化します...\n")
        from database_setup import EstimateDatabase
        db = EstimateDatabase(DB_NAME)
        db.connect()
        db.create_tables()
        db.close()
        print("[OK] データベース初期化完了\n")

    # データ数をチェック
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]

        conn.close()

        print(f"[DATA] 現在のデータ: 顧客 {customer_count}件, 商品 {product_count}件\n")

        # データが不足している場合
        if customer_count == 0 or product_count == 0:
            print("[!] データが不足しています")

            # PDFファイルをチェック
            pdf_files = glob.glob("pdf_estimates/*.pdf")

            if pdf_files:
                print(f"[PDF] {len(pdf_files)}件のPDFファイルを発見")
                print("[*] PDFからデータをインポートします...\n")

                from import_from_pdf import PDFEstimateImporter
                importer = PDFEstimateImporter(DB_NAME)
                importer.connect()

                for pdf_file in pdf_files:
                    try:
                        data = importer.parse_pdf_estimate(pdf_file)
                        if data and data['customer_name']:
                            importer.import_customer(data['customer_name'], data['address'])
                        if data and data['products']:
                            for product in data['products']:
                                importer.import_product(product['name'], product['unit'], product['base_price'])
                    except Exception as e:
                        print(f"  [!] {os.path.basename(pdf_file)}: {e}")

                importer.conn.commit()
                importer.close()

                # 最新のデータ数を確認
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM customers")
                customer_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM products")
                product_count = cursor.fetchone()[0]
                conn.close()

                print(f"\n[OK] インポート完了: 顧客 {customer_count}件, 商品 {product_count}件\n")

                # 顧客の座標・距離を計算
                if customer_count > 0:
                    print("[*] 顧客の座標・距離を計算中...\n")
                    try:
                        from update_customer_distances import update_all_customer_distances
                        # 関数を直接呼び出さず、コマンドライン実行を推奨
                        print("[TIP] 座標計算を実行してください: python update_customer_distances.py\n")
                    except:
                        pass

                # 商品の距離係数を設定
                if product_count > 0:
                    print("[*] 商品の距離係数を設定中...\n")
                    try:
                        distance_pricing_service.add_distance_coefficient_column()
                        print("[OK] 距離係数設定完了\n")
                    except Exception as e:
                        print(f"[!] 距離係数設定エラー: {e}\n")

            else:
                print("[!] pdf_estimates/ にPDFファイルがありません")
                print("\n以下のいずれかを実行してください:")
                print("  1. pdf_estimates/ にPDFファイルを配置")
                print("  2. python add_sample_data.py でサンプルデータを追加")
                print("  3. Webインターフェースから手動で登録\n")
        else:
            print("[OK] データは正常です\n")

    except Exception as e:
        print(f"[!] エラー: {e}\n")
        print("データベースを初期化してください: python setup_system.py\n")

if __name__ == '__main__':
    # 起動前チェック
    check_and_setup_data()

    print("="*60)
    print("[START] AI見積書生成システム")
    print("="*60)
    print("\nサーバーを起動しています...")
    print("アクセス: http://localhost:5000")
    print("\nCtrl+C で停止\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
