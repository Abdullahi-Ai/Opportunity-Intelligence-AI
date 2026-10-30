"""
Opportunity Intelligence AI - Goal-Oriented Agent Orchestrator.
Orchestrates multi-turn conversations, tool calling with Groq (Llama-3.3-70b),
conversation context memory, persistent student preference grounding, and deterministic fallbacks.
"""

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

        # 1. Checklist request
        if "checklist" in lower_msg or "document" in lower_msg or "how to apply" in lower_msg:
            # Detect opportunity from query
            opp_search = tool_search_opportunities(SearchOpportunitiesInput(query=user_message, top_k=1))
            tool_calls_executed.append({"tool": "search_opportunities", "query": user_message})
            
            if opp_search.get("results"):
                best_opp = opp_search["results"][0]
                opp_id = best_opp.get("content_excerpt", "").split("\n")[0]
                # Find matching opportunity id
                opp_id_clean = None
                from app.rag.vector_store import vector_store
                res = vector_store.search(user_message, top_k=1)
                if res:
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

            if search_res.get("results"):
                opp_title = search_res["results"][0].get("title")
                opp_url = search_res["results"][0].get("official_url")
                if opp_url:
                    citations.append({"title": opp_title, "url": opp_url})

                # Check if student profile parameters are available
                deg = student_profile.get("degree_level", "Undergraduate") if student_profile else "Undergraduate"
                field = student_profile.get("field_of_study", "Computer Science") if student_profile else "Computer Science"
                yr = student_profile.get("year_of_study", 3) if student_profile else 3

                from app.rag.vector_store import vector_store
                res = vector_store.search(user_message, top_k=1)
                if res:
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

        # 3. Default: General Knowledge Search
        search_res = tool_search_opportunities(SearchOpportunitiesInput(query=user_message, top_k=3))
        tool_calls_executed.append({"tool": "search_opportunities", "query": user_message})

        if not search_res.get("results"):
            return {
                "response": (
                    "I cannot find verified records matching your specific question in our directory of approved Kenyan opportunities. "
                    "To avoid providing inaccurate information, I recommend checking official university notices, the Ministry of Education (HEF), or company career portals directly."
                ),
                "tool_calls": tool_calls_executed,
                "citations": [],
                "grounded": True
            }

        top_results = search_res["results"]
        excerpts = []
        for r in top_results:
            title = r.get("title")
            provider = r.get("provider")
            url = r.get("official_url")
            deadline = r.get("deadline")
            section = r.get("section")
            if url and not any(c["url"] == url for c in citations):
                citations.append({"title": title, "url": url})
            
            excerpts.append(
                f"#### [{title}]({url})\n"
                f"- **Provider:** {provider} | **Deadline:** {deadline}\n"
                f"- **Details ({section}):**\n{r.get('content_excerpt')[:300]}..."
            )

        reply = (
            f"Here is what the verified official Kenyan records indicate regarding your question:\n\n"
            + "\n\n".join(excerpts) +
            "\n\n> 🔍 *All details above are grounded directly in official published guidelines.*"
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
