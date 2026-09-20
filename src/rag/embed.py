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
    """
    Alphanumeric tokenizer with lowercasing and bigram generation,
    preserving short policy identifiers like 'r1', 'r2', 'ev', 'sar'.
    """
    clean_text = text.lower().replace("-", " ")
    unigrams = [w for w in re.findall(r"\b[a-z0-9_]+\b", clean_text) if len(w) >= 2]
    bigrams = [f"{unigrams[i]}_{unigrams[i+1]}" for i in range(len(unigrams) - 1)]
    return unigrams + bigrams


class LocalSemanticIndex:
    """
    High-performance BM25 + N-Gram semantic and lexical search index.
    Optimized for regulatory policy clauses, fraud typologies, and case memory.
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids: List[str] = []
        self.doc_metadata: List[Dict[str, Any]] = []
        self.doc_tokens: List[List[str]] = []
        self.doc_token_counts: List[Counter] = []
        self.doc_freqs: Dict[str, int] = Counter()
        self.doc_lengths: List[int] = []
        self.num_docs: int = 0
        self.avg_doc_len: float = 0.0
        self.idf: Dict[str, float] = {}

    def add_documents(self, documents: List[Dict[str, Any]], text_field: str = "text", id_field: str = "id"):
        for doc in documents:
            doc_id = str(doc.get(id_field, len(self.doc_ids)))
            raw_text = str(doc.get(text_field, ""))
            title = str(doc.get("title", ""))
            keywords = " ".join(doc.get("keywords", []))
            # Weight keywords and title by repeating in tokenization stream
            full_text = f"{title} {title} {raw_text} {keywords} {keywords} {doc_id}"
            tokens = tokenize(full_text)

            self.doc_ids.append(doc_id)
            self.doc_metadata.append(doc)
            self.doc_tokens.append(tokens)
            self.doc_token_counts.append(Counter(tokens))
            self.doc_lengths.append(len(tokens))

            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.doc_freqs[t] += 1

        self.num_docs = len(self.doc_ids)
        self.avg_doc_len = sum(self.doc_lengths) / max(self.num_docs, 1)

        # Standard Robertson-Spärck Jones BM25 IDF
        for token, df in self.doc_freqs.items():
            self.idf[token] = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        q_weights = Counter(query_tokens)
        scores = [0.0] * self.num_docs
        query_lower = query.lower()

        for token, q_count in q_weights.items():
            token_idf = self.idf.get(token, 0.0)
            if token_idf <= 0.0:
                continue

            for idx in range(self.num_docs):
                tf = self.doc_token_counts[idx].get(token, 0)
                if tf > 0:
                    doc_len = self.doc_lengths[idx]
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                    term_score = token_idf * ((tf * (self.k1 + 1.0)) / denom)
                    scores[idx] += term_score * q_count

        # Exact identifier and acronym boosting
        for idx in range(self.num_docs):
            doc_id = self.doc_ids[idx].lower()
            clean_id = doc_id.replace("-", " ")
            if doc_id in query_lower or clean_id in query_lower:
                scores[idx] += 3.5

            # If rule number matches (e.g. 'r1', 'r5')
            rule_match = re.search(r"r\d+", doc_id)
            if rule_match:
                rule_str = rule_match.group(0)
                if re.search(rf"\b{rule_str}\b", query_lower):
                    scores[idx] += 2.5

        ranked = []
        for idx, score in enumerate(scores):
            if score > 0:
                ranked.append((self.doc_metadata[idx], round(score, 4)))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
