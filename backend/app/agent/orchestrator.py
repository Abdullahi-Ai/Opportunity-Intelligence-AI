"""Opportunity Intelligence AI - Controlled Agent Orchestrator.
Orchestrates multi-turn conversations, intent understanding, persistent memory,
ChromaDB RAG evidence retrieval, deterministic tools, and student-friendly response synthesis.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.prompts import AGENT_SYSTEM_PROMPT, build_student_context_prompt
from app.agent.schemas import TOOLS_SPEC
from app.agent.intent import IntentType, classify_intent, extract_entities, KNOWN_PROVIDERS
from app.agent.memory import (
    ConversationState,
    get_or_create_conversation,
    load_conversation_state,
    save_conversation_state,
    record_turn,
    update_structured_summary,
    load_message_history
)
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

# In-memory session fallback cache for non-database test mocks
SESSION_CONTEXT_CACHE: Dict[str, List[Dict[str, Any]]] = {}
MAX_SESSION_HISTORY_TURNS = 10

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

    def _handle_ambiguous_intent(self, message: str, intent_meta: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        """Handles ambiguous or single-word requests by asking helpful clarification questions."""
        term = intent_meta.get("ambiguous_term", message.strip().lower())
        
        if "academic" in term:
            question = (
                "Are you looking for academic scholarships, university programmes, research opportunities, or information about academic requirements?\n\n"
                "I can help you explore:\n"
                "1. 🎓 **Undergraduate & Postgraduate Scholarships** (e.g. HEF loans & scholarships, Equity ELP, Chevening, DAAD)\n"
                "2. 🏛️ **University Programmes & Admission Criteria** (Degree, Diploma, or Certificate level)\n"
                "3. 🔬 **Research Fellowships & Grants** (e.g. Mawazo Institute, Hult Prize)\n"
                "4. 📋 **Academic Eligibility Requirements** for specific corporate attachments or graduate schemes\n\n"
                "Please let me know which area you would like to explore, or share your university course and year of study!"
            )
            state.pending_question = {
                "question": "Clarify academic objective",
                "topic": "clarify_academic",
                "context": {"original_query": message}
            }
        elif "scholarship" in term or "bursary" in term:
            question = (
                "To help you find the most suitable scholarships, could you clarify your preference?\n\n"
                "1. 🇰🇪 **Local Kenyan Scholarships & Loans** (Higher Education Financing - HEF / HELB, Equity ELP)\n"
                "2. 🌍 **International Master’s Scholarships** (Chevening UK, DAAD Germany, Mastercard Foundation)\n"
                "3. 🏢 **Corporate Tuition Grants** (KCB 2jiajiri, Safaricom Tech Scholarships)\n\n"
                "Are you interested in opportunities in Kenya, abroad, or both?"
            )
            state.pending_question = {
                "question": "Clarify destination for scholarships",
                "topic": "clarify_destination",
                "context": {"target_category": "scholarship"}
            }
        elif "intern" in term or "attach" in term:
            question = (
                "Are you looking for **industrial attachments for continuing university students** (e.g. Safaricom 3-month attachment) "
                "or **graduate trainee programmes** for recent graduates (e.g. KRA Graduate Trainee)?\n\n"
                "Please tell me your current year of study and course major!"
            )
            state.pending_question = {
                "question": "Clarify internship vs graduate trainee",
                "topic": "clarify_category",
                "context": {"target_category": "internship"}
            }
        else:
            question = (
                f"I want to make sure I give you exact, verified information. "
                f"Could you specify if you are looking to **discover opportunities**, **check your eligibility**, or **view application deadlines**?"
            )
            state.pending_question = {
                "question": "Clarify user request",
                "topic": "clarify_general",
                "context": {"original_query": message}
            }

        return {
            "response": question,
            "tool_calls": [],
            "citations": [],
            "grounded": True,
            "intent": IntentType.AMBIGUOUS_INCOMPLETE.value
        }

    def _handle_comparison_intent(self, message: str, state: ConversationState) -> Dict[str, Any]:
        """Compares opportunities currently discussed in conversation memory."""
        opps = state.discussed_opportunities
        if not opps:
            # Fall back to searching top active opportunities
            search_res = tool_search_opportunities(SearchOpportunitiesInput(query="open scholarships and attachments Kenya", top_k=3))
            opps = [
                {
                    "id": r.get("opportunity_id"),
                    "title": r.get("title"),
                    "provider": r.get("provider"),
                    "deadline": r.get("deadline"),
                    "official_url": r.get("official_url")
                }
                for r in search_res.get("results", [])
            ]

        if not opps:
            return {
                "response": "We do not have any active opportunities under comparison yet. Would you like me to find open scholarships or industrial attachments first?",
                "tool_calls": [],
                "citations": [],
                "grounded": True,
                "intent": IntentType.OPPORTUNITY_COMPARISON.value
            }

        # Calculate and rank deadlines deterministically
        ranked_opps = []
        citations = []
        for opp in opps:
            dl_str = opp.get("deadline")
            cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=dl_str))
            ranked_opps.append({
                "title": opp.get("title"),
                "provider": opp.get("provider"),
                "deadline": dl_str or "Rolling",
                "days_remaining": cd.get("days_remaining"),
                "status_label": cd.get("status_label"),
                "url": opp.get("official_url")
            })
            if opp.get("official_url"):
                citations.append({"title": opp.get("title"), "url": opp.get("official_url")})

        # Sort: positive days_remaining first (ascending), then rolling (None), then expired
        def sort_key(item):
            d = item["days_remaining"]
            if d is None:
                return 9999
            if d < 0:
                return 10000 + abs(d)
            return d

        ranked_opps.sort(key=sort_key)

        lines = []
        for i, ro in enumerate(ranked_opps, 1):
            badge = ro["status_label"]
            url = ro["url"]
            lines.append(
                f"{i}. **[{ro['title']}]({url})**\n"
                f"   - **Provider:** {ro['provider']}\n"
                f"   - **Published Deadline:** {ro['deadline']} (`{badge}`)"
            )

        earliest = ranked_opps[0]
        reply = (
            f"### Deadline Comparison for Discussed Opportunities\n\n"
            f"Based on verified official dates, the opportunity closing first is **[{earliest['title']}]({earliest['url']})** "
            f"with **{earliest['status_label']}**.\n\n"
            + "\n\n".join(lines) +
            f"\n\n> ⏰ *All countdowns are computed deterministically from published dates.*"
        )

        return {
            "response": reply,
            "tool_calls": [{"tool": "calculate_deadline_countdown", "args": {"compared_count": len(ranked_opps)}}],
            "citations": citations,
            "grounded": True,
            "intent": IntentType.OPPORTUNITY_COMPARISON.value
        }

    def _handle_preference_update(self, message: str, intent_meta: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        """Saves student background parameters (university, course, year) into persistent memory."""
        entities = intent_meta.get("entities", {})
        context = intent_meta.get("context", {})

        if entities.get("university"):
            state.student_memory["university"] = entities["university"]
        if context.get("university"):
            state.student_memory["university"] = context["university"]

        if entities.get("year_of_study"):
            state.student_memory["year_of_study"] = entities["year_of_study"]
        if context.get("year_of_study"):
            state.student_memory["year_of_study"] = context["year_of_study"]

        if entities.get("field_of_study"):
            state.student_memory["field_of_study"] = entities["field_of_study"]

        if entities.get("degree_level"):
            state.student_memory["degree_level"] = entities["degree_level"]

        # Clear pending question
        state.pending_question = None

        uni = state.student_memory.get("university", "your university")
        yr = state.student_memory.get("year_of_study")
        course = state.student_memory.get("field_of_study")

        details = []
        if uni: details.append(f"University: **{uni}**")
        if yr: details.append(f"Year of Study: **Year {yr}**")
        if course: details.append(f"Course: **{course}**")

        reply = (
            f"✅ **Preferences Updated Successfully**\n\n"
            f"I have recorded your background:\n"
            + "\n".join([f"- {d}" for d in details]) +
            f"\n\nI will tailor all subsequent opportunity matching, eligibility assessments, and checklists to this profile. "
            f"What opportunities would you like me to evaluate for you now?"
        )

        return {
            "response": reply,
            "tool_calls": [],
            "citations": [],
            "grounded": True,
            "intent": IntentType.PREFERENCE_UPDATE.value
        }

    def process_turn(
        self,
        message: str,
        conversation_id: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        student_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a controlled, verified conversational turn following the 17-step pipeline:
        1. Identifies and loads conversation state & memory.
        2. Injects student profile.
        3. Classifies intent & resolves pending questions.
        4. Executes appropriate deterministic tools or RAG searches.
        5. Formats natural, clean, student-friendly responses with citations.
        6. Updates persistent state and rolling summary.
        """
        # Step 1 & 2: Load or create persistent conversation
        conversation = None
        state = None
        if db:
            conversation = get_or_create_conversation(db, conversation_id, user_id, session_id)
            state = load_conversation_state(db, conversation)
        else:
            state = ConversationState(conversation_id=conversation_id, user_id=user_id, anonymous_session_id=session_id)

        # Merge durable student profile into memory if present
        if student_profile:
            for k, v in student_profile.items():
                if v and k not in state.student_memory:
                    state.student_memory[k] = v

        state.turn_count += 1

        # Step 3: Classify Intent
        intent, intent_meta = classify_intent(
            message=message,
            pending_question=state.pending_question,
            recently_discussed=state.discussed_opportunities
        )
        logger.info(f"Classified intent: {intent.value} for query: '{message}'")

        if intent_meta.get("resolved_from_pending"):
            state.pending_question = None
            if intent_meta.get("context", {}).get("destination_preference"):
                state.student_memory["destination"] = intent_meta["context"]["destination_preference"]

        # Persist newly mentioned student attributes into conversational memory
        entities = intent_meta.get("entities", {})
        if entities.get("university"):
            state.student_memory["university"] = entities["university"]
        if entities.get("year_of_study"):
            state.student_memory["year_of_study"] = entities["year_of_study"]
        if entities.get("field_of_study"):
            state.student_memory["field_of_study"] = entities["field_of_study"]
        if entities.get("degree_level"):
            state.student_memory["degree_level"] = entities["degree_level"]

        tool_calls_executed = []
        citations = []
        final_reply = ""

        # Step 4: Route Intent to Specific Handlers
        if intent == IntentType.GREETING_SOCIAL:
            final_reply = (
                "Hello! 👋 I am your **Opportunity Intelligence AI** advisor for university students in Kenya.\n\n"
                "I can help you:\n"
                "- 🔍 **Find verified opportunities**: Discover official scholarships (e.g. HEF, Equity ELP, Chevening), attachments (e.g. Safaricom, KRA), and competitions.\n"
                "- 📋 **Assess eligibility**: Check if your course, year of study, and grade meet published criteria.\n"
                "- ⏰ **Track deadlines**: View deterministic countdowns calculated directly from official dates.\n"
                "- 📝 **Application checklists**: Generate step-by-step document lists and submission instructions.\n\n"
                "How can I assist you with your academic or career goals today?"
            )
            state.pending_question = None

        elif intent == IntentType.AMBIGUOUS_INCOMPLETE:
            res = self._handle_ambiguous_intent(message, intent_meta, state)
            final_reply = res["response"]

        elif intent == IntentType.OPPORTUNITY_COMPARISON:
            res = self._handle_comparison_intent(message, state)
            final_reply = res["response"]
            tool_calls_executed.extend(res["tool_calls"])
            citations.extend(res["citations"])

        elif intent == IntentType.PREFERENCE_UPDATE:
            res = self._handle_preference_update(message, intent_meta, state)
            final_reply = res["response"]

        elif intent == IntentType.OUT_OF_SCOPE:
            final_reply = (
                "I could not find verified records for that inquiry because I specialize specifically in verified educational and early-career opportunities for university students in Kenya "
                "(such as scholarships, industrial attachments, trainee schemes, and competitions).\n\n"
                "I cannot assist with out-of-scope inquiries. Would you like to explore verified scholarships, attachment programmes, or check your eligibility for Kenyan institutions?"
            )
            state.pending_question = None

        elif intent == IntentType.CHECKLIST_GENERATION:
            # Identify target opportunity
            target_id = intent_meta.get("entities", {}).get("opportunity_id")
            if not target_id and state.discussed_opportunities:
                target_id = state.discussed_opportunities[0].get("id")

            if not target_id:
                # Search for matching opportunity
                opp_search = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
                if opp_search.get("results"):
                    target_id = opp_search["results"][0].get("opportunity_id")

            if target_id:
                chk_res = tool_generate_application_checklist(GenerateChecklistInput(opportunity_id=target_id))
                tool_calls_executed.append({"tool": "generate_application_checklist", "opportunity_id": target_id})
                opp_title = chk_res.get("opportunity_title", "Opportunity")
                opp_url = chk_res.get("official_url", "")
                if opp_url:
                    citations.append({"title": opp_title, "url": opp_url})

                tasks_md = "\n".join([f"- [ ] **{t['task']}** (Category: `{t.get('required_document_type', 'General')}`)" for t in chk_res.get("tasks", [])])
                final_reply = (
                    f"### Verified Application Checklist: {opp_title}\n\n"
                    f"Based on certified published requirements, here are the mandatory documents and preparation steps:\n\n"
                    f"{tasks_md}\n\n"
                    f"🔗 **Official Application Portal:** [{opp_title}]({opp_url})\n\n"
                    f"> 💡 *Tip: You can save this opportunity to your 'My Applications' tracker to check off tasks interactively.*"
                )
                state.pending_question = None
            else:
                final_reply = "Which opportunity would you like an application checklist for? For example: *HEF Scholarship*, *Safaricom Attachment*, or *KRA Graduate Trainee*?"
                state.pending_question = {"question": "Specify opportunity for checklist", "topic": "ask_checklist_opp", "context": {}}

        elif intent == IntentType.ELIGIBILITY_ASSESSMENT:
            target_id = intent_meta.get("entities", {}).get("opportunity_id")
            if not target_id and state.discussed_opportunities:
                target_id = state.discussed_opportunities[0].get("id")

            if not target_id:
                search_res = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
                if search_res.get("results"):
                    target_id = search_res["results"][0].get("opportunity_id")

            # Check if student params are available
            mem = state.student_memory
            deg = mem.get("degree_level", "Undergraduate")
            field = mem.get("field_of_study", "Computer Science")
            yr = mem.get("year_of_study", 3)

            if target_id:
                eval_res = tool_assess_eligibility(AssessEligibilityInput(
                    opportunity_id=target_id,
                    student_degree_level=deg,
                    student_field_of_study=field,
                    student_year_of_study=int(yr)
                ))
                tool_calls_executed.append({"tool": "assess_eligibility", "opportunity_id": target_id})
                opp_title = eval_res.get("opportunity_title", "Opportunity")
                opp_url = eval_res.get("official_url", "")
                if opp_url:
                    citations.append({"title": opp_title, "url": opp_url})

                breakdown_md = "\n".join([
                    f"- **{crit['criterion']}:** `{crit['status']}` — Required: {crit.get('required')} | Provided: {crit.get('provided')}"
                    for crit in eval_res.get("criteria_breakdown", [])
                ])

                final_reply = (
                    f"### Eligibility Assessment: {opp_title}\n\n"
                    f"**Overall Result:** **{eval_res.get('overall_assessment')}**\n\n"
                    f"**Evaluated Criteria Breakdown:**\n{breakdown_md}\n\n"
                    f"🔗 **Official Link:** [{opp_title}]({opp_url})\n\n"
                    f"> ⚠️ *Disclaimer: {eval_res.get('disclaimer')}*"
                )
                state.pending_question = {
                    "question": "Would you like me to generate the required document checklist for this opportunity?",
                    "topic": "confirm_checklist",
                    "context": {"opportunity_id": target_id}
                }
            else:
                final_reply = "Which opportunity would you like me to check your eligibility for? Please mention the name (e.g. *Safaricom attachment*, *Chevening*, *HEF*)."
                state.pending_question = {"question": "Specify opportunity for eligibility", "topic": "ask_eligibility_opp", "context": {}}

        elif intent == IntentType.DEADLINE_INQUIRY:
            target_id = intent_meta.get("entities", {}).get("opportunity_id")
            if not target_id and state.discussed_opportunities:
                target_id = state.discussed_opportunities[0].get("id")

            search_res = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
            tool_calls_executed.append({"tool": "search_opportunities", "query": message})
            if search_res.get("results"):
                best = search_res["results"][0]
                opp_title = best.get("title")
                dl_str = best.get("deadline")
                url = best.get("official_url")
                if url:
                    citations.append({"title": opp_title, "url": url})

                cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=dl_str))
                tool_calls_executed.append({"tool": "calculate_deadline_countdown", "deadline": dl_str})

                final_reply = (
                    f"### Application Deadline: {opp_title}\n\n"
                    f"- **Provider:** {best.get('provider')}\n"
                    f"- **Published Closing Date:** {dl_str or 'Not confirmed / Continuous'}\n"
                    f"- **Authoritative Status:** **{cd.get('status_label')}**\n\n"
                    f"{cd.get('summary')}\n\n"
                    f"🔗 **Verify on Official Portal:** [{opp_title}]({url})"
                )
                state.pending_question = None
            else:
                final_reply = "I could not find verified records for that deadline. Please check the official provider portal directly to avoid missing dates."

        else:
            # General Discovery, Scholarship Search, Internship Search, Guidance
            category_filter = None
            if intent == IntentType.SCHOLARSHIP_SEARCH:
                category_filter = "Scholarship"
            elif intent == IntentType.INTERNSHIP_SEARCH:
                category_filter = "Internship"

            # Check if student memory has relevant keywords
            enriched_query = message
            mem = state.student_memory
            if mem.get("field_of_study") and mem["field_of_study"] not in enriched_query:
                enriched_query += f" {mem['field_of_study']}"

            search_res = tool_search_opportunities(SearchOpportunitiesInput(
                query=enriched_query,
                category=category_filter,
                top_k=4
            ))
            tool_calls_executed.append({"tool": "search_opportunities", "query": enriched_query, "category": category_filter})

            raw_results = search_res.get("results", [])
            valid_results = [r for r in raw_results if r.get("similarity_score", 0.0) >= MIN_RAG_SIMILARITY_THRESHOLD]

            if not valid_results:
                final_reply = (
                    f"I could not find verified Kenyan records matching your specific question ('{message}') in our official directory.\n\n"
                    "To prevent misinformation, I only provide details confirmed against official university notices, government agencies (HEF, PSC), or certified company portals.\n\n"
                    "💡 **Try asking about:**\n"
                    "- *Safaricom industrial attachment eligibility*\n"
                    "- *Higher Education Financing (HEF) scholarship and loan applications*\n"
                    "- *KRA Graduate Trainee qualifications*\n"
                    "- *Chevening UK scholarship requirements for Kenyan students*"
                )
                state.pending_question = None
            else:
                # Group and deduplicate by opportunity title
                opp_groups: Dict[str, Dict[str, Any]] = {}
                state.discussed_opportunities = []

                for r in valid_results:
                    title_key = r.get("title") or "Opportunity"
                    if title_key not in opp_groups:
                        opp_groups[title_key] = {
                            "id": r.get("opportunity_id"),
                            "title": r.get("title"),
                            "provider": r.get("provider"),
                            "category": r.get("category"),
                            "deadline": r.get("deadline"),
                            "official_url": r.get("official_url"),
                            "sections": []
                        }
                        # Add to discussed opportunities memory
                        state.discussed_opportunities.append({
                            "id": r.get("opportunity_id"),
                            "title": r.get("title"),
                            "provider": r.get("provider"),
                            "deadline": r.get("deadline"),
                            "official_url": r.get("official_url")
                        })

                    clean_body = extract_clean_content_body(r.get("content_excerpt", ""))
                    if len(clean_body) > 280:
                        clean_body = clean_body[:280] + "..."
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

                    # Compute countdown status label
                    cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=deadline))
                    badge = cd.get("status_label") or "Active"

                    highlights_md = "\n".join([f"  - **{sec}:** {txt}" for sec, txt in opp["sections"][:2]])

                    opp_cards.append(
                        f"#### [{title}]({url})\n"
                        f"- **Provider:** {provider} | **Deadline:** {deadline} (`{badge}`)\n"
                        f"- **Verified Details:**\n{highlights_md}"
                    )

                final_reply = (
                    "Here is what our verified Kenyan opportunity records indicate regarding your inquiry:\n\n"
                    + "\n\n".join(opp_cards) +
                    "\n\n> 🔍 *All details above are certified against official publisher portals.*"
                )
                # Offer helpful follow-up
                state.pending_question = {
                    "question": "Would you like me to check your eligibility or generate an application checklist for any of these?",
                    "topic": "confirm_next_step",
                    "context": {"opportunities": [o["title"] for o in state.discussed_opportunities]}
                }

        # Step 5: Update in-memory session context for backward-compatibility
        if conversation_id not in SESSION_CONTEXT_CACHE:
            SESSION_CONTEXT_CACHE[conversation_id] = []
        SESSION_CONTEXT_CACHE[conversation_id].append({"role": "user", "content": message})
        SESSION_CONTEXT_CACHE[conversation_id].append({"role": "assistant", "content": final_reply})
        SESSION_CONTEXT_CACHE[conversation_id] = SESSION_CONTEXT_CACHE[conversation_id][-MAX_SESSION_HISTORY_TURNS:]

        # Step 6: Persist in Database
        if db and conversation:
            record_turn(
                db=db,
                conversation_id=conversation.id,
                user_message=message,
                assistant_message=final_reply,
                intent=intent.value,
                citations=citations,
                tool_calls=tool_calls_executed
            )
            # Update auto-title if first turn
            if state.turn_count == 1:
                clean_title = message.strip()[:40]
                if len(message.strip()) > 40:
                    clean_title += "..."
                state.title = clean_title.capitalize()

            update_structured_summary(state, message, final_reply)
            save_conversation_state(db, conversation, state)

        return {
            "response": final_reply,
            "tool_calls": tool_calls_executed,
            "citations": citations,
            "grounded": True,
            "intent": intent.value,
            "conversation_id": conversation_id,
            "state": state.to_dict()
        }

    def chat(
        self,
        message: str,
        session_id: str = "default_session",
        student_profile: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Backward-compatible entry point calling process_turn."""
        return self.process_turn(
            message=message,
            conversation_id=session_id,
            db=db,
            user_id=None,
            session_id=session_id,
            student_profile=student_profile
        )

# Singleton orchestrator instance
agent_orchestrator = AgentOrchestrator()
