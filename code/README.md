# Support Triage Agent

This agent triages and resolves support tickets for HackerRank, Claude, and Visa using a local markdown corpus and the Gemini API.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install google-generativeai pandas rank_bm25 python-dotenv tqdm
   ```

2. **Configure API Key**:
   Create a `.env` file in the root directory (or inside `code/`) and add your Google API key:
   ```env
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage

Run the agent from the root directory:

```bash
python code/main.py
```

The agent will:
1. Load the support corpus from `data/`.
2. Read tickets from `support_tickets/support_tickets.csv`.
3. Process each ticket (classify, retrieve, respond).
4. Save the results to `support_tickets/output.csv`.

## Architecture

- **`corpus.py`**: Handles loading and indexing the markdown support documents using BM25 for keyword-based retrieval.
- **`triage_agent.py`**: Contains the core logic. It uses Gemini to classify the ticket, determine the triage status (replied/escalated), and generate grounded responses based on retrieved context.
- **`main.py`**: The entry point that orchestrates the data flow.
