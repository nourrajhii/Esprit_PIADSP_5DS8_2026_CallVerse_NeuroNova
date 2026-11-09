"""
Routeur local fine-tuné (LoRA). Utilisé par agent.py quand ROUTER_LORA_PATH est défini dans .env.
Renvoie None si la sortie est invalide -> agent.py retombe alors sur le routeur LLM (Groq/Gemini).
"""
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from router_common import BASE_MODEL_DEFAULT, build_messages, parse_route


class LocalRouter:
    def __init__(self, path, base_model=None):
        path = Path(path)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.tok = AutoTokenizer.from_pretrained(path)
        is_adapter = (path / "adapter_config.json").exists()
        if is_adapter:  # adaptateur LoRA : base + PEFT
            from peft import PeftModel
            bm_file = path / "base_model.txt"
            bm = base_model or (bm_file.read_text(encoding="utf-8").strip() if bm_file.exists() else BASE_MODEL_DEFAULT)
            model = AutoModelForCausalLM.from_pretrained(bm, torch_dtype=dtype)
            model = PeftModel.from_pretrained(model, path).merge_and_unload()  # fusion en mémoire : inférence plus rapide
        else:  # modèle déjà fusionné (models/router-merged)
            model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=dtype)
        self.model = model.to(self.device).eval()

    @torch.no_grad()
    def route_raw(self, message, max_new_tokens=160):
        prompt = self.tok.apply_chat_template(build_messages(message), tokenize=False, add_generation_prompt=True)
        enc = self.tok(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)
        out = self.model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                  pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
        return self.tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)

    def route(self, message):
        return parse_route(self.route_raw(message))
