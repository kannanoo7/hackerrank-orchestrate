# Support Triage Agent — Production Edition

A production-ready AI agent for triaging support tickets across three ecosystems: **HackerRank**, **Claude**, and **Visa**. Uses **LLM-powered decision-making** with automatic fallback to heuristics for reliability and scalability.

## Architecture

### Core Components

1. **CorpusBuilder** (`build_corpus.py`) — **NEW: Dedicated Corpus Building**
   - Dedicated component for loading and preparing support documentation.
   - Handles markdown parsing, frontmatter extraction, and cleaning.
   - Builds the initial corpus for the `CorpusManager`.

2. **CorpusManager** (`corpus.py`)
   - Loads and indexes support documentation from all three company corpora
   - Parses `index.md` files as metadata for product areas
   - Implements BM25-based retrieval for fast, relevant document search
   - Supports category-specific searches within each company

3. **TriageAgent** (`triage_agent.py`) — **LLM-Powered**
   - **Escalation Detection (LLM-Powered)**
     - Structured JSON-based escalation decisions
     - Categories: fraud, account_security, billing_dispute, account_access, legal, critical_bug
     - Automatic fallback to keyword-based heuristics
   - **Product Area Classification (LLM-Powered)**
     - Structured JSON-based product area inference
     - Company-specific product areas with validation
     - Automatic fallback to pattern-based heuristics
   - **Request Classification**: Heuristic-based (bug, feature_request, product_issue, invalid)
   - **Comprehensive Error Handling**
     - Exponential backoff retry logic for API failures
     - Rate limit handling with automatic fallback
     - JSON parsing error handling
     - Per-ticket error isolation
   - **Response Generation**: Uses retrieved documentation with optional LLM polishing

4. **SupportTriageAgent** (`agent.py`) — **NEW: Unified Agent Wrapper**
   - Orchestrates the entire agent logic by combining `CorpusManager` and `TriageAgent`.
   - Provides a unified interface for initializing and processing tickets.

5. **TriageAgentLifecycle** (`main.py`) — **NEW: Complete Lifecycle Orchestrator**
   - Manages the end-to-end lifecycle: Corpus Building → Agent Initialization → Ticket Processing.
   - Reads support tickets from CSV, coordinates processing, and generates output CSV.
   - Provides summary statistics with detailed logging.

## Key Features

✅ **Complete Lifecycle Management** — Dedicated components for corpus building, agent logic, and orchestration.
✅ **LLM-Powered Decision Making** — Escalation and product area use Claude API with JSON outputs  
✅ **Automatic Fallback to Heuristics** — Seamless degradation if LLM unavailable  
✅ **Production-Ready Reliability** — Comprehensive error handling and retry logic  
✅ **Comprehensive Logging** — All decisions, errors, and API calls logged  
✅ **Corpus-Grounded** — Responses based on local support documentation  
✅ **Scalable** — Batch processes hundreds of tickets with progress tracking  
✅ **Flexible** — Works with or without API keys (falls back gracefully)  

## Installation

### Prerequisites
- Python 3.9+
- pip

### Setup

```bash
cd code

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies (updated for LLM support and corpus building)
pip install -r requirements.txt
```

### Dependencies

- `pandas` — CSV processing
- `rank-bm25` — Fast BM25 retrieval
- `anthropic>=0.9.0` — Anthropic Claude API (LLM-powered decisions)
- `python-dotenv` — Environment variable management
- `tqdm` — Progress bars
- `beautifulsoup4>=4.9.0` — Web scraping for corpus building (if external links are enabled)
- `requests>=2.28.0` — HTTP requests for web scraping

## Configuration

Create a `.env` file in the `code/` directory:

```env
# Required for LLM-powered escalation and product area classification
ANTHROPIC_API_KEY=sk-ant-...
```

**Optional**: Without the API key, the agent falls back to heuristics (see "Using Without LLM" below).

Never commit `.env` with real keys. Use `.env.example` as a template.

## Usage

### Process main support tickets:

```bash
python main.py
```

This will:
1. Build the corpus using `build_corpus.py`.
2. Initialize the `SupportTriageAgent`.
3. Read tickets from `../support_tickets/support_tickets.csv`.
4. Use LLM for escalation and product area decisions (or heuristics if unavailable).
5. Generate predictions and save to `../support_tickets/output.csv`.

### Process sample tickets (for testing):

```bash
python main.py --sample
```

### Custom paths:

```bash
python main.py \
  --input /path/to/tickets.csv \
  --output /path/to/output.csv \
  --data-dir /path/to/data
```

### Using Without LLM (Heuristics Only)

```bash
# Without ANTHROPIC_API_KEY in .env
python main.py
# → Agent will use heuristic fallbacks automatically
```

## Output Format

| Column | Description |
|--------|-------------|
| `Issue` | Original issue text |
| `Subject` | Original subject line |
| `Company` | Company (Claude, HackerRank, Visa) |
| `status` | `replied` or `escalated` |
| `product_area` | Categorized support domain (LLM-inferred) |
| `response` | User-facing answer or escalation message |
| `justification` | Reasoning for the decision |
| `request_type` | `product_issue`, `feature_request`, `bug`, or `invalid` |

## Decision Logic

### Escalation Decision (LLM-Powered)

Uses structured LLM prompts to classify into escalation categories:

```
- fraud: Financial fraud, scams, suspicious transactions
- account_security: Account compromise, security breaches
- billing_dispute: Payment issues, refund requests
- account_access: Locked accounts, login issues
- legal: Compliance, GDPR/CCPA, regulatory
- critical_bug: System outages, data loss
- none: Can be handled with documentation
```

**Fallback**: Keyword matching on predefined escalation keywords

### Product Area Classification (LLM-Powered)

Company-specific areas with validation:

**Claude**: account_management, features_and_capabilities, billing, conversation_management, troubleshooting, claude_api, usage_and_limits, privacy_and_security, pro_and_max_plans

**HackerRank**: tests_and_assessments, account_management, billing, candidate_experience, reports, integrations, hiring_workflow, platform_features, troubleshooting

**Visa**: account_services, payment_services, travel_services, dispute_resolution, data_security, fraud_protection, support, technical_support, general_inquiry

**Fallback**: Pattern-based keyword matching

### Request Type Classification

- **feature_request**: Keywords like "new feature", "add", "implement"
- **bug**: Keywords like "bug", "error", "crash"
- **product_issue**: Keywords like "how", "help", "question"

## Production Features

### Comprehensive Logging

All decisions logged with timestamps:

```
2026-05-02 11:00:00 - triage_agent - INFO - ✓ Initialized Anthropic client
2026-05-02 11:00:05 - triage_agent - DEBUG - LLM escalation: escalate=True, category=fraud
2026-05-02 11:00:06 - triage_agent - DEBUG - LLM product area: account_management
```

### Automatic Retry Logic

- **Rate Limits**: Retries with exponential backoff (1s, 2s, 4s delays)
- **Connection Errors**: Logs and falls back to heuristics
- **JSON Parsing**: Handles malformed LLM responses gracefully

### Error Isolation

- Per-ticket error handling prevents single failures from stopping the pipeline
- Failed tickets are escalated with error details logged
- Processing continues with next ticket

### Validation

- LLM outputs are validated against predefined enumerations
- Invalid areas are replaced with most appropriate fallback
- JSON parsing errors trigger heuristic fallback

## Testing

To validate the agent on sample tickets:

```bash
python main.py --sample
# Check sample_output.csv for predictions
```

With detailed logging:

```bash
# In triage_agent.py:
logging.basicConfig(level=logging.DEBUG)  # Change from INFO to DEBUG
python main.py --sample
```

Compare predictions with expected outputs to verify:
- Correct status (replied vs. escalated)
- Appropriate product_area classification
- Request type accuracy
- Response quality and groundedness

## Troubleshooting

### LLM Not Being Used

Check:
1. `.env` file exists with `ANTHROPIC_API_KEY`
2. `anthropic` package installed: `pip install anthropic>=0.9.0`
3. Logs for "LLM unavailable" warnings

### Rate Limiting (429 errors)

Increase delays in `triage_agent.py`:

```python
RETRY_DELAY = 2  # Default: 1 second
MAX_RETRIES = 5  # Default: 3 attempts
```

### JSON Parsing Errors

Enable debug logging to see LLM responses:

```python
logging.basicConfig(level=logging.DEBUG)
```

These indicate LLM is returning non-standard JSON. Check the debug output to see the response format.

### No Documents Retrieved

- Ensure `../data/` directory exists with `claude/`, `hackerrank/`, `visa/` subdirectories
- Check that `.md` files are present
- Verify `index.md` exists in each company folder

## File Structure

```
code/
├── main.py              # Entry point (orchestration)
├── agent.py             # SupportTriageAgent (unified agent wrapper)
├── build_corpus.py      # CorpusBuilder (dedicated corpus building)
├── corpus.py            # CorpusManager (document retrieval)
├── triage_agent.py      # TriageAgent (LLM-powered decisions)
├── requirements.txt     # Python dependencies
├── README.md            # This file
└── .env.example         # Environment variable template
```

## Performance

- **Corpus Loading**: ~2-5 seconds
- **Per-Ticket Processing**: ~2-5 seconds (with LLM), ~0.5s (heuristics only)
- **Full Batch (29 tickets)**: ~2-3 minutes (with LLM), ~15 seconds (heuristics only)
- **Memory**: ~200-300 MB

## Design Highlights

### 1. Structured LLM Outputs

Escalation and product area decisions use JSON-based prompts for reliable parsing and validation.

### 2. Automatic Fallback Architecture

LLM unavailability doesn't break the system—heuristics seamlessly take over:

```
LLM Available → Structured JSON Decision → Validation → Fallback if invalid
       ↓
LLM Unavailable → Heuristic Keywords → Predefined Categories
```

### 3. Per-Company Validation

Product area outputs are validated against company-specific enumerations, ensuring consistency.

### 4. Comprehensive Error Handling

- Rate limits: Exponential backoff
- Connection errors: Logged, fallback triggered
- JSON errors: Fallback to heuristics
- Per-ticket errors: Isolated, logged, processing continues

### 5. Logging & Observability

Every decision is logged with sufficient detail for debugging and monitoring in production.

## Evaluation Criteria

This agent is evaluated on:

1. **Design Quality** — Architecture, LLM integration, fallback logic, error handling
2. **Accuracy** — Correctness of status, product_area, response, request_type
3. **Reliability** — Graceful degradation, automatic fallback, error handling
4. **Groundedness** — Responses based on corpus documentation
5. **Scalability** — Batch processing, progress tracking, resource efficiency
