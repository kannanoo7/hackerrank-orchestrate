"""
Production-level support ticket triage agent with LLM-powered escalation and product area classification.
"""
import os
import json
import re
import time
import logging
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

load_dotenv()

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TriageAgent:
    """
    Support ticket triage agent with LLM-powered escalation and product area classification.
    Uses structured LLM outputs with automatic fallback to heuristics for reliability.
    """
    
    # Fallback escalation keywords for when LLM is unavailable
    ESCALATION_KEYWORDS = {
        'fraud': ['fraud', 'scam', 'suspicious', 'unauthorized', 'stolen', 'compromised card'],
        'account_security': ['hacked', 'compromised', 'breach', 'password reset', 'account recovery', 'security breach'],
        'billing_dispute': ['charge', 'refund', 'billing', 'dispute', 'payment issue', 'incorrect charge', 'overcharge'],
        'account_access': ['locked', 'cannot login', 'access denied', 'two factor', '2fa', 'account locked', 'locked out'],
        'legal': ['lawsuit', 'compliance', 'regulation', 'gdpr', 'ccpa', 'legal', 'terms', 'pci'],
        'critical_bug': ['crash', 'data loss', 'critical', 'severe', 'not working at all', 'complete outage', 'down']
    }
    
    # Company to product areas mapping
    COMPANY_PRODUCT_AREAS = {
        'claude': [
            'account_management', 'features_and_capabilities', 'billing',
            'conversation_management', 'troubleshooting', 'claude_api',
            'usage_and_limits', 'privacy_and_security', 'pro_and_max_plans'
        ],
        'hackerrank': [
            'tests_and_assessments', 'account_management', 'billing',
            'candidate_experience', 'reports', 'integrations', 'hiring_workflow',
            'platform_features', 'troubleshooting'
        ],
        'visa': [
            'account_services', 'payment_services', 'travel_services',
            'dispute_resolution', 'data_security', 'fraud_protection',
            'support', 'technical_support', 'general_inquiry'
        ]
    }
    
    # Request type options
    REQUEST_TYPES = ['product_issue', 'feature_request', 'bug', 'invalid']
    
    # LLM configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    LLM_MODEL = "claude-3-5-sonnet-20241022"
    LLM_MAX_TOKENS = 1024

    def __init__(self, corpus_manager, api_key: Optional[str] = None):
        """
        Initialize the triage agent with corpus and optional LLM client.
        
        Args:
            corpus_manager: CorpusManager instance for document retrieval
            api_key: Optional Anthropic API key (falls back to env var)
        """
        self.corpus = corpus_manager
        self.client = None
        self.model_type = "heuristic"
        
        # Initialize LLM client
        anthropic_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and HAS_ANTHROPIC:
            try:
                self.client = anthropic.Anthropic(api_key=anthropic_key)
                self.model_type = "anthropic"
                logger.info("✓ Initialized Anthropic client for LLM-powered decisions")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}. Falling back to heuristics.")
                self.model_type = "heuristic"
        else:
            if not anthropic_key:
                logger.warning("No ANTHROPIC_API_KEY found. Using heuristic fallbacks.")
            if not HAS_ANTHROPIC:
                logger.warning("anthropic package not installed. Using heuristic fallbacks.")
            self.model_type = "heuristic"

    def _call_llm_with_retry(self, prompt: str, max_retries: int = None) -> Optional[str]:
        """
        Call LLM with exponential backoff retry logic and comprehensive error handling.
        
        Args:
            prompt: The prompt to send to the LLM
            max_retries: Maximum number of retry attempts
            
        Returns:
            LLM response text or None if all retries fail
        """
        if not self.client:
            logger.warning("LLM client not available")
            return None
            
        max_retries = max_retries or self.MAX_RETRIES
        
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.LLM_MODEL,
                    max_tokens=self.LLM_MAX_TOKENS,
                    messages=[{"role": "user", "content": prompt}]
                )
                logger.debug(f"LLM call successful on attempt {attempt + 1}")
                return response.content[0].text
                
            except anthropic.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = self.RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Rate limit hit. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries exceeded for rate limit: {e}")
                    return None
                    
            except anthropic.APIConnectionError as e:
                logger.error(f"API connection error on attempt {attempt + 1}: {e}")
                return None
                
            except anthropic.APIError as e:
                logger.error(f"API error during LLM call: {e}")
                return None
                
            except Exception as e:
                logger.error(f"Unexpected error during LLM call: {e}")
                return None
        
        return None

    def _parse_json_response(self, response_text: str) -> Optional[Dict]:
        """
        Safely parse JSON response from LLM.
        
        Args:
            response_text: Raw response text from LLM
            
        Returns:
            Parsed JSON dict or None if parsing fails
        """
        try:
            # Try to extract JSON from response (handles markdown code blocks)
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            logger.warning(f"No JSON found in response: {response_text[:100]}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
        return None

    def should_escalate_llm(self, issue: str, subject: str = "") -> Tuple[bool, str, str]:
        """
        Determine if ticket should be escalated using LLM with structured JSON output.
        Automatically falls back to heuristics if LLM is unavailable.
        
        Returns:
            Tuple of (should_escalate: bool, category: str, reasoning: str)
        """
        if self.model_type != "anthropic" or not self.client:
            logger.debug("LLM unavailable, using heuristic escalation detection")
            return self._should_escalate_heuristic(issue, subject)
        
        prompt = f"""Analyze this support ticket and determine if it should be escalated to a human agent.

Subject: {subject}
Issue: {issue}

Escalation categories:
- fraud: Financial fraud, scams, suspicious transactions, stolen accounts
- account_security: Account compromise, security breaches, unauthorized access
- billing_dispute: Payment issues, refund requests, billing disputes
- account_access: Locked accounts, login issues, access restoration
- legal: Legal/compliance matters, GDPR/CCPA requests, regulatory issues
- critical_bug: System outages, data loss, critical functionality broken
- none: Can be handled with documentation/standard procedures

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
    "should_escalate": true/false,
    "category": "one_of_the_categories",
    "reasoning": "Brief explanation (max 100 chars)"
}}
"""
        response = self._call_llm_with_retry(prompt)
        
        if response:
            result = self._parse_json_response(response)
            if result:
                should_escalate = result.get("should_escalate", False)
                category = result.get("category", "unknown")
                reasoning = result.get("reasoning", "LLM decision")
                logger.debug(f"LLM escalation: escalate={should_escalate}, category={category}")
                return bool(should_escalate), str(category), str(reasoning)
        
        # Fallback to heuristics if LLM fails
        logger.info("LLM escalation failed, falling back to heuristics")
        return self._should_escalate_heuristic(issue, subject)

    def _should_escalate_heuristic(self, issue: str, subject: str = "") -> Tuple[bool, str, str]:
        """
        Fallback heuristic-based escalation detection using keyword matching.
        """
        combined_text = f"{subject} {issue}".lower()
        
        for category, keywords in self.ESCALATION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined_text:
                    return True, category, f"Keyword detected: '{keyword}'"
        
        return False, "none", "No escalation indicators found"

    def infer_product_area_llm(self, company: str, issue: str, subject: str = "") -> Tuple[str, str]:
        """
        Infer product area using LLM with structured JSON output.
        Automatically falls back to heuristics if LLM is unavailable.
        
        Returns:
            Tuple of (product_area: str, reasoning: str)
        """
        if self.model_type != "anthropic" or not self.client:
            logger.debug("LLM unavailable, using heuristic product area inference")
            return self._infer_product_area_heuristic(company, issue, subject), "Heuristic fallback"
        
        valid_areas = self.COMPANY_PRODUCT_AREAS.get(company.lower(), [])
        if not valid_areas:
            logger.warning(f"Unknown company '{company}', using generic areas")
            valid_areas = ['general_support', 'account_management', 'billing', 'technical_support']
        
        areas_str = ", ".join(valid_areas)
        
        prompt = f"""Classify this support ticket into the most appropriate product area.

Company: {company}
Subject: {subject}
Issue: {issue}

Valid product areas for {company}:
{areas_str}

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
    "product_area": "one_of_the_valid_areas_above",
    "reasoning": "Brief explanation (max 100 chars)"
}}
"""
        response = self._call_llm_with_retry(prompt)
        
        if response:
            result = self._parse_json_response(response)
            if result:
                area = result.get("product_area", valid_areas[0] if valid_areas else "general_support")
                reasoning = result.get("reasoning", "LLM classification")
                
                # Validate the area is in the valid list
                if area not in valid_areas:
                    logger.warning(f"LLM returned invalid area '{area}', using '{valid_areas[0]}'")
                    area = valid_areas[0] if valid_areas else "general_support"
                
                logger.debug(f"LLM product area: {area}")
                return str(area), str(reasoning)
        
        # Fallback to heuristics if LLM fails
        logger.info("LLM product area inference failed, falling back to heuristics")
        return self._infer_product_area_heuristic(company, issue, subject), "Heuristic fallback"

    def _infer_product_area_heuristic(self, company: str, issue: str, subject: str = "") -> str:
        """
        Fallback heuristic-based product area inference using keyword patterns.
        """
        combined_text = f"{subject} {issue}".lower()
        
        # Pattern-based classification
        patterns = {
            'account_management': ['account', 'login', 'password', 'profile', 'settings', 'email', 'username', 'signin', 'logout'],
            'billing': ['billing', 'charge', 'payment', 'invoice', 'refund', 'pricing', 'cost', 'subscription', 'plan'],
            'features_and_capabilities': ['feature', 'capability', 'can i', 'how do i', 'use', 'access', 'how to', 'guide'],
            'troubleshooting': ['error', 'not working', 'bug', 'crash', 'issue', 'problem', 'fail', 'broken', 'doesn\'t work'],
            'conversation_management': ['conversation', 'chat', 'delete', 'share', 'archive', 'rename', 'history', 'message'],
            'technical_support': ['api', 'integration', 'code', 'deploy', 'server', 'connection', 'network', 'sync', 'webhook'],
        }
        
        for area, keywords in patterns.items():
            for keyword in keywords:
                if keyword in combined_text:
                    return area
        
        # Default based on company
        company_lower = company.lower() if company else 'unknown'
        defaults = {
            'claude': 'features_and_capabilities',
            'hackerrank': 'tests_and_assessments',
            'visa': 'payment_services'
        }
        
        return defaults.get(company_lower, 'general_support')

    def infer_request_type(self, issue: str, subject: str = "") -> str:
        """
        Classify request type using heuristic keyword matching.
        """
        combined_text = f"{subject} {issue}".lower()
        
        # Feature request patterns
        if any(word in combined_text for word in ['new feature', 'add', 'feature request', 'could you', 'would like', 'implement', 'suggestion', 'request']):
            return 'feature_request'
        
        # Bug report patterns
        if any(word in combined_text for word in ['bug', 'error', 'crash', 'broken', 'not working', 'issue', 'problem', 'fail', 'exception']):
            return 'bug'
        
        # Help/question patterns
        if any(word in combined_text for word in ['how', 'help', 'question', 'what', 'where', 'can i', 'guide', 'tutorial', 'assistance']):
            return 'product_issue'
        
        return 'product_issue'

    def _infer_company(self, issue: str, subject: str = "") -> str:
        """Infer company from issue content if not provided."""
        combined_text = f"{subject} {issue}".lower()
        
        if any(word in combined_text for word in ['claude', 'anthropic', 'ai chat', 'conversation']):
            return 'claude'
        elif any(word in combined_text for word in ['hackerrank', 'coding', 'interview', 'assessment', 'challenges']):
            return 'hackerrank'
        elif any(word in combined_text for word in ['visa', 'card', 'payment', 'transaction', 'travel']):
            return 'visa'
        
        return 'unknown'

    def process_ticket(self, issue: str, subject: str = "", company: str = None) -> Dict:
        """
        Process a support ticket and generate comprehensive triage decision.
        
        Args:
            issue: The support ticket issue text
            subject: The ticket subject/title
            company: The company (claude, hackerrank, or visa)
            
        Returns:
            Dict with status, product_area, response, justification, and request_type
        """
        try:
            # Step 1: Normalize company
            if not company or company.lower() in ['none', 'unknown', '']:
                company = self._infer_company(issue, subject)
            company_norm = company.lower().strip() if company else 'unknown'
            
            # Step 2: Use LLM to determine escalation
            should_escalate, escalation_category, escalation_reason = self.should_escalate_llm(issue, subject)
            
            # Step 3: Classify request type
            request_type = self.infer_request_type(issue, subject)
            
            # Step 4: Use LLM to determine product area
            product_area, area_reasoning = self.infer_product_area_llm(company_norm, issue, subject)
            
            # Step 5: Generate response
            if should_escalate:
                status = 'escalated'
                response = f"This ticket has been escalated to our support team. " \
                          f"Category: {escalation_category}. A specialist will follow up shortly."
                justification = f"Escalated: {escalation_reason}"
            else:
                # Retrieve relevant documentation
                search_query = f"{subject} {issue}".strip()
                retrieved_docs = self.corpus.retrieve(company_norm, search_query, top_k=3)
                
                if retrieved_docs:
                    response, justification = self._generate_response_with_docs(
                        issue, subject, company_norm, retrieved_docs, product_area
                    )
                    status = 'replied'
                else:
                    response = f"I couldn't find specific documentation for your question. " \
                              f"Please escalate for personalized support."
                    justification = "No matching documentation found in knowledge base"
                    status = 'escalated'
            
            result = {
                'status': status,
                'product_area': product_area,
                'response': response,
                'justification': justification,
                'request_type': request_type
            }
            
            logger.info(f"Ticket processed: status={status}, area={product_area}, type={request_type}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing ticket: {e}", exc_info=True)
            return {
                'status': 'escalated',
                'product_area': 'unknown',
                'response': 'Error processing request. Escalating to support team.',
                'justification': f"Processing error: {str(e)[:100]}",
                'request_type': 'product_issue'
            }

    def _generate_response_with_docs(self, issue: str, subject: str, company: str,
                                      docs: List[Dict], product_area: str) -> Tuple[str, str]:
        """
        Generate response using documentation context (with LLM if available).
        
        Returns:
            Tuple of (response: str, justification: str)
        """
        if not docs:
            return ("Unable to generate response - no documentation found.", "No documentation match")
        
        context = "\n\n".join([
            f"Source: {doc.get('path', 'unknown')}\nContent: {doc.get('content', '')[:300]}"
            for doc in docs[:2]
        ])
        
        # If LLM is available, use it to generate a polished response
        if self.model_type == "anthropic" and self.client:
            prompt = f"""You are a professional support agent for {company}.
            
User's Question:
Subject: {subject}
Issue: {issue}

Relevant Documentation:
{context}

Instructions:
1. Answer ONLY based on the provided documentation.
2. Be concise and professional (2-3 sentences max).
3. If documentation doesn't cover the question, say so clearly.

Generate a helpful support response:"""
            
            try:
                response = self._call_llm_with_retry(prompt, max_retries=2)
                if response:
                    justification = f"LLM-generated response based on {len(docs)} documentation articles"
                    return response.strip(), justification
            except Exception as e:
                logger.warning(f"LLM response generation failed: {e}, using fallback")
        
        # Fallback: return summary of top document
        top_doc = docs[0]
        content = top_doc.get('content', 'No content')[:250]
        path = top_doc.get('path', 'documentation')
        
        response = f"Based on our documentation: {content}... For complete details, please refer to {path}."
        justification = f"Documentation-based response from {path}"
        
        return response, justification
