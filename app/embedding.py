
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

model = SentenceTransformer(MODEL_NAME)


def generate_embedding(text: str) -> list[float]:
    """Transforme un texte en vecteur numérique."""
    embedding = model.encode(
        text,
        normalize_embeddings=True
    )

    return embedding.tolist()


def compare_similarity(text1: str, text2: str) -> float:
    """Calcule la similarité sémantique entre deux textes."""
    embedding1 = generate_embedding(text1)
    embedding2 = generate_embedding(text2)

    score = cosine_similarity(
        [embedding1],
        [embedding2]
    )[0][0]

    return float(score)
