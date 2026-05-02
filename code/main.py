"""
Complete lifecycle orchestrator for support ticket triage.
Integrates: Corpus Building → Agent Initialization → Ticket Processing
"""
import os
import sys
import logging
import pandas as pd
from pathlib import Path
from typing import Optional
import argparse
from tqdm import tqdm

from agent import SupportTriageAgent
from build_corpus import build_corpus_for_lifecycle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TriageAgentLifecycle:
    """
    Complete lifecycle manager for support ticket triage.
    Orchestrates: Corpus Building → Agent Init → Batch Processing → Output Generation
    """
    
    def __init__(self, data_dir: str = None, api_key: Optional[str] = None):
        """Initialize the complete lifecycle."""
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.api_key = api_key
        self.agent = None
        self.corpus_info = None
        
    def initialize(self) -> bool:
        """Initialize the complete lifecycle."""
        logger.info("=" * 70)
        logger.info("SUPPORT TICKET TRIAGE - COMPLETE LIFECYCLE")
        logger.info("=" * 70)
        
        try:
            # Step 1: Build/Verify Corpus
            logger.info("\n[STEP 1/3] Corpus Initialization")
            self._initialize_corpus()
            
            # Step 2: Initialize Agent
            logger.info("\n[STEP 2/3] Agent Initialization")
            self._initialize_agent()
            
            logger.info("\n" + "=" * 70)
            logger.info("✓ LIFECYCLE FULLY INITIALIZED")
            logger.info("=" * 70)
            return True
            
        except Exception as e:
            logger.error(f"Lifecycle initialization failed: {e}", exc_info=True)
            return False

    def _initialize_corpus(self) -> None:
        """Initialize and verify corpus."""
        try:
            logger.info(f"\n  Building corpus from: {self.data_dir}")
            self.corpus_info = build_corpus_for_lifecycle(str(self.data_dir))
            
            if not self.corpus_info["corpus"]:
                raise ValueError("No corpus documents loaded")
            
            logger.info(f"  ✓ Corpus ready: {self.corpus_info['stats']['total_documents']} documents")
            
        except Exception as e:
            logger.error(f"Corpus initialization failed: {e}")
            raise

    def _initialize_agent(self) -> None:
        """Initialize support triage agent."""
        try:
            logger.info(f"\n  Initializing triage agent...")
            self.agent = SupportTriageAgent(
                data_dir=str(self.data_dir),
                api_key=self.api_key
            )
            logger.info(f"  ✓ Agent ready (LLM: {self.agent.triage.model_type})")
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            raise

    def process_csv_file(self, input_file: str, output_file: str, use_sample: bool = False) -> int:
        """
        Process tickets from CSV file.
        
        Args:
            input_file: Path to input CSV
            output_file: Path to output CSV
            use_sample: Whether to process sample tickets
            
        Returns:
            Number of tickets processed
        """
        if not self.agent:
            logger.error("Agent not initialized. Call initialize() first.")
            return 0
        
        try:
            # Read input
            logger.info(f"\n[STEP 3/3] Ticket Processing")
            logger.info(f"\n  Reading: {input_file}")
            
            if not Path(input_file).exists():
                logger.error(f"Input file not found: {input_file}")
                return 0
            
            df = pd.read_csv(input_file)
            logger.info(f"  ✓ Loaded {len(df)} tickets")
            
            # Process tickets
            logger.info(f"\n  Processing tickets...")
            results = []
            
            for index, row in tqdm(df.iterrows(), total=len(df), desc="  Processing"):
                issue = str(row.get("Issue", "")).strip()
                subject = str(row.get("Subject", "")).strip() if "Subject" in row else ""
                company = str(row.get("Company", "")).strip() if "Company" in row else ""
                
                try:
                    result = self.agent.process_ticket(issue, subject, company)
                    
                    results.append({
                        "Issue": issue[:500],
                        "Subject": subject[:200],
                        "Company": company,
                        "status": result['status'],
                        "product_area": result['product_area'],
                        "response": result['response'][:1000],
                        "justification": result['justification'][:500],
                        "request_type": result['request_type']
                    })
                except Exception as e:
                    logger.warning(f"Error processing row {index}: {e}")
                    results.append({
                        "Issue": issue[:500],
                        "Subject": subject[:200],
                        "Company": company,
                        "status": "escalated",
                        "product_area": "unknown",
                        "response": "Internal error. Escalating to human agent.",
                        "justification": str(e)[:500],
                        "request_type": "product_issue"
                    })
            
            # Save output
            logger.info(f"\n  Saving: {output_file}")
            output_df = pd.DataFrame(results)
            output_df.to_csv(output_file, index=False)
            logger.info(f"  ✓ Processed {len(results)} tickets")
            
            # Print statistics
            self._print_statistics(output_df)
            
            return len(results)
            
        except Exception as e:
            logger.error(f"Error processing CSV: {e}", exc_info=True)
            return 0

    def _print_statistics(self, df: pd.DataFrame) -> None:
        """Print processing statistics."""
        logger.info(f"\n  Statistics:")
        logger.info(f"    ✓ Replied: {(df['status'] == 'replied').sum()}")
        logger.info(f"    ✓ Escalated: {(df['status'] == 'escalated').sum()}")
        logger.info(f"    ✓ Bug reports: {(df['request_type'] == 'bug').sum()}")
        logger.info(f"    ✓ Feature requests: {(df['request_type'] == 'feature_request').sum()}")
        logger.info(f"    ✓ Product issues: {(df['request_type'] == 'product_issue').sum()}")


def main():
    """Main entry point for the support triage agent."""
    
    print("=" * 70)
    print("HackerRank Orchestrate - Support Triage Agent (Complete Lifecycle)")
    print("=" * 70)
    
    # Setup paths
    base_dir = Path(__file__).parent.parent
    default_data_dir = base_dir / "data"
    default_input_file = base_dir / "support_tickets" / "support_tickets.csv"
    default_output_file = base_dir / "support_tickets" / "output.csv"
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Complete Support Triage Agent Lifecycle"
    )
    parser.add_argument("--input", type=str, default=str(default_input_file),
                       help="Path to input support_tickets.csv")
    parser.add_argument("--output", type=str, default=str(default_output_file),
                       help="Path to output.csv")
    parser.add_argument("--data-dir", type=str, default=str(default_data_dir),
                       help="Path to data directory with support corpus")
    parser.add_argument("--sample", action="store_true",
                       help="Process sample tickets instead of main tickets")
    
    args = parser.parse_args()
    
    # Override with sample if requested
    if args.sample:
        args.input = str(base_dir / "support_tickets" / "sample_support_tickets.csv")
        args.output = str(base_dir / "support_tickets" / "sample_output.csv")
    
    # Validate paths
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)
    
    if not Path(args.data_dir).exists():
        logger.error(f"Data directory not found: {args.data_dir}")
        sys.exit(1)
    
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize lifecycle
    lifecycle = TriageAgentLifecycle(
        data_dir=args.data_dir,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    if not lifecycle.initialize():
        logger.error("Failed to initialize lifecycle")
        sys.exit(1)
    
    # Process CSV file
    lifecycle.process_csv_file(args.input, args.output, use_sample=args.sample)
    
    logger.info("\n" + "=" * 70)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()

