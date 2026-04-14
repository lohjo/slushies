/**
 * apps_script_trigger.gs
 *
 * Paste this into Extensions → Apps Script inside your Google Sheet.
 * Then add a trigger: Triggers → Add Trigger →
 *   Function: onFormSubmit | Event: From spreadsheet → On form submit
 *
 * Replace WEBHOOK_URL and WEBHOOK_SECRET with your actual values.
 */

var WEBHOOK_URL    = "https://your-server.com/webhook/form-submit";
var WEBHOOK_SECRET = "replace-with-your-webhook-secret";

function onFormSubmit(e) {
  var values   = e.values;              // array of strings, one per column
  var rowIndex = getLastRowIndex_();    // 1-based row number of this submission

  var payload = JSON.stringify({
    row_index: rowIndex,
    values:    values,
  });

  var options = {
    method:      "post",
    contentType: "application/json",
    payload:     payload,
    headers:     { "X-Webhook-Secret": WEBHOOK_SECRET },
    muteHttpExceptions: true,
  };

  var response = UrlFetchApp.fetch(WEBHOOK_URL, options);
  Logger.log("Webhook response: " + response.getContentText());
}

function getLastRowIndex_() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  return sheet.getLastRow();
}