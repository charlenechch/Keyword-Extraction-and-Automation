from typing import List, Dict
import re
import numpy as np

from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from .category_loader import Category

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOP = {
    "training", "program", "course", "workplace", "roles", "role", "employee", "staff",
    "learn", "learning", "session", "module", "participants", "skills", "skill", "basic",
    "introduction", "overview", "using", "use", "management", "development"
}


def tokenize(text: str) -> List[str]:
    toks = _TOKEN_RE.findall((text or "").lower())
    # CHANGE: Changed len(t) > 2 to len(t) >= 2 to allow "AI"
    return [t for t in toks if t not in STOP and len(t) >= 2]

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


class CategoryIndex:
    def __init__(self, categories: List[Category], model_name: str = "all-MiniLM-L6-v2"):
        self.categories = categories
        self.model = SentenceTransformer(model_name)

        # BM25 corpus
        self.cat_blobs = [c.blob for c in categories]
        self.cat_tokens = [tokenize(t) for t in self.cat_blobs]
        self.bm25 = BM25Okapi(self.cat_tokens)

        # Embeddings
        self.cat_vecs = self.model.encode(self.cat_blobs, normalize_embeddings=True)

    def retrieve_topk(self, brochure_text: str, k: int = 5, bm25_pool: int = 40, sim_pool: int = 60) -> List[Dict]:
        """
        UNION pool retrieval:
          - BM25 pool for exact match recall
          - embedding pool for semantic recall
          - union then rerank by mostly semantic score
        """
        q_tokens = tokenize(brochure_text)
        bm25_scores = np.array(self.bm25.get_scores(q_tokens), dtype=float)

        # BM25 pool
        bm25_idx = np.argsort(-bm25_scores)[:min(bm25_pool, len(self.categories))]

        # Embedding pool
        bro_vec = self.model.encode([brochure_text], normalize_embeddings=True)[0]
        sims_all = np.array([cosine(bro_vec, v) for v in self.cat_vecs], dtype=float)
        sim_idx = np.argsort(-sims_all)[:min(sim_pool, len(self.categories))]

        # UNION pool
        pool_idx = np.array(sorted(set(bm25_idx.tolist()) | set(sim_idx.tolist())), dtype=int)

        # Normalize BM25 within pool
        pool_bm25 = bm25_scores[pool_idx]
        pool_bm25_norm = pool_bm25 / pool_bm25.max() if pool_bm25.max() > 0 else pool_bm25

        pool_sims = sims_all[pool_idx]

        # Mostly semantic
        combo = 0.15 * pool_bm25_norm + 0.85 * pool_sims

        order = np.argsort(-combo)[:k]
        out = []
        for j in order:
            i = int(pool_idx[j])
            c = self.categories[i]
            out.append({
                "domain": c.domain,
                "category": c.name,
                "score": float(combo[j]),
                "sim": float(pool_sims[j]),
                "bm25": float(pool_bm25_norm[j]),
                "blob": c.blob
            })
        return out
