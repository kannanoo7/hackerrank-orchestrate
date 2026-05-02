"""
Corpus builder for support documentation.
Loads, indexes, and manages support corpus from markdown files.
"""
import os
import json
import re
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CorpusBuilder:
    """Builds and manages support documentation corpus."""
    
    def __init__(self, data_dir: str, cache_dir: str = None):
        """
        Initialize corpus builder.
        
        Args:
            data_dir: Path to data directory with markdown files
            cache_dir: Optional path for caching scraped web content
        """
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(cache_dir or self.data_dir.parent / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.corpus = []
        
        logger.info(f"Corpus Builder initialized")
        logger.info(f"  Data directory: {self.data_dir}")
        logger.info(f"  Cache directory: {self.cache_dir}")

    def build_corpus(self) -> List[Dict]:
        """
        Build complete corpus from markdown files.
        
        Returns:
            List of document dicts with metadata and content
        """
        logger.info("\nBuilding corpus from markdown files...")
        self.corpus = []
        
        # Load all markdown files
        self._load_markdown_files()
        logger.info(f"✓ Loaded {len(self.corpus)} documents from markdown files")
        
        # Optionally enrich with external links (set to False for production)
        # self._enrich_with_external_links()
        
        return self.corpus

    def _load_markdown_files(self) -> None:
        """Load all markdown files from data directory."""
        if not self.data_dir.exists():
            logger.warning(f"Data directory not found: {self.data_dir}")
            return
        
        for root, _, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith(".md"):
                    if file == "index.md":
                        continue  # Skip index files
                    
                    file_path = Path(root) / file
                    try:
                        doc = self._load_markdown_file(file_path)
                        if doc:
                            self.corpus.append(doc)
                    except Exception as e:
                        logger.warning(f"Failed to load {file_path}: {e}")

    def _load_markdown_file(self, file_path: Path) -> Optional[Dict]:
        """Load and parse a single markdown file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata
            company, category = self._get_metadata(file_path)
            
            # Parse frontmatter
            frontmatter, md_content = self._extract_frontmatter(content)
            
            # Clean content
            md_content = self._remove_related_articles(md_content)
            extracted_links = self._extract_links(md_content)
            clean_text = self._clean_markdown(md_content)
            
            # Extract article ID
            filename = file_path.name
            article_id = filename.split("-")[0] if "-" in filename else filename.replace(".md", "")
            
            return {
                "id": article_id,
                "title": frontmatter.get("title", ""),
                "content": clean_text,
                "links": extracted_links,
                "source_url": frontmatter.get("source_url"),
                "company": company,
                "category": category,
                "type": "local",
                "path": str(file_path.relative_to(self.data_dir))
            }
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None

    def _extract_frontmatter(self, md_text: str) -> tuple[Dict, str]:
        """Extract YAML frontmatter from markdown."""
        frontmatter = {}
        
        match = re.match(r"---(.*?)---", md_text, re.DOTALL)
        if match:
            yaml_text = match.group(1)
            
            for line in yaml_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip().strip('"')
            
            md_text = md_text[match.end():]
        
        return frontmatter, md_text

    def _remove_related_articles(self, md_text: str) -> str:
        """Remove 'Related Articles' section."""
        return re.split(r"## Related Articles", md_text)[0]

    def _extract_links(self, md_text: str) -> List[str]:
        """Extract URLs from markdown."""
        raw_links = re.findall(r"https?://[^\s)]+", md_text)
        cleaned_links = []
        
        for url in raw_links:
            url = url.rstrip(").,]")
            cleaned_links.append(url)
        
        return cleaned_links

    def _clean_markdown(self, md_text: str) -> str:
        """Clean markdown formatting."""
        md_text = re.sub(r"```.*?```", "", md_text, flags=re.DOTALL)
        md_text = re.sub(r"`.*?`", "", md_text)
        md_text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", md_text)
        md_text = re.sub(r"!\[.*?\]\(.*?\)", "", md_text)
        md_text = re.sub(r"#+\s*", "", md_text)
        md_text = re.sub(r"[*_]", "", md_text)
        md_text = re.sub(r"\n+", "\n", md_text)
        return md_text.strip()

    def _get_metadata(self, file_path: Path) -> tuple[str, str]:
        """Extract company and category from file path."""
        rel_path = file_path.relative_to(self.data_dir)
        parts = rel_path.parts
        
        company = parts[0] if len(parts) > 0 else "unknown"
        category = parts[1] if len(parts) > 1 else "root"
        
        return company, category

    def _enrich_with_external_links(self) -> None:
        """Optionally enrich corpus with external link content."""
        logger.info("\nEnriching corpus with external links...")
        new_docs = []
        
        for doc in self.corpus:
            for link in doc.get("links", []):
                if not link.startswith("http"):
                    continue
                
                try:
                    content = self._scrape_webpage(link)
                    if content:
                        new_docs.append({
                            "id": f"{doc['id']}_ext_{abs(hash(link)) % 100000}",
                            "title": f"External: {link}",
                            "content": content[:5000],
                            "source_url": link,
                            "company": doc["company"],
                            "category": "external",
                            "type": "external"
                        })
                except Exception as e:
                    logger.debug(f"Failed to scrape {link}: {e}")
        
        self.corpus.extend(new_docs)
        logger.info(f"✓ Added {len(new_docs)} external documents")

    def _scrape_webpage(self, url: str) -> Optional[str]:
        """Scrape webpage with caching."""
        cache_path = self._get_cache_path(url)
        
        # Check cache
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove noise
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            
            text = soup.get_text(separator="\n")
            
            # Clean whitespace
            lines = [line.strip() for line in text.split("\n")]
            text = "\n".join([line for line in lines if line])
            
            # Save cache
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            return text
        except Exception as e:
            logger.debug(f"Failed to scrape {url}: {e}")
            return None

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        name = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{name}.txt"

    def save_corpus(self, output_file: str) -> None:
        """Save corpus to JSON file."""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.corpus, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved corpus to {output_file}")

    def get_corpus_stats(self) -> Dict:
        """Get corpus statistics."""
        stats = {
            "total_documents": len(self.corpus),
            "by_company": {},
            "by_type": {}
        }
        
        for doc in self.corpus:
            company = doc.get("company", "unknown")
            doc_type = doc.get("type", "unknown")
            
            stats["by_company"][company] = stats["by_company"].get(company, 0) + 1
            stats["by_type"][doc_type] = stats["by_type"].get(doc_type, 0) + 1
        
        return stats


def build_corpus_for_lifecycle(data_dir: str = None, cache_dir: str = None) -> Dict:
    """
    Convenience function to build corpus for use in agent lifecycle.
    
    Args:
        data_dir: Path to data directory
        cache_dir: Optional cache directory
        
    Returns:
        Dict with corpus stats and builder instance
    """
    if data_dir is None:
        data_dir = str(Path(__file__).parent.parent / "data")
    
    builder = CorpusBuilder(data_dir, cache_dir)
    corpus = builder.build_corpus()
    stats = builder.get_corpus_stats()
    
    logger.info("\nCorpus Build Summary:")
    logger.info(f"  Total documents: {stats['total_documents']}")
    for company, count in stats.get("by_company", {}).items():
        logger.info(f"  {company}: {count} documents")
    
    return {
        "builder": builder,
        "corpus": corpus,
        "stats": stats
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example: Build corpus
    result = build_corpus_for_lifecycle()
    print(json.dumps(result["stats"], indent=2))
