"""Intent Classification and Conversational Context Resolution Module.
Implements distinct intent categories with deterministic rule priority,
contextual entity extraction, and pending-question resolution.
"""

import re
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

class IntentType(str, Enum):
    GREETING_SOCIAL = "greeting_social"
    THANK_YOU = "thank_you"
    AMBIGUOUS_INCOMPLETE = "ambiguous_incomplete"
    OPPORTUNITY_DISCOVERY = "opportunity_discovery"
    SCHOLARSHIP_SEARCH = "scholarship_search"
    INTERNSHIP_SEARCH = "internship_search"
    GRADUATE_PROGRAMME_SEARCH = "graduate_programme_search"
    FELLOWSHIP_SEARCH = "fellowship_search"
    FIELD_SEARCH = "field_search"
    EXPLAIN_REQUIREMENTS = "explain_requirements"
    ELIGIBILITY_ASSESSMENT = "eligibility_assessment"
    DEADLINE_INQUIRY = "deadline_inquiry"
    OPPORTUNITY_COMPARISON = "opportunity_comparison"
    APPLICATION_PLANNING = "application_planning"
    CHECKLIST_GENERATION = "checklist_generation"
    TRACKING_PROGRESS = "tracking_progress"
    FOLLOW_UP_QUESTION = "follow_up_question"
    PREFERENCE_UPDATE = "preference_update"
    GENERAL_GUIDANCE = "general_guidance"
    OUT_OF_SCOPE = "out_of_scope"

# Keywords associated with known verified providers in Kenya
KNOWN_PROVIDERS = {
    # 1. Safaricom PLC
    "safaricom": "opp-safaricom-attachment-2026",
    "safaricom attachment": "opp-safaricom-attachment-2026",
    "safaricom internship": "opp-safaricom-attachment-2026",
    "safaricom graduate": "opp-safaricom-discover-gt-2026",
    "safaricom discover": "opp-safaricom-discover-gt-2026",
    "discover graduate": "opp-safaricom-discover-gt-2026",

    # 2. Kenya Revenue Authority (KRA)
    "kra": "opp-kra-internship-2026",
    "kenya revenue authority": "opp-kra-internship-2026",
    "kra internship": "opp-kra-internship-2026",

    # 3. Higher Education Financing (HEF / HELB)
    "hef": "opp-hef-undergraduate-2026",
    "higher education financing": "opp-hef-undergraduate-2026",
    "helb": "opp-hef-undergraduate-2026",

    # 4. Chevening Scholarships (UK FCDO)
    "chevening": "opp-chevening-kenya-2027",
    "chevening scholarship": "opp-chevening-kenya-2027",
    "chevening kenya": "opp-chevening-kenya-2027",

    # 5. DAAD Eastern Africa
    "daad": "opp-daad-region-kenya-2027",
    "daad scholarship": "opp-daad-region-kenya-2027",

    # 6. Equity Group Foundation (ELP)
    "equity": "opp-equity-leaders-elp-2026",
    "equity leaders": "opp-equity-leaders-elp-2026",
    "elp": "opp-equity-leaders-elp-2026",
    "wings to fly": "opp-equity-leaders-elp-2026",

    # 7. KCB Foundation
    "kcb": "opp-kcb-foundation-tertiary-2026",
    "2jiajiri": "opp-kcb-foundation-tertiary-2026",
    "kcb foundation": "opp-kcb-foundation-tertiary-2026",

    # 8. Mawazo Institute
    "mawazo": "opp-mawazo-fellowship-2027",
    "mawazo institute": "opp-mawazo-fellowship-2027",
    "mawazo fellowship": "opp-mawazo-fellowship-2027",

    # 9. Hult Prize
    "hult prize": "opp-hult-prize-kenya-2026",

    # 10. United Nations Gigiri (UNON)
    "un gigiri": "opp-un-gigiri-internship-2026",
    "united nations": "opp-un-gigiri-internship-2026",

    # 11. Presidential Digital Talent Programme (PDTP)
    "pdtp": "opp-pdtp-digika-2026",
    "presidential digital": "opp-pdtp-digika-2026",
    "digika": "opp-pdtp-digika-2026",
    "presidential digital talent": "opp-pdtp-digika-2026",

    # 12. Public Service Commission (PSC PSIP)
    "psip": "opp-psc-psip-internship-2026",
    "public service": "opp-psc-psip-internship-2026",
    "public service commission": "opp-psc-psip-internship-2026",
    "psip internship": "opp-psc-psip-internship-2026",

    # 13. Mastercard Foundation & USIU-Africa
    "mastercard": "opp-mastercard-fdn-usiu-2026",
    "mastercard foundation": "opp-mastercard-fdn-usiu-2026"
}

def extract_entities(text: str) -> Dict[str, Any]:
    """Extracts mentioned organizations, study levels, courses, and year of study."""
    clean = text.lower()
    entities: Dict[str, Any] = {
        "opportunity_id": None,
        "provider_keyword": None,
        "university": None,
        "field_of_study": None,
        "degree_level": None,
        "year_of_study": None
    }

    # Match provider
    for kw, opp_id in KNOWN_PROVIDERS.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', clean):
            entities["opportunity_id"] = opp_id
            entities["provider_keyword"] = kw
            break

    # Match universities
    uni_patterns = [
        (r'\b(uon|university of nairobi)\b', 'University of Nairobi'),
        (r'\b(ku|kenyatta university)\b', 'Kenyatta University'),
        (r'\b(jkuat|jomo kenyatta)\b', 'JKUAT'),
        (r'\b(strathmore|strathmore university)\b', 'Strathmore University'),
        (r'\b(moi university|moi)\b', 'Moi University'),
        (r'\b(egerton|egerton university)\b', 'Egerton University'),
        (r'\b(usiu|usiu-africa)\b', 'USIU-Africa')
    ]
    for pattern, name in uni_patterns:
        if re.search(pattern, clean):
            entities["university"] = name
            break

    # Match year of study
    yr_patterns = [
        (r'\b(first year|1st year|year 1)\b', 1),
        (r'\b(second year|2nd year|year 2)\b', 2),
        (r'\b(third year|3rd year|year 3)\b', 3),
        (r'\b(fourth year|4th year|year 4)\b', 4),
        (r'\b(fifth year|5th year|year 5)\b', 5)
    ]
    for pattern, yr in yr_patterns:
        if re.search(pattern, clean):
            entities["year_of_study"] = yr
            break

    # Match degree levels
    if re.search(r'\b(undergrad|undergraduate|bachelor|bachelors|degree)\b', clean):
        entities["degree_level"] = "Undergraduate"
    elif re.search(r'\b(diploma|cert|certificate)\b', clean):
        entities["degree_level"] = "Diploma"
    elif re.search(r'\b(master|masters|msc|mba|postgraduate)\b', clean):
        entities["degree_level"] = "Masters"
    elif re.search(r'\b(phd|doctorate)\b', clean):
        entities["degree_level"] = "PhD"

    # Match field of study
    field_patterns = [
        (r'\b(computer science|cs|computing|software engineering|it|information technology)\b', 'Computer Science'),
        (r'\b(engineering|electrical engineering|civil engineering|mechanical engineering)\b', 'Engineering'),
        (r'\b(business|commerce|economics|finance|accounting)\b', 'Business & Economics'),
        (r'\b(law|llb)\b', 'Law'),
        (r'\b(medicine|nursing|pharmacy|health)\b', 'Health Sciences'),
        (r'\b(agriculture|agribusiness)\b', 'Agriculture')
    ]
    for pattern, field in field_patterns:
        if re.search(pattern, clean):
            entities["field_of_study"] = field
            break

    return entities

def resolve_contextual_reply(
    message: str,
    pending_question: Optional[Dict[str, Any]]
) -> Tuple[Optional[IntentType], Optional[Dict[str, Any]]]:
    """Checks if student is answering an explicit question previously asked by assistant."""
    if not pending_question:
        return None, None

    clean = message.strip().lower()
    q_topic = pending_question.get("topic")
    q_context = pending_question.get("context", {})

    # 1. Yes/No confirmation (e.g. for checklist or applying)
    if clean in ["yes", "yeah", "yep", "sure", "please", "proceed", "create it", "do it"]:
        if q_topic == "confirm_checklist":
            return IntentType.CHECKLIST_GENERATION, q_context
        if q_topic == "confirm_eligibility":
            return IntentType.ELIGIBILITY_ASSESSMENT, q_context

    # 2. Destination choice ("Kenya", "Abroad", "Both")
    if clean in ["both", "kenya", "abroad", "international", "local"]:
        if q_topic == "clarify_destination":
            resolved_context = {**q_context, "destination_preference": clean}
            target_category = q_context.get("target_category", "scholarship")
            intent = IntentType.SCHOLARSHIP_SEARCH if target_category == "scholarship" else IntentType.OPPORTUNITY_DISCOVERY
            return intent, resolved_context

    # 3. Opportunity Category Selection
    category_map = {
        "1": "scholarship",
        "scholarships": "scholarship",
        "scholarship": "scholarship",
        "2": "internship",
        "internships": "internship",
        "internship": "internship",
        "attachment": "internship",
        "attachments": "internship",
        "3": "graduate_trainee",
        "graduate": "graduate_trainee",
        "jobs": "graduate_trainee",
        "4": "fellowship",
        "fellowships": "fellowship",
        "research": "fellowship"
    }
    if q_topic == "clarify_category" and clean in category_map:
        cat = category_map[clean]
        if cat == "scholarship":
            return IntentType.SCHOLARSHIP_SEARCH, q_context
        elif cat == "internship":
            return IntentType.INTERNSHIP_SEARCH, q_context
        elif cat == "graduate_trainee":
            return IntentType.GRADUATE_PROGRAMME_SEARCH, q_context
        elif cat == "fellowship":
            return IntentType.FELLOWSHIP_SEARCH, q_context

    # 4. University answering
    if q_topic == "ask_university":
        extracted = extract_entities(message)
        if extracted.get("university"):
            return IntentType.PREFERENCE_UPDATE, {"university": extracted["university"], "next_action": q_context.get("next_action")}

    # 5. Year of study answering
    if q_topic == "ask_year":
        extracted = extract_entities(message)
        if extracted.get("year_of_study"):
            return IntentType.PREFERENCE_UPDATE, {"year_of_study": extracted["year_of_study"], "next_action": q_context.get("next_action")}

    return None, None

def classify_intent(
    message: str,
    pending_question: Optional[Dict[str, Any]] = None,
    recently_discussed: Optional[List[Dict[str, Any]]] = None
) -> Tuple[IntentType, Dict[str, Any]]:
    """Classifies user message into one of the specialized intent categories.

    Returns: (IntentType, metadata_dict)
    """
    clean = message.strip().lower()
    tokens = re.sub(r'[^\w\s]', '', clean).split()
    entities = extract_entities(message)

    # Step 1: Check pending question resolution
    if pending_question:
        resolved_intent, resolved_ctx = resolve_contextual_reply(message, pending_question)
        if resolved_intent:
            return resolved_intent, {
                "resolved_from_pending": True,
                "pending_topic": pending_question.get("topic"),
                "context": resolved_ctx,
                "entities": entities
            }

    # Step 2: Out of Scope Check
    out_of_scope_patterns = [
        r'\b(rocket|mars|astronomy|spacecraft)\b',
        r'\b(hack|crack|bypass password|exploit)\b',
        r'\b(write a poem|write code for|write python script)\b',
        r'\b(recipe|cook|restaurant in paris)\b'
    ]
    for pattern in out_of_scope_patterns:
        if re.search(pattern, clean):
            return IntentType.OUT_OF_SCOPE, {"entities": entities}

    # Step 3: Gratitude / Thank You
    thank_you_phrases = ["thank you", "thanks", "asante", "shukran", "appreciated", "appreciate it", "many thanks", "thank you so much", "thx"]
    if clean in thank_you_phrases or any(clean.startswith(p) for p in ["thank you", "thanks", "asante"]):
        return IntentType.THANK_YOU, {"entities": entities}

    # Step 4: Greeting and Social Pleasantries
    greetings = {"hello", "hi", "hey", "habari", "sasa", "jambo", "howdy", "sup", "yo", "morning", "good morning", "good evening", "good afternoon"}
    conversational_phrases = ["who are you", "what are you", "what can you do", "introduce yourself", "tell me about yourself", "how does this work", "how do you work"]
    if clean in greetings or any(phrase in clean for phrase in conversational_phrases) or (len(tokens) <= 2 and any(t in greetings for t in tokens)):
        return IntentType.GREETING_SOCIAL, {"entities": entities}

    # Step 5: Broad Opportunity Discovery (e.g. 'I need some of the opportunity', 'Show me opportunities')
    discovery_patterns = [
        r'\bi need some (of the )?opportunit(y|ies)\b',
        r'\bi need opportunit(y|ies)\b',
        r'\bshow me (some )?opportunit(y|ies)\b',
        r'\bwhat opportunit(y|ies)\b',
        r'\bexplore opportunit(y|ies)\b',
        r'\blist (some )?opportunit(y|ies)\b',
        r'\bfind (some )?opportunit(y|ies)\b',
        r'\bavailable opportunit(y|ies)\b',
        r'\bany opportunit(y|ies)\b',
        r'\bshow me more\b',
        r'\bopportunities for me\b',
        r'\bgive me opportunit(y|ies)\b'
    ]
    if any(re.search(p, clean) for p in discovery_patterns):
        return IntentType.OPPORTUNITY_DISCOVERY, {"entities": entities}

    # Step 6: Ambiguous & Incomplete Requests (Single vague words like 'academic', 'scholarships')
    ambiguous_keywords = {
        "academic", "academics", "scholarship", "scholarships", "bursary", "bursaries",
        "internship", "internships", "attachment", "attachments", "opportunities", "opportunity",
        "help", "apply", "info", "funding"
    }
    if clean in ambiguous_keywords or (len(tokens) == 1 and clean in ambiguous_keywords):
        return IntentType.AMBIGUOUS_INCOMPLETE, {
            "ambiguous_term": clean,
            "entities": entities
        }

    if len(tokens) <= 2 and not any(t in ["find", "search", "check", "how", "what", "when", "can", "am", "which", "compare", "need", "show"] for t in tokens):
        if "academic" in clean:
            return IntentType.AMBIGUOUS_INCOMPLETE, {"ambiguous_term": "academic", "entities": entities}

    # Step 7: Opportunity Comparison & Superlative Queries ("Which one is best for me?", "Which one has earliest deadline?")
    comparison_patterns = [
        r'\bwhich one is best\b',
        r'\bwhich (one )?is best for me\b',
        r'\bwhich one\b',
        r'\bwhich (closes|deadline|has the earliest|is first|is earliest)\b',
        r'\bearliest deadline\b',
        r'\bcompare\b',
        r'\bwhich of (these|them)\b'
    ]
    for pattern in comparison_patterns:
        if re.search(pattern, clean):
            return IntentType.OPPORTUNITY_COMPARISON, {
                "comparison_type": "earliest_deadline" if "earliest" in clean or "first" in clean or "close" in clean else "best_fit",
                "entities": entities
            }

    # Step 8: Graduate Trainee & Job Inquiries (Matched before general eligibility)
    job_patterns = [
        r'\bwhat jobs can i apply for\b',
        r'\bjobs can i apply\b',
        r'\bgraduate trainee\b',
        r'\bgraduate trainee programme\b',
        r'\bgraduate programme\b',
        r'\bjobs for fresh graduates\b',
        r'\bentry level jobs\b'
    ]
    for pattern in job_patterns:
        if re.search(pattern, clean):
            return IntentType.GRADUATE_PROGRAMME_SEARCH, {"entities": entities}

    # Step 9: Application Checklist & Help Applying
    checklist_patterns = [
        r'\bhelp me apply\b',
        r'\bchecklist\b',
        r'\brequired documents\b',
        r'\bwhat documents\b',
        r'\bdocuments do i need\b',
        r'\bdocuments required\b',
        r'\bhow to apply\b',
        r'\bapplication steps\b',
        r'\bapplication checklist\b'
    ]
    for pattern in checklist_patterns:
        if re.search(pattern, clean):
            return IntentType.CHECKLIST_GENERATION, {"entities": entities}

    # Step 10: Explain Requirements of Opportunity
    requirement_patterns = [
        r'\bwhat are the requirements\b',
        r'\bwhat are the published requirements\b',
        r'\brequirements of (this|the|safaricom|hef|kra|chevening|equity)\b',
        r'\bwhat is required\b',
        r'\bwhat do i need to qualify\b',
        r'\bqualification requirements\b',
        r'\bwhat are the qualifications\b'
    ]
    for pattern in requirement_patterns:
        if re.search(pattern, clean):
            return IntentType.EXPLAIN_REQUIREMENTS, {"entities": entities}

    # Step 11: Eligibility Assessment
    eligibility_patterns = [
        r'\b(eligible|eligibility|qualify|qualification|can i apply|am i eligible|am i qualified)\b',
        r'\bcheck my (eligibility|chances|qualifications)\b',
        r'\bdo i meet\b'
    ]
    for pattern in eligibility_patterns:
        if re.search(pattern, clean):
            return IntentType.ELIGIBILITY_ASSESSMENT, {"entities": entities}

    # Step 12: Deadline Inquiry
    deadline_patterns = [
        r'\bdeadline\b',
        r'\bclosing date\b',
        r'\bwhen does it close\b',
        r'\bwhen is the deadline\b',
        r'\bwhat is the deadline\b',
        r'\bhow many days (left|remaining)\b',
        r'\bis it still open\b'
    ]
    for pattern in deadline_patterns:
        if re.search(pattern, clean):
            return IntentType.DEADLINE_INQUIRY, {"entities": entities}

    # Step 13: Follow-up Question or Specific Provider Lookup
    followup_patterns = [
        r'\bwhat about\s+([a-zA-Z\s]+)\b',
        r'\btell me about\s+([a-zA-Z\s]+)\b',
        r'\bhow about\s+([a-zA-Z\s]+)\b',
        r'\btell me (more|about that|about the first|about the second|about it)\b',
        r'\bwhat about (that|the other|the first|the second|it)\b',
        r'\bcan you explain that\b'
    ]
    for pattern in followup_patterns:
        if re.search(pattern, clean):
            return IntentType.FOLLOW_UP_QUESTION, {"entities": entities}

    # Step 14: Search by Field of Study
    if entities.get("field_of_study") and any(w in clean for w in ["anything for", "for students", "opportunities for", "for computer science", "for engineering"]):
        return IntentType.FIELD_SEARCH, {"entities": entities}

    # Step 15: Student Preference Update
    pref_patterns = [
        r'\bi am in (my )?(1st|2nd|3rd|4th|first|second|third|fourth) year\b',
        r'\bi study\b',
        r'\bmy gpa is\b',
        r'\bmy grade is\b',
        r'\bi attend\b'
    ]
    for pattern in pref_patterns:
        if re.search(pattern, clean):
            return IntentType.PREFERENCE_UPDATE, {"entities": entities}

    # Step 16: Internship & Attachment Search
    if re.search(r'\b(attachment|internship|internships|industrial attachment|practicum)\b', clean):
        return IntentType.INTERNSHIP_SEARCH, {"entities": entities}

    # Step 17: Scholarship Search
    if re.search(r'\b(scholarship|scholarships|bursary|bursaries|tuition grant|financial aid|hef|helb)\b', clean):
        return IntentType.SCHOLARSHIP_SEARCH, {"entities": entities}

    # Step 18: Fellowships & Research Competitions
    if re.search(r'\b(fellowship|fellowships|research grant|competition|hult prize|mawazo)\b', clean):
        return IntentType.FELLOWSHIP_SEARCH, {"entities": entities}

    # Step 19: Application Planning
    planning_patterns = [
        r'\bhow should i prepare\b',
        r'\bapplication plan\b',
        r'\bprepare my application\b',
        r'\btimeline to apply\b'
    ]
    for pattern in planning_patterns:
        if re.search(pattern, clean):
            return IntentType.APPLICATION_PLANNING, {"entities": entities}

    # Step 20: General Educational / Career Guidance
    guidance_patterns = [
        r'\bwhat is (an )?attachment\b',
        r'\bhow does (hef|helb|kuccps) work\b',
        r'\bdifference between\b',
        r'\bcareer advice\b'
    ]
    for pattern in guidance_patterns:
        if re.search(pattern, clean):
            return IntentType.GENERAL_GUIDANCE, {"entities": entities}

    # Default to Opportunity Discovery
    return IntentType.OPPORTUNITY_DISCOVERY, {"entities": entities}
