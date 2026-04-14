/**
 * apps_script_trigger.gs
 *
 * Setup:
 * 1 Open the response Google Sheet: Extensions → Apps Script
 * 2 Paste this file into the script editor
 * 3 Set WEBHOOK_URL to your public endpoint:
 *      https://<your-host>/webhook/form-submit
 *    (If running Flask locally, expose it via a tunnel first.)
 * 4 Set WEBHOOK_SECRET to exactly match your app WEBHOOK_SECRET env value
 * 5 Add trigger: Triggers → Add Trigger →
 *      Function: onFormSubmit
 *      Event source: From spreadsheet
 *      Event type: On form submit
 *
 * After setup, each form submission sends:
 *   { "row_index": <sheet row>, "values": [...] }
 * with header:
 *   X-Webhook-Secret: <WEBHOOK_SECRET>
 */

var WEBHOOK_URL    = "https://slushies-411994757215.europe-west1.run.app";
var WEBHOOK_SECRET = "64031848b7eac25d50d56f3153acaaf995662b2202f1f123";

function onFormSubmit(e) {
  if (!e) {
    throw new Error(
      "Missing trigger event. Run via a spreadsheet 'On form submit' trigger, not from the editor."
    );
  }

  var values = normalizeSubmissionValues_(e);
  if (!values || !values.length) {
    throw new Error(
      "No submitted values found on trigger event (expected e.values or e.namedValues)."
    );
  }

  // Prefer the actual submitted row from event range when available.
  var rowIndex = getRowIndexFromEvent_(e);

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

function getRowIndexFromEvent_(e) {
  if (e.range && typeof e.range.getRow === "function") {
    return e.range.getRow();
  }
  return getLastRowIndex_();
}

function normalizeSubmissionValues_(e) {
  if (Array.isArray(e.values) && e.values.length) {
    return e.values;
  }

  // Some trigger contexts provide namedValues only.
  if (e.namedValues && typeof e.namedValues === "object") {
    var out = [];
    for (var key in e.namedValues) {
      if (!Object.prototype.hasOwnProperty.call(e.namedValues, key)) {
        continue;
      }
      var value = e.namedValues[key];
      out.push(Array.isArray(value) ? value[0] : value);
    }
    return out;
  }

  // Form-submit events can expose FormResponse API objects.
  if (e.response && typeof e.response.getItemResponses === "function") {
    var itemResponses = e.response.getItemResponses();
    return itemResponses.map(function (itemResponse) {
      return itemResponse.getResponse();
    });
  }

  return [];
}