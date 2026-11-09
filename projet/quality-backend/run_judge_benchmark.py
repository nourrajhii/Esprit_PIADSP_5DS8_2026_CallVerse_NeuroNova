"""Run actual judge calls on e-commerce/health scenarios and compare to human A.

Never fabricates scores after API failures. Unknown human labels are excluded from risk metrics.
"""
import argparse
import csv
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent
W = {'pertinence': .35, 'empathie': .20, 'clarte': .20, 'conformite': .25}


def human_score(row):
    try:
        return round(sum(float(row[f'{k}_humaine'].replace(',', '.')) * v for k, v in W.items()), 2)
    except (KeyError, ValueError, AttributeError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='http://127.0.0.1:8003')
    parser.add_argument('--max', type=int, default=3, help='Max judge requests; 0 means all')
    parser.add_argument('--timeout', type=int, default=100)
    args = parser.parse_args()
    scenarios_path = BASE/'datasets'/'scenarios_ecommerce_sante.json'
    if not scenarios_path.is_file():
        raise SystemExit(f'Dataset introuvable: {scenarios_path} (garder ton dataset initial).')
    scenarios = json.loads(scenarios_path.read_text(encoding='utf-8-sig'))
    annot_file = BASE/'datasets'/'annotations_ecommerce_sante_A.csv'
    with annot_file.open(encoding='utf-8-sig', newline='') as f:
        humans = {r['conversation_id']: r for r in csv.DictReader(f)}
    results = []
    for scenario in scenarios[:args.max or len(scenarios)]:
        sid = scenario['scenario']
        payload = { 'request': scenario['request'], 'response': scenario['response'], 'conversationId': sid }
        try:
            req = Request(args.api.rstrip('/')+'/judge/evaluate', data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json'}, method='POST')
            with urlopen(req, timeout=args.timeout) as response:
                verdict = json.load(response)
            human = humans.get(sid, {})
            score_h = human_score(human)
            label_h = human.get('critique_humain', '').strip().lower()
            row = {'conversation_id': sid, 'status': 'ok', 'model': verdict.get('model'),
                   'judge_score': verdict['weightedScore'], 'human_score_A': score_h,
                   'absolute_error': abs(verdict['weightedScore']-score_h) if score_h is not None else '',
                   'judge_critical': verdict['riskLabel'], 'human_critical_A': label_h if label_h in ('oui','non') else '',
                   'human_review': verdict['requiresHumanReview'], 'evidence_verified': verdict['evidenceQuotesVerified'],
                   'http_error': ''}
            print(f'{sid}: score juge={row["judge_score"]}, score humain A={score_h}, risque={row["judge_critical"]}')
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
            row = {'conversation_id': sid, 'status': 'error', 'model': '', 'judge_score': '',
                   'human_score_A': '', 'absolute_error': '', 'judge_critical': '',
                   'human_critical_A': '', 'human_review': '', 'evidence_verified': '',
                   'http_error': str(getattr(exc,'code',type(exc).__name__))}
            print(f'{sid}: ECHEC, pas de score inventé ({row["http_error"]})')
        results.append(row)
        time.sleep(.2)
    path = BASE/'datasets'/'judge_predictions_ecommerce_sante.csv'
    with path.open('w', newline='', encoding='utf-8-sig') as out:
        w = csv.DictWriter(out, fieldnames=list(results[0])); w.writeheader(); w.writerows(results)
    paired = [r for r in results if r['status']=='ok' and r['absolute_error'] != '']
    agreement = [r for r in results if r['status']=='ok' and r['human_critical_A']]
    print(f'CSV: {path}')
    print(f'Appels OK: {sum(r["status"]=="ok" for r in results)}/{len(results)}')
    print(f'MAE juge vs A ({len(paired)} paires): {sum(r["absolute_error"] for r in paired)/len(paired):.2f}/100' if paired else 'MAE: données insuffisantes')
    print(f'Accord critique humain/juge ({len(agreement)} paires): '+
          (f'{sum((r["judge_critical"] == "CRITIQUE") == (r["human_critical_A"] == "oui") for r in agreement)}/{len(agreement)}' if agreement else 'inconnu'))
    print('ATTENTION : les annotations et le corpus sont exploratoires; pas de généralisation clinique.')

if __name__ == '__main__':
    main()
