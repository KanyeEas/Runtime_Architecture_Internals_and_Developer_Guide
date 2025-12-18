# Mermaid 图本地校验（Mermaid 10.9.1）

本仓库的 Mermaid 渲染链路是：Markdown 中的 ```mermaid fenced block → `pymdownx.superfences` 生成 `<div class="mermaid">...</div>` → 浏览器端加载 `mermaid@10.9.1` 解析渲染（见根目录 `mkdocs.yml` 的 `extra_javascript`）。

为了避免“盲改 Mermaid”，这里提供一个**可重复的本地校验脚本**，用于把 `Syntax error in text` 精确定位到：文件 + 第几个图 + 起始行号（尽力包含 Mermaid 行/列）。

## 一次性安装（只需要做一次）

在仓库根目录执行：

```bash
cd tools/mermaid
npm install --no-fund --no-audit
```

## 运行校验

```bash
cd tools/mermaid
npm run validate
```

说明：校验器会启动一个无头浏览器（Puppeteer），加载 `node_modules/mermaid/dist/mermaid.min.js`（版本锁定为 `10.9.1`），并对每个 Mermaid 块执行 `mermaid.parse()`。这与 MkDocs/Material 的前端渲染行为一致，因此报错更可信。

可选参数：

- `--fail-fast`：遇到第一个错误就退出
- `--json`：输出机器可读 JSON
- `--root <repoRoot>`：显式指定仓库根目录（默认会自动推断）
- `--docs-dir <docsDir>`：显式覆盖 mkdocs 的 `docs_dir`（默认从 `mkdocs.yml` 读取）

示例：

```bash
node validate_mermaid_blocks.mjs --json > mermaid-errors.json
```

## 输出怎么看

每条错误会像这样：

```
.../docs/03_ClassLoading/README.md:170 (block#1, mermaidLine:12, col:5)
  Parse error on line 12:
  ...
```

- `file:line`：Markdown 里 ```mermaid fence 的起始行
- `block#N`：该文件里第 N 个 Mermaid 图
- `mermaidLine/col`：Mermaid 源码内部的行/列（如果解析器能提供）



