import random

from app.models import Client
from app.profiles import PROFILES


PRENOMS = [
    "Ahmed",
    "Mohamed",
    "Yassine",
    "Amine",
    "Sami",
    "Nour",
    "Mariem",
    "Sarra",
    "Ines",
    "Aya"
]

NOMS = [
    "Ben Ali",
    "Trabelsi",
    "Mansouri",
    "Gharbi",
    "Jaziri",
    "Haddad",
    "Khalfallah",
    "Mejri"
]

VILLES = [
    "Tunis",
    "Ariana",
    "Ben Arous",
    "Manouba",
    "Sousse",
    "Sfax",
    "Nabeul",
    "Bizerte"
]


def generate_client(client_id: int) -> Client:
    prenom = random.choice(PRENOMS)
    nom = random.choice(NOMS)
    age = random.randint(18, 75)
    ville = random.choice(VILLES)
    profil = random.choice(list(PROFILES.keys()))

    return Client(
        id=client_id,
        prenom=prenom,
        nom=nom,
        age=age,
        ville=ville,
        profil=profil
    )


def generate_clients(number: int) -> list[Client]:
    clients = []

    for client_id in range(1, number + 1):
        client = generate_client(client_id)
        clients.append(client)

    return clients