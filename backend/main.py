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

    # Build a strict JSON-patch prompt
    prompt = f"""
You are a code‐fix assistant. INPUT: a Python snippet, an error message, and the exact range to correct.
Return a JSON array of edits—and nothing else—in this form:

[
  {{
    "start_line": <int>,
    "start_char": <int>,
    "end_line":   <int>,
    "end_char":   <int>,
    "replacement":"<corrected code fragment>"
  }}
]

ERROR: {req.error}

CODE SNIPPET:
{req.snippet}

RANGE TO FIX:
start_line={req.start_line}, start_char={req.start_char}
end_line={req.end_line},     end_char={req.end_char}
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content
        # Extract and parse JSON
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        payload = m.group(0) if m else raw
        edits_list = json.loads(payload)
        # Validate edits
        validated: List[Edit] = []
        for e in edits_list:
            try:
                validated.append(Edit(**e))
            except ValidationError:
                logging.exception("Invalid edit schema from LLM")
                raise HTTPException(status_code=500, detail="AI returned malformed edit data")
        return FixResponse(edits=validated)
    except RateLimitError:
        raise HTTPException(429, detail="OpenAI quota exceeded—please check your billing plan.")
    except Exception as e:
        logging.exception("❌ Exception in /fix handler")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")