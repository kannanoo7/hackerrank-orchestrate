from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z0-9']+")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class Document:
    path: str
    company: str
    product_area: str
    title: str
    content: str
    tokens: tuple[str, ...]


class CorpusIndex:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.documents: list[Document] = []
        self.df: dict[str, int] = defaultdict(int)
        self.doc_token_counts: list[Counter[str]] = []
        self.avg_doc_len = 0.0
        self._load()

    def _detect_company(self, relative_path: str) -> str:
        if relative_path.startswith("hackerrank/"):
            return "HackerRank"
        if relative_path.startswith("claude/"):
            return "Claude"
        if relative_path.startswith("visa/"):
            return "Visa"
        return "None"

    def _detect_product_area(self, relative_path: str) -> str:
        parts = relative_path.split("/")
        if len(parts) <= 1:
            return "general_support"
        if parts[0] == "hackerrank":
            if len(parts) >= 3:
                return parts[1].replace("-", "_")
            return "general_support"
        if parts[0] == "claude":
            if len(parts) >= 3:
                return parts[1].replace("-", "_")
            return "general_support"
        if parts[0] == "visa":
            if len(parts) >= 4:
                return parts[2].replace("-", "_")
            if len(parts) >= 3:
                return parts[1].replace("-", "_")
            return "general_support"
        return "general_support"

    def _extract_title(self, text: str, fallback: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return normalize_text(line[2:])
            if line.startswith("title:"):
                return normalize_text(line.split(":", 1)[1].strip().strip('"'))
        return fallback

    def _load(self) -> None:
        md_files = sorted(self.data_dir.rglob("*.md"))
        for path in md_files:
            rel = path.relative_to(self.data_dir).as_posix()
            if rel.endswith("index.md"):
                continue
            raw = path.read_text(encoding="utf-8", errors="ignore")
            title = self._extract_title(raw, fallback=path.stem.replace("-", " "))
            content = normalize_text(raw)
            tokens = tuple(tokenize(f"{title} {content} {rel}"))
            if not tokens:
                continue
            document = Document(
                path=rel,
                company=self._detect_company(rel),
                product_area=self._detect_product_area(rel),
                title=title,
                content=content,
                tokens=tokens,
            )
            self.documents.append(document)
            token_counts = Counter(tokens)
            self.doc_token_counts.append(token_counts)
            for tok in token_counts:
                self.df[tok] += 1
        if self.documents:
            self.avg_doc_len = sum(len(doc.tokens) for doc in self.documents) / len(
                self.documents
            )

    def _idf(self, token: str) -> float:
        n_docs = max(1, len(self.documents))
        df = self.df.get(token, 0)
        return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    def search(self, query: str, company_hint: str | None = None, top_k: int = 3) -> list[Document]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        k1 = 1.2
        b = 0.75
        scored: list[tuple[float, int]] = []
        for idx, doc in enumerate(self.documents):
            if company_hint and company_hint in {"HackerRank", "Claude", "Visa"}:
                if doc.company != company_hint:
                    continue
            tf = self.doc_token_counts[idx]
            score = 0.0
            doc_len = len(doc.tokens)
            for tok in q_tokens:
                freq = tf.get(tok, 0)
                if freq <= 0:
                    continue
                idf = self._idf(tok)
                denom = freq + k1 * (1 - b + b * (doc_len / max(1e-9, self.avg_doc_len)))
                score += idf * ((freq * (k1 + 1)) / denom)
            if score > 0:
                scored.append((score, idx))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self.documents[idx] for _, idx in scored[:top_k]]
