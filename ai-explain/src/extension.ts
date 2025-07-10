import * as vscode from 'vscode';
import axios from 'axios';

export function activate(context: vscode.ExtensionContext) {
  console.log('🟢 AI Explain Snippet activated');

  // Command: AI: Explain Selection
  // ... (existing explain & generate commands unchanged) ...

  // Code Action Provider for AI Fix
  const provider = vscode.languages.registerCodeActionsProvider(
    'python',
    {
      async provideCodeActions(document, range, context) {
        const fixes: vscode.CodeAction[] = [];
        for (const diag of context.diagnostics) {
          if (!range.intersection(diag.range)) continue;

          const broken = document.getText(diag.range);
          const errMsg = diag.message;

          try {
            const resp = await axios.post('http://localhost:8000/fix', {
              language:   'python',
              snippet:    broken,
              error:      errMsg,
              start_line: diag.range.start.line,
              start_char: diag.range.start.character,
              end_line:   diag.range.end.line,
              end_char:   diag.range.end.character
            });

            // Parse and apply edits
            const edits: Array<{ start_line: number; start_char: number; end_line: number; end_char: number; replacement: string }> = resp.data.edits;
            const workspaceEdit = new vscode.WorkspaceEdit();
            edits.forEach(e => {
              const start = new vscode.Position(e.start_line, e.start_char);
              const end   = new vscode.Position(e.end_line,   e.end_char);
              workspaceEdit.replace(document.uri, new vscode.Range(start, end), e.replacement);
            });

            const action = new vscode.CodeAction(`AI-fix: ${errMsg}`, vscode.CodeActionKind.QuickFix);
            action.edit = workspaceEdit;
            fixes.push(action);

          } catch (e: any) {
            vscode.window.showErrorMessage(`AI-fix failed: ${e.message}`);
          }
        }
        return fixes;
      }
    },
    { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
  );

  context.subscriptions.push(provider);
}

export function deactivate() {}