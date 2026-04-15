/**
 * apps_script_trigger.gs
 *
 * Setup:
 * 1 Open the response Google Sheet: Extensions → Apps Script
 * 2 Paste this file into the script editor
 * 3 Set WEBHOOK_URL to your public endpoint:
 *      https://<your-host>/webhook/form-submit
 *    (If running Flask locally, expose it via a tunnel first.)
 * 4 Set WEBHOOK_SECRET to exactly match your app WEBHOOK_SECRET env value.
 *   DO NOT commit a real secret here — set it only in the Apps Script editor,
 *   not in source control.
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

var WEBHOOK_URL = "https://slushies-xcnn5ccpma-ew.a.run.app/webhook/form-submit";
// Optional fallback for local/manual testing only. Prefer Script Properties.
var WEBHOOK_SECRET = "";

// Store production config in Apps Script > Project Settings > Script properties:
// - WEBHOOK_URL
// - WEBHOOK_SECRET
function setupWebhookConfig(url, secret) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty("WEBHOOK_URL", String(url || "").trim());
  props.setProperty("WEBHOOK_SECRET", String(secret || "").trim());
}

function getWebhookUrl_() {
  var fromProps = PropertiesService.getScriptProperties().getProperty("WEBHOOK_URL");
  var effective = String(fromProps || WEBHOOK_URL || "").trim();
  if (!effective) {
    throw new Error("Missing WEBHOOK_URL. Set Script Property WEBHOOK_URL or file constant WEBHOOK_URL.");
  }
  return effective;
}

function getWebhookSecret_() {
  var fromProps = PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET");
  var effective = String(fromProps || WEBHOOK_SECRET || "").trim();
  if (!effective || effective.indexOf("<REPLACE_WITH_WEBHOOK_SECRET") === 0) {
    throw new Error("Missing WEBHOOK_SECRET. Set Script Property WEBHOOK_SECRET.");
  }
  return effective;
}

function onFormSubmit(e) {
  if (!e) {
    throw new Error(
      "Missing trigger event. Run via a spreadsheet 'On form submit' trigger, not from the editor."
    );
  }

  // Prefer the actual submitted row from event range when available.
  var rowIndex = getRowIndexFromEvent_(e);

  var values = normalizeSubmissionValues_(e, rowIndex);
  if (!values || !values.length) {
    throw new Error(
      "No submitted values found on trigger event (expected e.values or e.namedValues)."
    );
  }

  var code = values.length > 1 ? values[1] : "";
  var surveyType = values.length > 2 ? values[2] : "";
  Logger.log("Webhook payload row_index=" + rowIndex + " code=" + code + " survey_type=" + surveyType);

  var payload = JSON.stringify({
    row_index: rowIndex,
    values:    values,
  });

  var options = {
    method:      "post",
    contentType: "application/json",
    payload:     payload,
    headers:     { "X-Webhook-Secret": getWebhookSecret_() },
    muteHttpExceptions: true,
  };

  var response = UrlFetchApp.fetch(getWebhookUrl_(), options);
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

function normalizeSubmissionValues_(e, rowIndex) {
  // Most reliable source: read exact sheet row to preserve order and trailing empties.
  if (e.range && e.range.getSheet && typeof e.range.getSheet === "function") {
    var sheet = e.range.getSheet();
    var effectiveRow = rowIndex || e.range.getRow();
    var lastCol = sheet.getLastColumn();
    var exactRow = sheet.getRange(effectiveRow, 1, 1, lastCol).getValues()[0];
    if (exactRow && exactRow.length) {
      return exactRow;
    }
  }

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