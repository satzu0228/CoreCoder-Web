type MonacoApi = typeof import('monaco-editor/esm/vs/editor/editor.api')

let monacoPromise: Promise<MonacoApi> | null = null

export function loadMonaco(): Promise<MonacoApi> {
  if (!monacoPromise) {
    monacoPromise = Promise.all([
      import('monaco-editor/esm/vs/editor/editor.api'),
      import('monaco-editor/esm/vs/basic-languages/python/python.contribution'),
      import('monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution'),
      import('monaco-editor/esm/vs/basic-languages/typescript/typescript.contribution'),
      import('monaco-editor/esm/vs/basic-languages/shell/shell.contribution'),
      import('monaco-editor/esm/vs/language/json/monaco.contribution'),
    ]).then(([monaco]) => monaco)
  }
  return monacoPromise
}

export function languageForFile(fileName: string): string {
  const extension = fileName.toLowerCase().split('.').pop() || ''
  const languages: Record<string, string> = {
    bash: 'shell',
    js: 'javascript',
    json: 'json',
    jsx: 'javascript',
    py: 'python',
    sh: 'shell',
    ts: 'typescript',
    tsx: 'typescript',
  }
  return languages[extension] || 'plaintext'
}
