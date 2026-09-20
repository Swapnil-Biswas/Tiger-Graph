"""
Vector Embedding & Semantic Indexing Module (GraphRAG)
Computes and indexes embeddings for policy chunks, regulatory standards,
and historical closed cases memory. Supports Gemini embeddings with high-speed
local TF-IDF / cosine fallback.
"""

import os
import sys
import math
import re
from collections import Counter
from typing import List, Dict, Any, Tuple


def tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer with lowercasing."""
    return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 2]


class LocalSemanticIndex:
    """
    High-speed, memory-efficient TF-IDF semantic search index.
    """

    def __init__(self):
        self.doc_ids: List[str] = []
        self.doc_metadata: List[Dict[str, Any]] = []
        self.doc_tokens: List[List[str]] = []
        self.doc_freqs: Dict[str, int] = Counter()
        self.num_docs: int = 0
        self.idf: Dict[str, float] = {}

    def add_documents(self, documents: List[Dict[str, Any]], text_field: str = "text", id_field: str = "id"):
        for doc in documents:
            doc_id = str(doc.get(id_field, len(self.doc_ids)))
            raw_text = str(doc.get(text_field, ""))
            keywords = " ".join(doc.get("keywords", []))
            full_text = f"{raw_text} {keywords}"
            tokens = tokenize(full_text)

            self.doc_ids.append(doc_id)
            self.doc_metadata.append(doc)
            self.doc_tokens.append(tokens)

            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.doc_freqs[t] += 1

        self.num_docs = len(self.doc_ids)
        # Compute IDF
        for token, df in self.doc_freqs.items():
            self.idf[token] = math.log((self.num_docs + 1) / (df + 1)) + 1.0

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        q_weights = Counter(query_tokens)
        scores = [0.0] * self.num_docs

        for token, q_count in q_weights.items():
            token_idf = self.idf.get(token, 0.0)
            if token_idf <= 0:
                continue

            for idx, doc_toks in enumerate(self.doc_tokens):
                tf = doc_toks.count(token)
                if tf > 0:
                    tf_score = 1.0 + math.log(tf)
                    scores[idx] += tf_score * token_idf * q_count

        # Normalize by doc length
        ranked = []
        for idx, score in enumerate(scores):
            if score > 0:
                doc_len = max(len(self.doc_tokens[idx]), 1)
                norm_score = score / math.sqrt(doc_len)
                ranked.append((self.doc_metadata[idx], round(norm_score, 4)))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
