from __future__ import annotations

import math
import re
from collections import Counter


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_'-]*")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "change",
    "changed",
    "for",
    "from",
    "give",
    "in",
    "is",
    "it",
    "list",
    "of",
    "on",
    "or",
    "show",
    "summarize",
    "that",
    "the",
    "tell",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}

SYNONYMS = {
    "approval": {"authorization", "signoff", "approve", "approved"},
    "asset": {"hardware", "software", "inventory", "equipment"},
    "audit": {"review", "inspection", "trail", "compliance"},
    "backup": {"restore", "recovery", "snapshot"},
    "breach": {"incident", "exposure", "compromise"},
    "certificate": {"tls", "ssl", "renewal", "expiry"},
    "compliance": {"gdpr", "regulatory", "regulation", "control"},
    "contract": {"agreement", "sla", "renewal", "vendor"},
    "customer": {"client", "account"},
    "employee": {"staff", "worker", "personnel", "hire"},
    "infrastructure": {"server", "cloud", "network", "migration"},
    "legal": {"contract", "counsel", "agreement", "liability"},
    "payment": {"invoice", "vendor", "payable"},
    "payroll": {"compensation", "salary", "wages"},
    "penetration": {"pentest", "vulnerability", "exploit", "finding"},
    "policy": {"procedure", "guideline", "benefit"},
    "revenue": {"income", "earnings", "sales", "forecast"},
    "security": {"soc", "alert", "identity", "access"},
    "travel": {"geo", "location", "impossible"},
    "vendor": {"supplier", "third-party", "procurement"},
}


def tokenize(text: str) -> list[str]:
    normalized_text = text.replace("_", " ").replace("-", " ")
    tokens: list[str] = []
    for raw_token in TOKEN_RE.findall(normalized_text):
        token = _normalize_token(raw_token)
        if token not in STOPWORDS and len(token) > 1:
            tokens.append(token)
    return tokens


def _normalize_token(token: str) -> str:
    token = token.lower().strip("'")
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def expand_query_terms(tokens: list[str]) -> set[str]:
    expanded = set(tokens)
    for token in tokens:
        expanded.update(SYNONYMS.get(token, set()))
        for root, variants in SYNONYMS.items():
            if token in variants:
                expanded.add(root)
                expanded.update(variants)
    return expanded


def term_counts(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def cosine_score(query_terms: set[str], doc_counts: Counter[str]) -> float:
    if not query_terms or not doc_counts:
        return 0.0
    overlap = sum(doc_counts.get(term, 0) for term in query_terms)
    doc_norm = math.sqrt(sum(count * count for count in doc_counts.values()))
    query_norm = math.sqrt(len(query_terms))
    return overlap / (doc_norm * query_norm)


def first_matching_sentence(text: str, query_terms: set[str], fallback_chars: int = 220) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    best_sentence = ""
    best_score = 0
    for sentence in sentences:
        sentence_terms = set(tokenize(sentence))
        score = len(sentence_terms & query_terms)
        if score > best_score:
            best_sentence = sentence
            best_score = score
    if best_sentence:
        return best_sentence[:fallback_chars].strip()
    return text.strip()[:fallback_chars]


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> list[str]:
    """Split text into overlapping chunks of approximately *chunk_size* words.

    Returns at least one chunk.  Overlap lets context bleed across boundaries
    so retrieval does not miss sentences that span a split point.
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
        if start >= len(words):
            break
    return chunks
