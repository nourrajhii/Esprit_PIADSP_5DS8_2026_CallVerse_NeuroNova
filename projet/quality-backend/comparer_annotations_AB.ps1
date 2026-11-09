# Quality Analyst Agent - comparaison des annotations A et B.
# Lecture seule sur A/B; produit datasets/comparaison_annotateurs_AB.csv.
param(
    [string]$Dossier = ".\datasets"
)

$ErrorActionPreference = "Stop"
$pathA = Join-Path $Dossier "annotations_ecommerce_sante_A.csv"
$pathB = Join-Path $Dossier "annotations_ecommerce_sante_B.csv"
$outPath = Join-Path $Dossier "comparaison_annotateurs_AB.csv"

if (-not (Test-Path -LiteralPath $pathA) -or -not (Test-Path -LiteralPath $pathB)) {
    throw "Fichier A ou B introuvable. Lancez ce script depuis quality-backend."
}

$A = @(Import-Csv -LiteralPath $pathA -Encoding UTF8)
$B = @(Import-Csv -LiteralPath $pathB -Encoding UTF8)
$idsA = @($A | ForEach-Object { $_.conversation_id })
$idsB = @($B | ForEach-Object { $_.conversation_id })
if (@($idsA | Select-Object -Unique).Count -ne $A.Count -or @($idsB | Select-Object -Unique).Count -ne $B.Count) {
    throw "Identifiant conversation_id duplique dans A ou B."
}

$indexB = @{}
foreach ($b in $B) { $indexB[[string]$b.conversation_id] = $b }
$poids = [ordered]@{
    pertinence_humaine = 0.35
    empathie_humaine = 0.20
    clarte_humaine = 0.20
    conformite_humaine = 0.25
}
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$styles = [System.Globalization.NumberStyles]::Float
$sortie = @()

foreach ($a in $A) {
    $id = [string]$a.conversation_id
    if (-not $indexB.ContainsKey($id)) {
        Write-Warning "Absent de B : $id"
        continue
    }
    $b = $indexB[$id]
    $scoreA = 0.0
    $scoreB = 0.0
    $ecartsCriteres = @()
    $estValide = $true
    foreach ($critere in $poids.Keys) {
        $x = 0.0; $y = 0.0
        $textA = ([string]$a.$critere).Trim().Replace(",", ".")
        $textB = ([string]$b.$critere).Trim().Replace(",", ".")
        $okA = [double]::TryParse($textA, $styles, $culture, [ref]$x)
        $okB = [double]::TryParse($textB, $styles, $culture, [ref]$y)
        if (-not ($okA -and $okB) -or $x -lt 0 -or $x -gt 100 -or $y -lt 0 -or $y -gt 100) {
            Write-Warning "Notes manquantes/invalides ($critere) : $id"
            $estValide = $false
            break
        }
        $scoreA += $x * $poids[$critere]
        $scoreB += $y * $poids[$critere]
        $ecartsCriteres += [math]::Abs($x - $y)
    }
    $critA = ([string]$a.critique_humain).Trim().ToLowerInvariant()
    $critB = ([string]$b.critique_humain).Trim().ToLowerInvariant()
    if ($critA -notin @('oui', 'non') -or $critB -notin @('oui', 'non')) {
        Write-Warning "Decision critique manquante : $id"
        $estValide = $false
    }
    if (-not $estValide) { continue }

    $delta = [math]::Abs($scoreA - $scoreB)
    $sortie += [PSCustomObject]@{
        conversation_id = $id
        score_A = [math]::Round($scoreA, 2)
        score_B = [math]::Round($scoreB, 2)
        ecart_score = [math]::Round($delta, 2)
        ecart_moyen_criteres = [math]::Round(($ecartsCriteres | Measure-Object -Average).Average, 2)
        critique_A = $critA
        critique_B = $critB
        accord_critique = if ($critA -eq $critB) { 'oui' } else { 'non' }
        a_arbitrer = if ($critA -ne $critB -or $delta -ge 15) { 'oui' } else { 'non' }
    }
}

if ($sortie.Count -eq 0) { throw "Aucune paire A/B valide. Fichiers sources inchanges." }
$sortie | Sort-Object ecart_score -Descending | Export-Csv -LiteralPath $outPath -Encoding UTF8 -NoTypeInformation
$sortie | Sort-Object ecart_score -Descending | Format-Table conversation_id, score_A, score_B, ecart_score, critique_A, critique_B, a_arbitrer -AutoSize

$maeAB = ($sortie | Measure-Object ecart_score -Average).Average
$accords = @($sortie | Where-Object { $_.accord_critique -eq 'oui' }).Count
Write-Host "`nPaires A/B valides : $($sortie.Count)"
Write-Host ("Ecart moyen absolu des scores A/B : {0:N2} /100" -f $maeAB)
Write-Host "Accord brut sur critique : $accords/$($sortie.Count)"
Write-Host "Rapport : $outPath"
Write-Host "Les fichiers A/B n'ont pas ete modifies."
if (@($sortie | Where-Object { $_.conversation_id -eq 'ECOSANTE-06-conseil-sante-risque' -and $_.accord_critique -eq 'non' }).Count -gt 0) {
    Write-Warning "Desaccord sur ECOSANTE-06 : revoir l'annotation du conseil de dose avant le consensus."
}
