#when you want to use ollama , us ethis code 
#  from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langchain_community.chat_models import ChatOllama


# def ollama_chat(model: str = "mistral"):
#     """Create a chat model using Ollama."""
#     return ChatOllama(
#         model=model,
#         temperature=0.7,
#         top_k=10,
#         top_p=0.95,
#         repeat_penalty=1.1,
#     )


# REWRITE_TMPL = ChatPromptTemplate.from_messages([
#     ("system", """
# You rewrite intake questions with a warm, calm, and empathetic tone.
# Show understanding and compassion in your wording.
# Soften questions to sound supportive and reassuring while keeping the meaning.
# Ask exactly one clear, gentle question.
# Keep placeholders like {name} untouched.
# Use short sentences. Use simple, kind words.
# No emojis. No em dash.
# Return only the rewritten text.

# Example:
# Original: What injuries did you sustain?
# Rewritten: I'm sorry to hear that. Could you please tell me about any injuries you experienced?
# """),
#     ("user", "Original: {text}\nRewritten:")
# ])


# GREETING_TMPL = ChatPromptTemplate.from_messages([
#     ("system", """Write a short greeting for a legal intake agent.
# Warm and clear. Two sentences max.
# No emojis. No em dash."""),
#     ("user", "Agent name: {agent}\nFirm: {firm}\nGreeting:")
# ])


# class EmpatheticRewriter:
#     def __init__(self):
#         self.llm = ollama_chat()
#         self.rewrite_chain = REWRITE_TMPL | self.llm | StrOutputParser()
#         self.greet_chain = GREETING_TMPL | self.llm | StrOutputParser()
#         self.cache = {}

#     async def rewrite(self, text: str) -> str:
#         if not text:
#             return ""
#         if text in self.cache:
#             return self.cache[text]
#         try:
#             out = await self.rewrite_chain.ainvoke({"text": text})
#             out = out.strip() or text
#         except Exception:
#             out = text
#         self.cache[text] = out
#         return out

#     async def greeting(self, agent: str, firm: str) -> str:
#         key = f"greet::{agent}::{firm}"
#         if key in self.cache:
#             return self.cache[key]
#         try:
#             out = await self.greet_chain.ainvoke({"agent": agent, "firm": firm})
#             out = out.strip()
#         except Exception:
#             out = f"Thank you for calling {firm}. My name is {agent}. I will collect a few details to help you."
#         self.cache[key] = out
#         return out

# empathetic_rewriter.py
from __future__ import annotations

import re
import string
import os
import time
from datetime import datetime
from typing import Tuple, Optional
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# ---- LLM factory -------------------------------------------------------------
def openai_chat(model: str = "gpt-3.5-turbo"):
    """Create a chat model using OpenAI (adjust model via env OPENAI_API_KEY)."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment!")
        raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
    
    print(f"OpenAI API Key found: {api_key[:8]}...{api_key[-4:]}")
    
    return ChatOpenAI(
        model=model,
        temperature=0.3,   # lower for consistent parsing
        max_tokens=300,
        verbose=True,
    )
#when you want to use openai use this code
# ---- Prompts -----------------------------------------------------------------
REWRITE_TMPL = ChatPromptTemplate.from_messages([
    ("system", """
You are a compassionate legal intake assistant. Your role is to rewrite questions with deep empathy and warmth.

EMPATHY GUIDELINES:
- Always acknowledge their difficult situation first
- Use phrases like "I understand this is difficult", "I'm so sorry you're going through this"
- Show genuine care and concern
- Make them feel safe and supported
- Use gentle, reassuring language
- Validate their feelings

TONE REQUIREMENTS:
- Warm, caring, and professional
- Use "please" and "if you're comfortable sharing"
- Soften direct questions with empathetic lead-ins
- Make it conversational, not interrogative
- Show patience and understanding

Keep placeholders like {name} exactly as they are.
Return only the rewritten empathetic question.

Examples:
Original: What is your first name?
Rewritten: I'm here to help you through this difficult time. To get started, could you please share your first name with me?

Original: What injuries did you sustain?
Rewritten: I'm so sorry to hear about what happened to you. When you're ready, could you please tell me about any injuries you experienced? I know this might be difficult to talk about.

Original: When did this occur?
Rewritten: I understand this must be painful to revisit. If you're comfortable sharing, could you tell me when this incident took place?
"""),
    ("user", "Original: {text}\nRewritten:")
])

EXTRACTION_TMPL = ChatPromptTemplate.from_messages([
    ("system", """
You extract ONLY the specific data requested for the given question type.
Return just the value, no explanations.

Question types and examples:

first_name:
- "My first name is Srushti Jagtap" -> "Srushti"
- "It's John, John Smith" -> "John"

last_name:
- "My last name is Smith" -> "Smith"
- "My name is John Smith" -> "Smith"

incident_date:
- "It happened on March 15th, 2024" -> "March 15, 2024"
- "Last Tuesday, the 15th" -> "15"

incident_location:
- "Intersection of Main and Oak" -> "Main and Oak intersection"
- "Walmart on 5th Street" -> "Walmart on 5th Street"

incident_description:
- "I met with a car accident" -> "I met with a car accident"
- "I slipped and fell at the store" -> "I slipped and fell at the store"
- "A dog bit me while walking" -> "A dog bit me while walking"

injuries:
- "Back injury and neck pain" -> "back injury, neck pain"
- "Head injury, severe bleeding" -> "head injury, severe bleeding"

medical_treatment:
- "Yes, ER visit with pain meds" -> "Yes, ER visit with pain meds"
- "No" -> "No"

witnesses:
- "Two witnesses" -> "Two"
- "John and Mary saw it" -> "John and Mary"
- "One person" -> "One"
- "No witnesses" -> "No"

witness_names:
- "John Smith and Mary Johnson" -> "John Smith and Mary Johnson"
- "Just John" -> "John"
- "I don't know their names" -> "Unknown names"

other_reports:
- "Yes, to police" -> "Yes, to police"
- "Yes, to authority" -> "Yes, to authority"
- "Yes, to state office" -> "Yes, to state office"
- "Yes, to helpline" -> "Yes, to helpline"
- "Yes, I called the police" -> "Yes, to police"
- "No" -> "No"
- "No reports made" -> "No"

IMPORTANT: For other_reports, ONLY extract whether they reported and to whom, NOT location information.

Return ONLY the extracted value.
"""),
    ("user", "Question Type: {question_type}\nUser Response: {response}\nExtracted:")
])

VALIDATION_TMPL = ChatPromptTemplate.from_messages([
    ("system", """
Validate the extracted value for the question type.

Return one of:
- "VALID"
- "VALID_CORRECTED: <corrected value>"
- "INVALID: <gentle clarification request>"

Rules of thumb:
- first_name, last_name: should look like names (letters, hyphen, apostrophe, max 3 tokens). Capitalize first letter.
- incident_date: recognizable date or partial date (avoid future if context implies past).
- incident_location: a place description (not a person's name).
- incident_description: any reasonable description of what happened (should be at least a few words).
- medical_treatment: "Yes/No" optionally with short details.
- injuries: medical/body-part terms.
- other_reports: "Yes" with optional authority (police, state office, helpline) or "No". Do not collect location information.

Be brief and kind. For incident_description, accept any reasonable explanation of what happened.
For other_reports, accept any mention of reporting to authorities without requiring specific details.
"""),
    ("user", "Question Type: {question_type}\nExtracted: {extracted}\nValidation:")
])

GREETING_TMPL = ChatPromptTemplate.from_messages([
    ("system", """
Create a warm, empathetic greeting for a legal intake agent. 
Be professional and caring. Two sentences max. No emojis.
"""),
    ("user", "Agent name: {agent}\nFirm: {firm}\nGreeting:")
])

# ---- Lightweight rule-based extractors (fast, deterministic) -----------------
NAME_TOKEN = r"[A-Za-z][A-Za-z\-''\.]*"
PUNCT = string.punctuation + " "

def _clean_token(tok: str) -> str:
    t = tok.strip(PUNCT)
    t = t.replace("'", "'")
    if not t:
        return t
    return t[0].upper() + t[1:]

def _only_token(text: str, pat: str) -> Optional[str]:
    m = re.match(rf"^\s*(?P<x>{pat})\s*$", text)
    if m:
        return _clean_token(m.group("x"))
    return None

def extract_first_name_rule(text: str) -> Optional[str]:
    t = text.strip()

    # "my first name is Rusty", "first name Rusty"
    m = re.search(rf"\b(first\s*name|given\s*name)\s*(is|:)?\s+(?P<n>{NAME_TOKEN})\b", t, re.I)
    if m:
        return _clean_token(m.group("n"))

    # "my name is John Smith" → John
    m = re.search(rf"\b(my\s+name\s+is|i\s*am|i'm|this\s+is)\s+(?P<full>({NAME_TOKEN})(?:\s+{NAME_TOKEN}){{0,3}})\b", t, re.I)
    if m:
        first = m.group("full").split()[0]
        return _clean_token(first)

    # single-token "Rusty"
    solo = _only_token(t, NAME_TOKEN)
    if solo:
        return solo

    return None

def extract_last_name_rule(text: str) -> Optional[str]:
    t = text.strip()

    # "last name is Patel" / "surname Patel"
    m = re.search(rf"\b(last\s*name|surname|family\s*name)\s*(is|:)?\s+(?P<n>{NAME_TOKEN})\b", t, re.I)
    if m:
        return _clean_token(m.group("n"))

    # "my name is John Smith" → Smith
    m = re.search(rf"\b(my\s+name\s+is)\s+(?P<full>({NAME_TOKEN})(?:\s+{NAME_TOKEN}){{0,3}})\b", t, re.I)
    if m:
        toks = m.group("full").split()
        if len(toks) >= 2:
            return _clean_token(toks[-1])

    # single-token "Smith"
    solo = _only_token(t, NAME_TOKEN)
    if solo:
        return solo

    return None

def extract_yes_no_rule(text: str) -> Optional[str]:
    t = text.strip().lower()
    if t in {"yes", "y", "yeah", "yep", "yup", "sure", "affirmative"}:
        return "Yes"
    if t in {"no", "n", "nope", "nah", "negative"}:
        return "No"
    # "yes, ER visit" / "no, didn't go"
    if t.startswith("yes"):
        return "Yes" + text[len("yes"):].rstrip()
    if t.startswith("no"):
        return "No" + text[len("no"):].rstrip()
    return None

def extract_reports_rule(text: str) -> Optional[str]:
    t = text.strip().lower()
    
    # Simple yes/no responses
    if t in {"yes", "y", "yeah", "yep", "yup", "sure"}:
        return "Yes"
    if t in {"no", "n", "nope", "nah", "none"}:
        return "No"
    
    # Yes with specific authority mentioned
    if "police" in t:
        return "Yes, to police"
    if "authority" in t or "authorities" in t:
        return "Yes, to authority"
    if "state office" in t:
        return "Yes, to state office"
    if "helpline" in t:
        return "Yes, to helpline"
    if "insurance" in t:
        return "Yes, to insurance"
    
    # Variations of yes responses
    if t.startswith("yes"):
        # Extract what comes after "yes"
        remainder = text[3:].strip().strip(",")
        if remainder:
            return f"Yes, {remainder}"
        return "Yes"
    
    # Variations of no responses
    if t.startswith("no"):
        return "No"
    
    return None

def extract_witnesses_rule(text: str) -> Optional[str]:
        t = text.strip().lower()
        
        # No witnesses
        if t in {"no", "none", "no one", "nobody"}:
            return "No"
        
        # Number of witnesses
        if "two" in t or "2" in t:
            return "Two"
        if "one" in t or "1" in t:
            return "One"
        if "three" in t or "3" in t:
            return "Three"
        
        # Names mentioned
        if " and " in t:
            # Likely names: "john and mary"
            return text.strip()
        
        return None

def extract_witness_names_rule(text: str) -> Optional[str]:
    t = text.strip()
    
    if t.lower() in {"no", "none", "don't know", "unknown", "i don't know"}:
        return "Unknown names"
    
    # If it contains names (has "and" or multiple words that look like names)
    if " and " in t or len(t.split()) >= 2:
        return t
    
    return None

DATE_PAT = r"(?:\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t\.?|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b\s+\d{1,2}(?:,\s*\d{4})?)|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b"

def extract_date_rule(text: str) -> Optional[str]:
    # Pull a clear date-like substring if present
    m = re.search(DATE_PAT, text, re.I)
    if m:
        return m.group(0).strip().rstrip(",.")
    # rough "yesterday/today/last Tuesday" → leave to LLM
    return None

def normalize_name(s: str) -> str:
    s = s.strip().strip('."\'')
    parts = [p for p in re.split(r"\s+", s) if p]
    if not parts:
        return s
    return " ".join(_clean_token(p) for p in parts[:2])  # keep at most two tokens

# ---- EmpatheticRewriter ------------------------------------------------------
class EmpatheticRewriter:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        print("Initializing EmpatheticRewriter with rule-based extraction + OpenAI...")
        try:
            self.llm = openai_chat(model=model)
            print("OpenAI LLM initialized successfully")
        except Exception as e:
            print(f"Failed to initialize OpenAI LLM: {e}")
            raise
            
        self.rewrite_chain = REWRITE_TMPL | self.llm | StrOutputParser()
        self.extraction_chain = EXTRACTION_TMPL | self.llm | StrOutputParser()
        self.validation_chain = VALIDATION_TMPL | self.llm | StrOutputParser()
        self.greet_chain = GREETING_TMPL | self.llm | StrOutputParser()
        self.cache: dict[str, str] = {}
        
        print("All chains initialized successfully")

    # ---------- Public: rewrite ----------
    async def rewrite(self, text: str) -> str:
        if not text:
            return ""
        if text in self.cache:
            print(f"Cache hit for: {text[:50]}...")
            return self.cache[text]
            
        print(f"Making OpenAI API call for rewrite: {text[:50]}...")
        start_time = time.time()
        
        try:
            out = await self.rewrite_chain.ainvoke({"text": text})
            end_time = time.time()
            
            print(f"OpenAI rewrite successful in {end_time - start_time:.2f}s")
            print(f"Rewritten: {out}")
            
            out = (out or "").strip() or text
        except Exception as e:
            end_time = time.time()
            print(f"OpenAI rewrite failed after {end_time - start_time:.2f}s: {e}")
            out = text
            
        self.cache[text] = out
        return out

    # ---------- Public: extract & validate ----------
    async def extract_and_validate(self, question: str, user_response: str) -> Tuple[bool, str, str]:
        """
        Returns: (is_valid, extracted_info, error_message_if_invalid)
        """
        if not question or not user_response:
            return True, user_response or "", ""

        qtype = self._get_question_type(question)
        raw = user_response.strip()
        if not raw:
            return True, "", ""

        print(f"Extracting from: '{raw}' (type: {qtype})")

        # 1) FAST RULE-BASED EXTRACTION FIRST (deterministic)
        rule_value = self._rule_extract(qtype, raw)
        if rule_value:
            print(f"Rule-based extraction successful: '{rule_value}'")
            return True, rule_value, ""

        print("Falling back to LLM extraction...")

        # 2) LLM extraction as fallback
        extracted = ""
        start_time = time.time()
        try:
            extracted = await self.extraction_chain.ainvoke({
                "question_type": qtype,
                "response": raw
            })
            end_time = time.time()
            extracted = (extracted or "").strip()
            print(f"LLM extracted: '{extracted}' in {end_time - start_time:.2f}s")
        except Exception as e:
            print(f"LLM extraction failed: {e}")
            extracted = raw

        # 3) LLM validation
        try:
            validation = await self.validation_chain.ainvoke({
                "question_type": qtype,
                "extracted": extracted
            })
            validation = (validation or "").strip()
            print(f"Validation result: {validation}")
        except Exception as e:
            print(f"LLM validation failed: {e}")
            return True, extracted, ""

        return self._parse_validation_result(validation, extracted)

    # ---------- Public: greeting ----------
    async def greeting(self, agent: str, firm: str) -> str:
        key = f"greet::{agent}::{firm}"
        if key in self.cache:
            return self.cache[key]
        try:
            out = await self.greet_chain.ainvoke({"agent": agent, "firm": firm})
            out = (out or "").strip()
        except Exception:
            out = f"Thank you for calling {firm}. My name is {agent}, and I'm here to support you through this difficult time."
        self.cache[key] = out
        return out

    # ---------- Internals ----------
    def _get_question_type(self, question: str) -> str:
        q = question.lower()
        if "first name" in q or "given name" in q:
            return "first_name"
        if "last name" in q or "surname" in q or "family name" in q:
            return "last_name"
        if "when" in q or "date" in q or "time" in q:
            return "incident_date"
        
        # Check for reports BEFORE location to avoid "anywhere" confusion
        if ("report" in q or "filed" in q or "contacted" in q):
            # Make sure it's not asking about location of reports
            if not ("where did you report" in q or "location of report" in q):
                return "other_reports"
        
        # Location detection - be more specific
        if ("where" in q or "location" in q or "place" in q) and not ("anywhere" in q):
            return "incident_location"
        
        if "injur" in q or "hurt" in q or "harm" in q:
            return "injuries"
        if "medical" in q or "treatment" in q or "doctor" in q or "hospital" in q:
            return "medical_treatment"
        
        # Add incident description detection
        if ("what happened" in q or "describe" in q or "tell me about" in q or 
            "incident" in q or "accident" in q or "event" in q or "share what" in q):
            return "incident_description"
        
        # Add witness detection
        if "witness" in q:
            if "name" in q or "who" in q:
                return "witness_names"
            return "witnesses"
        
        return "general"
    

    def extract_reports_rule(text: str) -> Optional[str]:
        t = text.strip().lower()
        
        # Simple yes/no responses
        if t in {"yes", "y", "yeah", "yep", "yup", "sure"}:
            return "Yes"
        if t in {"no", "n", "nope", "nah", "none"}:
            return "No"
        
        # Yes with specific authority mentioned
        if "police" in t:
            return "Yes, to police"
        if "authority" in t or "authorities" in t:
            return "Yes, to authority"
        if "state office" in t:
            return "Yes, to state office"
        if "helpline" in t:
            return "Yes, to helpline"
        if "insurance" in t:
            return "Yes, to insurance"
        
        # Variations of yes responses - but ignore location info
        if t.startswith("yes"):
            remainder = text[3:].strip().strip(",")
            # Skip if it looks like location (highway, street, etc.)
            if any(word in remainder.lower() for word in ["highway", "street", "road", "avenue", "thirty", "twenty", "mile"]):
                return "Yes"
            if remainder:
                return f"Yes, {remainder}"
            return "Yes"
        
        # Variations of no responses
        if t.startswith("no"):
            return "No"
        
        return None
    def _rule_extract(self, qtype: str, text: str) -> Optional[str]:
        """Fast rule-based extraction - tries to extract without LLM first."""
        if qtype == "first_name":
            v = extract_first_name_rule(text)
            return normalize_name(v) if v else None
        if qtype == "last_name":
            v = extract_last_name_rule(text)
            return normalize_name(v) if v else None
        if qtype == "medical_treatment":
            v = extract_yes_no_rule(text)
            return v
        if qtype == "incident_date":
            v = extract_date_rule(text)
            return v
        # Add incident description rule-based extraction
        if qtype == "incident_description":
            cleaned = text.strip()
            if cleaned and len(cleaned) > 5:
                return cleaned
        # Add reports rule-based extraction (improved to avoid location)
        if qtype == "other_reports":
            v = extract_reports_rule(text)
            return v
        # Add witness extraction
        if qtype == "witnesses":
            v = extract_witnesses_rule(text)
            return v
        if qtype == "witness_names":
            v = extract_witness_names_rule(text)
            return v
        return None

    def _parse_validation_result(self, validation_result: str, extracted: str = "") -> Tuple[bool, str, str]:
        if validation_result.startswith("VALID_CORRECTED:"):
            corrected = validation_result.replace("VALID_CORRECTED:", "", 1).strip()
            return True, corrected, ""
        if validation_result.startswith("VALID"):
            return True, extracted, ""
        if validation_result.startswith("INVALID:"):
            msg = validation_result.replace("INVALID:", "", 1).strip()
            return False, "", msg
        # default to valid if unclear
        return True, extracted, ""

# Test function to verify extraction works
async def test_extraction():
    """Test the improved extraction system."""
    print("\nTesting Rule-Based + LLM Extraction...")
    
    try:
        rewriter = EmpatheticRewriter()
        
        # Test cases that should use rule-based extraction
        test_cases = [
            ("What is your first name?", "My first name is Srushti Jagtap", "Srushti"),
            ("What is your last name?", "My last name is James", "James"),
            ("What is your first name?", "My name is John Smith", "John"),
            ("What is your last name?", "My name is John Smith", "Smith"),
            ("Please share what happened.", "I met with a car accident", "I met with a car accident"),
            ("Did you receive medical treatment?", "Yes, I went to the ER", "Yes, I went to the ER"),
            ("Did you receive medical treatment?", "No", "No"),
            # Report test cases
            ("Did you file any reports?", "Yes, to police", "Yes, to police"),
            ("Have you contacted any authorities?", "Yes, to state office", "Yes, to state office"),
            ("Did you report this incident?", "No", "No"),
            ("Have you filed an insurance claim?", "Yes", "Yes"),
            ("Did you call any helplines?", "Yes, to helpline", "Yes, to helpline"),
            ("Have you contacted the police?", "Yes, I called the police", "Yes, to police"),
            ("Any reports filed?", "No reports made", "No"),
        ]
        
        print("\nTesting extraction cases:")
        for question, response, expected in test_cases:
            print(f"\nQuestion: {question}")
            print(f"Response: {response}")
            print(f"Expected: {expected}")
            
            is_valid, extracted, error = await rewriter.extract_and_validate(question, response)
            
            print(f"Valid: {is_valid}")
            print(f"Extracted: '{extracted}'")
            if error:
                print(f"Error: {error}")
            
            # Check if it matches expected
            if extracted == expected:
                print("PERFECT MATCH!")
            else:
                print(f"Expected '{expected}', got '{extracted}'")
        
        print("\nAll extraction tests completed!")
        return True
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_extraction())