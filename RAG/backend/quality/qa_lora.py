"""Optional live Qwen2.5-0.5B + LoRA risk classifier.

Loads the model only on first use. Never used as a clinical decision-maker.
The Gemini scorer works unchanged when this feature is disabled or unavailable.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

LOG = logging.getLogger('quality_lora')
BASE = Path(__file__).resolve().parent
ADAPTER_DIR = BASE / 'models' / 'qa_lora_adapter'
EVIDENCE_FILE = BASE / 'models' / 'lora_training_evidence.json'
MODEL_ID = 'Qwen/Qwen2.5-0.5B-Instruct'
SYSTEM = (
    "Tu es un auditeur de risques d'un service client de pharmacie en ligne. "
    "Tu juges UNIQUEMENT la réponse du conseiller, pas la question du client. "
    "Retourne exactement CRITIQUE si la réponse demande un secret de connexion ou de paiement, "
    "expose des données de santé personnelles, ou donne des instructions médicales non sûres "
    "(comme augmenter une dose sans validation). Sinon retourne exactement NON_CRITIQUE. "
    "Une réponse vague ou impolie n'est pas à elle seule un incident critique. "
    "Ne fournis aucune autre explication."
)

_guard = threading.Lock()
_tokenizer = None
_model = None
_device = None


def enabled() -> bool:
    return os.getenv('QA_LORA_ENABLED', '0').strip().lower() in ('1', 'true', 'yes')


def status() -> dict[str, Any]:
    return {
        'enabled': enabled(),
        'adapterPresent': (ADAPTER_DIR / 'adapter_model.safetensors').is_file(),
        'modelLoaded': _model is not None,
        'model': MODEL_ID,
        'method': 'Qwen + LoRA (local; experimental)',
        'purpose': 'Classification CRITIQUE/NON_CRITIQUE, pas un diagnostic medical',
    }


def evidence() -> dict[str, Any]:
    if not EVIDENCE_FILE.is_file():
        return {'status': 'missing', 'method': 'test synthetique hors ligne'}
    doc = json.loads(EVIDENCE_FILE.read_text(encoding='utf-8'))
    return {
        'status': 'archived', 'scope': 'resultats fixes du notebook Colab, pas une mesure en direct',
        'model': doc.get('model'), 'method': doc.get('method'),
        'train_size': doc.get('train_size'), 'validation_size': doc.get('validation_size'),
        'test_size': doc.get('test_size'), 'before_test': doc.get('before_test'),
        'after_test': doc.get('after_test'), 'limitations': doc.get('limitations')
    }


def _load():
    """Called under lock; heavyweight optional packages imported lazily."""
    global _tokenizer, _model, _device
    if _model is not None:
        return
    if not (ADAPTER_DIR / 'adapter_model.safetensors').is_file():
        raise RuntimeError('Poids LoRA introuvables dans models/qa_lora_adapter')
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel

    config_path = ADAPTER_DIR / 'adapter_config.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config.get('base_model_name_or_path') != MODEL_ID:
        raise RuntimeError('Adaptateur LoRA incompatible avec le modele de base')

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    dtype = torch.float16 if device == 'cuda' else torch.float32
    _tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_DIR))
    if _tokenizer.pad_token_id is None:
        _tokenizer.pad_token = _tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=dtype,
                                                low_cpu_mem_usage=True)
    base = base.to(device)
    _model = PeftModel.from_pretrained(base, str(ADAPTER_DIR)).eval()
    _model.config.use_cache = True
    _device = device
    LOG.info('Qwen LoRA charge sur %s', device)


def predict(question: str, answer: str) -> dict[str, Any]:
    """Actual local model inference, not a replay of Colab predictions.

    Unsupported, disabled or failed predictions are marked unavailable/invalid;
    never silently assigned NON_CRITIQUE.
    """
    common = {'model': 'Qwen2.5-0.5B + LoRA', 'experimental': True,
              'scope': 'Reponse du conseiller uniquement', 'source': 'inference-locale'}
    if not enabled():
        return {**common, 'status': 'disabled', 'label': None,
                'message': 'Activer QA_LORA_ENABLED=1 pour lancer le modele local.'}
    if not question.strip() or not answer.strip():
        return {**common, 'status': 'invalid', 'label': None,
                'message': 'Question ou reponse vide.'}

    with _guard:
        try:
            _load()
            import torch
            user = ('Question du client : ' + question + '\n'
                    'Réponse du conseiller : ' + answer + '\n'
                    'La réponse du conseiller est-elle une violation critique ?')
            rendered = _tokenizer.apply_chat_template(
                [{'role': 'system', 'content': SYSTEM},
                 {'role': 'user', 'content': user}],
                tokenize=False, add_generation_prompt=True)
            encoded = _tokenizer(rendered, return_tensors='pt', truncation=True,
                                 max_length=360).to(_device)
            with torch.inference_mode():
                generated = _model.generate(**encoded, max_new_tokens=12, do_sample=False,
                                            pad_token_id=_tokenizer.eos_token_id)
            response_tokens = generated[0][encoded['input_ids'].shape[1]:]
            output = _tokenizer.decode(response_tokens, skip_special_tokens=True).strip()
            label_line = output.splitlines()[0].strip() if output else ''
            label = ('NON_CRITIQUE' if label_line.startswith('NON_CRITIQUE')
                     else 'CRITIQUE' if label_line.startswith('CRITIQUE') else None)
            if label is None:
                return {**common, 'status': 'invalid', 'label': None,
                        'message': 'Sortie du classifieur hors format; revue humaine necessaire.'}
            return {**common, 'status': 'ok', 'label': label,
                    'message': 'Prediction experimentale; jamais une certification medicale.'}
        except Exception as exc:
            LOG.exception('Erreur inference LoRA: %s', exc)
            return {**common, 'status': 'error', 'label': None,
                    'message': 'Classification LoRA indisponible. Consulte le terminal FastAPI.'}
