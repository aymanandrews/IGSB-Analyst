"""Analysis Service — Claude API integration and prompt engine for financial analysis."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import anthropic

# Default model
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def get_client() -> anthropic.Anthropic:
    """Get Anthropic client. API key from environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    return anthropic.Anthropic(api_key=api_key)


def build_system_prompt() -> str:
    """Build the system prompt for financial analysis."""
    return """You are an expert financial analyst specializing in investment-grade corporate bond analysis.

Your task is to analyze financial data and produce a structured JSON analysis report. You MUST respond with valid JSON matching the AnalysisJSON schema exactly.

## Output Requirements

Your response must be a single valid JSON object with these top-level keys:
- metadata: Analysis metadata
- company: Company information
- financial_statements: Income statement, balance sheet, cash flow (use data provided)
- derived_metrics: Calculated ratios grouped by profitability, liquidity, leverage, efficiency
- kpis: Array of 6-8 key performance indicators for dashboard cards
- narrative: AI-generated analysis with summary, sections, risks, outlook
- sources: Attribution for all data sources
- data_quality: Assessment of data completeness

## Formatting Rules
- All monetary values as raw numbers (not formatted strings)
- All percentages as decimals (0.463 not 46.3%)
- All dates in ISO 8601 format
- Period labels: YYYY-QN or YYYY-FY format
- Trends: "up", "down", or "stable"
- Sentiment: "positive", "negative", "neutral", or "mixed"

## Analysis Guidelines
- Focus on credit quality and bond-relevant metrics
- Highlight interest coverage, leverage ratios, cash flow adequacy
- Identify risks to debt service capacity
- Compare trends across available periods
- Note any data gaps or quality concerns"""


def build_user_prompt(
    company_info: dict[str, Any] | None,
    financial_statements: dict[str, Any] | None,
    uploaded_documents: list[dict[str, Any]] | None,
    analyst_notes: str | None,
) -> str:
    """Build the user prompt with all available data."""
    parts = ["Analyze the following financial data and produce an AnalysisJSON report.\n"]

    if company_info:
        parts.append("## Company Information")
        parts.append(json.dumps(company_info, indent=2))
        parts.append("")

    if financial_statements:
        parts.append("## Financial Statements (from SEC EDGAR)")
        parts.append(json.dumps(financial_statements, indent=2))
        parts.append("")

    if uploaded_documents:
        parts.append("## Uploaded Documents")
        for doc in uploaded_documents:
            parts.append(f"### {doc.get('filename', 'Unknown document')}")
            if doc.get("type") == "pdf":
                parts.append(f"Pages: {doc.get('pages', 'N/A')}")
                parts.append(doc.get("text", "")[:15000])  # Truncate very long docs
            elif doc.get("type") == "spreadsheet":
                for sheet in doc.get("sheets", []):
                    parts.append(f"Sheet: {sheet.get('name', 'Sheet1')} ({sheet.get('rowCount', 0)} rows)")
                    # Include headers and first 50 rows
                    if sheet.get("headers"):
                        parts.append("Headers: " + " | ".join(str(h) for h in sheet["headers"]))
                    for row in sheet.get("rows", [])[:50]:
                        parts.append(" | ".join(str(v) for v in row))
            elif doc.get("type") == "text":
                parts.append(doc.get("content", "")[:10000])
            parts.append("")

    if analyst_notes:
        parts.append("## Analyst Notes")
        parts.append(analyst_notes)
        parts.append("")

    parts.append("Respond with ONLY valid JSON matching the AnalysisJSON schema. No markdown fences, no explanation — just the JSON object.")
    return "\n".join(parts)


def run_analysis(
    company_info: dict[str, Any] | None = None,
    financial_statements: dict[str, Any] | None = None,
    uploaded_documents: list[dict[str, Any]] | None = None,
    analyst_notes: str | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Run a synchronous analysis and return the parsed AnalysisJSON."""
    client = get_client()

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=build_system_prompt(),
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(company_info, financial_statements, uploaded_documents, analyst_notes),
            }
        ],
    )

    raw_text = message.content[0].text

    # Parse JSON from response (handle potential markdown fences)
    json_text = raw_text.strip()
    if json_text.startswith("```"):
        # Remove markdown code fences
        lines = json_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        json_text = "\n".join(lines)

    result = json.loads(json_text)

    # Inject metadata
    result["metadata"] = {
        "analysis_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_version": "1.0",
        "analysis_type": "full",
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

    return result


async def run_analysis_stream(
    company_info: dict[str, Any] | None = None,
    financial_statements: dict[str, Any] | None = None,
    uploaded_documents: list[dict[str, Any]] | None = None,
    analyst_notes: str | None = None,
    model: str = DEFAULT_MODEL,
) -> AsyncGenerator[str, None]:
    """Run analysis with SSE streaming. Yields Server-Sent Event formatted strings."""
    client = get_client()

    analysis_id = str(uuid.uuid4())

    # Send start event
    yield f"data: {json.dumps({'event': 'start', 'analysis_id': analysis_id})}\n\n"

    try:
        with client.messages.stream(
            model=model,
            max_tokens=8192,
            system=build_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": build_user_prompt(company_info, financial_statements, uploaded_documents, analyst_notes),
                }
            ],
        ) as stream:
            full_text = ""
            for text in stream.text_stream:
                full_text += text
                yield f"data: {json.dumps({'event': 'delta', 'text': text})}\n\n"

            # Get final message for usage stats
            final_message = stream.get_final_message()

            # Parse the complete JSON
            json_text = full_text.strip()
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                json_text = "\n".join(lines)

            result = json.loads(json_text)
            result["metadata"] = {
                "analysis_id": analysis_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": model,
                "prompt_version": "1.0",
                "analysis_type": "full",
                "input_tokens": final_message.usage.input_tokens,
                "output_tokens": final_message.usage.output_tokens,
            }

            yield f"data: {json.dumps({'event': 'complete', 'result': result})}\n\n"

    except json.JSONDecodeError as e:
        yield f"data: {json.dumps({'event': 'error', 'message': f'Failed to parse analysis JSON: {str(e)}'})}\n\n"
    except anthropic.APIError as e:
        yield f"data: {json.dumps({'event': 'error', 'message': f'Claude API error: {str(e)}'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'event': 'error', 'message': f'Analysis failed: {str(e)}'})}\n\n"
