"""
見積書生成機能 - PDF形式の見積書を生成
ReportLabを使用してテンプレートベースの見積書を作成
"""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os

class EstimateGenerator:
    """見積書生成クラス"""

    def __init__(self):
        self.page_width, self.page_height = A4
        self.output_dir = "generated_estimates"

        # 出力ディレクトリを作成
        os.makedirs(self.output_dir, exist_ok=True)

        # 日本語フォントの登録（Windowsの標準フォント）
        try:
            font_path = "C:/Windows/Fonts/msgothic.ttc"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('MSGothic', font_path))
                self.font_name = 'MSGothic'
            else:
                print("[警告] 日本語フォントが見つかりません。デフォルトフォントを使用します。")
                self.font_name = 'Helvetica'
        except Exception as e:
            print(f"[警告] フォント登録エラー: {e}")
            self.font_name = 'Helvetica'

    def generate_estimate(
        self,
        customer_name: str,
        customer_address: str,
        items: list,
        estimate_number: str = None,
        estimate_date: str = None,
        notes: str = None
    ) -> str:
        """
        見積書PDFを生成

        Args:
            customer_name: 顧客名
            customer_address: 顧客住所
            items: 見積項目のリスト [{'name': '商品名', 'quantity': 数量, 'unit': '単位', 'unit_price': 単価, 'amount': 金額}, ...]
            estimate_number: 見積番号
            estimate_date: 見積日付
            notes: 備考

        Returns:
            生成したPDFファイルのパス
        """
        # デフォルト値の設定
        if estimate_number is None:
            estimate_number = f"EST-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        if estimate_date is None:
            estimate_date = datetime.now().strftime('%Y年%m月%d日')

        # ファイル名
        filename = f"{self.output_dir}/見積書_{estimate_number}.pdf"

        # PDFキャンバスの作成
        c = canvas.Canvas(filename, pagesize=A4)

        # 見積書の描画
        self._draw_header(c, estimate_number, estimate_date)
        self._draw_customer_info(c, customer_name, customer_address)
        y_position = self._draw_items_table(c, items)
        self._draw_total(c, items, y_position)

        if notes:
            self._draw_notes(c, notes, y_position - 40*mm)

        self._draw_footer(c)

        # PDF保存
        c.save()

        print(f"[OK] 見積書を生成しました: {filename}")
        return filename

    def _draw_header(self, c: canvas.Canvas, estimate_number: str, estimate_date: str):
        """ヘッダー部分を描画"""
        c.setFont(self.font_name, 20)
        c.drawString(80*mm, 270*mm, "御 見 積 書")

        c.setFont(self.font_name, 10)
        c.drawString(140*mm, 260*mm, f"見積番号: {estimate_number}")
        c.drawString(140*mm, 255*mm, f"発行日: {estimate_date}")

    def _draw_customer_info(self, c: canvas.Canvas, customer_name: str, customer_address: str):
        """顧客情報を描画"""
        c.setFont(self.font_name, 12)
        c.drawString(20*mm, 245*mm, f"{customer_name} 御中")
        c.setFont(self.font_name, 9)
        c.drawString(20*mm, 240*mm, f"〒 {customer_address}")

        # 発行元情報
        c.setFont(self.font_name, 10)
        c.drawString(140*mm, 245*mm, "ダイキョウクリーン株式会社")
        c.setFont(self.font_name, 8)
        c.drawString(140*mm, 241*mm, "〒000-0000")
        c.drawString(140*mm, 237*mm, "東京都〇〇区〇〇 1-2-3")
        c.drawString(140*mm, 233*mm, "TEL: 03-0000-0000")

    def _draw_items_table(self, c: canvas.Canvas, items: list) -> float:
        """見積明細表を描画"""
        # テーブルの開始位置
        table_top = 220*mm
        row_height = 7*mm

        # テーブルヘッダー
        c.setFont(self.font_name, 9)
        headers = ["No.", "品名・仕様", "数量", "単位", "単価", "金額"]
        col_widths = [10*mm, 80*mm, 15*mm, 15*mm, 25*mm, 25*mm]
        col_positions = [20*mm]

        for width in col_widths[:-1]:
            col_positions.append(col_positions[-1] + width)

        # ヘッダー描画
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(20*mm, table_top - row_height, 170*mm, row_height, fill=1)
        c.setFillColorRGB(0, 0, 0)

        for i, header in enumerate(headers):
            c.drawString(col_positions[i] + 2*mm, table_top - row_height + 2*mm, header)

        # 明細行の描画
        current_y = table_top - row_height

        for idx, item in enumerate(items, 1):
            current_y -= row_height

            # 罫線
            c.rect(20*mm, current_y, 170*mm, row_height, fill=0)

            # データ
            c.drawString(col_positions[0] + 2*mm, current_y + 2*mm, str(idx))
            c.drawString(col_positions[1] + 2*mm, current_y + 2*mm, item.get('name', ''))
            c.drawRightString(col_positions[2] + 13*mm, current_y + 2*mm, str(item.get('quantity', '')))
            c.drawString(col_positions[3] + 2*mm, current_y + 2*mm, item.get('unit', ''))
            c.drawRightString(col_positions[4] + 23*mm, current_y + 2*mm, f"￥{item.get('unit_price', 0):,}")
            c.drawRightString(col_positions[5] + 23*mm, current_y + 2*mm, f"￥{item.get('amount', 0):,}")

        return current_y

    def _draw_total(self, c: canvas.Canvas, items: list, y_position: float):
        """合計金額を描画"""
        total_amount = sum(item.get('amount', 0) for item in items)

        # 合計欄
        c.setFont(self.font_name, 12)
        c.drawString(140*mm, y_position - 15*mm, "合計金額:")
        c.setFont(self.font_name, 14)
        c.drawRightString(185*mm, y_position - 15*mm, f"￥{total_amount:,}")

        # 税込み表記
        c.setFont(self.font_name, 8)
        c.drawRightString(185*mm, y_position - 20*mm, "(税込)")

    def _draw_notes(self, c: canvas.Canvas, notes: str, y_position: float):
        """備考欄を描画"""
        c.setFont(self.font_name, 9)
        c.drawString(20*mm, y_position, "【備考】")
        c.drawString(20*mm, y_position - 5*mm, notes)

    def _draw_footer(self, c: canvas.Canvas):
        """フッター部分を描画"""
        c.setFont(self.font_name, 7)
        c.drawCentredString(
            self.page_width / 2,
            15*mm,
            "本見積書は発行日より30日間有効です。"
        )

def main():
    """テスト用のメイン処理"""
    generator = EstimateGenerator()

    # サンプルデータ
    customer_name = "株式会社サンプル商事"
    customer_address = "100-0001 東京都千代田区千代田1-1-1"

    items = [
        {
            'name': '業務用冷蔵庫',
            'quantity': 2,
            'unit': '台',
            'unit_price': 50000,
            'amount': 100000
        },
        {
            'name': '業務用洗濯機',
            'quantity': 1,
            'unit': '台',
            'unit_price': 30000,
            'amount': 30000
        },
        {
            'name': 'オフィステーブル',
            'quantity': 5,
            'unit': '台',
            'unit_price': 15000,
            'amount': 75000
        },
    ]

    notes = "配送費込みの価格です。設置作業が必要な場合は別途お見積りいたします。"

    # 見積書生成
    pdf_path = generator.generate_estimate(
        customer_name=customer_name,
        customer_address=customer_address,
        items=items,
        notes=notes
    )

    print(f"\n生成されたPDF: {pdf_path}")

if __name__ == "__main__":
    main()
