"""Intent Classification and Conversational Context Resolution Module.
Implements 15 distinct intent categories with deterministic rule priority,
contextual entity extraction, and pending-question resolution.
"""

import re
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

class IntentType(str, Enum):
    GREETING_SOCIAL = "greeting_social"
    AMBIGUOUS_INCOMPLETE = "ambiguous_incomplete"
    OPPORTUNITY_DISCOVERY = "opportunity_discovery"
    SCHOLARSHIP_SEARCH = "scholarship_search"
    INTERNSHIP_SEARCH = "internship_search"
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
    "safaricom": "opp-safaricom-attachment-2026",
    "safaricom attachment": "opp-safaricom-attachment-2026",
    "safaricom internship": "opp-safaricom-attachment-2026",
    "safaricom graduate": "opp-safaricom-gt-2026",
    "kra": "opp-kra-gt-2026",
    "kenya revenue authority": "opp-kra-gt-2026",
    "hef": "opp-hef-undergraduate-2026",
    "higher education financing": "opp-hef-undergraduate-2026",
    "helb": "opp-hef-undergraduate-2026",
    "chevening": "opp-chevening-kenya-2026",
    "daad": "opp-daad-postgraduate-2026",
    "equity": "opp-equity-elp-2026",
    "equity leaders": "opp-equity-elp-2026",
    "elp": "opp-equity-elp-2026",
    "wings to fly": "opp-equity-elp-2026",
    "kcb": "opp-kcb-2jiajiri-2026",
    "2jiajiri": "opp-kcb-2jiajiri-2026",
    "mawazo": "opp-mawazo-fellowship-2026",
    "hult prize": "opp-hult-prize-kenya-2026",
    "un gigiri": "opp-un-gigiri-internship-2026",
    "united nations": "opp-un-gigiri-internship-2026",
    "pdtp": "opp-pdtp-internship-2026",
    "presidential digital": "opp-pdtp-internship-2026",
    "psip": "opp-psc-psip-2026",
    "public service": "opp-psc-psip-2026",
    "mastercard": "opp-mastercard-foundation-usiu-2026"
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
        (r'\b(medicine|nursing|pharmacy|health)\b', 'Health Sciences')
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
    """
    Checks if student is answering an explicit question previously asked by assistant.
    Examples:
    - Assistant asked Kenya or abroad? -> Student says 'Both' or 'Kenya'
    - Assistant asked for application checklist? -> Student says 'Yes'
    - Assistant asked for university? -> Student says 'University of Nairobi'
    - Assistant asked for year of study? -> Student says '3rd year'
    """
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

    # 3. Opportunity Category Choice ("Scholarships", "Internships", "Both")
    if clean in ["scholarship", "scholarships", "internship", "internships", "attachments", "attachment", "both"]:
        if q_topic == "clarify_category":
            if "scholarship" in clean:
                return IntentType.SCHOLARSHIP_SEARCH, q_context
            elif "internship" in clean or "attachment" in clean:
                return IntentType.INTERNSHIP_SEARCH, q_context
            else:
                return IntentType.OPPORTUNITY_DISCOVERY, q_context

    # 4. Clarify academic choice ("scholarships", "degree", "research", "requirements")
    if q_topic == "clarify_academic":
        if "scholarship" in clean or "aid" in clean or "loan" in clean or "hef" in clean:
            return IntentType.SCHOLARSHIP_SEARCH, q_context
        if "intern" in clean or "attach" in clean:
            return IntentType.INTERNSHIP_SEARCH, q_context
        if "research" in clean or "fellow" in clean:
            return IntentType.OPPORTUNITY_DISCOVERY, {**q_context, "category": "Fellowship"}
        if "requirement" in clean or "criteria" in clean:
            return IntentType.GENERAL_GUIDANCE, q_context

    # 5. University answering
    if q_topic == "ask_university":
        extracted = extract_entities(message)
        if extracted.get("university") or len(clean.split()) <= 4:
            uni_name = extracted.get("university") or message.strip()
            return IntentType.PREFERENCE_UPDATE, {"university": uni_name, "next_action": q_context.get("next_action")}

    # 6. Year of study answering
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
    """
    Classifies user message into one of 15 intent categories.
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

    # Step 3: Greeting and Social Pleasantries
    greetings = {"hello", "hi", "hey", "habari", "sasa", "jambo", "howdy", "sup", "yo", "morning", "good morning", "good evening", "good afternoon"}
    conversational_phrases = ["who are you", "what are you", "what can you do", "introduce yourself", "tell me about yourself", "how does this work", "how do you work"]
    if clean in greetings or any(phrase in clean for phrase in conversational_phrases) or (len(tokens) <= 2 and any(t in greetings for t in tokens)):
        return IntentType.GREETING_SOCIAL, {"entities": entities}

    # Step 4: Ambiguous & Incomplete Requests (Single words or vague keywords)
    # When a student types single words like "academic", "scholarship", "opportunities", "internship", "help"
    ambiguous_keywords = {"academic", "academics", "scholarship", "scholarships", "bursary", "bursaries", "internship", "internships", "attachment", "attachments", "opportunities", "opportunity", "help", "apply", "info"}
    if clean in ambiguous_keywords or (len(tokens) == 1 and clean in ambiguous_keywords):
        return IntentType.AMBIGUOUS_INCOMPLETE, {
            "ambiguous_term": clean,
            "entities": entities
        }

    # If message is 1-2 words and has no action verb or question structure
    if len(tokens) <= 2 and not any(t in ["find", "search", "check", "how", "what", "when", "can", "am", "which", "compare"] for t in tokens):
        if "academic" in clean:
            return IntentType.AMBIGUOUS_INCOMPLETE, {"ambiguous_term": "academic", "entities": entities}
        if "scholarship" in clean:
            return IntentType.AMBIGUOUS_INCOMPLETE, {"ambiguous_term": "scholarship", "entities": entities}
        if "internship" in clean or "attachment" in clean:
            return IntentType.AMBIGUOUS_INCOMPLETE, {"ambiguous_term": "internship", "entities": entities}

    # Step 5: Opportunity Comparison & Superlative Queries ("Which one has earliest deadline?", "Which closes first?")
    comparison_patterns = [
        r'\bwhich one\b',
        r'\bwhich (closes|deadline|has the earliest|is first|is earliest)\b',
        r'\bearliest deadline\b',
        r'\bcompare\b',
        r'\bwhich of (these|them)\b'
    ]
    for pattern in comparison_patterns:
        if re.search(pattern, clean):
            return IntentType.OPPORTUNITY_COMPARISON, {
                "comparison_type": "earliest_deadline" if "earliest" in clean or "first" in clean or "close" in clean else "general",
                "entities": entities
            }

    # Step 6: Follow-up Question about previously discussed opportunity
    followup_patterns = [
        r'\btell me (more|about that|about the first|about the second|about it)\b',
        r'\bwhat about (that|the other|the first|the second|it)\b',
        r'\bwhat does it (offer|require|pay)\b',
        r'\bcan you explain that\b'
    ]
    for pattern in followup_patterns:
        if re.search(pattern, clean):
            return IntentType.FOLLOW_UP_QUESTION, {"entities": entities}

    # Step 7: Application Checklist Generation
    checklist_patterns = [
        r'\bchecklist\b',
        r'\brequired documents\b',
        r'\bwhat documents\b',
        r'\bdocuments do i need\b',
        r'\bdocuments required\b',
        r'\bhow to apply\b',
        r'\bapplication steps\b'
    ]
    for pattern in checklist_patterns:
        if re.search(pattern, clean):
            return IntentType.CHECKLIST_GENERATION, {"entities": entities}

    # Step 8: Eligibility Assessment
    eligibility_patterns = [
        r'\b(eligible|eligibility|qualify|qualification|can i apply|am i eligible|am i qualified)\b',
        r'\bcheck my (eligibility|chances|qualifications)\b',
        r'\bdo i meet\b'
    ]
    for pattern in eligibility_patterns:
        if re.search(pattern, clean):
            return IntentType.ELIGIBILITY_ASSESSMENT, {"entities": entities}

    # Step 9: Deadline Inquiry
    deadline_patterns = [
        r'\bdeadline\b',
        r'\bclosing date\b',
        r'\bwhen does it close\b',
        r'\bwhen is the deadline\b',
        r'\bhow many days (left|remaining)\b',
        r'\bis it still open\b'
    ]
    for pattern in deadline_patterns:
        if re.search(pattern, clean):
            return IntentType.DEADLINE_INQUIRY, {"entities": entities}

    # Step 10: Application Planning
    planning_patterns = [
        r'\bhow should i prepare\b',
        r'\bapplication plan\b',
        r'\bprepare my application\b',
        r'\btimeline to apply\b'
    ]
    for pattern in planning_patterns:
        if re.search(pattern, clean):
            return IntentType.APPLICATION_PLANNING, {"entities": entities}

    # Step 11: Application Tracking Progress
    tracking_patterns = [
        r'\bmy applications\b',
        r'\btracked applications\b',
        r'\bstatus of my\b',
        r'\bwhat have i saved\b'
    ]
    for pattern in tracking_patterns:
        if re.search(pattern, clean):
            return IntentType.TRACKING_PROGRESS, {"entities": entities}

    # Step 12: Student Preference Update
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

    # Step 13: Internship & Attachment Search
    if re.search(r'\b(attachment|internship|internships|industrial attachment|practicum)\b', clean):
        return IntentType.INTERNSHIP_SEARCH, {"entities": entities}

    # Step 14: Scholarship Search
    if re.search(r'\b(scholarship|scholarships|bursary|bursaries|tuition grant|fellowship|financial aid)\b', clean):
        return IntentType.SCHOLARSHIP_SEARCH, {"entities": entities}

    # Step 15: General Educational / Career Guidance
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
