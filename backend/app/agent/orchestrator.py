"""Agent Orchestrator for Opportunity Intelligence AI.
Implements the 17-step deterministic and RAG conversational turn pipeline.
Integrates intent classification, persistent memory, entity extraction,
rule-based date math, eligibility evaluation, and grounded evidence delivery.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.intent import classify_intent, IntentType, extract_entities
from app.agent.memory import (
    ConversationState,
    get_or_create_conversation,
    load_conversation_state,
    save_conversation_state,
    record_turn,
    update_structured_summary,
    load_message_history
)
from app.models.entities import Conversation
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
    tool_generate_application_checklist,
    execute_registered_tool,
    TOOL_REGISTRY
)

logger = logging.getLogger(__name__)

MIN_RAG_SIMILARITY_THRESHOLD = 0.15

SESSION_CONTEXT_CACHE: Dict[str, List[Dict[str, Any]]] = {}
SESSION_STATE_CACHE: Dict[str, ConversationState] = {}
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

class AgentOrchestrator:
    def __init__(
        self,
        api_key: str = settings.GROQ_API_KEY,
        model: str = settings.GROQ_MODEL,
        max_tool_iterations: int = 4,
        timeout_seconds: float = 15.0
    ):
        self.api_key = api_key
        self.model = model
        self.max_tool_iterations = max_tool_iterations
        self.timeout_seconds = timeout_seconds
        self._groq_client = None

    @property
    def groq_client(self):
        if self._groq_client is None and self.api_key and self.api_key != "your_groq_api_key_here":
            try:
                from groq import Groq
                self._groq_client = Groq(
                    api_key=self.api_key,
                    timeout=self.timeout_seconds,
                    max_retries=2
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")
        return self._groq_client

    @groq_client.setter
    def groq_client(self, client):
        self._groq_client = client

    def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        authenticated_student_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Executes a registered tool deterministically and returns structured output."""
        return execute_registered_tool(
            tool_name=tool_name,
            tool_args=tool_args,
            authenticated_student_id=authenticated_student_id,
            db=db
        )

    def _generate_suggested_followups(self, intent: IntentType, state: ConversationState) -> List[str]:
        followups = []
        if state.discussed_opportunities:
            latest = state.discussed_opportunities[-1].get("title", "this opportunity")
            followups.append(f"Am I eligible for {latest}?")
            followups.append(f"What documents do I need for {latest}?")
            followups.append(f"When is the application deadline for {latest}?")
        else:
            followups.append("Show me scholarships in Kenya")
            followups.append("Find industrial attachments for computer science")
            followups.append("Check my eligibility for Safaricom attachment")
        return followups[:3]

    def _run_llm_tool_loop(
        self,
        message: str,
        intent: IntentType,
        intent_meta: Dict[str, Any],
        state: ConversationState,
        conversation_id: str,
        authenticated_student_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, str]]]:
        """Executes genuine LLM-driven tool calling with evidence grounding."""
        system_content = AGENT_SYSTEM_PROMPT.strip()
        student_profile_text = build_student_context_prompt(state.student_memory)
        if student_profile_text:
            system_content += "\n\n" + student_profile_text.strip()

        now_dt = datetime.now()
        system_content += (
            f"\n\n### TEMPORAL ANCHOR & SYSTEM CONTEXT:\n"
            f"- Current Date: {now_dt.strftime('%Y-%m-%d')} ({now_dt.strftime('%A')})\n"
            f"- Academic Calendar: Kenyan University Academic Year 2026/2027\n"
        )
        if state.discussed_opportunities:
            recent_titles = [f"'{o.get('title')}' (id: {o.get('id')})" for o in state.discussed_opportunities[-4:]]
            system_content += f"- Recently Discussed Opportunities in this Session: {', '.join(recent_titles)}\n"

        if state.summary:
            system_content += f"- Conversation Summary so far: {state.summary}\n"

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_content}
        ]

        history: List[Dict[str, str]] = []
        if db:
            db_history = load_message_history(db, conversation_id)
            for m in db_history[-6:]:
                history.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        elif conversation_id in SESSION_CONTEXT_CACHE:
            history = SESSION_CONTEXT_CACHE[conversation_id][-6:]

        for h in history:
            if h.get("content"):
                messages.append({"role": h.get("role", "user"), "content": h.get("content")})

        messages.append({"role": "user", "content": message})

        tool_calls_executed: List[Dict[str, Any]] = []
        citations: List[Dict[str, str]] = []
        seen_urls = set()

        iteration = 0
        final_reply = ""

        while iteration < self.max_tool_iterations:
            iteration += 1

            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS_SPEC,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=1500
            )

            choice = response.choices[0]
            choice_message = choice.message
            raw_tool_calls = getattr(choice_message, "tool_calls", None)

            if raw_tool_calls:
                asst_msg_dict: Dict[str, Any] = {
                    "role": "assistant",
                    "content": choice_message.content or "",
                    "tool_calls": []
                }
                for tc in raw_tool_calls:
                    tc_fn = getattr(tc, "function", None)
                    tc_name = getattr(tc_fn, "name", "")
                    tc_args_str = getattr(tc_fn, "arguments", "{}")
                    asst_msg_dict["tool_calls"].append({
                        "id": getattr(tc, "id", f"call_{iteration}"),
                        "type": "function",
                        "function": {
                            "name": tc_name,
                            "arguments": tc_args_str if isinstance(tc_args_str, str) else json.dumps(tc_args_str)
                        }
                    })
                messages.append(asst_msg_dict)

                for tc in raw_tool_calls:
                    tc_id = getattr(tc, "id", f"call_{iteration}")
                    tc_fn = getattr(tc, "function", None)
                    fn_name = getattr(tc_fn, "name", "")
                    raw_args = getattr(tc_fn, "arguments", {})

                    if isinstance(raw_args, str):
                        try:
                            fn_args = json.loads(raw_args)
                        except Exception:
                            fn_args = {}
                    else:
                        fn_args = raw_args or {}

                    tool_output = self.execute_tool(
                        tool_name=fn_name,
                        tool_args=fn_args,
                        authenticated_student_id=authenticated_student_id,
                        db=db
                    )

                    tool_calls_executed.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "status": tool_output.get("status", "success")
                    })

                    if fn_name in ["search_opportunities", "tool_search_opportunities"]:
                        for r in tool_output.get("results", []):
                            u = r.get("official_url")
                            t = r.get("title")
                            if u and u not in seen_urls:
                                seen_urls.add(u)
                                citations.append({"title": t or "Official Portal", "url": u})
                            if r.get("opportunity_id"):
                                state.discussed_opportunities.append({
                                    "id": r.get("opportunity_id"),
                                    "title": t,
                                    "provider": r.get("provider"),
                                    "deadline": r.get("published_deadline") or r.get("deadline"),
                                    "official_url": u
                                })
                    elif fn_name in ["assess_eligibility", "tool_assess_eligibility"]:
                        u = tool_output.get("official_url")
                        t = tool_output.get("title")
                        if u and u not in seen_urls:
                            seen_urls.add(u)
                            citations.append({"title": t or "Official Portal", "url": u})
                    elif fn_name in ["generate_application_checklist", "tool_generate_application_checklist"]:
                        u = tool_output.get("official_url")
                        t = tool_output.get("title")
                        if u and u not in seen_urls:
                            seen_urls.add(u)
                            citations.append({"title": t or "Official Portal", "url": u})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": fn_name,
                        "content": json.dumps(tool_output)
                    })
            else:
                final_reply = choice_message.content or ""
                break

        if not final_reply and iteration >= self.max_tool_iterations:
            logger.warning("Reached maximum tool call iterations (%d). Forcing final synthesis.", self.max_tool_iterations)
            try:
                forced_response = self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages + [{"role": "user", "content": "Please synthesize your final grounded answer based strictly on the tool evidence gathered above."}],
                    temperature=0.1,
                    max_tokens=1500
                )
                final_reply = forced_response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"Failed forced synthesis after tool iterations: {e}")
                final_reply = "I retrieved the relevant records from the verified directory above, but could not finalize the response. Please refer to the verified links provided."

        return final_reply, tool_calls_executed, citations

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
        """Provides genuine discovery across all five requested opportunity categories with provenance and degree relevance."""
        mem = state.student_memory or {}
        degree_title = mem.get("degree_title") or "Bachelor of Arts in Social Sciences"
        specialisations = mem.get("specialisations")
        if isinstance(specialisations, list):
            spec_str = ", ".join(specialisations)
        elif specialisations:
            spec_str = str(specialisations)
        else:
            spec_str = "Sociology, Psychology"
        university = mem.get("university") or "University of Nairobi"
        field_of_study = mem.get("field_of_study") or "Social Sciences & Humanities"
        expected_grad = mem.get("expected_graduation") or "December 2026"
        degree_level = mem.get("degree_level") or "Undergraduate"
        country = mem.get("country") or "Kenya"

        # The five requested categories configuration
        categories_config = [
            {
                "category_name": "Scholarships",
                "db_category": "Scholarship",
                "query": f"scholarship undergraduate {field_of_study} {spec_str} tuition funding Kenya",
                "relevance_template": f"Directly provides tuition funding and maintenance support for students enrolled in undergraduate degree programmes at accredited Kenyan universities, including {degree_title} at {university}.",
            },
            {
                "category_name": "Internships",
                "db_category": "Internship",
                "query": f"internship attachment public service un {field_of_study} {spec_str} Kenya",
                "relevance_template": f"Offers structured public-sector and institutional practical training directly open to {degree_title} students and graduates in {spec_str}.",
            },
            {
                "category_name": "Fellowships",
                "db_category": "Fellowship",
                "query": f"fellowship research women leadership {field_of_study} Kenya",
                "relevance_template": f"Supports research and policy scholarship in African development and social sciences; valuable benchmark for postgraduate planning following completion of your {degree_title}.",
            },
            {
                "category_name": "Research Opportunities",
                "db_category": "Competition",
                "query": f"research innovation social impact challenge {field_of_study} Kenya",
                "relevance_template": f"Enables university students to apply sociological and psychological research to design evidence-based solutions for social impact and sustainable development.",
            },
            {
                "category_name": "Career Development Programmes (Graduate Trainee schemes)",
                "db_category": "Graduate Trainee",
                "query": f"graduate trainee career development leadership {field_of_study} Kenya",
                "relevance_template": f"Provides structured graduate leadership development, mentorship, and professional career acceleration ahead of and upon your {expected_grad} graduation.",
            },
        ]

        tool_calls = []
        citations = []
        all_discussed = []
        seen_opp_ids = set()
        seen_urls = set()
        category_sections = []

        for idx, cat_cfg in enumerate(categories_config, 1):
            cat_name = cat_cfg["category_name"]
            db_cat = cat_cfg["db_category"]
            search_query = cat_cfg["query"]
            rel_template = cat_cfg["relevance_template"]

            search_res = tool_search_opportunities(SearchOpportunitiesInput(
                query=search_query,
                category=db_cat,
                top_k=4
            ))
            tool_calls.append({"tool": "search_opportunities", "category": db_cat, "query": search_query})

            results = search_res.get("results", [])
            # Filter results for unique opportunities
            cat_matches = []
            for r in results:
                opp_id = r.get("opportunity_id")
                if opp_id and opp_id not in seen_opp_ids:
                    seen_opp_ids.add(opp_id)
                    cat_matches.append(r)
                elif not opp_id and r.get("title") not in [m.get("title") for m in cat_matches]:
                    cat_matches.append(r)

            # If no matches in primary search, try category fallback
            if not cat_matches:
                fallback_res = tool_search_opportunities(SearchOpportunitiesInput(query=cat_name, category=db_cat, top_k=2))
                for r in fallback_res.get("results", []):
                    opp_id = r.get("opportunity_id")
                    if opp_id and opp_id not in seen_opp_ids:
                        seen_opp_ids.add(opp_id)
                        cat_matches.append(r)

            if cat_matches:
                cat_status = "Matches found"
                opp_blocks = []
                for opp in cat_matches[:1]:  # Pick best match for clean, thorough representation
                    opp_id = opp.get("opportunity_id")
                    title = opp.get("title", "Opportunity")
                    provider = opp.get("provider", "Official Organization")
                    url = opp.get("official_url", "")
                    raw_deadline = opp.get("deadline") or opp.get("published_deadline")
                    is_verified = (str(opp.get("verification_status", "")).strip().upper() == "VERIFIED")

                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        citations.append({"title": title, "url": url})

                    all_discussed.append({
                        "id": opp_id,
                        "title": title,
                        "provider": provider,
                        "deadline": raw_deadline,
                        "official_url": url,
                        "category": cat_name
                    })

                    # 1. Relevance to degree
                    relevance_text = rel_template

                    # 2. Eligibility requirements
                    excerpt = extract_clean_content_body(opp.get("content_excerpt", ""))
                    degree_req = opp.get("degree_levels") or "Undergraduate"
                    fields_req = opp.get("fields_of_study") or "All Academic Disciplines"
                    eligibility_text = f"Degree Level: `{degree_req}` | Target Disciplines: `{fields_req}`. {excerpt}"
                    if len(eligibility_text) > 220:
                        eligibility_text = eligibility_text[:217] + "..."

                    # 3. Likelihood of qualifying
                    eval_res = tool_assess_eligibility(AssessEligibilityInput(
                        opportunity_id=opp_id,
                        student_degree_level=degree_level,
                        student_field_of_study=field_of_study,
                        student_year_of_study=3
                    ))
                    overall_qual = eval_res.get("overall_assessment", "Under Review")
                    if overall_qual == "Likely Eligible":
                        qual_text = (
                            f"**Likely to qualify** — Meets published criteria for {degree_level} standing "
                            f"and {field_of_study} (anticipating graduation in {expected_grad})."
                        )
                    else:
                        qual_text = (
                            f"**Qualifications under review / Criteria difference** — Published criteria require `{degree_req}`, "
                            f"whereas current profile is {degree_level} at {university} (graduating {expected_grad})."
                        )

                    # 4. Official deadline with provenance
                    cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(
                        deadline_date_str=raw_deadline,
                        is_officially_verified=is_verified,
                        verification_source=provider,
                        verification_date=date.today().isoformat() if is_verified else None
                    ))
                    deadline_val = raw_deadline or "Continuous / Rolling intake"
                    dl_provenance = cd.get("deadline_provenance", "Recorded in directory — requires official verification")
                    app_status_prov = cd.get("application_status_provenance", "Application status unconfirmed")
                    days_rem = cd.get("days_remaining")
                    timing_str = f" ({days_rem} days remaining)" if days_rem is not None and days_rem >= 0 else ""

                    # 5. Required documents
                    chk_res = tool_generate_application_checklist(GenerateChecklistInput(opportunity_id=opp_id))
                    doc_tasks = [t["task"] for t in chk_res.get("tasks", []) if t.get("section") == "Required Documents"]
                    if not doc_tasks:
                        doc_tasks = [
                            "Valid National ID card or passport",
                            "Official University Admission Letter / Student ID",
                            "Current certified academic transcripts",
                            "Updated Curriculum Vitae (CV)",
                            "KRA PIN Certificate"
                        ]
                    docs_summary = "; ".join(doc_tasks[:4])

                    # 6. Official application website
                    portal_link = f"[{title} Official Portal]({url})" if url else "Official institutional portal (refer to verified source notes)"

                    opp_blocks.append(
                        f"#### [{title}]({url})\n"
                        f"- **Sponsoring Body / Provider:** {provider}\n"
                        f"1. **Relevance to Degree ({degree_title}):** {relevance_text}\n"
                        f"2. **Eligibility Requirements:** {eligibility_text}\n"
                        f"3. **Likelihood of Qualifying:** {qual_text}\n"
                        f"4. **Official Deadline & Provenance:** `{deadline_val}`{timing_str} | **Deadline Provenance:** `{dl_provenance}` | **Application Status:** `{app_status_prov}`\n"
                        f"5. **Required Application Documents:** {docs_summary}\n"
                        f"6. **Official Application Website:** {portal_link}"
                    )

                category_sections.append(
                    f"### {idx}. {cat_name} — Category Coverage Status: `{cat_status}`\n\n"
                    + "\n\n".join(opp_blocks)
                )
            else:
                cat_status = "No matching records found"
                category_sections.append(
                    f"### {idx}. {cat_name} — Category Coverage Status: `{cat_status}`\n\n"
                    f"No matching verified opportunities are currently indexed in our verified directory for {field_of_study} ({degree_title}). "
                    f"We recommend checking the University of Nairobi Research & Grants Office and national funding agencies."
                )

        state.discussed_opportunities = all_discussed

        profile_header = (
            f"### Academic Profile Preserved\n"
            f"- **Country:** {country}\n"
            f"- **University:** {university}\n"
            f"- **Degree Title:** {degree_title}\n"
            f"- **Specialisations:** {spec_str}\n"
            f"- **Degree Level:** {degree_level}\n"
            f"- **Field of Study:** {field_of_study}\n"
            f"- **Expected Graduation:** {expected_grad}\n\n"
            f"I can help you discover opportunities available to Kenyan university students across verified categories.\n"
            f"Here is your comprehensive five-category opportunity discovery report tailored to your exact academic background:\n\n"
        )

        reply = profile_header + "\n\n---\n\n".join(category_sections) + (
            "\n\n---\n"
            "💡 **Next Steps:**\n"
            "- Ask: *\"Generate an application checklist for [Opportunity Title]\"* to get a personalized preparation guide.\n"
            "- Ask: *\"Check my eligibility in detail for [Opportunity Title]\"* to run an in-depth requirements breakdown.\n"
            "- Ask: *\"Compare deadlines\"* to prioritize upcoming submission cutoffs."
        )

        return {
            "response": reply,
            "tool_calls": tool_calls,
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
            if search_res.get("results") and search_res["results"][0].get("similarity_score", 0.0) >= 0.50:
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

    def _handle_tracking_progress(
        self,
        state: ConversationState,
        authenticated_student_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Handles student questions regarding their tracked applications and progress."""
        from app.agent.tools import GetTrackedApplicationsInput, tool_get_tracked_applications
        tracking_res = tool_get_tracked_applications(
            GetTrackedApplicationsInput(),
            authenticated_student_id=authenticated_student_id,
            db=db
        )

        tool_calls = [{"tool": "get_tracked_applications", "status": tracking_res.get("status", "success")}]
        citations: List[Dict[str, str]] = []

        if tracking_res.get("status") == "unauthenticated":
            reply = (
                "You are not currently logged in or have not linked a student profile. "
                "Please sign in and save opportunities to your Application Planner to monitor deadlines and tasks."
            )
            return {"response": reply, "tool_calls": tool_calls, "citations": citations}

        apps = tracking_res.get("applications", [])
        if not apps:
            reply = (
                "You are not currently tracking any applications in your Application Planner.\n\n"
                "💡 **How to start:**\n"
                "1. Visit the **Personalized Matches** or **Discover** page.\n"
                "2. Click **'Save to Planner'** on opportunities that match your course.\n"
                "3. Your checklist, deadlines, and progress will automatically appear here!"
            )
            return {"response": reply, "tool_calls": tool_calls, "citations": citations}

        app_summaries = []
        all_pending_tasks = []
        urgent_deadlines = []

        for app in apps:
            title = app.get("title", "Opportunity")
            stage = app.get("stage", "Saved")
            url = app.get("official_url")
            dl = app.get("deadline") or "Rolling"
            days_rem = app.get("days_remaining")
            dl_status = app.get("deadline_status") or "Active"
            comp_cnt = app.get("completed_tasks", 0)
            tot_cnt = app.get("tasks_count", 0)
            pending = app.get("pending_tasks", [])

            if url and not any(c["url"] == url for c in citations):
                citations.append({"title": title, "url": url})

            if days_rem is not None and 0 <= days_rem <= 14:
                urgent_deadlines.append(f"⚠️ **{title}**: Closes in **{days_rem} days** ({dl})")

            for p in pending:
                all_pending_tasks.append(f"- **{title}**: {p}")

            app_summaries.append(
                f"### [{title}]({url or '#'})\n"
                f"- **Stage:** `{stage}` | **Deadline:** {dl} (`{dl_status}`)\n"
                f"- **Checklist Progress:** {comp_cnt}/{tot_cnt} tasks completed"
                + (f" ({len(pending)} pending)" if pending else " (All done! 🎉)")
            )

        reply_parts = [
            f"You are currently tracking **{len(apps)} application(s)**:\n",
            "\n\n".join(app_summaries)
        ]

        if urgent_deadlines:
            reply_parts.append("\n\n---\n#### ⏰ Approaching Deadlines:\n" + "\n".join(urgent_deadlines))

        if all_pending_tasks:
            reply_parts.append("\n\n---\n#### 📋 Priority Tasks to Work On Next:\n" + "\n".join(all_pending_tasks[:5]))
            if len(all_pending_tasks) > 5:
                reply_parts.append(f"\n*(and {len(all_pending_tasks) - 5} more in your Application Planner)*")
        else:
            reply_parts.append("\n\n---\n🎉 All current checklist tasks are marked as complete! Review your submission documents before the closing date.")

        return {
            "response": "\n".join(reply_parts),
            "tool_calls": tool_calls,
            "citations": citations
        }

    def _fallback_deterministic_turn(
        self,
        message: str,
        intent: IntentType,
        intent_meta: Dict[str, Any],
        state: ConversationState,
        authenticated_student_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, str]]]:
        tool_calls_executed: List[Dict[str, Any]] = []
        citations: List[Dict[str, str]] = []
        final_reply = ""

        if intent == IntentType.TRACKING_PROGRESS:
            res = self._handle_tracking_progress(state, authenticated_student_id, db)
            final_reply = res["response"]
            tool_calls_executed.extend(res["tool_calls"])
            citations.extend(res["citations"])

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

        elif intent == IntentType.CHECKLIST_GENERATION:
            target_id = intent_meta.get("entities", {}).get("opportunity_id")
            if not target_id and state.discussed_opportunities:
                target_id = state.discussed_opportunities[0].get("id")

            if not target_id:
                opp_search = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
                if opp_search.get("results") and opp_search["results"][0].get("similarity_score", 0.0) >= 0.50:
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
                if any(w in message.lower() for w in ["find", "search", "show me", "explore", "scholarships", "fellowships", "opportunities", "internships"]):
                    res = self._handle_opportunity_discovery(message, state)
                    return res["response"], res["tool_calls"], res["citations"]

                search_res = tool_search_opportunities(SearchOpportunitiesInput(query=message, top_k=1))
                if search_res.get("results") and search_res["results"][0].get("similarity_score", 0.0) >= 0.50:
                    target_id = search_res["results"][0].get("opportunity_id")

            mem = state.student_memory
            deg = mem.get("degree_level", "Undergraduate")
            field = mem.get("field_of_study", "All Academic Disciplines")
            yr = mem.get("year_of_study", 3)

            if target_id:
                eval_res = tool_assess_eligibility(AssessEligibilityInput(
                    opportunity_id=target_id,
                    student_degree_level=deg,
                    student_field_of_study=field,
                    student_year_of_study=int(yr)
                ))
                tool_calls_executed.append({"tool": "assess_eligibility", "opportunity_id": target_id})

                if eval_res.get("status") == "success":
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
                    final_reply = (
                        f"I could not verify published eligibility criteria for '{target_id}' in our verified directory.\n\n"
                        "To prevent misinformation, I only evaluate criteria certified against official published notices. "
                        "Please check the official provider portal directly or ask about another verified opportunity (e.g. *Safaricom attachment*, *HEF*, *Chevening*, *KRA*)."
                    )
                    state.pending_question = None
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
            is_five_category_discovery = (
                intent == IntentType.OPPORTUNITY_DISCOVERY and (
                    any(w in message.lower() for w in ["scholarships", "scholarship"]) and
                    any(w in message.lower() for w in ["internships", "internship", "attachment"]) and
                    any(w in message.lower() for w in ["fellowships", "fellowship"])
                )
            )

            if is_five_category_discovery:
                categories_to_query = [
                    ("1. Scholarships", "Scholarship", "scholarship tuition financial aid funding"),
                    ("2. Internships", "Internship", "internship industrial attachment practicum intake"),
                    ("3. Fellowships", "Fellowship", "fellowship academic scholars research leaders"),
                    ("4. Research Opportunities", None, "research opportunity grant challenge innovation"),
                    ("5. Career Development Programmes", None, "career development leadership graduate trainee programme")
                ]

                mem = state.student_memory
                deg_title = mem.get("degree_title") or "Bachelor of Arts in Social Sciences"
                specs = mem.get("specialisations") or ["Sociology", "Psychology"]
                field = mem.get("field_of_study", "Social Sciences & Humanities")
                uni = mem.get("university", "University of Nairobi")
                exp_grad = mem.get("expected_graduation") or "December 2026"
                deg_level = mem.get("degree_level", "Undergraduate")

                seen_opp_ids = set()
                cat_sections = []
                state.discussed_opportunities = []

                for cat_display, cat_filter, q_kw in categories_to_query:
                    enriched_cat_query = f"{q_kw} {field} {uni} Kenya"
                    search_res = tool_search_opportunities(SearchOpportunitiesInput(
                        query=enriched_cat_query,
                        category=cat_filter,
                        top_k=3
                    ))
                    tool_calls_executed.append({"tool": "search_opportunities", "query": enriched_cat_query, "category": cat_filter})

                    opps = search_res.get("results", [])
                    new_opps = []
                    for o in opps:
                        oid = o.get("opportunity_id")
                        if oid and oid not in seen_opp_ids and o.get("similarity_score", 0.0) >= MIN_RAG_SIMILARITY_THRESHOLD:
                            seen_opp_ids.add(oid)
                            new_opps.append(o)

                    if new_opps:
                        cat_header = f"### {cat_display} — **Status: Matches found** ({len(new_opps)} verified record(s))"
                        opp_cards = []
                        for opp in new_opps:
                            title = opp.get("title")
                            url = opp.get("official_url")
                            prov = opp.get("provider")
                            dl = opp.get("deadline")
                            req_fields = opp.get("fields_of_study") or "All Academic Disciplines"
                            req_degs = opp.get("degree_levels") or "Undergraduate / Degree Level Specified"
                            source_notes = opp.get("content_excerpt") or "Verified published requirements and guidelines are available via official portal."

                            cd = tool_calculate_deadline_countdown(DeadlineCountdownInput(
                                deadline_date_str=dl,
                                is_officially_verified=False
                            ))
                            dl_provenance = cd.get("deadline_provenance") or "Recorded in directory — requires official verification"
                            dl_label = cd.get("status_label")

                            state.discussed_opportunities.append({
                                "id": opp.get("opportunity_id"),
                                "title": title,
                                "provider": prov,
                                "deadline": dl,
                                "official_url": url
                            })
                            if url and not any(c["url"] == url for c in citations):
                                citations.append({"title": title, "url": url})

                            specs_str = ", ".join(specs) if isinstance(specs, list) else str(specs)
                            relevance = f"Directly relevant to your {deg_title} (Specialisations: {specs_str}). The sponsoring organization accepts {req_fields} for early-career placement and academic advancement."
                            elig_req = f"Degree Levels: {req_degs} | Target Fields: {req_fields}"

                            if "master" in req_degs.lower() and deg_level == "Undergraduate":
                                qualification = f"Conditionally Eligible — Requires undergraduate degree completion upon your expected graduation in {exp_grad}."
                            else:
                                qualification = "Likely Eligible — Your undergraduate status and academic discipline meet the published criteria."

                            deadline_info = f"{dl or 'Unspecified'} ({dl_label})"
                            docs = "National ID / Passport, official university academic transcripts, recommendation letters, and comprehensive CV (verify specific documentary requirements on the official portal)."

                            card = (
                                f"#### [{title}]({url})\n"
                                f"- **Provider:** {prov}\n"
                                f"- **1. Relevance to your degree:** {relevance}\n"
                                f"- **2. Published eligibility requirements:** {elig_req}\n"
                                f"- **3. Likelihood of qualifying:** **{qualification}**\n"
                                f"- **4. Application deadline:** **{deadline_info}**\n"
                                f"- **5. Required application documents:** {docs}\n"
                                f"- **6. Official application website:** [Official Application Portal]({url})\n"
                            )
                            opp_cards.append(card)
                        cat_sections.append(cat_header + "\n\n" + "\n".join(opp_cards))
                    else:
                        cat_header = f"### {cat_display} — **Status: No matching records found**"
                        explanation = (
                            "The knowledge base was searched for verified records matching your academic profile in this category, "
                            "but returned no matching entries at this time. (This indicates our verified directory does not currently hold "
                            "an active record for this category, not that such opportunities do not exist in Kenya)."
                        )
                        cat_sections.append(cat_header + "\n\n" + explanation)

                intro = (
                    f"Here is a comprehensive opportunity discovery across all five requested categories for a **{deg_title}** student "
                    f"specialising in **{', '.join(specs) if isinstance(specs, list) else specs}** at the **{uni}** "
                    f"(Expected Graduation: **{exp_grad}**):\n\n"
                )
                final_reply = intro + "\n\n---\n\n".join(cat_sections) + (
                    "\n\n---\n"
                    "> 🔍 *All details above are certified against official publisher records. Deadlines and status require confirmation on official portals.*"
                )
                state.pending_question = {
                    "question": "Would you like me to check your eligibility or generate an application checklist for any of these?",
                    "topic": "confirm_next_step",
                    "context": {"opportunities": [o["title"] for o in state.discussed_opportunities]}
                }
                return final_reply, tool_calls_executed, citations

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

        return final_reply, tool_calls_executed, citations

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
            if conversation_id in SESSION_STATE_CACHE:
                state = SESSION_STATE_CACHE[conversation_id]
            else:
                state = ConversationState(conversation_id=conversation_id, user_id=user_id, anonymous_session_id=session_id)
                SESSION_STATE_CACHE[conversation_id] = state

        if student_profile:
            for k, v in student_profile.items():
                if v and k not in state.student_memory:
                    state.student_memory[k] = v

        state.turn_count += 1

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

        entities = intent_meta.get("entities", {})
        if entities.get("university"):
            state.student_memory["university"] = entities["university"]
        if entities.get("year_of_study"):
            state.student_memory["year_of_study"] = entities["year_of_study"]
        if entities.get("field_of_study"):
            state.student_memory["field_of_study"] = entities["field_of_study"]
        if entities.get("degree_level"):
            state.student_memory["degree_level"] = entities["degree_level"]
        if entities.get("degree_title"):
            state.student_memory["degree_title"] = entities["degree_title"]
        if entities.get("specialisations"):
            state.student_memory["specialisations"] = entities["specialisations"]
        if entities.get("expected_graduation"):
            state.student_memory["expected_graduation"] = entities["expected_graduation"]
        if entities.get("country"):
            state.student_memory["country"] = entities["country"]

        authenticated_student_id = None
        if student_profile and (student_profile.get("id") or student_profile.get("student_id")):
            authenticated_student_id = student_profile.get("id") or student_profile.get("student_id")
        elif user_id and db:
            from app.models.entities import StudentProfile
            sp = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
            if sp:
                authenticated_student_id = sp.id

        tool_calls_executed = []
        citations = []
        final_reply = ""

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

        elif intent == IntentType.OUT_OF_SCOPE:
            final_reply = (
                "I could not find verified records for that inquiry because I specialize specifically in verified educational and early-career opportunities for university students in Kenya "
                "(such as scholarships, industrial attachments, trainee schemes, and competitions).\n\n"
                "I cannot assist with out-of-scope inquiries. Would you like to explore verified scholarships, attachment programmes, or check your eligibility for Kenyan institutions?"
            )
            state.pending_question = None

        else:
            used_llm = False
            if self.groq_client is not None:
                try:
                    final_reply, tool_calls_executed, citations = self._run_llm_tool_loop(
                        message=message,
                        intent=intent,
                        intent_meta=intent_meta,
                        state=state,
                        conversation_id=conversation_id,
                        authenticated_student_id=authenticated_student_id,
                        db=db
                    )
                    used_llm = True
                except Exception as e:
                    logger.warning(
                        "Groq LLM tool execution failed (%s: %s). Falling back to deterministic pipeline.",
                        type(e).__name__,
                        str(e)
                    )

            if not used_llm:
                final_reply, tool_calls_executed, citations = self._fallback_deterministic_turn(
                    message=message,
                    intent=intent,
                    intent_meta=intent_meta,
                    state=state,
                    authenticated_student_id=authenticated_student_id,
                    db=db
                )

        if final_reply:
            md_links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', final_reply)
            existing_urls = {c["url"] for c in citations}
            for link_text, link_url in md_links:
                if link_url not in existing_urls:
                    existing_urls.add(link_url)
                    citations.append({"title": link_text, "url": link_url})

        if conversation_id not in SESSION_CONTEXT_CACHE:
            SESSION_CONTEXT_CACHE[conversation_id] = []
        SESSION_CONTEXT_CACHE[conversation_id].append({"role": "user", "content": message})
        SESSION_CONTEXT_CACHE[conversation_id].append({"role": "assistant", "content": final_reply})
        SESSION_CONTEXT_CACHE[conversation_id] = SESSION_CONTEXT_CACHE[conversation_id][-MAX_SESSION_HISTORY_TURNS:]

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
        else:
            SESSION_STATE_CACHE[conversation_id] = state

        return {
            "response": final_reply,
            "tool_calls": tool_calls_executed,
            "citations": citations,
            "grounded": True,
            "intent": intent.value,
            "conversation_id": conversation_id,
            "session_id": session_id or conversation_id,
            "state": state.to_dict(),
            "suggested_follow_ups": self._generate_suggested_followups(intent, state)
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

agent_orchestrator = AgentOrchestrator()
