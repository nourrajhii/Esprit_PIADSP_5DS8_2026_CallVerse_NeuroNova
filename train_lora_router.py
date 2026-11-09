#!/usr/bin/env python3
"""
Fine-tuning LoRA (PEFT) du routeur : message utilisateur -> JSON de routage.

Usage (GPU requis, ex. Colab T4 / Kaggle) :
    python train_lora_router.py                       # LoRA standard (fp16/bf16)
    python train_lora_router.py --qlora               # QLoRA 4 bits (si peu de VRAM, nécessite bitsandbytes)
    python train_lora_router.py --merge               # fusionne l'adaptateur dans le modèle à la fin

Sorties : models/router-lora/ (adaptateur LoRA + tokenizer), et models/router-merged/ avec --merge.
"""
import argparse
import json
import random
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq, Trainer,
                          TrainingArguments, set_seed)

from router_common import BASE_MODEL_DEFAULT


class RouterSFT(Dataset):
    """Masque la perte sur le prompt : seul le JSON de l'assistant est appris."""

    def __init__(self, path, tok, max_len):
        self.items = []
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            msgs = json.loads(line)["messages"]
            prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
            p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
            a_ids = tok(msgs[-1]["content"] + tok.eos_token, add_special_tokens=False)["input_ids"]
            ids = (p_ids + a_ids)[:max_len]
            labels = ([-100] * len(p_ids) + a_ids)[:max_len]
            self.items.append({"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels})

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.items[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base_model", default=BASE_MODEL_DEFAULT)
    ap.add_argument("--train", default="data/finetune/router_train.jsonl")
    ap.add_argument("--val", default="data/finetune/router_val.jsonl")
    ap.add_argument("--out", default="models/router-lora")
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--grad_accum", type=int, default=2)
    ap.add_argument("--max_len", type=int, default=512)
    ap.add_argument("--r", type=int, default=16, help="rang LoRA")
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--qlora", action="store_true", help="base quantifiée en 4 bits (QLoRA)")
    ap.add_argument("--merge", action="store_true", help="fusionne LoRA dans le modèle de base à la fin")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("Aucun GPU détecté : l'entraînement d'un modèle 1.5B sur CPU est impraticable. "
                         "Lance ce script sur Colab (GPU T4 gratuit) ou Kaggle.")
    set_seed(args.seed)
    random.seed(args.seed)

    use_bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if use_bf16 else torch.float16

    tok = AutoTokenizer.from_pretrained(args.base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    kw = {"torch_dtype": dtype, "device_map": {"": 0}}
    if args.qlora:
        from transformers import BitsAndBytesConfig
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
    model = AutoModelForCausalLM.from_pretrained(args.base_model, **kw)
    model.config.use_cache = False

    if args.qlora:
        model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.r, lora_alpha=args.alpha, lora_dropout=args.dropout, bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)
    if not use_bf16:  # fp16 : les poids entraînables doivent être en fp32 pour l'AMP
        for p in model.parameters():
            if p.requires_grad:
                p.data = p.data.float()
    model.print_trainable_parameters()

    train_ds = RouterSFT(args.train, tok, args.max_len)
    val_ds = RouterSFT(args.val, tok, args.max_len)
    print(f"train={len(train_ds)}  val={len(val_ds)}")

    targs = TrainingArguments(
        output_dir=args.out + "-checkpoints",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.0,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=use_bf16, fp16=not use_bf16,
        gradient_checkpointing=args.qlora,
        optim="paged_adamw_8bit" if args.qlora else "adamw_torch",
        report_to="none",
        seed=args.seed,
    )
    collator = DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8)
    trainer = Trainer(model=model, args=targs, train_dataset=train_ds, eval_dataset=val_ds, data_collator=collator)
    trainer.train()

    out = Path(args.out)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    (out / "base_model.txt").write_text(args.base_model, encoding="utf-8")
    print(f"Adaptateur LoRA sauvegardé dans {out}")

    if args.merge:
        # on recharge la base en pleine précision (pas en 4 bits) pour fusionner proprement
        from peft import PeftModel
        base = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype=dtype, device_map={"": 0})
        merged = PeftModel.from_pretrained(base, out).merge_and_unload()
        merged_dir = Path("models/router-merged")
        merged.save_pretrained(merged_dir)
        tok.save_pretrained(merged_dir)
        print(f"Modèle fusionné sauvegardé dans {merged_dir}")


if __name__ == "__main__":
    main()
