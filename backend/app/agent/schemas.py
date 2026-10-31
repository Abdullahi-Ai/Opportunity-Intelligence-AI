"""
Groq & OpenAI-compatible Tool Specifications for Opportunity Intelligence AI Agent.
"""

from typing import List, Dict, Any

TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_opportunities",
            "description": "Searches the verified Kenyan knowledge base in ChromaDB for opportunities, eligibility criteria, benefits, and requirements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query e.g. 'Safaricom industrial attachment computer science' or 'Mastercard Foundation scholarship'"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Scholarship", "Internship", "Graduate Trainee", "Fellowship", "Competition"],
                        "description": "Optional category filter"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to retrieve (default 4)",
                        "default": 4
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_deadline_countdown",
            "description": "Computes exact days remaining, today's date, and open/expired status for a published deadline date. Must ALWAYS be used for date arithmetic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deadline_date_str": {
                        "type": "string",
                        "description": "ISO date string YYYY-MM-DD (e.g. '2026-11-30')"
                    }
                },
                "required": ["deadline_date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assess_eligibility",
            "description": "Deterministically evaluates a student's degree level, course of study, and year of study against published opportunity criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "opportunity_id": {
                        "type": "string",
                        "description": "The exact ID of the opportunity, e.g. 'opp-safaricom-attachment-2026' or 'opp-hef-undergraduate-2026'"
                    },
                    "student_degree_level": {
                        "type": "string",
                        "description": "Student degree level e.g. Undergraduate, Diploma, Masters, PhD"
                    },
                    "student_field_of_study": {
                        "type": "string",
                        "description": "Student course/major e.g. Computer Science, Civil Engineering"
                    },
                    "student_year_of_study": {
                        "type": "integer",
                        "description": "Current year of study e.g. 1, 2, 3, 4"
                    }
                },
                "required": ["opportunity_id", "student_degree_level", "student_field_of_study", "student_year_of_study"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_application_checklist",
            "description": "Extracts verified document requirements and practical application steps for an opportunity as an actionable checklist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "opportunity_id": {
                        "type": "string",
                        "description": "The ID of the opportunity, e.g. 'opp-hef-undergraduate-2026'"
                    }
                },
                "required": ["opportunity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_tracked_applications",
            "description": "Retrieves the student's currently tracked and saved applications and checklist progress. Requires authenticated student session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_profile_id": {
                        "type": "string",
                        "description": "Optional student profile ID."
                    }
                },
                "required": []
            }
        }
    }
]
