import os
import pandas as pd
from corpus import SupportCorpus
from triage_agent import TriageAgent
from tqdm import tqdm

import argparse

def main():
    print("Initializing Support Triage Agent...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_input_dir = os.path.join(base_dir, "support_tickets")
    default_output_dir = os.path.join(base_dir, "support_tickets")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Support Triage Agent")
    parser.add_argument("input_dir", type=str, nargs='?', default=default_input_dir, help="Directory containing support_tickets.csv")
    parser.add_argument("output_dir", type=str, nargs='?', default=default_output_dir, help="Directory to save output.csv")
    args = parser.parse_args()
    
    data_dir = os.path.join(base_dir, "data")
    input_file = os.path.join(args.input_dir, "support_tickets.csv")
    output_file = os.path.join(args.output_dir, "output.csv")
    
    # Create output dir if missing
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Initialize Corpus
    print("Loading support corpus...")
    corpus = SupportCorpus(data_dir)
    
    # Initialize Agent
    print("Configuring AI agent...")
    agent = TriageAgent(corpus)
    
    # Read Tickets
    print(f"Reading input from {input_file}...")
    df = pd.read_csv(input_file)
    
    results = []
    
    print("Processing tickets...")
    for index, row in tqdm(df.iterrows(), total=len(df)):
        issue = str(row.get("Issue", ""))
        subject = str(row.get("Subject", ""))
        company = str(row.get("Company", ""))
        
        import time
        try:
            result = agent.process_ticket(issue, subject, company)
            # Ensure all required columns are present
            results.append({
                "Issue": issue,
                "Subject": subject,
                "Company": company,
                "status": result.get("status"),
                "product_area": result.get("product_area"),
                "response": result.get("response"),
                "justification": result.get("justification"),
                "request_type": result.get("request_type")
            })
            time.sleep(1.5)  # Avoid hitting rate limits
        except Exception as e:
            print(f"Error processing row {index}: {e}")
            results.append({
                "Issue": issue,
                "Subject": subject,
                "Company": company,
                "status": "escalated",
                "product_area": "unknown",
                "response": "Internal processing error.",
                "justification": str(e),
                "request_type": "product_issue"
            })
            
    # Save Results
    print(f"Saving output to {output_file}...")
    output_df = pd.DataFrame(results)
    output_df.to_csv(output_file, index=False)
    print("Done!")

if __name__ == "__main__":
    main()
