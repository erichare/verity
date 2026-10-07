// Node's test runner needs CommonJS output for extensionless TS imports and the
// gallery JSON. Transpile only this app's source in memory, without build artifacts.
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const sourceRoot = path.resolve(__dirname, "../lib") + path.sep;
require.extensions[".ts"] = (module, filename) => {
  if (!filename.startsWith(sourceRoot)) throw new Error(`Unexpected TypeScript module: ${filename}`);
  const { outputText } = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    fileName: filename,
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.CommonJS,
      esModuleInterop: true,
    },
  });
  // CommonJS otherwise resolves ./gallery to gallery.json before gallery.ts.
  // Mirror TypeScript's source-module resolution for these relative imports.
  const resolvedOutput = outputText.replace(/require\("(\.[^"]+)"\)/g, (call, specifier) => {
    return fs.existsSync(path.resolve(path.dirname(filename), `${specifier}.ts`))
      ? `require(${JSON.stringify(`${specifier}.ts`)})`
      : call;
  });
  module._compile(resolvedOutput, filename);
};
