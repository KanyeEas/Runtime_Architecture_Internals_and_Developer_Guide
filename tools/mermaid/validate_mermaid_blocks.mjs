import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

function parseArgs(argv) {
  const out = {
    root: null,
    docsDir: null,
    failFast: false,
    json: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--fail-fast") out.failFast = true;
    else if (a === "--json") out.json = true;
    else if (a === "--root") out.root = argv[++i];
    else if (a === "--docs-dir") out.docsDir = argv[++i];
    else if (a === "--help" || a === "-h") out.help = true;
    else throw new Error(`Unknown arg: ${a}`);
  }
  return out;
}

async function fileExists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function readMkDocsDocsDir(mkdocsYmlPath) {
  const text = await fs.readFile(mkdocsYmlPath, "utf8");
  // Minimal parse: look for a top-level 'docs_dir: xxx'
  const m = text.match(/^\s*docs_dir:\s*([^\n#]+)\s*$/m);
  if (!m) return "docs";
  return m[1].trim();
}

async function walkMdFiles(rootDir) {
  const out = [];
  async function walk(dir) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const e of entries) {
      const p = path.join(dir, e.name);
      // MkDocs docs/ tree in this repo may be mostly symlinks (see tools/sync_mkdocs_symlinks.sh),
      // so we need to follow symlinks to reach actual files/dirs.
      if (e.isSymbolicLink()) {
        let st;
        try {
          st = await fs.stat(p);
        } catch {
          continue;
        }
        if (st.isDirectory()) {
          await walk(p);
        } else if (st.isFile() && e.name.toLowerCase().endsWith(".md")) {
          out.push(p);
        }
        continue;
      }

      if (e.isDirectory()) {
        await walk(p);
      } else if (e.isFile() && e.name.toLowerCase().endsWith(".md")) {
        out.push(p);
      }
    }
  }
  await walk(rootDir);
  return out;
}

function extractMermaidBlocks(markdownText) {
  const lines = markdownText.split(/\r?\n/);
  const blocks = [];
  let inBlock = false;
  let startLine = 0;
  let buf = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!inBlock) {
      // Accept ```mermaid or ``` mermaid
      if (/^\s*```\s*mermaid\s*$/.test(line)) {
        inBlock = true;
        startLine = i + 1; // 1-based
        buf = [];
      }
      continue;
    }

    if (/^\s*```\s*$/.test(line)) {
      blocks.push({
        startLine,
        text: buf.join("\n"),
      });
      inBlock = false;
      startLine = 0;
      buf = [];
      continue;
    }

    buf.push(line);
  }

  // Unterminated fence: still report it as a block (likely a markdown error)
  if (inBlock) {
    blocks.push({
      startLine,
      text: buf.join("\n"),
      unterminated: true,
    });
  }

  return blocks;
}

function normalizeMermaidText(text) {
  // Mermaid tolerates leading/trailing newlines inconsistently; normalize a bit.
  return text.replace(/^\s*\n/, "").replace(/\n\s*$/, "\n");
}

function extractLineCol(err) {
  // Best-effort: Mermaid errors differ by diagram type.
  const msg = String(err?.message ?? err);
  // Common patterns: "Parse error on line X:" or "line X" / "col Y"
  const lineMatch = msg.match(/\bline\s+(\d+)\b/i) || msg.match(/\bon\s+line\s+(\d+)\b/i);
  const colMatch = msg.match(/\bcol(?:umn)?\s+(\d+)\b/i);
  const line = lineMatch ? Number(lineMatch[1]) : null;
  const col = colMatch ? Number(colMatch[1]) : null;
  return { line, col, msg };
}

async function createMermaidParsePage({ mermaidScriptPath }) {
  const puppeteerMod = await import("puppeteer");
  const puppeteer = puppeteerMod.default ?? puppeteerMod;

  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const page = await browser.newPage();
  await page.setContent("<!doctype html><html><head></head><body></body></html>", {
    waitUntil: "load",
  });
  await page.addScriptTag({ path: mermaidScriptPath });
  await page.evaluate(() => {
    // Align with mkdocs: mermaid is loaded as a global script.
    // We explicitly disable startOnLoad to use parse-only.
    // eslint-disable-next-line no-undef
    mermaid.initialize({ startOnLoad: false });
  });

  return {
    async parse(text) {
      return await page.evaluate(async (code) => {
        try {
          // eslint-disable-next-line no-undef
          const r = mermaid.parse(code);
          if (r && typeof r.then === "function") await r;
          return { ok: true };
        } catch (e) {
          return { ok: false, message: String(e?.message ?? e) };
        }
      }, text);
    },
    async close() {
      await page.close();
      await browser.close();
    },
  };
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    process.stdout.write(
      [
        "Validate all ```mermaid blocks under MkDocs docs_dir using mermaid@10.9.1 parser.",
        "",
        "Usage:",
        "  node tools/mermaid/validate_mermaid_blocks.mjs [--root <repoRoot>] [--docs-dir <docsDir>] [--fail-fast] [--json]",
        "",
      ].join("\n"),
    );
    process.exit(0);
  }

  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const defaultRoot = path.resolve(scriptDir, "../..");
  const root = path.resolve(args.root ?? defaultRoot);
  const mkdocsYml = path.join(root, "mkdocs.yml");
  if (!(await fileExists(mkdocsYml))) {
    throw new Error(`mkdocs.yml not found at: ${mkdocsYml} (use --root to point to repo root)`);
  }

  const docsDirName = args.docsDir ?? (await readMkDocsDocsDir(mkdocsYml));
  const docsDir = path.resolve(root, docsDirName);
  if (!(await fileExists(docsDir))) {
    throw new Error(`docs_dir not found: ${docsDir}`);
  }

  // IMPORTANT: We validate in a real browser context to match MkDocs/Material runtime behavior.
  // Direct `import mermaid` in Node can fail due to DOMPurify differences.
  const mermaidScriptPath = path.resolve(
    scriptDir,
    "node_modules/mermaid/dist/mermaid.min.js",
  );
  if (!(await fileExists(mermaidScriptPath))) {
    throw new Error(
      `Missing mermaid browser bundle at ${mermaidScriptPath}. Did you run: cd tools/mermaid && npm install ?`,
    );
  }

  const mermaidPage = await createMermaidParsePage({ mermaidScriptPath });

  const mdFiles = await walkMdFiles(docsDir);
  const errors = [];
  let totalBlocks = 0;

  try {
    for (const filePath of mdFiles) {
      const content = await fs.readFile(filePath, "utf8");
      const blocks = extractMermaidBlocks(content);
      if (blocks.length === 0) continue;

      for (let i = 0; i < blocks.length; i++) {
        const b = blocks[i];
        totalBlocks++;
        if (b.unterminated) {
          errors.push({
            file: filePath,
            blockIndex: i + 1,
            startLine: b.startLine,
            line: null,
            col: null,
            message: "Unterminated ```mermaid fence (missing closing ```)",
          });
          if (args.failFast) break;
          continue;
        }

        const text = normalizeMermaidText(b.text);
        const r = await mermaidPage.parse(text);
        if (!r.ok) {
          const { line, col, msg } = extractLineCol(r.message);
          errors.push({
            file: filePath,
            blockIndex: i + 1,
            startLine: b.startLine,
            line,
            col,
            message: msg,
          });
          if (args.failFast) break;
        }
      }
    }
  } finally {
    await mermaidPage.close();
  }

  if (args.json) {
    process.stdout.write(
      JSON.stringify(
        {
          root,
          docsDir,
          totalFiles: mdFiles.length,
          totalBlocks,
          errorCount: errors.length,
          errors,
        },
        null,
        2,
      ) + "\n",
    );
  } else {
    for (const e of errors) {
      const loc =
        e.line != null
          ? `${e.file}:${e.startLine} (block#${e.blockIndex}, mermaidLine:${e.line}${e.col != null ? `, col:${e.col}` : ""})`
          : `${e.file}:${e.startLine} (block#${e.blockIndex})`;
      process.stdout.write(`${loc}\n  ${e.message}\n`);
    }
    process.stdout.write(
      `\nScanned ${mdFiles.length} markdown files under ${docsDir}\nFound ${totalBlocks} mermaid blocks, ${errors.length} error(s)\n`,
    );
  }

  process.exit(errors.length === 0 ? 0 : 1);
}

main().catch((e) => {
  process.stderr.write(String(e?.stack ?? e) + "\n");
  process.exit(2);
});


