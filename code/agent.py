"""
Unified Support Triage Agent - Production Ready
Integrates corpus building, LLM-powered triage, and ticket processing into a single lifecycle.
"""
import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from corpus import CorpusManager
from triage_agent import TriageAgent

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupportTriageAgent:
    """
    Unified support triage agent that orchestrates the entire lifecycle:
    1. Corpus initialization and management
    2. LLM-powered decision making (escalation & product area)
    3. Response generation with corpus grounding
    """
    
    def __init__(self, data_dir: str = None, api_key: Optional[str] = None):
        """
        Initialize the unified support triage agent.
        
        Args:
            data_dir: Path to data directory with support corpus
            api_key: Optional Anthropic API key (falls back to env var)
        """
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.corpus = None
        self.triage = None
        self.api_key = api_key
        
        logger.info("=" * 60)
        logger.info("Support Triage Agent - Initialization")
        logger.info("=" * 60)
        
        # Step 1: Initialize corpus
        self._initialize_corpus()
        
        # Step 2: Initialize triage agent with LLM
        self._initialize_triage_agent()
        
        logger.info("✓ Agent fully initialized and ready")
        logger.info("=" * 60)

    def _initialize_corpus(self) -> None:
        """Initialize corpus manager and load documentation."""
        try:
            logger.info(f"\n1. Loading support corpus from: {self.data_dir}")
            
            if not self.data_dir.exists():
                raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
            
            self.corpus = CorpusManager(str(self.data_dir))
            
            companies = self.corpus.get_companies()
            logger.info(f"   ✓ Loaded {len(companies)} company corpora: {', '.join(companies)}")
            
            for company in companies:
                try:
                    areas = self.corpus.get_product_areas(company)
                    doc_count = len(self.corpus.corpus.get(company, {}))
                    logger.info(f"     - {company}: {doc_count} documents, {len(areas)} product areas")
                except Exception as e:
                    logger.warning(f"     - {company}: Error loading metadata - {e}")
            
        except Exception as e:
            logger.error(f"Failed to initialize corpus: {e}", exc_info=True)
            raise

    def _initialize_triage_agent(self) -> None:
        """Initialize LLM-powered triage agent."""
        try:
            logger.info(f"\n2. Initializing triage agent (LLM-powered)...")
            
            self.triage = TriageAgent(self.corpus, api_key=self.api_key)
            
            logger.info(f"   ✓ Agent initialized")
            logger.info(f"   ✓ LLM Model: {self.triage.model_type}")
            logger.info(f"   ✓ Escalation categories: {len(self.triage.ESCALATION_KEYWORDS)}")
            logger.info(f"   ✓ Request types: {', '.join(self.triage.REQUEST_TYPES)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize triage agent: {e}", exc_info=True)
            raise

    def process_ticket(self, issue: str, subject: str = "", company: str = None) -> Dict:
        """
        Process a single support ticket through the complete lifecycle.
        
        Args:
            issue: The support ticket issue text
            subject: The ticket subject/title
            company: The company (claude, hackerrank, or visa)
            
        Returns:
            Dict with complete triage decision and response
        """
        if not self.triage:
            raise RuntimeError("Triage agent not initialized")
        
        try:
            return self.triage.process_ticket(issue, subject, company)
        except Exception as e:
            logger.error(f"Error processing ticket: {e}")
            return {
                'status': 'escalated',
                'product_area': 'unknown',
                'response': 'Error processing request. Escalating to support team.',
                'justification': f"Processing error: {str(e)[:100]}",
                'request_type': 'product_issue'
            }

    def batch_process_tickets(self, tickets: List[Dict]) -> List[Dict]:
        """
        Process multiple tickets in batch.
        
        Args:
            tickets: List of ticket dicts with 'Issue', 'Subject', 'Company' keys
            
        Returns:
            List of processed tickets with decisions and responses
        """
        results = []
        for i, ticket in enumerate(tickets, 1):
            logger.debug(f"Processing ticket {i}/{len(tickets)}")
            issue = str(ticket.get("Issue", "")).strip()
            subject = str(ticket.get("Subject", "")).strip()
            company = str(ticket.get("Company", "")).strip()
            
            result = self.process_ticket(issue, subject, company)
            results.append({**ticket, **result})
        
        return results

    def get_stats(self) -> Dict:
        """Get corpus and agent statistics."""
        if not self.corpus or not self.triage:
            return {}
        
        stats = {
            "corpus": {
                "companies": self.corpus.get_companies(),
            },
            "agent": {
                "model": self.triage.model_type,
                "escalation_categories": list(self.triage.ESCALATION_KEYWORDS.keys()),
                "request_types": self.triage.REQUEST_TYPES,
            }
        }
        
        for company in stats["corpus"]["companies"]:
            try:
                areas = self.corpus.get_product_areas(company)
                doc_count = len(self.corpus.corpus.get(company, {}))
                stats["corpus"][company] = {
                    "documents": doc_count,
                    "product_areas": areas
                }
            except Exception as e:
                logger.warning(f"Error getting stats for {company}: {e}")
        
        return stats


# Legacy support: Maintain agent.py as alias to SupportTriageAgent
class Agent(SupportTriageAgent):
    """Legacy Agent class - alias for SupportTriageAgent."""
    pass


if __name__ == "__main__":
    # Example usage
    try:
        # Initialize agent
        agent = SupportTriageAgent()
        
        # Get stats
        stats = agent.get_stats()
        print("\nAgent Statistics:")
        print(json.dumps(stats, indent=2))
        
        # Process sample ticket
        sample_ticket = {
            "Issue": "I cannot login to my Claude account",
            "Subject": "Login issue",
            "Company": "claude"
        }
        
        logger.info("\n3. Processing sample ticket...")
        result = agent.process_ticket(
            sample_ticket["Issue"],
            sample_ticket["Subject"],
            sample_ticket["Company"]
        )
        
        print("\nSample Ticket Result:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)
