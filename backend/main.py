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
        logging.exception("Exception in /explain handler")
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
        logging.exception("Exception in /generate handler")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


# ———————— /fix Endpoint ————————

@app.post("/fix", response_model=FixResponse)
async def fix_code(req: FixRequest):
    if req.language.lower() != "python":
        raise HTTPException(status_code=400, detail="Currently only Python is supported")

    # Detect error type for specialized handling
    error_type = detect_error_type(req.error)
    prompt = generate_error_specific_prompt(error_type, req)
    
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
        logging.exception("Exception in /fix handler")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

def detect_error_type(error_message: str) -> str:
    """Detect the type of error from the error message"""
    error_msg = error_message.lower()
    
    if "indentationerror" in error_msg:
        return "indentation"
    elif "syntaxerror" in error_msg and (":" in error_msg or "colon" in error_msg):
        return "missing_colon"
    elif "syntaxerror" in error_msg and ("(" in error_msg or ")" in error_msg or "never closed" in error_msg):
        return "missing_parenthesis"
    elif "syntaxerror" in error_msg and ("[" in error_msg or "]" in error_msg):
        return "missing_bracket"
    elif "syntaxerror" in error_msg and ("{" in error_msg or "}" in error_msg):
        return "missing_brace"
    elif "syntaxerror" in error_msg and ("quote" in error_msg or "string" in error_msg):
        return "quote_error"
    elif "nameerror" in error_msg:
        return "undefined_variable"
    elif "syntaxerror" in error_msg and "," in error_msg:
        return "missing_comma"
    else:
        return "general_syntax"

def generate_error_specific_prompt(error_type: str, req) -> str:
    """Generate specialized prompts based on error type"""
    
    base_format = f"""
Return format (JSON only, no markdown):
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
CODE SNIPPET:
{req.snippet}
"""

    if error_type == "indentation":
        return f"""You are a Python indentation expert. Fix this IndentationError.

PYTHON INDENTATION RULES:
- Use exactly 4 spaces per indentation level
- After a colon (:), the next line MUST be indented
- All lines in the same block must have identical indentation
- Never mix tabs and spaces

EXAMPLES:
Broken: def hello():\\nprint("hi")
Fixed: def hello():\\n    print("hi")

Broken: if x > 5:\\nreturn x
Fixed: if x > 5:\\n    return x

CRITICAL: Return the COMPLETE corrected line with proper indentation.
Look at the surrounding code to understand the correct indentation level.
{base_format}"""

    elif error_type == "missing_colon":
        return f"""You are a Python syntax expert. Fix this missing colon error.

PYTHON COLON RULES:
- Function definitions need colons: def func():
- Control flow needs colons: if/for/while/try/except/else/elif/finally:
- Class definitions need colons: class MyClass:

EXAMPLES:
Broken: if x > 5
Fixed: if x > 5:

Broken: def calculate()
Fixed: def calculate():

CRITICAL: Return the COMPLETE line with the colon added.
{base_format}"""

    elif error_type == "missing_parenthesis":
        return f"""You are a Python syntax expert. Fix this missing parenthesis error.

PARENTHESIS RULES:
- Every opening ( needs a closing )
- Function calls need both: func()
- Conditions in if/while can use them: if (condition):

EXAMPLES:
Broken: print("hello"
Fixed: print("hello")

Broken: total = sum(numbers
Fixed: total = sum(numbers)
{base_format}"""

    elif error_type == "missing_bracket":
        return f"""You are a Python syntax expert. Fix this missing bracket error.

BRACKET RULES:
- Every opening [ needs a closing ]
- Lists need both: [1, 2, 3]
- Index access needs both: array[0]

EXAMPLES:
Broken: numbers = [1, 2, 3
Fixed: numbers = [1, 2, 3]
{base_format}"""

    elif error_type == "missing_brace":
        return f"""You are a Python syntax expert. Fix this missing brace error.

BRACE RULES:
- Every opening {{ needs a closing }}
- Dictionaries need both: {{"key": "value"}}
- Sets need both: {{1, 2, 3}}

EXAMPLES:
Broken: data = {{"name": "John"
Fixed: data = {{"name": "John"}}
{base_format}"""

    elif error_type == "quote_error":
        return f"""You are a Python syntax expert. Fix this quote/string error.

QUOTE RULES:
- Every opening quote needs a closing quote
- Use single quotes: 'text' or double quotes: "text"
- Escape quotes inside strings: "She said \\"hello\\""

EXAMPLES:
Broken: message = "Hello world
Fixed: message = "Hello world"

Broken: name = 'John's car'
Fixed: name = "John's car"
{base_format}"""

    elif error_type == "undefined_variable":
        return f"""You are a Python variable expert. Fix this undefined variable error.

VARIABLE RULES:
- Look at surrounding code for similar variable names
- Suggest the most likely intended variable name
- Consider function parameters and local variables

EXAMPLES:
If you see 'numbers' nearby but error says 'nums':
Broken: total = sum(nums)
Fixed: total = sum(numbers)
{base_format}"""

    elif error_type == "missing_comma":
        return f"""You are a Python syntax expert. Fix this missing comma error.

COMMA RULES:
- Function parameters need commas: func(a, b, c)
- List items need commas: [1, 2, 3]
- Dictionary items need commas: {{"a": 1, "b": 2}}

EXAMPLES:
Broken: def func(a b, c):
Fixed: def func(a, b, c):
{base_format}"""

    else:  # general_syntax
        return f"""You are a Python syntax expert. Fix this syntax error.

GENERAL RULES:
- Ensure valid Python syntax
- Match brackets, parentheses, and quotes
- Add missing punctuation (colons, commas)
- Maintain proper indentation

{base_format}"""