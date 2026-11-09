# Étape 5 : soumettre au Quality Analyst les 10 scénarios du dataset.
# Utilise l'API FastAPI déjà lancée sur http://127.0.0.1:8001
# Chaque évaluation est un appel réel à Gemini, éventuellement facturé.
$ErrorActionPreference = 'Stop'
$apiUrl = 'http://127.0.0.1:8001/evaluate'
$datasetPath = Join-Path $PSScriptRoot 'datasets\scenarios_telecom.json'
$outputPath = Join-Path $PSScriptRoot 'datasets\benchmark_predictions.csv'

if (-not (Test-Path -LiteralPath $datasetPath)) {
    throw "Dataset introuvable : $datasetPath. Copier ce script à la racine de quality-backend."
}

# ConvertFrom-Json returns the root JSON array. Do NOT wrap the invocation in
# @( ... ): under Windows PowerShell 5.1 this can create one nested item.
$jsonText = Get-Content -LiteralPath $datasetPath -Raw -Encoding UTF8
$scenarios = ConvertFrom-Json -InputObject $jsonText
$scenarioCount = @($scenarios).Count
Write-Host "Scenarios a evaluer : $scenarioCount" -ForegroundColor Cyan
if ($scenarioCount -ne 10) {
    throw "Dataset inattendu : $scenarioCount scenario(s) au lieu de 10. Arret sans appel a Gemini."
}
foreach ($s in $scenarios) {
    if (-not $s.scenario -or -not $s.request.message -or -not $s.response.answer) {
        throw "Un scenario est incomplet. Arret sans appel a Gemini."
    }
}
# Check the backend *before* any paid calls and before rewriting the output CSV.
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health' -Method Get -TimeoutSec 8
}
catch {
    throw "FastAPI injoignable sur http://127.0.0.1:8001. Ouvrir un autre terminal, configurer Gemini et demarrer uvicorn. Detail : $($_.Exception.Message)"
}
if ($health.status -ne 'up') {
    throw "FastAPI n'est pas pret : statut=$($health.status)"
}
if ($health.llmConfigured -ne $true) {
    throw "FastAPI est actif, mais GEMINI_API_KEY n'est pas configuree dans SON terminal."
}
Write-Host "Backend OK ; modele=$($health.model) ; cle Gemini configuree." -ForegroundColor Green
Write-Host 'Chaque appel peut entrainer une consommation du quota Gemini.' -ForegroundColor Yellow
$results = @()
$index = 0

foreach ($scenario in $scenarios) {
    $index++
    $id = [string]$scenario.scenario
    Write-Host "[$index/$scenarioCount] $id" -ForegroundColor Cyan

    $payload = @{
        conversationId = $id
        request        = $scenario.request
        response       = $scenario.response
    } | ConvertTo-Json -Depth 20

    try {
        $report = Invoke-RestMethod `
            -Uri $apiUrl `
            -Method Post `
            -ContentType 'application/json; charset=utf-8' `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
            -TimeoutSec 160
        $results += [pscustomobject]@{
            conversation_id = $id
            statut          = 'OK'
            score_ia        = $report.globalScore
            priorite_ia     = $report.priority
            revue_humaine   = $report.requiresHumanReview
            erreur          = ''
        }
        Write-Host "  OK : $($report.globalScore)/100 ; priorite=$($report.priority)" -ForegroundColor Green
    }
    catch {
        $errorText = $_.Exception.Message
        $results += [pscustomobject]@{
            conversation_id = $id
            statut          = 'ERREUR'
            score_ia        = ''
            priorite_ia     = ''
            revue_humaine   = ''
            erreur          = $errorText
        }
        Write-Host "  ERREUR : $errorText" -ForegroundColor Red
    }
    if ($index -lt $scenarioCount) { Start-Sleep -Seconds 2 }
}

$results | Export-Csv -LiteralPath $outputPath -NoTypeInformation -Encoding UTF8
$success = @($results | Where-Object { $_.statut -eq 'OK' }).Count
Write-Host "Bilan : $success/$scenarioCount evaluations reussies." -ForegroundColor Cyan
Write-Host "CSV : $outputPath" -ForegroundColor Cyan
if ($success -ne $scenarioCount) {
    Write-Warning "Ne pas considerer les erreurs comme des evaluations. Reexecuter les scenarii echoues apres diagnostic."
}
