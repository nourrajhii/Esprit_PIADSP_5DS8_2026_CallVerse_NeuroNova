from dataclasses import dataclass


@dataclass
class Client:
    id: int
    prenom: str
    nom: str
    age: int
    ville: str
    

    profil: str
  