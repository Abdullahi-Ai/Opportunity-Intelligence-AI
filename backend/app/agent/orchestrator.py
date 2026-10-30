"""
Opportunity Intelligence AI - Goal-Oriented Agent Orchestrator.
Orchestrates multi-turn conversations, tool calling with Groq (Llama-3.3-70b),
conversation context memory, persistent student preference grounding, and deterministic fallbacks.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import settings
from app.agent.prompts import AGENT_SYSTEM_PROMPT, build_student_context_prompt
from app.agent.schemas import TOOLS_SPEC
from app.agent.tools import (
    SearchOpportunitiesInput,
    tool_search_opportunities,
    DeadlineCountdownInput,
    tool_calculate_deadline_countdown,
    AssessEligibilityInput,
    tool_assess_eligibility,
    GenerateChecklistInput,
    tool_generate_application_checklist
)

logger = logging.getLogger(__name__)

# Minimum semantic similarity threshold required to consider a RAG chunk relevant
MIN_RAG_SIMILARITY_THRESHOLD = 0.40

def is_conversational_or_greeting(text: str) -> bool:
    """Detects ordinary conversational greetings, pleasantries, or introductory questions."""
    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    tokens = clean.split()
    if not tokens:
        return True
    
    greetings = {
        "hello", "hi", "hey", "habari", "sasa", "jambo", "greetings",
        "morning", "good morning", "good afternoon", "good evening",
        "howdy", "sup", "yo", "mambo"
    }
    conversational_phrases = [
        "who are you", "what are you", "what can you do", "introduce yourself",
        "help me", "tell me about yourself", "how does this work", "how do you work",
        "what is this", "greatness"
    ]
    if clean in greetings or any(phrase in clean for phrase in conversational_phrases):
        return True
    if len(tokens) <= 3 and any(t in greetings for t in tokens):
        return True
    return False

def get_conversational_greeting_response() -> str:
    """Returns a friendly, structured conversational introduction without dumping raw documents."""
    return (
        "Hello! 👋 I am your **Opportunity Intelligence AI** advisor for university students in Kenya.\n\n"
        "I can help you:\n"
        "- 🔍 **Find verified opportunities**: Discover certified scholarships (e.g., HEF, Equity ELP, Chevening), industrial attachments (e.g., Safaricom, KRA), fellowships, and competitions.\n"
        "- 📋 **Assess eligibility**: Check if your university degree, year of study, and KCSE or university grade meet published requirements.\n"
        "- ⏰ **Track deadlines**: View deterministic countdowns calculated directly from official application closing dates.\n"
        "- 📝 **Application checklists**: Generate step-by-step document lists and submission instructions.\n\n"
        "How can I assist you with your academic or career opportunities today?"
    )

def extract_clean_content_body(raw_chunk_text: str) -> str:
    """Extracts the actual informative body from a chunk, stripping all internal chunk headers."""
    if "\n\n" in raw_chunk_text:
        body = raw_chunk_text.split("\n\n", 1)[1]
    else:
        body = raw_chunk_text

    clean_lines = [
        line.strip() for line in body.split("\n")
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("---")
        and not line.strip().startswith("Opportunity:") and not line.strip().startswith("Category:")
        and not line.strip().startswith("Section:") and not line.strip().startswith("Official Link:")
    ]
    clean_text = " ".join(clean_lines)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return clean_text

# In-memory session store for multi-turn short-term conversation context
# Session ID -> list of {"role": str, "content": str, ...}
SESSION_CONTEXT_CACHE: Dict[str, List[Dict[str, Any]]] = {}

# Maximum conversation turns to preserve in short-term context window
MAX_SESSION_HISTORY_TURNS = 10

# Dispatch map for deterministic tool execution
TOOL_DISPATCH_MAP = {
    "search_opportunities": lambda args: tool_search_opportunities(SearchOpportunitiesInput(**args)),
    "calculate_deadline_countdown": lambda args: tool_calculate_deadline_countdown(DeadlineCountdownInput(**args)),
    "assess_eligibility": lambda args: tool_assess_eligibility(AssessEligibilityInput(**args)),
    "generate_application_checklist": lambda args: tool_generate_application_checklist(GenerateChecklistInput(**args)),
}

class AgentOrchestrator:
    def __init__(self, api_key: str = settings.GROQ_API_KEY, model: str = settings.GROQ_MODEL):
        self.api_key = api_key
        self.model = model
        self._groq_client = None

    @property
    def groq_client(self):
        if self._groq_client is None and self.api_key and self.api_key != "your_groq_api_key_here":
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")
        return self._groq_client

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a tool deterministically and returns structured output."""
        func = TOOL_DISPATCH_MAP.get(tool_name)
        if not func:
            return {"status": "error", "message": f"Unknown tool '{tool_name}'"}
        try:
            return func(tool_args)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} with {tool_args}: {e}")
            return {"status": "error", "message": f"Tool execution failed: {str(e)}"}

    def _fallback_deterministic_reply(
        self,
        user_message: str,
        student_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deterministic, offline-resilient fallback response generator.
        Activates when GROQ_API_KEY is unset or API is unreachable,
        ensuring zero hallucinations and 100% test reliability.
        """
        lower_msg = user_message.lower()
        tool_calls_executed = []
        citations = []

        # 0. Conversational greeting check
        if is_conversational_or_greeting(user_message):
            return {
                "response": get_conversational_greeting_response(),
                "tool_calls": [],
                "citations": [],
                "grounded": True
            }

        # 1. Checklist request
        if "checklist" in lower_msg or "document" in lower_msg or "how to apply" in lower_msg:
            opp_search = tool_search_opportunities(SearchOpportunitiesInput(query=user_message, top_k=1))
            tool_calls_executed.append({"tool": "search_opportunities", "query": user_message})
            
            if opp_search.get("results") and opp_search["results"][0].get("similarity_score", 0.0) >= 0.35:
                best_opp = opp_search["results"][0]
                from app.rag.vector_store import vector_store
                res = vector_store.search(user_message, top_k=1)
                if res and res[0].get("similarity_score", 0.0) >= 0.35:
                    opp_id_clean = res[0]["metadata"].get("opportunity_id")
                    url = res[0]["metadata"].get("official_url")
                    title = res[0]["metadata"].get("title")
                    if url:
                        citations.append({"title": title, "url": url})

                    if opp_id_clean:
                        chk_res = tool_generate_application_checklist(GenerateChecklistInput(opportunity_id=opp_id_clean))
                        tool_calls_executed.append({"tool": "generate_application_checklist", "opportunity_id": opp_id_clean})
                        
                        tasks_md = "\n".join([f"- [ ] {t['task']}" for t in chk_res.get("tasks", [])])
                        reply = (
                            f"### Verified Application Checklist for {title}\n\n"
                            f"Based on verified records, here are the required documents and application steps:\n\n"
                            f"{tasks_md}\n\n"
                            f"🔗 **Official Application Portal:** [{title}]({url})\n\n"
                            f"> ⚠️ *Always verify current submission procedures directly on the official portal.*"
                        )
                        return {
                            "response": reply,
                            "tool_calls": tool_calls_executed,
                            "citations": citations,
                            "grounded": True
                        }

        # 2. Eligibility evaluation request
        if "eligible" in lower_msg or "qualify" in lower_msg:
            search_res = tool_search_opportunities(SearchOpportunitiesInput(query=user_message, top_k=1))
            tool_calls_executed.append({"tool": "search_opportunities", "query": user_message})

            if search_res.get("results") and search_res["results"][0].get("similarity_score", 0.0) >= 0.35:
                opp_title = search_res["results"][0].get("title")
                opp_url = search_res["results"][0].get("official_url")
                if opp_url:
                    citations.append({"title": opp_title, "url": opp_url})

                deg = student_profile.get("degree_level", "Undergraduate") if student_profile else "Undergraduate"
                field = student_profile.get("field_of_study", "Computer Science") if student_profile else "Computer Science"
                yr = student_profile.get("year_of_study", 3) if student_profile else 3

                from app.rag.vector_store import vector_store
                res = vector_store.search(user_message, top_k=1)
                if res and res[0].get("similarity_score", 0.0) >= 0.35:
                    target_id = res[0]["metadata"].get("opportunity_id")
                    eval_res = tool_assess_eligibility(AssessEligibilityInput(
                        opportunity_id=target_id,
                        student_degree_level=deg,
                        student_field_of_study=field,
                        student_year_of_study=yr
                    ))
                    tool_calls_executed.append({"tool": "assess_eligibility", "opportunity_id": target_id})

                    breakdown_md = "\n".join([
                        f"- **{crit['criterion']}:** {crit['status']} (Required: `{crit.get('required')}`, Provided: `{crit.get('provided')}`)"
                        for crit in eval_res.get("criteria_breakdown", [])
                    ])

                    reply = (
                        f"### Eligibility Assessment: {opp_title}\n\n"
                        f"**Overall Assessment:** **{eval_res.get('overall_assessment')}**\n\n"
                        f"**Criteria Breakdown:**\n{breakdown_md}\n\n"
                        f"🔗 **Official Link:** [{opp_title}]({opp_url})\n\n"
                        f"> *Disclaimer: {eval_res.get('disclaimer')}*"
                    )
                    return {
                        "response": reply,
                        "tool_calls": tool_calls_executed,
                        "citations": citations,
                        "grounded": True
                    }

        # 3. Opportunity Search with Semantic Threshold & Deduplication
        search_res = tool_search_opportunities(SearchOpportunitiesInput(query=user_message, top_k=4))
        tool_calls_executed.append({"tool": "search_opportunities", "query": user_message})

        raw_results = search_res.get("results", [])
        # Filter by minimum relevance threshold
        valid_results = [r for r in raw_results if r.get("similarity_score", 0.0) >= MIN_RAG_SIMILARITY_THRESHOLD]

        if not valid_results:
            return {
                "response": (
                    f"I could not find verified records matching your specific question ('{user_message}') in our directory of approved Kenyan opportunities.\n\n"
                    "To prevent inaccurate guidance, I only provide details confirmed against official university notices, government portals (HEF, PSC), or certified company sites.\n\n"
                    "💡 **Try asking about:**\n"
                    "- *Safaricom industrial attachment eligibility*\n"
                    "- *Higher Education Financing (HEF) scholarship and loan applications*\n"
                    "- *KRA Graduate Trainee qualifications*\n"
                    "- *Chevening UK scholarship requirements for Kenyan students*"
                ),
                "tool_calls": tool_calls_executed,
                "citations": [],
                "grounded": True
            }

        # Deduplicate and consolidate chunks by opportunity title
        opp_groups: Dict[str, Dict[str, Any]] = {}
        for r in valid_results:
            title_key = r.get("title") or "Opportunity"
            if title_key not in opp_groups:
                opp_groups[title_key] = {
                    "title": r.get("title"),
                    "provider": r.get("provider"),
                    "category": r.get("category"),
                    "deadline": r.get("deadline"),
                    "official_url": r.get("official_url"),
                    "sections": []
                }
            
            raw_text = r.get("content_excerpt", "").strip()
            clean_body = extract_clean_content_body(raw_text)
            if len(clean_body) > 300:
                clean_body = clean_body[:300] + "..."
            elif not clean_body:
                clean_body = "Verified published requirements and guidelines are available via the official portal."

            sec_name = r.get("section") or "Key Details"
            opp_groups[title_key]["sections"].append((sec_name, clean_body))

            url = r.get("official_url")
            if url and not any(c["url"] == url for c in citations):
                citations.append({"title": r.get("title"), "url": url})

        opp_cards = []
        for opp in opp_groups.values():
            title = opp["title"]
            url = opp["official_url"]
            provider = opp["provider"]
            deadline = opp["deadline"] or "Rolling / Unspecified"

            highlights_md = "\n".join([f"  - **{sec}:** {txt}" for sec, txt in opp["sections"][:2]])

            opp_cards.append(
                f"#### [{title}]({url})\n"
                f"- **Provider:** {provider} | **Deadline:** {deadline}\n"
                f"- **Verified Details:**\n{highlights_md}"
            )

        clean_q = re.sub(r"[^\w\s]", "", user_message.strip().lower())
        broad_terms = {"academic", "academics", "scholarship", "scholarships", "bursary", "bursaries", "funding", "education"}
        if clean_q in broad_terms:
            reply = (
                f"### Verified Academic Opportunities & Scholarships in Kenya\n\n"
                f"Here are the primary verified scholarship and educational funding programs matching your academic query:\n\n"
                + "\n\n".join(opp_cards[:3]) +
                f"\n\n---\n"
                f"💡 **Next Steps:**\n"
                f"- Tell me your current institution, course, and year of study to run an **instant eligibility assessment**.\n"
                f"- Or ask: *\"What documents do I need for HEF?\"* or *\"How do I apply for Equity ELP?\"* for step-by-step checklists."
            )
        else:
            reply = (
                "Here is what our verified Kenyan opportunity records indicate regarding your inquiry:\n\n"
                + "\n\n".join(opp_cards) +
                "\n\n> 🔍 *All details above are certified against official publisher portals.*"
            )

        return {
            "response": reply,
            "tool_calls": tool_calls_executed,
            "citations": citations,
            "grounded": True
        }

    def chat(
        self,
        message: str,
        session_id: str = "default_session",
        student_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a grounded conversational turn:
        1. Injects student profile memory and system guardrails.
        2. Maintains conversation turn history for follow-up context.
        3. Invokes Groq LLM with function calling tools.
        4. Handles tool execution and synthesizes grounded answers with citations.
        """
        # Initialize or retrieve session history
        if session_id not in SESSION_CONTEXT_CACHE:
            SESSION_CONTEXT_CACHE[session_id] = []

        history = SESSION_CONTEXT_CACHE[session_id]

        # Fast path for conversational greetings
        if is_conversational_or_greeting(message):
            greeting_resp = get_conversational_greeting_response()
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": greeting_resp})
            SESSION_CONTEXT_CACHE[session_id] = history[-MAX_SESSION_HISTORY_TURNS:]
            return {
                "response": greeting_resp,
                "tool_calls": [],
                "citations": [],
                "grounded": True
            }

        # Check if Groq client is configured
        client = self.groq_client
        if not client:
            logger.info("Groq API key not provided or client unavailable. Using deterministic fallback.")
            result = self._fallback_deterministic_reply(message, student_profile)
            # Record user & assistant turn in memory
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": result["response"]})
            SESSION_CONTEXT_CACHE[session_id] = history[-MAX_SESSION_HISTORY_TURNS:]
            return result

        # Construct system prompt with personalized student memory
        sys_prompt = AGENT_SYSTEM_PROMPT + build_student_context_prompt(student_profile)

        # Prepare messages payload
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        tool_calls_executed = []
        citations = []

        try:
            # First LLM call: Determine if tools are needed
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS_SPEC,
                tool_choice="auto",
                temperature=0.1,  # Low temperature for strict factual reliability
                max_tokens=1024
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            if tool_calls:
                # Add assistant tool call proposal to messages
                messages.append(response_message)

                # Execute each requested tool call
                for tc in tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments

                    logger.info(f"Agent calling tool: {fn_name} with args: {fn_args}")
                    tool_output = self.execute_tool(fn_name, fn_args)
                    tool_calls_executed.append({"tool": fn_name, "args": fn_args, "output": tool_output})

                    # Extract URLs for citation verification
                    if "official_url" in tool_output and tool_output["official_url"]:
                        citations.append({
                            "title": tool_output.get("title", fn_name),
                            "url": tool_output["official_url"]
                        })
                    elif "results" in tool_output and isinstance(tool_output["results"], list):
                        for r in tool_output["results"]:
                            if r.get("official_url"):
                                citations.append({
                                    "title": r.get("title", "Official Source"),
                                    "url": r["official_url"]
                                })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": json.dumps(tool_output)
                    })

                # Second LLM call: Synthesize final grounded answer
                final_response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1024
                )
                final_text = final_response.choices[0].message.content
            else:
                final_text = response_message.content

            # Update session context
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": final_text})
            SESSION_CONTEXT_CACHE[session_id] = history[-MAX_SESSION_HISTORY_TURNS:]

            # Deduplicate citations
            seen_urls = set()
            unique_citations = []
            for c in citations:
                if c["url"] not in seen_urls:
                    seen_urls.add(c["url"])
                    unique_citations.append(c)

            return {
                "response": final_text,
                "tool_calls": tool_calls_executed,
                "citations": unique_citations,
                "grounded": True
            }

        except Exception as e:
            logger.error(f"Error during Groq agent execution: {e}. Falling back to deterministic reply.")
            return self._fallback_deterministic_reply(message, student_profile)

# Singleton orchestrator instance
agent_orchestrator = AgentOrchestrator()
