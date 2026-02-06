# Null Safety Issue Detector
# Finds unsafe property access patterns in TypeScript/TSX files

param(
    [string]$Path = "src"
)

Write-Host "Scanning for null safety issues in: $Path" -ForegroundColor Cyan

$issues = @()
$fileCount = 0

Get-ChildItem -Path $Path -Include "*.tsx", "*.ts" -Recurse | ForEach-Object {
    $file = $_
    $fileCount++
    $lines = Get-Content $file.FullName
    
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $lineNum = $i + 1
        
        # Skip comments and imports
        if ($line -match '^\s*(//|/\*|\*|import)') { continue }
        
        # Pattern 1: obj.prop.prop without optional chaining
        if ($line -match '(\w+)\.(\w+)\.(\w+)' -and $line -notmatch '\?\.' -and $line -notmatch '(window|console|Math|Object|Array|JSON|Date)\.') {
            $issues += [PSCustomObject]@{
                File  = $file.Name
                Path  = $file.FullName
                Line  = $lineNum
                Code  = $line.Trim()
                Issue = "Nested property access without optional chaining"
            }
        }
        
        # Pattern 2: obj.arr.map/filter/slice without guard
        if ($line -match '(\w+)\.(\w+)\.(map|filter|slice|forEach|find)\(' -and $line -notmatch '\?\.' -and $line -notmatch '\|\|\s*\[') {
            $issues += [PSCustomObject]@{
                File  = $file.Name
                Path  = $file.FullName
                Line  = $lineNum
                Code  = $line.Trim()
                Issue = "Array method on potentially undefined property"
            }
        }
    }
}

Write-Host "`nScan Results:" -ForegroundColor Yellow
Write-Host "Files Scanned: $fileCount"
Write-Host "Issues Found: $($issues.Count)"

if ($issues.Count -eq 0) {
    Write-Host "`nNo null safety issues detected!" -ForegroundColor Green
    exit 0
}

$groupedIssues = $issues | Group-Object -Property File | Sort-Object Count -Descending

Write-Host "`nIssues by File:" -ForegroundColor Red
foreach ($group in $groupedIssues) {
    Write-Host "`n  $($group.Name) ($($group.Count) issues)" -ForegroundColor Yellow
    
    foreach ($issue in ($group.Group | Select-Object -First 5)) {
        Write-Host "    Line $($issue.Line): $($issue.Issue)" -ForegroundColor Gray
        Write-Host "      $($issue.Code)" -ForegroundColor DarkGray
    }
    
    if ($group.Count -gt 5) {
        Write-Host "    ... and $($group.Count - 5) more" -ForegroundColor DarkGray
    }
}

# Save report
$reportPath = "null_safety_report.json"
$issues | ConvertTo-Json -Depth 5 | Out-File $reportPath
Write-Host "`nReport saved: $reportPath" -ForegroundColor Cyan

exit 0
