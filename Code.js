function recordWeather() {
  // スプレッドシートを取得
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // 今日の日付を取得
  const today = new Date();

  // ユーザーに天気を入力してもらう
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt('天気を記録', '今日の天気を入力してください:', ui.ButtonSet.OK_CANCEL);

  // キャンセルされた場合は終了
  if (response.getSelectedButton() !== ui.Button.OK) {
    return;
  }

  const weather = response.getResponseText();

  // 日付と天気をスプレッドシートに追加
  sheet.appendRow([today, weather]);
}
