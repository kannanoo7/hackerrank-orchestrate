import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
from rank_bm25 import BM25Okapi


class CorpusManager:
    """Manages support documentation across multiple companies using index.md metadata."""
    
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.corpus = {}  # {company: {doc_id: content}}
        self.bm25_indexes = {}  # {company: BM25Okapi}
        self.doc_mappings = {}  # {company: {doc_id: path}}
        self.index_metadata = {}  # {company: parsed index structure}
        self.company_product_areas = {}  # {company: [product_areas]}
        self.load_corpus()

    def parse_index_md(self, company: str, index_path: Path) -> Dict:
        """Parse index.md to extract metadata about product areas and categories."""
        metadata = {}
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            sections = []
            
            for line in lines:
                line = line.strip()
                # Detect sections (## or ###)
                if line.startswith('##'):
                    if line.startswith('###'):
                        section_name = line.replace('###', '').strip()
                    else:
                        section_name = line.replace('##', '').strip()
                    if section_name and section_name not in ['Root', 'Home']:
                        if section_name not in sections:
                            sections.append(section_name)
            
            metadata['sections'] = sections
            metadata['total_sections'] = len(sections)
        except Exception as e:
            print(f"Error parsing index.md for {company}: {e}")
        
        return metadata

    def load_corpus(self):
        """Load support documentation from all companies using index.md as metadata."""
        for company in ['claude', 'hackerrank', 'visa']:
            company_path = self.data_dir / company
            if company_path.exists():
                # Parse index.md first for metadata
                index_path = company_path / 'index.md'
                if index_path.exists():
                    self.index_metadata[company] = self.parse_index_md(company, index_path)
                
                # Load all markdown documents
                self._load_company_docs(company, company_path)

    def _load_company_docs(self, company: str, company_path: Path):
        """Load all markdown files for a company, indexed by relative path."""
        docs = []
        doc_paths = {}
        product_areas = set()
        
        for md_file in sorted(company_path.rglob('*.md')):
            # Skip index files
            if md_file.name == 'index.md':
                continue
            
            try:
                with open(md_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if content.strip():  # Only add non-empty files
                        doc_id = len(docs)
                        docs.append(content)
                        rel_path = str(md_file.relative_to(company_path))
                        doc_paths[doc_id] = rel_path
                        
                        # Extract product area from path
                        parts = rel_path.split('/')
                        if len(parts) > 1:
                            product_areas.add(parts[0])
            except Exception as e:
                print(f"Warning: Error loading {md_file}: {e}")
        
        # Create BM25 index for faster retrieval
        if docs:
            tokenized = [self._tokenize(doc) for doc in docs]
            self.bm25_indexes[company] = BM25Okapi(tokenized)
            self.corpus[company] = docs
            self.doc_mappings[company] = doc_paths
            self.company_product_areas[company] = sorted(list(product_areas))

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase and split on whitespace."""
        # Remove markdown syntax
        text = re.sub(r'[#*_\[\](){}]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        tokens = text.lower().split()
        return [t for t in tokens if len(t) > 2]  # Filter short tokens

    def retrieve(self, company: str, query: str, top_k: int = 3) -> List[Dict]:
        """Retrieve top-k relevant documents for a query from a specific company corpus."""
        if company not in self.bm25_indexes:
            return []
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        bm25 = self.bm25_indexes[company]
        scores = bm25.get_scores(query_tokens)
        
        # Get top-k indices by score
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    'doc_id': idx,
                    'content': self.corpus[company][idx][:2000],  # Truncate for context
                    'path': self.doc_mappings[company].get(idx, ''),
                    'score': float(scores[idx])
                })
        
        return results

    def get_product_areas(self, company: str) -> List[str]:
        """Get list of product areas for a company."""
        return self.company_product_areas.get(company, [])

    def get_companies(self) -> List[str]:
        """Get list of available companies."""
        return list(self.corpus.keys())

    def search_by_category(self, company: str, category: str, query: str, top_k: int = 2) -> List[Dict]:
        """Search within a specific category for more targeted retrieval."""
        if company not in self.corpus:
            return []
        
        # Filter docs by category in path
        category_docs = []
        category_indices = []
        
        for doc_id, path in self.doc_mappings.get(company, {}).items():
            if category.lower() in path.lower():
                category_docs.append(self.corpus[company][doc_id])
                category_indices.append(doc_id)
        
        if not category_docs:
            return self.retrieve(company, query, top_k)
        
        # BM25 search within category
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        tokenized = [self._tokenize(doc) for doc in category_docs]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(query_tokens)
        
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        
        for idx in top_indices:
            if scores[idx] > 0:
                actual_id = category_indices[idx]
                results.append({
                    'doc_id': actual_id,
                    'content': category_docs[idx][:2000],
                    'path': self.doc_mappings[company].get(actual_id, ''),
                    'score': float(scores[idx])
                })
        
        return results
