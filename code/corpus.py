import os
import glob
from rank_bm25 import BM25Okapi
import re

class SupportCorpus:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.documents = []  # List of dicts: {"text": ..., "source": ...}
        self.indexed_tokens = []
        self.bm25 = None
        self._load_corpus()

    def _load_corpus(self):
        md_files = glob.glob(os.path.join(self.data_dir, "**/*.md"), recursive=True)
        for md_file in md_files:
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Split content by sections (e.g., # or ##)
                    sections = self._split_into_sections(content)
                    for section in sections:
                        if section.strip():
                            self.documents.append({
                                "text": section.strip(),
                                "source": os.path.relpath(md_file, self.data_dir)
                            })
            except Exception as e:
                print(f"Error reading {md_file}: {e}")

        # Tokenize for BM25
        self.indexed_tokens = [self._tokenize(doc["text"]) for doc in self.documents]
        if self.indexed_tokens:
            self.bm25 = BM25Okapi(self.indexed_tokens)

    def _split_into_sections(self, content):
        # A simple split by headers
        sections = re.split(r'\n(?=#+ )', content)
        return sections

    def _tokenize(self, text):
        # Simple tokenization: lowercase and alphanumeric
        return re.findall(r'\w+', text.lower())

    def search(self, query, top_n=5):
        if not self.bm25:
            return []
        
        tokenized_query = self._tokenize(query)
        docs = self.bm25.get_top_n(tokenized_query, self.documents, n=top_n)
        return docs

if __name__ == "__main__":
    # Test
    corpus = SupportCorpus("data")
    results = corpus.search("how to delete account")
    for res in results:
        print(f"Source: {res['source']}\nText: {res['text'][:200]}...\n")
