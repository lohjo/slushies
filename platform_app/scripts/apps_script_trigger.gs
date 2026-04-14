/**
 * apps_script_trigger.gs
 *
 * Setup:
 * 1) Open the response Google Sheet: Extensions → Apps Script
 * 2) Paste this file into the script editor
 * 3) Set WEBHOOK_URL to your public endpoint:
 *      https://<your-host>/webhook/form-submit
 *    (If running Flask locally, expose it via a tunnel first.)
 * 4) Set WEBHOOK_SECRET to exactly match your app WEBHOOK_SECRET env value
 * 5) Add trigger: Triggers → Add Trigger →
 *      Function: onFormSubmit
 *      Event source: From spreadsheet
 *      Event type: On form submit
 *
 * After setup, each form submission sends:
 *   { "row_index": <sheet row>, "values": [...] }
 * with header:
 *   X-Webhook-Secret: <WEBHOOK_SECRET>
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
