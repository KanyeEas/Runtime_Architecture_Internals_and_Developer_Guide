# `quickener/quick.cpp`（逐行精读｜工具入口）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：`arkquicker` 工具的 CLI 入口：读取 panda 文件容器，调用 `ark::quick::Quickener` 执行 quickening，然后写回输出文件。

## 1) 这文件解决什么问题

本文件不实现 quickening 的“算法规则”，而是把工具跑起来，让 quickening 能作为“执行前变换层”落到工程里：

- 输入：`INPUT_FILE`（panda file container）
- 处理：`Quickener::QuickContainer()`
- 输出：`OUTPUT_FILE`（写回后的 panda file）

## 2) CLI 结构：Help / Parse / Process

- `PrintHelp(pa_parser)`：打印用法与参数帮助（`pa_parser.GetHelpString()`）。
- `ParseArgs(pa_parser, argc, argv)`：调用 `PandArgParser::Parse`；失败则打印 help 并返回 false。
- `ProcessArgs(...)`：
  - 检查 `INPUT/OUTPUT` 是否为空，或 `--help` 是否打开；
  - 初始化 logger：只开 `ERROR` 等级，并启用 `QUICKENER` 与 `PANDAFILE` 组件，避免工具输出过多噪音。

## 3) 主流程：`main`（工具闭环）

`main` 的职责是“读 → quicken → 写”：

- **参数定义**：
  - `help`：`--help`
  - `input/output`：两个 tail 参数（位置参数）
- **读输入**：
  - `ark::panda_file::File::Open(input)`
  - `ark::panda_file::FileReader reader(std::move(input_file))`
  - `reader.ReadContainer()`：读 container（失败直接返回）
  - `ark::panda_file::ItemContainer *container = reader.GetContainerPtr()`
- **执行 quickening**：
  - 构造 `ark::quick::Quickener`：传入 `container`、`File*`、`items`
  - 调 `quickener.QuickContainer()`
- **写输出**：
  - `ark::panda_file::FileWriter(output)`
  - `container->Write(&writer, false)`（失败直接返回）

## 4) 排障抓手（新人最常见问题）

- **打不开输入文件**：看 `File::Open` 返回值与 `LOG(ERROR, QUICKENER)`。
- **container 读失败**：看 `ReadContainer()` 是否返回 false。
- **写输出失败**：看 `FileWriter` 构造、以及 `container->Write(...)`。

## 5) 与 04 章执行引擎的边界

- 解释器/JIT/AOT 是 **运行时执行引擎**；
- quickener 是 **执行前/离线工具链**，它改变的是“运行时输入的 bytecode/常量池形态”，不是运行时控制流本身。

如果你需要把 quickening 的“实际变换规则/表驱动”也纳入证据链，请直接顺着这些源码入口下潜（本章已经把路径列全）：

- **核心实现**：`quickener/quickener.h` + 生成的 `quickener_gen.cpp`（由 `quickener/templates/quickener_gen.cpp.erb` 生成）
- **opcode 翻译表**：`translation_table_gen.h`（由 `quickener/templates/translation_table_gen.h.erb` 生成，并通过 `#include <translation_table_gen.h>` 注入）
- **构建入口**：`quickener/CMakeLists.txt`（模板生成与编译 target）