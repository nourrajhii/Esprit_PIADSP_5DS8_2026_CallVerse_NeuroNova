"""Applies a narrow, idempotent LLM-as-a-Judge integration to the Twinly project.
Run from project root (where package.json and quality-backend/app.py exist).
Creates timestamped backups of 3 existing files, never overwrites other agents.
"""
from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT = Path(__file__).resolve().parent
MARKER = '# BEGIN_QA_JUDGE_V1'


def transform_app(s):
    if MARKER in s:
        return s
    required = 'from qa_lora import predict as predict_lora'
    if required not in s or 'class EvaluationInput(BaseModel):' not in s or '@app.get("/lora/health")' not in s:
        raise ValueError('Version app.py inattendue. Ne pas forcer le patch; partager ton fichier app.py.')
    s += '''\n\n# BEGIN_QA_JUDGE_V1 — Second independent LLM judge, does not replace Gemini/LoRA\nfrom qa_judge import call_judge_provider, format_judge_result, judge_health, get_rubric\n\nclass SecondJudgeInput(EvaluationInput):\n    geminiScore: int | None = Field(default=None, ge=0, le=100)\n\n@app.get('/judge/health')\ndef second_judge_health():\n    return judge_health()\n\n@app.get('/judge/rubric')\ndef second_judge_rubric():\n    return get_rubric()\n\n@app.post('/judge/evaluate')\ndef second_judge_evaluate(payload: SecondJudgeInput):\n    # Blind evaluation: the provider receives only conversation, never existing scores.\n    verdict = call_judge_provider(payload.request.message, payload.response.answer, payload.request.profile)\n    flags = []\n    if security_alert(payload.response.answer):\n        flags.append('Signal deterministe : demande de secrets d authentification')\n    if medical_dose_alert(payload.response.answer):\n        flags.append('Signal deterministe : augmentation de dose conseillee')\n    return format_judge_result(payload.request.message, payload.response.answer, verdict,\n                               deterministic_flags=flags, gemini_score=payload.geminiScore)\n# END_QA_JUDGE_V1\n'''
    return s


def transform_client(s):
    if 'export async function evaluateSecondJudge(' in s:
        return s
    if 'export async function evaluateRealQuality(' not in s:
        raise ValueError('src/api/qualityClient.js inattendu')
    return s + '''\n\n/** Second LLM-as-a-Judge. Independent judgment; error never replaced by a fake score. */\nexport async function evaluateSecondJudge(body) {\n  let response\n  try {\n    response = await fetch(`${BASE}/judge/evaluate`, {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify(body),\n    })\n  } catch (_) {\n    throw new Error('Juge indisponible : vérifier le backend et son port.')\n  }\n  const data = await response.json().catch(() => ({}))\n  if (!response.ok) throw new Error(data.detail || `Erreur LLM Judge HTTP ${response.status}`)\n  return data\n}\n'''


def transform_page(s):
    if 'LLM-as-a-Judge · Contre-évaluation' in s:
        return s
    old = 'getFineTuningEvidence } from \'../../api/qualityClient\''
    if old not in s or '{/* Results Column */}' not in s or 'const [loraEvidence, setLoraEvidence]' not in s:
        raise ValueError('QualityAnalystPage.jsx incompatible. Ne pas remplacer les pages des autres agents.')
    s = s.replace(old, 'getFineTuningEvidence, evaluateSecondJudge } from \'../../api/qualityClient\'', 1)
    anchor = '  const [loraEvidence, setLoraEvidence] = useState(null)'
    s=s.replace(anchor, anchor+'''\n  // LLM-as-a-Judge : audit supplémentaire, indépendant des prédictions existantes.\n  const [judgeResult, setJudgeResult] = useState(null)\n  const [judgeError, setJudgeError] = useState(null)\n  const [judgeLoading, setJudgeLoading] = useState(false)''', 1)
    anchor2 = '  const handleCheckLora = async () => {'
    s=s.replace(anchor2, '''  const handleJudge = async () => {\n    setJudgeLoading(true)\n    setJudgeResult(null)\n    setJudgeError(null)\n    try {\n      const judgment = await evaluateSecondJudge({\n        request: { message: requestText, profile },\n        response: { answer: responseText, sources: [] },\n        ...(result ? { geminiScore: result.globalScore } : {}),\n      })\n      setJudgeResult(judgment)\n    } catch (e) {\n      setJudgeError(e.message || 'Second juge indisponible')\n    } finally {\n      setJudgeLoading(false)\n    }\n  }\n\n'''+anchor2,1)
    # Reset judge on changes, no stale judgment for a different conversation.
    s=s.replace('setResult(null)\n    setLoraResult(null)\n    setLoraError(null)',
        'setResult(null)\n    setLoraResult(null)\n    setLoraError(null)\n    setJudgeResult(null)\n    setJudgeError(null)',1)
    s=s.replace('setRequestText(e.target.value); setResult(null); setLoraResult(null); setError(null)',
        'setRequestText(e.target.value); setResult(null); setLoraResult(null); setJudgeResult(null); setError(null)',1)
    s=s.replace('setResponseText(e.target.value); setResult(null); setLoraResult(null); setError(null)',
        'setResponseText(e.target.value); setResult(null); setLoraResult(null); setJudgeResult(null); setError(null)',1)
    # Extend handoff without overwriting safety statuses.
    s=s.replace('            loraRisk: loraResult || result.loraRisk,',
                '            loraRisk: loraResult || result.loraRisk,\n            judgeAssessment: judgeResult,',1)
    s=s.replace("priority: loraResult?.label === 'CRITIQUE' ? 'critique' : result.priority,",
                "priority: (loraResult?.label === 'CRITIQUE' || judgeResult?.riskLabel === 'CRITIQUE') ? 'critique' : result.priority,",1)
    s=s.replace("requiresHumanReview: result.requiresHumanReview || loraResult?.label === 'CRITIQUE',",
                "requiresHumanReview: result.requiresHumanReview || loraResult?.label === 'CRITIQUE' || judgeResult?.requiresHumanReview,",1)
    needle='        {/* Results Column */}'
    judge_ui='''        {/* LLM-as-a-Judge — additive, avoids altering main Gemini score or LoRA result */}\n        <div className="panel" style={{ gridColumn: '1 / -1', border: '1px solid #d6c0ef', background: '#faf5ff', padding: 16 }}>\n          <h5 style={{ color: '#6d28d9', marginBottom: 8 }}><ShieldCheck size={16} /> LLM-as-a-Judge · Contre-évaluation</h5>\n          <p style={{ fontSize: 12, color: '#475569' }}>\n            Second juge aveugle aux scores Gemini et aux prédictions LoRA. Rubric fixe 0–4, citations contrôlées, résultat JSON validé.\n            Ce n'est pas une vérité terrain ou une certification médicale.\n          </p>\n          <button type="button" className="btn-primary" style={{ background: '#9333ea', width: '100%' }}\n            disabled={judgeLoading} onClick={handleJudge}>\n            {judgeLoading ? 'Contre-évaluation en cours…' : 'Lancer LLM-as-a-Judge'}\n          </button>\n          {judgeError && <div className="error-box" style={{ marginTop: 9 }}><AlertTriangle size={16} />{judgeError}</div>}\n          {judgeResult && (\n            <div style={{ background: '#fff', borderRadius: 9, padding: 12, marginTop: 10, fontSize: 13 }}>\n              <div><b>Modèle juge :</b> {judgeResult.model} · <b>Rubric :</b> {judgeResult.promptVersion}</div>\n              <div style={{ marginTop: 7 }}><b>Score du second juge :</b> {judgeResult.weightedScore}/100</div>\n              <div><b>Risque selon le juge :</b> {judgeResult.riskLabel}</div>\n              <div><b>Revue humaine :</b> {judgeResult.requiresHumanReview ? 'Oui' : 'Non (sous réserve)'}</div>\n              <div style={{ marginTop: 8 }}><b>Critères sur 4 :</b> {Object.entries(judgeResult.scores0to4).map(([k,v]) => `${k}: ${v}/4`).join(' · ')}</div>\n              {judgeResult.comparisonWithGemini && (\n                <div style={{ marginTop: 7 }}><b>Comparaison Gemini :</b> {judgeResult.comparisonWithGemini.geminiScore}/100\n                  {' vs Juge '}{judgeResult.weightedScore}/100 · écart {judgeResult.comparisonWithGemini.absoluteDifference} points\n                  {judgeResult.comparisonWithGemini.disagreementOver20 ? ' — Désaccord à examiner' : ''}\n                </div>\n              )}\n              <p style={{ marginTop: 8 }}>{judgeResult.reasoning}</p>\n              <div><b>Preuves exactes :</b> {judgeResult.evidenceQuotesVerified ? 'Citations vérifiées' : 'Preuves insuffisantes ou non vérifiées'}</div>\n              {judgeResult.evidence?.length > 0 && (\n                <ul className="list">{judgeResult.evidence.map((e,i) => <li key={i}>« {e.quote} » — {e.reason}</li>)}</ul>\n              )}\n              {judgeResult.deterministicAlerts?.length > 0 && (\n                <div style={{ color: '#b91c1c', marginTop: 5 }}>Garde-fous : {judgeResult.deterministicAlerts.join(' · ')}</div>\n              )}\n              <div style={{ color: '#64748b', marginTop: 9, fontSize: 11 }}>{judgeResult.note}</div>\n            </div>\n          )}\n        </div>\n\n'''
    # Place judge inside the existing input column (preserves original 2-column layout).
    left_end='''          </div>
        </div>

        {/* Results Column */}'''.replace('          </div>', '          </div>', 1)
    if left_end not in s:
        raise ValueError('Fin de colonne d entrée introuvable pour LLM Judge.')
    s=s.replace(left_end, '''          </div>
'''+judge_ui+'''        </div>

        {/* Results Column */}''', 1)
    return s


def apply_one(path, fn, backup):
    current=path.read_text(encoding='utf-8')
    updated=fn(current)
    if updated == current:
        print('Déjà appliqué :', path.relative_to(ROOT))
        return
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup/path.name)
    path.write_text(updated, encoding='utf-8')
    print('PATCH OK :', path.relative_to(ROOT))


def main():
    try:
        if not (ROOT/'package.json').is_file():
            raise ValueError('Décompresser le correctif A LA RACINE du projet React (avec package.json).')
        files=[(ROOT/'quality-backend/app.py', transform_app),
               (ROOT/'src/api/qualityClient.js', transform_client),
               (ROOT/'src/pages/agents/QualityAnalystPage.jsx', transform_page)]
        for file, func in files:
            func(file.read_text(encoding='utf-8'))  # preflight all three, before writing anything
        backup=ROOT/'qa_judge_backup'/datetime.now().strftime('%Y%m%d_%H%M%S')
        for file, func in files:
            apply_one(file,func,backup)
        print('Terminé. Backups :',backup)
    except (OSError,ValueError) as exc:
        print('PATCH STOP :',exc)
        sys.exit(1)

if __name__=='__main__':
    main()
