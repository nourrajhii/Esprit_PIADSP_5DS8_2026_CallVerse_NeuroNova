"""Tester une conversation enchaînée dans le terminal : TU joues le conseiller.

python -m evaluation.test_conversation --profil impatient --urgence haute --n 5 --model qwen-client-v2 --model-suite qwen2.5:7b
"""
import argparse

import app.llm_service as llm
from app import conversation
from app.client_generator import generate_client

parser = argparse.ArgumentParser()
parser.add_argument("--profil", default="impatient")
parser.add_argument("--sujet", default="prendre un rendez-vous chez un médecin généraliste")
parser.add_argument("--urgence", default="haute", choices=["basse", "moyenne", "haute"])
parser.add_argument("--n", type=int, default=3, choices=[1, 2, 3, 4, 5], help="nombre de messages du client")
parser.add_argument("--model", default=None, help="modèle du 1er message (défaut : OLLAMA_MODEL du .env)")
parser.add_argument("--model-suite", default=None, help="modèle des messages 2 à 5 (défaut : le même)")
args = parser.parse_args()

if args.model:
    llm.MODEL_NAME = args.model
if args.model_suite:
    llm.MODEL_SUITE = args.model_suite

client = generate_client(1)
client.profil = args.profil
conv = conversation.demarrer(client, args.sujet, args.urgence, None, args.n)
print(f"\n[{client.prenom} {client.nom}, {client.age} ans, {args.profil}, urgence {args.urgence}, {args.n} messages]")
print(f"[1er message : {llm.MODEL_NAME} | suite : {llm.MODEL_SUITE or llm.MODEL_NAME}]\n")
print(f"CLIENT 1 : {conversation.etat(conv)['message']}")

while not conversation.etat(conv)["done"]:
    reponse = input("\nCONSEILLER (toi) : ")
    e = conversation.etat(conversation.repondre(conv, reponse))
    print(f"\nCLIENT {e['turn']} : {e['message']}")
print("\n=== fin de la conversation ===")
