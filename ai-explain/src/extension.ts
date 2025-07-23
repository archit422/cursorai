// ai-explain/src/extension.ts

import * as vscode from 'vscode';
import axios from 'axios';

export function activate(context: vscode.ExtensionContext) {
  console.log('🟢 AI Explain Snippet activated');

  // ... your existing /explain and /generate command registrations ...

  // ———————— NEW: Instant Auto-Fix Command ————————
  const autoFixCommand = vscode.commands.registerCommand('ai-explain.autoFix', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showErrorMessage('No active editor found');
      return;
    }

    const document = editor.document;
    if (document.languageId !== 'python') {
      vscode.window.showErrorMessage('Auto-fix only supports Python files');
      return;
    }

    // Get diagnostics for current file
    const diagnostics = vscode.languages.getDiagnostics(document.uri);
    
    if (diagnostics.length === 0) {
      vscode.window.showInformationMessage('No errors found to fix');
      return;
    }

    // Show progress while fixing
    await vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: "AI-fixing errors...",
      cancellable: false
    }, async (progress) => {
      const workspaceEdit = new vscode.WorkspaceEdit();
      let fixedCount = 0;
      const allEdits: Array<{
        start_line: number;
        start_char: number;
        end_line: number;
        end_char: number;
        replacement: string;
      }> = [];

      // Phase 1: Collect all edits
      for (const diag of diagnostics) {
        progress.report({ message: `Analyzing error ${fixedCount + 1}/${diagnostics.length}` });
        
        try {
          const edit = await getFixForDiagnostic(document, diag);
          console.log('DEBUG: Got edit for diagnostic:', { diag: diag.message, edit });
          
          if (edit && edit.length > 0) {
            allEdits.push(...edit);
            fixedCount++;
          }
        } catch (error) {
          console.error('Failed to fix diagnostic:', error);
        }
      }

      // Phase 2: Sort edits by position (reverse order so we apply from bottom to top)
      allEdits.sort((a, b) => {
        if (a.start_line !== b.start_line) {
          return b.start_line - a.start_line; // Reverse order
        }
        return b.start_char - a.start_char; // Reverse order
      });

      // Phase 3: Remove overlapping edits (keep the first one for each overlapping range)
      const nonOverlappingEdits: Array<{
        start_line: number;
        start_char: number;
        end_line: number;
        end_char: number;
        replacement: string;
      }> = [];

      for (const edit of allEdits) {
        const overlaps = nonOverlappingEdits.some(existing => {
          // Check if ranges overlap
          const editStart = edit.start_line * 10000 + edit.start_char;
          const editEnd = edit.end_line * 10000 + edit.end_char;
          const existingStart = existing.start_line * 10000 + existing.start_char;
          const existingEnd = existing.end_line * 10000 + existing.end_char;
          
          return (editStart < existingEnd && editEnd > existingStart);
        });
        
        if (!overlaps) {
          nonOverlappingEdits.push(edit);
        } else {
          console.log('DEBUG: Skipping overlapping edit:', edit);
        }
      }

      console.log('DEBUG: Applying', nonOverlappingEdits.length, 'non-overlapping edits');

      // Phase 4: Apply the non-overlapping edits
      nonOverlappingEdits.forEach((e: any) => {
        const start = new vscode.Position(e.start_line, e.start_char);
        const end = new vscode.Position(e.end_line, e.end_char);
        const range = new vscode.Range(start, end);
        
        console.log('DEBUG: Applying edit:', {
          range: `${start.line}:${start.character} to ${end.line}:${end.character}`,
          originalText: document.getText(range),
          replacement: e.replacement
        });
        
        workspaceEdit.replace(document.uri, range, e.replacement);
      });

      console.log('DEBUG: About to apply workspace edit with', workspaceEdit.size, 'changes');
      
      if (nonOverlappingEdits.length > 0) {
        const success = await vscode.workspace.applyEdit(workspaceEdit);
        console.log('DEBUG: Workspace edit applied successfully:', success);
        
        if (success) {
          vscode.window.showInformationMessage(`✅ Fixed ${nonOverlappingEdits.length} error(s) automatically`);
        } else {
          vscode.window.showErrorMessage(`❌ Failed to apply ${nonOverlappingEdits.length} fix(es)`);
        }
      } else {
        vscode.window.showWarningMessage('No errors could be fixed automatically');
      }
    });
  });

  // Helper function to get fix for a diagnostic
  async function getFixForDiagnostic(document: vscode.TextDocument, diag: vscode.Diagnostic) {
    // Get more context: 3 lines before and after the error line
    const errorLine = diag.range.start.line;
    const startLine = Math.max(0, errorLine - 3);
    const endLine = Math.min(document.lineCount - 1, errorLine + 3);
    
    const contextRange = new vscode.Range(startLine, 0, endLine, document.lineAt(endLine).text.length);
    const broken = document.getText(contextRange);
    
    const targetLine = document.lineAt(errorLine);
    const errMsg = diag.message;

    console.log('DEBUG: Sending fix request for:', {
      errorLine,
      errMsg,
      snippet: broken,
      targetLineText: targetLine.text
    });

    const resp = await axios.post('http://localhost:8000/fix', {
      language: 'python',
      snippet: broken,
      error: errMsg,
      start_line: errorLine,
      start_char: 0,
      end_line: errorLine,
      end_char: targetLine.text.length
    });

    console.log('DEBUG: Received edits from backend:', resp.data.edits);
    return resp.data.edits;
  }

  // Code Action Provider for AI Fix (existing lightbulb behavior)
  const provider = vscode.languages.registerCodeActionsProvider(
    'python',
    {
      async provideCodeActions(document, range, context) {
        const fixes: vscode.CodeAction[] = [];

        for (const diag of context.diagnostics) {
          if (!range.intersection(diag.range)) {
            continue;
          }

          // Get more context: 3 lines before and after the error line
          const errorLine = diag.range.start.line;
          const startLine = Math.max(0, errorLine - 3);
          const endLine = Math.min(document.lineCount - 1, errorLine + 3);
          
          const contextRange = new vscode.Range(startLine, 0, endLine, document.lineAt(endLine).text.length);
          const broken = document.getText(contextRange);
          
          const targetLine = document.lineAt(errorLine);
          const errMsg = diag.message;

          try {
            const resp = await axios.post('http://localhost:8000/fix', {
              language:   'python',
              snippet:    broken,
              error:      errMsg,
              start_line: errorLine,
              start_char: 0,
              end_line: errorLine,
              end_char: targetLine.text.length
            });

            // Apply returned JSON patches
            const edits: Array<{
              start_line:  number;
              start_char:  number;
              end_line:    number;
              end_char:    number;
              replacement: string;
            }> = resp.data.edits;

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
            // NEW: Log the entire error object
            console.error('AI-fix raw error object:', e);

            // Existing code
            const respData = e.response?.data;
            console.error('AI-fix full error response:', JSON.stringify(respData, null, 2));

            let message = e.message;
            if (respData?.detail) {
              if (Array.isArray(respData.detail)) {
                message = respData.detail
                  .map((d: any) => `${d.loc.join('.')}: ${d.msg}`)
                  .join('; ');
              } else {
                message = JSON.stringify(respData.detail);
              }
            }
            vscode.window.showErrorMessage(`AI-fix failed: ${message}`);
          }
        }

        return fixes;
      }
    },
    { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
  );

  context.subscriptions.push(autoFixCommand, provider);
}

export function deactivate() {}