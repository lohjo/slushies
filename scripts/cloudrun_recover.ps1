param(
    [string]$ProjectId = "precise-dragon-491422-e8",
    [string]$Service = "slushies",
    [string]$PrimaryRegion = "asia-southeast1",
    [string]$FallbackRegion = "europe-west1"
)

$ErrorActionPreference = "Stop"

Write-Host "== Cloud Run recovery preflight =="
Write-Host "Project: $ProjectId"
Write-Host "Service: $Service"
Write-Host "Primary region: $PrimaryRegion"
Write-Host "Fallback region: $FallbackRegion"

Write-Host "\n1) Service discovery"
gcloud run services list --project=$ProjectId --region=$PrimaryRegion --format="table(metadata.name,status.url,status.conditions[0].status)"
gcloud run services list --project=$ProjectId --region=$FallbackRegion --format="table(metadata.name,status.url,status.conditions[0].status)"

Write-Host "\n2) Logs (primary region)"
gcloud run services logs read $Service --project=$ProjectId --region=$PrimaryRegion --limit=80

Write-Host "\n3) Logs (fallback region)"
gcloud run services logs read $Service --project=$ProjectId --region=$FallbackRegion --limit=80

Write-Host "\n4) Required runtime env vars (set these before next deploy)"
Write-Host "FLASK_ENV=production"
Write-Host "DATABASE_URL=<postgres-connection-string>"
Write-Host "SECRET_KEY=<32+ byte random hex>"
Write-Host "GOOGLE_SHEET_ID=<sheet-id>"
Write-Host "WEBHOOK_SECRET=<apps-script-secret>"
Write-Host "GOOGLE_SERVICE_ACCOUNT_JSON=<full-json-blob>"

Write-Host "\n5) Example update command (replace placeholders first)"
Write-Host 'gcloud run services update slushies --project=precise-dragon-491422-e8 --region=<region> --set-env-vars=FLASK_ENV=production,DATABASE_URL=<db>,SECRET_KEY=<secret>,GOOGLE_SHEET_ID=<sheet>,WEBHOOK_SECRET=<wh>,GOOGLE_SERVICE_ACCOUNT_JSON=<json>'

Write-Host "\n6) Migration job check"
gcloud run jobs list --project=$ProjectId --region=$PrimaryRegion --format="table(metadata.name,status.conditions[0].status)"
gcloud run jobs list --project=$ProjectId --region=$FallbackRegion --format="table(metadata.name,status.conditions[0].status)"

Write-Host "\n7) If missing, create migration job (replace image + region)"
Write-Host 'gcloud run jobs create slushies-migrate --project=precise-dragon-491422-e8 --region=<region> --image=<region>-docker.pkg.dev/<project>/<repo>/slushies:latest --command=flask --args=db,upgrade --set-env-vars=FLASK_ENV=production,DATABASE_URL=<db>,SECRET_KEY=<secret>,GOOGLE_SHEET_ID=<sheet>,WEBHOOK_SECRET=<wh>,GOOGLE_SERVICE_ACCOUNT_JSON=<json>'

Write-Host "\n8) Execute migration job"
Write-Host 'gcloud run jobs execute slushies-migrate --project=precise-dragon-491422-e8 --region=<region> --wait'

Write-Host "\n9) Ready condition check"
Write-Host 'gcloud run services describe slushies --project=precise-dragon-491422-e8 --region=<region> --format="value(status.conditions)"'
