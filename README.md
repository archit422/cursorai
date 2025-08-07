# AI Code Editor

An intelligent VS Code extension that automatically fixes Python syntax errors using AI-powered analysis.

## Features

- **Instant Error Detection**: Automatically identifies Python syntax errors in real-time
- **AI-Powered Fixes**: Uses GPT-4o-mini to generate intelligent code corrections
- **Bulk Auto-Fix**: Fix all errors in a file with a single command (`Ctrl+Shift+F`)
- **Contextual Analysis**: Provides expanded context for complex errors like indentation issues
- **Specialized Error Handling**: Tailored prompts for different error types (indentation, missing colons, brackets, etc.)

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   cd ai-explain
   npm install
   ```
3. Set up the backend:
   ```bash
   cd backend
   pip install fastapi openai python-multipart uvicorn
   ```
4. Add your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

## Usage

### Start the Backend
```bash
cd backend
python main.py
```

### Install the Extension
1. Open VS Code
2. Press `F5` to launch the extension in development mode
3. Open a Python file with syntax errors

### Fix Errors
- **Auto-fix all errors**: Press `Ctrl+Shift+F` (or `Cmd+Shift+F` on Mac)
- **Fix individual errors**: Click the lightbulb icon next to any error

## Supported Error Types

- **Indentation Errors**: Automatically corrects Python indentation issues
- **Missing Colons**: Adds missing colons to function definitions, if statements, etc.
- **Bracket Matching**: Fixes missing parentheses, brackets, and braces
- **Quote Errors**: Corrects unclosed strings and quote mismatches
- **Variable Name Issues**: Suggests corrections for undefined variables
- **Missing Commas**: Adds missing commas in function parameters and lists

## Architecture

### Backend (FastAPI)
- **Error Type Detection**: Analyzes error messages to determine the specific issue
- **Specialized Prompts**: Uses tailored prompts for different error categories
- **Context-Aware**: Provides relevant code context to the AI model

### Frontend (VS Code Extension)
- **Real-time Diagnostics**: Monitors file changes for syntax errors
- **Bulk Processing**: Handles multiple errors simultaneously
- **Conflict Resolution**: Prevents overlapping edits that could cause issues

## API Endpoints

- `POST /explain` - Explains code snippets in plain English
- `POST /generate` - Generates code from natural language descriptions
- `POST /fix` - Fixes syntax errors in Python code

## Development

### Project Structure
```
├── backend/
│   └── main.py          # FastAPI backend server
├── ai-explain/
│   ├── src/
│   │   └── extension.ts # VS Code extension logic
│   └── package.json     # Extension configuration
└── README.md
```

### Testing
The system has been tested on over 100 different error scenarios with high accuracy rates for common Python syntax issues.

## Requirements

- **VS Code**: Version 1.60.0 or higher
- **Python**: 3.7 or higher
- **Node.js**: 14.0 or higher
- **OpenAI API Key**: Required for AI functionality

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License. 
