"""Apply a narrow LLM Judge schema fix from the project root.

Only replaces quality-backend/qa_judge.py after verifying a known pristine
previous version. Makes a local backup. No network, no API key required.
"""
from pathlib import Path
from datetime import datetime
from hashlib import sha256
import shutil
import sys

ROOT = Path(__file__).resolve().parent
OLD_SHA256 = '9bd7523365557572ea7475cd569ea3031e577bfe4e8d0ae2471ec96155de7669'
NEW_SHA256 = 'eb0d5ca002f1f616a2ff25c4c425c4b4a3e7e8846bec979f2d8820e47670160f'


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def main() -> int:
    source = ROOT / 'correctif_judge_json' / 'quality-backend' / 'qa_judge.py'
    test_source = ROOT / 'correctif_judge_json' / 'tests' / 'test_schema_fix.py'
    target = ROOT / 'quality-backend' / 'qa_judge.py'
    test_target = ROOT / 'quality-backend' / 'tests' / 'test_schema_fix.py'
    if not (ROOT / 'package.json').is_file() or not target.is_file():
        print('ERREUR : lance le script depuis la racine Twinly contenant package.json.'); return 1
    if not source.exists() or digest(source.read_bytes()) != NEW_SHA256:
        print('ERREUR : correctif manquant ou modifié.'); return 1
    current = digest(target.read_bytes())
    if current == NEW_SHA256:
        print('Déjà installé : aucun changement nécessaire.'); return 0
    if current != OLD_SHA256:
        print('ATTENTION : qa_judge.py a été modifié depuis notre correctif précédent.')
        print('Aucun fichier remplacé. Conserver ce fichier et demander une fusion adaptée.'); return 2
    backups = ROOT / 'qa_judge_backup' / datetime.now().strftime('%Y%m%d_%H%M%S')
    backups.mkdir(parents=True, exist_ok=False)
    shutil.copy2(target, backups / 'qa_judge.py')
    shutil.copy2(source, target)
    if test_source.is_file() and not test_target.exists():
        shutil.copy2(test_source, test_target)
    print('PATCH OK : quality-backend/qa_judge.py')
    print('Sauvegarde :', backups)
    print('Aucun changement dans Gemini principal, Qwen-LoRA, React ou autres agents.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
