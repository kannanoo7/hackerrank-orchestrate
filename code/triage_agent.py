import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re

load_dotenv()

class TriageAgent:
    def __init__(self, corpus, model_name="gemma-3-27b-it"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.corpus = corpus

    def process_ticket(self, issue, subject, company):
        # Step 1: Classification & Reasoning
        prompt = f"""
You are an expert support triage agent for HackerRank, Claude, and Visa.
Analyze the following support ticket and decide how to handle it.

Ticket Details:
Issue: {issue}
Subject: {subject}
Company: {company}

Allowed values:
- status: "replied", "escalated"
- request_type: "product_issue", "feature_request", "bug", "invalid"

Guidelines:
- Escalate if the issue involves high-risk, sensitive topics (fraud, billing disputes, account recovery for others, security vulnerabilities, etc.) or if it's a complex bug.
- Replied if it can be answered using general support documentation or if it's out of scope.
- If out of scope, status should be "replied" and the response should state it is out of scope.
- Product area should be a concise category (e.g., "account_management", "billing", "technical_issue", "general_support", "travel_support", "privacy", etc.).

Provide your analysis in JSON format with the following keys:
- status
- product_area
- request_type
- justification (short explanation of why you chose this status/type)
- search_query (a good search query to find relevant documentation if status is "replied")
"""
        import time
        max_retries = 5
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                text = response.text
                # Try to find JSON block
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    # Fallback or retry
                    raise ValueError("No JSON found in response")
                break
            except Exception as e:
                if ("429" in str(e) or "quota" in str(e).lower()) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                print(f"Error during classification: {e}")
                return {
                    "status": "escalated",
                    "product_area": "unknown",
                    "request_type": "product_issue",
                    "response": "An error occurred during processing. Escalating to human agent.",
                    "justification": f"Error: {str(e)}"
                }

        if analysis["status"] == "escalated":
            analysis["response"] = "Escalate to a human agent for further assistance."
            return analysis

        # Step 2: Retrieval
        search_query = analysis.get("search_query", issue)
        context_docs = self.corpus.search(search_query, top_n=3)
        context_text = "\n\n".join([f"Source: {doc['source']}\n{doc['text']}" for doc in context_docs])

        # Step 3: Grounded Response Generation
        response_prompt = f"""
You are a support agent. Use the provided context to answer the user's issue.
If the issue is out of scope or not covered by the context, politely say so.

Context:
{context_text}

Issue: {issue}
Subject: {subject}
Company: {company}

Requirements:
- Your response must be grounded ONLY in the provided context.
- Do NOT hallucinate policies.
- If you can't find the answer, state that you are unable to assist and recommend escalation if appropriate.
- Be polite and professional.

Final Output:
Provide a user-facing response.
"""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(response_prompt)
                analysis["response"] = response.text.strip()
                break
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                analysis["response"] = f"Error generating response: {str(e)}"
                analysis["status"] = "escalated"

        return analysis

if __name__ == "__main__":
    # Test
    from corpus import SupportCorpus
    corpus = SupportCorpus("data")
    agent = TriageAgent(corpus)
    result = agent.process_ticket("I lost my Visa card in Paris, help!", "Lost card", "Visa")
    print(json.dumps(result, indent=2))
