# Test report generation E2E
# Run: .\scripts\test_report_e2e.ps1
# Make sure uvicorn is running on :8081 first

$BASE = "http://localhost:8081"
$CONV_ID = "conv001"

Write-Host "==== 1. Register SQL datasource ====" -ForegroundColor Cyan
Write-Host "(Schema auto-discovery enabled, no need to provide table_schema)" -ForegroundColor Gray

$body = '{
    "type": "sql",
    "name": "student_db",
    "metadata": {
        "db_type": "mysql",
        "host": "172.16.0.164",
        "port": 3306,
        "database": "student",
        "username": "root",
        "password": "root@2024."
    }
}'

$resp = Invoke-RestMethod -Uri "$BASE/api/v1/conversations/$CONV_ID/data-sources" -Method POST -ContentType "application/json" -Body $body
$DS_ID = $resp.datasource_id
Write-Host "  -> datasource_id: $DS_ID" -ForegroundColor Green

# Step 2: NL query test
Write-Host "`n==== 2. NL query test ====" -ForegroundColor Cyan
try {
    $q = Invoke-RestMethod -Uri "$BASE/api/v1/conversations/$CONV_ID/data-sources/$DS_ID/query" -Method POST -ContentType "application/json" -Body '{"query":"count students per major enrolled in 2024","max_results":10}'
    Write-Host "  SQL: $($q.generated_query)" -ForegroundColor Yellow
    Write-Host "  rows: $($q.row_count)" -ForegroundColor Green
    if ($q.columns -and $q.columns.Count -gt 0) {
        Write-Host "  columns: $($q.columns -join ', ')" -ForegroundColor Green
    }
    if ($q.error) {
        Write-Host "  error: $($q.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "  FAILED: $_" -ForegroundColor Red
}

# Step 3: Generate report
Write-Host "`n==== 3. Create report ====" -ForegroundColor Cyan
$reportBody = @"
{
    "title": "2024 Student Grade Analysis Report",
    "format": ["html", "docx"],
    "report_type": "analysis",
    "datasource_ids": ["$DS_ID"],
    "user_query": "analyze 2024 CS major student grades, avg score per course, max score, fail count",
    "language": "en",
    "include_conversation": false,
    "include_citations": true
}
"@

$r = Invoke-RestMethod -Uri "$BASE/api/v1/conversations/$CONV_ID/reports" -Method POST -ContentType "application/json" -Body $reportBody
$REPORT_ID = $r.report_id
Write-Host "  report_id: $REPORT_ID" -ForegroundColor Green
Write-Host "  status: $($r.status)" -ForegroundColor Yellow

Write-Host "`n==== 4. Poll report status (wait 10s) ====" -ForegroundColor Cyan
Start-Sleep -Seconds 10

try {
    $s = Invoke-RestMethod -Uri "$BASE/api/v1/reports/$REPORT_ID" -Method GET
    Write-Host "  status: $($s.status)" -ForegroundColor Yellow

    if ($s.status -eq "success") {
        Write-Host "`n==== 5. Download artifacts ====" -ForegroundColor Cyan
        foreach ($art in $s.artifacts) {
            $url = "$BASE$($art.url)"
            $file = "d:\code\agent\intelli-engine\$($art.filename)"
            Invoke-WebRequest -Uri $url -OutFile $file
            Write-Host "  [$($art.format)] saved to $file" -ForegroundColor Green
        }
        Write-Host "`n==== ALL DONE! ====" -ForegroundColor Cyan
    } elseif ($s.status -eq "failed") {
        Write-Host "  FAILED: $($s.error)" -ForegroundColor Red
    } else {
        Write-Host "  still $($s.status), try: curl $BASE/api/v1/reports/$REPORT_ID" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
}
