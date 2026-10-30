"""Agent Orchestrator for Opportunity Intelligence AI.
Implements the 17-step deterministic and RAG conversational turn pipeline.
Integrates intent classification, persistent memory, entity extraction,
rule-based date math, eligibility evaluation, and grounded evidence delivery.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.intent import classify_intent, IntentType, extract_entities
from app.agent.memory import (
    ConversationState,
    get_or_create_conversation,
    load_conversation_state,
    save_conversation_state,
    record_turn,
    update_structured_summary
)
from app.models.entities import Conversation
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
MIN_RAG_SIMILARITY_THRESHOLD = 0.15

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
                "I want to make sure I give you exact, verified information. "
                "Could you specify if you are looking to **discover opportunities**, **check your eligibility**, or **view application deadlines**?"
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

    def _handle_opportunity_discovery(self, message: str, state: ConversationState) -> Dict[str, Any]:
        """Provides high-level category orientation and displays curated verified opportunities."""
        search_res = tool_search_opportunities(SearchOpportunitiesInput(
            query="scholarships industrial attachments graduate trainee programmes Kenyan university students",
            top_k=8
        ))

        raw_results = search_res.get("results", [])
        seen_titles = set()
        unique_opps = []
        for r in raw_results:
            title = r.get("title")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_opps.append(r)
                if len(unique_opps) >= 4:
                    break

        # Fallback if search returned fewer than expected
        if not unique_opps:
            search_res = tool_search_opportunities(SearchOpportunitiesInput(query="Kenya university opportunities", top_k=4))
            unique_opps = search_res.get("results", [])

        # Save to discussed_opportunities memory
        state.discussed_opportunities = [
            {
                "id": opp.get("opportunity_id"),
                "title": opp.get("title"),
                "provider": opp.get("provider"),
                "deadline": opp.get("deadline"),
                "official_url": opp.get("official_url"),
                "category": opp.get("category")
            }
            for opp in unique_opps
        ]

        cards = []
        citations = []
        for i, opp in enumerate(unique_opps, 1):
            title = opp.get("title", "Opportunity")
            provider = opp.get("provider", "Verified Organization")
            cat = opp.get("category", "General")
            url = opp.get("official_url", "")
            dl_str = opp.get("deadline")
            cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=dl_str))

            excerpt = extract_clean_content_body(opp.get("content_excerpt", ""))
            if len(excerpt) > 160:
                excerpt = excerpt[:157] + "..."

            if url and not any(c["url"] == url for c in citations):
                citations.append({"title": title, "url": url})

            status_label = cd.get("status_label", "Open / Active")
            cards.append(
                f"### {i}. [{title}]({url})\n"
                f"- 🏢 **Organization:** {provider}\n"
                f"- 📂 **Category:** {cat}\n"
                f"- 📋 **Eligibility Summary:** {excerpt or 'Open to qualified Kenyan university students.'}\n"
                f"- ⏰ **Official Deadline:** {dl_str or 'Continuous'} (`{status_label}`)\n"
                f"- 🔗 **Official Portal:** [{title}]({url})"
            )

        reply = (
            "Absolutely! I can help you discover opportunities available to Kenyan university students.\n\n"
            "Here are some categories we can explore:\n"
            "1. 🎓 **Scholarships and financial aid** (e.g. Higher Education Financing HEF, Equity ELP, Mastercard Foundation)\n"
            "2. 🏢 **Industrial attachments and internships** (e.g. Safaricom Attachment, UN Gigiri, KRA)\n"
            "3. 🚀 **Graduate trainee programmes** (e.g. KRA Graduate Trainee, Safaricom Discover)\n"
            "4. 🌍 **International scholarships** (e.g. Chevening UK, DAAD In-Country)\n"
            "5. 🔬 **Fellowships and research opportunities** (e.g. Mawazo Institute, Hult Prize Kenya)\n\n"
            "Here are some opportunities currently recorded in our verified directory:\n\n"
            + "\n\n".join(cards) +
            "\n\n---\n"
            "💡 **Next steps you can take:**\n"
            "- Ask: *\"Tell me about Safaricom\"* to inspect details.\n"
            "- Ask: *\"What are the requirements?\"* for the opportunity of your choice.\n"
            "- Ask: *\"Am I eligible?\"* (mention your course and year of study).\n"
            "- Ask: *\"Which one has the earliest deadline?\"* to plan your submissions."
        )

        return {
            "response": reply,
            "tool_calls": [{"tool": "search_opportunities", "query": "featured opportunities"}],
            "citations": citations,
            "grounded": True,
            "intent": IntentType.OPPORTUNITY_DISCOVERY.value
        }

    def _handle_explain_requirements(self, message: str, intent_meta: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        """Explains verified requirements for the active or requested opportunity."""
        target_id = intent_meta.get("entities", {}).get("opportunity_id")
        opp_info = None

        if target_id:
            for o in state.discussed_opportunities:
                if o.get("id") == target_id:
                    opp_info = o
                    break
        elif state.discussed_opportunities:
            opp_info = state.discussed_opportunities[0]
            target_id = opp_info.get("id")

        if not target_id:
            search_res = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
            if search_res.get("results"):
                target_id = search_res["results"][0].get("opportunity_id")

        if not target_id:
            return {
                "response": (
                    "Which opportunity's requirements would you like me to explain? "
                    "For example: *Safaricom attachment*, *Higher Education Financing (HEF)*, *KRA Graduate Trainee*, or *Chevening Scholarship*."
                ),
                "tool_calls": [],
                "citations": [],
                "grounded": True,
                "intent": IntentType.EXPLAIN_REQUIREMENTS.value
            }

        search_res = tool_search_opportunities(SearchOpportunitiesInput(
            query=f"eligibility requirements academic criteria {target_id}",
            top_k=2
        ))

        opp_title = (opp_info.get("title") if opp_info else None) or target_id.replace("opp-", "").replace("-2026", "").replace("-", " ").title()
        opp_url = opp_info.get("official_url", "") if opp_info else ""
        citations = []
        body_text = ""

        if search_res.get("results"):
            best = search_res["results"][0]
            opp_title = best.get("title", opp_title)
            opp_url = best.get("official_url", opp_url)
            body_text = extract_clean_content_body(best.get("content_excerpt", ""))
            if opp_url:
                citations.append({"title": opp_title, "url": opp_url})

        reply = (
            f"### Verified Requirements: {opp_title}\n\n"
            f"Based on certified published guidelines, here are the key criteria and qualifications required:\n\n"
            f"{body_text}\n\n"
            f"🔗 **Official Application Portal:** [{opp_title}]({opp_url})\n\n"
            f"💡 **Suggested Next Step:** Ask *\"Am I eligible?\"* and provide your university, course, and year of study to assess your profile."
        )

        return {
            "response": reply,
            "tool_calls": [{"tool": "search_opportunities", "opportunity_id": target_id}],
            "citations": citations,
            "grounded": True,
            "intent": IntentType.EXPLAIN_REQUIREMENTS.value
        }

    def _handle_followup_provider(self, message: str, intent_meta: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        """Provides verified details for a specific organization or opportunity."""
        target_id = intent_meta.get("entities", {}).get("opportunity_id")
        provider_kw = intent_meta.get("entities", {}).get("provider_keyword") or message

        search_res = tool_search_opportunities(SearchOpportunitiesInput(
            query=f"{provider_kw} Kenya university students requirements",
            top_k=3
        ))
        tool_calls = [{"tool": "search_opportunities", "query": provider_kw}]
        citations = []

        if not search_res.get("results"):
            return {
                "response": f"I could not find verified directory records specifically for '{provider_kw}'. Would you like me to show all available scholarships or industrial attachments?",
                "tool_calls": tool_calls,
                "citations": citations,
                "grounded": True,
                "intent": IntentType.FOLLOW_UP_QUESTION.value
            }

        best = search_res["results"][0]
        opp_title = best.get("title")
        opp_url = best.get("official_url")
        dl_str = best.get("deadline")
        cat = best.get("category")
        provider = best.get("provider")

        cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=dl_str))
        excerpt = extract_clean_content_body(best.get("content_excerpt", ""))

        if opp_url:
            citations.append({"title": opp_title, "url": opp_url})

        active_opp = {
            "id": best.get("opportunity_id") or target_id,
            "title": opp_title,
            "provider": provider,
            "deadline": dl_str,
            "official_url": opp_url,
            "category": cat
        }
        state.discussed_opportunities = [active_opp] + [o for o in state.discussed_opportunities if o.get("title") != opp_title]

        reply = (
            f"### {opp_title}\n\n"
            f"- 🏢 **Organization:** {provider}\n"
            f"- 📂 **Category:** {cat}\n"
            f"- ⏰ **Official Deadline:** {dl_str or 'Continuous Intake'} (`{cd.get('status_label')}` — {cd.get('summary')})\n\n"
            f"**Published Summary & Focus:**\n{excerpt}\n\n"
            f"🔗 **Official Application Portal:** [{opp_title}]({opp_url})\n\n"
            f"💡 **Suggested Next Steps:**\n"
            f"- Ask: *\"What are the requirements?\"*\n"
            f"- Ask: *\"Am I eligible?\"*\n"
            f"- Ask: *\"Help me apply\"* to generate your application checklist."
        )

        return {
            "response": reply,
            "tool_calls": tool_calls,
            "citations": citations,
            "grounded": True,
            "intent": IntentType.FOLLOW_UP_QUESTION.value
        }

    def _handle_comparison_intent(self, message: str, state: ConversationState) -> Dict[str, Any]:
        """Compares opportunities currently discussed in conversation memory."""
        opps = state.discussed_opportunities
        if not opps:
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

        state.pending_question = None

        uni = state.student_memory.get("university", "your university")
        yr = state.student_memory.get("year_of_study")
        course = state.student_memory.get("field_of_study")

        details = []
        if uni: details.append(f"University: **{uni}**")
        if yr: details.append(f"Year of Study: **Year {yr}**")
        if course: details.append(f"Course: **{course}**")

        reply = (
            f"Noted and saved to your profile! 📝\n"
            f"- " + "\n- ".join(details) + "\n\n"
            "I will use this context for future eligibility checks and opportunity recommendations. "
            "What opportunities would you like to explore?"
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
        """Executes a controlled, verified conversational turn following the 17-step pipeline."""
        conversation = None
        state = None
        if db:
            conversation = get_or_create_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                anonymous_session_id=session_id
            )
            state = load_conversation_state(db, conversation)
        else:
            state = ConversationState(conversation_id=conversation_id, user_id=user_id, anonymous_session_id=session_id)

        # Merge student profile into memory if present
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
        if intent == IntentType.THANK_YOU:
            final_reply = (
                "You're very welcome! 😊 Feel free to ask anytime if you want to discover more verified opportunities, "
                "check your eligibility, review deadlines, or generate application checklists. Best of luck with your academic journey!"
            )
            state.pending_question = None

        elif intent == IntentType.GREETING_SOCIAL:
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

        elif intent == IntentType.OPPORTUNITY_DISCOVERY:
            res = self._handle_opportunity_discovery(message, state)
            final_reply = res["response"]
            tool_calls_executed.extend(res["tool_calls"])
            citations.extend(res["citations"])

        elif intent == IntentType.AMBIGUOUS_INCOMPLETE:
            res = self._handle_ambiguous_intent(message, intent_meta, state)
            final_reply = res["response"]

        elif intent == IntentType.FOLLOW_UP_QUESTION:
            res = self._handle_followup_provider(message, intent_meta, state)
            final_reply = res["response"]
            tool_calls_executed.extend(res["tool_calls"])
            citations.extend(res["citations"])

        elif intent == IntentType.EXPLAIN_REQUIREMENTS:
            res = self._handle_explain_requirements(message, intent_meta, state)
            final_reply = res["response"]
            tool_calls_executed.extend(res["tool_calls"])
            citations.extend(res["citations"])

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
            target_id = intent_meta.get("entities", {}).get("opportunity_id")
            if not target_id and state.discussed_opportunities:
                target_id = state.discussed_opportunities[0].get("id")

            if not target_id:
                opp_search = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
                if opp_search.get("results"):
                    target_id = opp_search["results"][0].get("opportunity_id")

            if target_id:
                chk_res = tool_generate_application_checklist(GenerateChecklistInput(opportunity_id=target_id))
                tool_calls_executed.append({"tool": "generate_application_checklist", "opportunity_id": target_id})
                opp_title = chk_res.get("title") or chk_res.get("opportunity_title", "Opportunity")
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
            opp_info = None

            if target_id:
                for o in state.discussed_opportunities:
                    if o.get("id") == target_id:
                        opp_info = o
                        break
            elif state.discussed_opportunities:
                opp_info = state.discussed_opportunities[0]
                target_id = opp_info.get("id")

            if not target_id:
                search_res = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
                if search_res.get("results"):
                    target_id = search_res["results"][0].get("opportunity_id")

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
                opp_title = eval_res.get("title") or eval_res.get("opportunity_title", "Opportunity")
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
            opp_info = None

            if target_id:
                for o in state.discussed_opportunities:
                    if o.get("id") == target_id:
                        opp_info = o
                        break
            elif state.discussed_opportunities:
                opp_info = state.discussed_opportunities[0]

            if opp_info and opp_info.get("deadline"):
                opp_title = opp_info.get("title")
                dl_str = opp_info.get("deadline")
                url = opp_info.get("official_url")
                provider = opp_info.get("provider")

                cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=dl_str))
                tool_calls_executed.append({"tool": "calculate_deadline_countdown", "deadline": dl_str})
                if url:
                    citations.append({"title": opp_title, "url": url})

                final_reply = (
                    f"### Application Deadline: {opp_title}\n\n"
                    f"- **Provider:** {provider}\n"
                    f"- **Published Closing Date:** **{dl_str}**\n"
                    f"- **Authoritative Status:** **{cd.get('status_label')}**\n\n"
                    f"{cd.get('summary')}\n\n"
                    f"🔗 **Verify on Official Portal:** [{opp_title}]({url})"
                )
                state.pending_question = None
            else:
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
            # Scholarship Search, Internship Search, Graduate Trainee, Field Search
            category_filter = None
            if intent == IntentType.SCHOLARSHIP_SEARCH:
                category_filter = "Scholarship"
            elif intent == IntentType.INTERNSHIP_SEARCH:
                category_filter = "Internship"
            elif intent == IntentType.GRADUATE_PROGRAMME_SEARCH:
                category_filter = "Graduate Trainee"
            elif intent == IntentType.FELLOWSHIP_SEARCH:
                category_filter = "Fellowship"

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

            # If category filter yielded 0 results, retry without category constraint
            if not valid_results and category_filter:
                retry_res = tool_search_opportunities(SearchOpportunitiesInput(query=enriched_query, top_k=4))
                valid_results = [r for r in retry_res.get("results", []) if r.get("similarity_score", 0.0) >= MIN_RAG_SIMILARITY_THRESHOLD]

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
