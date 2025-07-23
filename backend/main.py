# backend/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
from typing import List
import os
import re
import json
import logging
from openai import OpenAI, RateLimitError

# Initialize FastAPI and OpenAI client
app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ———————— Request & Response Models ————————

class ExplainRequest(BaseModel):
    language: str
    snippet:  str

class ExplainResponse(BaseModel):
    explanation: str

class GenerateRequest(BaseModel):
    language:     str
    instructions: str

class GenerateResponse(BaseModel):
    code: str

class FixRequest(BaseModel):
    language:   str
    snippet:    str
    error:      str
    start_line: int
    start_char: int
    end_line:   int
    end_char:   int

class Edit(BaseModel):
    start_line:  int
    start_char:  int
    end_line:    int
    end_char:    int
    replacement: str

class FixResponse(BaseModel):
    edits: List[Edit]


# ———————— Prompt Template ————————

SYSTEM_PROMPT = (
    "You are an expert {language} tutor. "
    "Explain the following code snippet in plain English, using only concise paragraphs:\n\n"
    "```{language}\n{snippet}\n```"
)


# ———————— /explain Endpoint ————————

@app.post("/explain", response_model=ExplainResponse)
async def explain_snippet(req: ExplainRequest):
    if req.language.lower() != "python":
        raise HTTPException(status_code=400, detail="Currently only Python is supported")
    prompt = SYSTEM_PROMPT.format(language=req.language, snippet=req.snippet)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        explanation = resp.choices[0].message.content.strip()
        return ExplainResponse(explanation=explanation)
    except Exception as e:
        logging.exception("❌ Exception in /explain handler")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


# ———————— /generate Endpoint ————————

@app.post("/generate", response_model=GenerateResponse)
async def generate_code(req: GenerateRequest):
    if req.language.lower() != "python":
        raise HTTPException(status_code=400, detail="Currently only Python is supported")
    prompt = (
        "You are an expert Python developer.\n\n"
        "Write complete, runnable Python code for the following specification:\n\n"
        f"{req.instructions}"
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        code = resp.choices[0].message.content.strip()
        return GenerateResponse(code=code)
    except Exception as e:
        logging.exception("❌ Exception in /generate handler")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


# ———————— /fix Endpoint ————————

@app.post("/fix", response_model=FixResponse)
async def fix_code(req: FixRequest):
    if req.language.lower() != "python":
        raise HTTPException(status_code=400, detail="Currently only Python is supported")

    prompt = f"""
You are a Python code-fix assistant. You will receive:
1. A Python code snippet (with context lines)
2. An error message
3. The exact line and character range to fix

Your task: Return a JSON array with ONE edit that fixes the error on the specified line.

CRITICAL RULES:
- Fix ONLY the line specified in the range (line {req.start_line})
- Ensure all brackets, parentheses, and quotes are properly matched
- The replacement must be valid Python syntax
- Do not change indentation unless necessary for the fix
- Return ONLY valid JSON - no markdown, no explanations

Return format:
[
  {{
    "start_line": {req.start_line},
    "start_char": {req.start_char},
    "end_line": {req.end_line},
    "end_char": {req.end_char},
    "replacement": "<corrected line content>"
  }}
]

ERROR: {req.error}

CODE SNIPPET (with context):
{req.snippet}

RANGE TO FIX:
Line {req.start_line}, characters {req.start_char} to {req.end_char}

Fix the syntax error on line {req.start_line} only. Ensure proper bracket/parentheses matching.
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content

        # Extract JSON array even if wrapped in markdown
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        payload = m.group(0) if m else raw
        edits_list = json.loads(payload)

        # Validate each edit against the Edit model
        validated: List[Edit] = []
        for e in edits_list:
            try:
                validated.append(Edit(**e))
            except ValidationError:
                logging.exception("Invalid edit schema from LLM")
                raise HTTPException(status_code=500, detail="AI returned malformed edit data")

        return FixResponse(edits=validated)

    except RateLimitError:
        raise HTTPException(status_code=429, detail="OpenAI quota exceeded—please check your billing plan.")
    except Exception as e:
        logging.exception("❌ Exception in /fix handler")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")