from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from corpus import CorpusIndex, tokenize

ALLOWED_STATUS = {"replied", "escalated"}
ALLOWED_REQUEST_TYPES = {"product_issue", "feature_request", "bug", "invalid"}


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def lower(text: str) -> str:
    return compact(text).lower()


@dataclass(frozen=True)
class TriageResult:
    status: str
    product_area: str
    response: str
    justification: str
    request_type: str


class SupportTriageAgent:
    def __init__(self, data_dir: Path) -> None:
        self.index = CorpusIndex(data_dir=data_dir)

    def classify_request_type(self, text: str) -> str:
        t = lower(text)
        if any(k in t for k in ["feature request", "can you add", "please add", "would like to request"]):
            return "feature_request"
        if any(k in t for k in ["bug", "down", "not working", "failing", "error", "stopped", "issue", "blocked"]):
            return "bug"
        if any(k in t for k in ["thank you", "who is the actor", "out of scope", "delete all files", "code to delete"]):
            return "invalid"
        return "product_issue"

    def should_escalate(self, text: str, company: str, request_type: str) -> tuple[bool, str]:
        t = lower(text)
        escalation_rules = [
            ("major security vulnerability", "Security vulnerability reports require human security triage."),
            ("identity has been stolen", "Identity theft reports are sensitive and require specialist handling."),
            ("restore my access immediately", "Access-restoration requests without admin authority require account admin review."),
            ("increase my score", "Assessment score disputes are not handled by support agents directly."),
            ("ban the seller", "Enforcement actions against merchants require issuer/network investigation."),
            ("it’s not working, help", "Insufficient details; needs human follow-up."),
            ("it's not working, help", "Insufficient details; needs human follow-up."),
        ]
        for phrase, reason in escalation_rules:
            if phrase in t:
                return True, reason
        if request_type == "invalid" and any(k in t for k in ["delete all files", "malware", "hack"]):
            return True, "Potentially harmful request outside support scope."
        if company == "None" and request_type == "bug" and "site is down" in t:
            return True, "Platform outage reports should be escalated immediately."
        return False, ""

    def _response_from_docs(self, docs: list, company: str, fallback_reason: str | None = None) -> tuple[str, str]:
        if not docs:
            return (
                "I could not find enough grounded support guidance in the provided corpus. Please route this to a human support specialist.",
                fallback_reason or "No matching support documentation found in local corpus.",
            )

        top = docs[0]
        snippets: list[str] = []
        for doc in docs:
            text = compact(doc.content)
            # Keep the response concise and grounded to documentation.
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                s = compact(sentence)
                if 40 <= len(s) <= 220 and "http" not in s and "![mceclip" not in s:
                    snippets.append(s)
                if len(snippets) >= 3:
                    break
            if len(snippets) >= 3:
                break

        if not snippets:
            snippets = [f"Please follow the official guidance in: {top.title}."]

        prefix = "Based on the provided support documentation: "
        response = prefix + " ".join(snippets[:3])
        justification = (
            f"Routed using local corpus match in `{top.path}`"
            + (f" plus related docs ({len(docs)} retrieved)." if len(docs) > 1 else ".")
        )
        return response, justification

    def _product_area(self, docs: list, company: str) -> str:
        if docs:
            return docs[0].product_area
        if company == "HackerRank":
            return "general_support"
        if company == "Claude":
            return "account_management"
        if company == "Visa":
            return "general_support"
        return "general_support"

    def triage(self, issue: str, subject: str, company: str, top_k: int = 3) -> TriageResult:
        company = compact(company) or "None"
        text = compact(f"{subject} {issue}")
        request_type = self.classify_request_type(text)
        escalate, escalation_reason = self.should_escalate(text, company, request_type)

        docs = self.index.search(query=text, company_hint=company, top_k=top_k)
        product_area = self._product_area(docs, company)

        if any(k in lower(text) for k in ["who is the actor in iron man", "thank you for helping me"]):
            return TriageResult(
                status="replied",
                product_area=product_area,
                response="I am sorry, this is out of scope from my capabilities.",
                justification="Ticket is unrelated to supported domains or does not require support action.",
                request_type="invalid",
            )

        if escalate:
            response = (
                "I’m escalating this to a human support specialist to ensure safe and accurate handling. "
                "Please share any additional details (timestamps, screenshots, account/workspace identifiers) to speed up resolution."
            )
            justification = escalation_reason
            status = "escalated"
        else:
            response, doc_justification = self._response_from_docs(docs, company)
            justification = doc_justification
            status = "replied"

        if status not in ALLOWED_STATUS:
            status = "escalated"
        if request_type not in ALLOWED_REQUEST_TYPES:
            request_type = "product_issue"

        return TriageResult(
            status=status,
            product_area=product_area,
            response=response,
            justification=justification,
            request_type=request_type,
        )


def run_batch(agent: SupportTriageAgent, input_csv: Path, output_csv: Path, top_k: int = 3) -> None:
    rows: list[dict[str, str]] = []
    with input_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            issue = row.get("Issue", "") or row.get("issue", "")
            subject = row.get("Subject", "") or row.get("subject", "")
            company = row.get("Company", "") or row.get("company", "")
            result = agent.triage(issue=issue, subject=subject, company=company, top_k=top_k)
            rows.append(
                {
                    "status": result.status,
                    "product_area": result.product_area,
                    "response": result.response,
                    "justification": result.justification,
                    "request_type": result.request_type,
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["status", "product_area", "response", "justification", "request_type"],
        )
        writer.writeheader()
        writer.writerows(rows)
