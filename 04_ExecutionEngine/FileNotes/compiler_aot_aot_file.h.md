# `compiler/aot/aot_file.h`（逐行精读｜AOT 文件抽象与查询）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：定义 `AotFile`（一个 `.an` ELF 库的运行期视图）以及它导出的“按 panda file/class/method 查询”能力。

## 1) `AotFile` 是什么

`AotFile` 把一个 `.an`（本质是 ELF 动态库）抽象成三块可查询数据：

- `handle_`：已加载的动态库句柄（用于 resolve 符号）
- `aotData_`：`aot..aot_end` 这一段（包含 `AotHeader` 与各类 header/strtab/bitmap）
- `code_`：`code..code_end` 这一段（包含机器码 + CodeInfo 等）

它提供的 API 目标是：**让 runtime 能把“method/class/panda file”映射到 AOT 机器码地址、以及必要的元信息（hash table、class context 等）**。

## 2) 关键常量：`MAGIC`/`VERSION`

- `MAGIC = {'.','a','n','\\0'}`：和 `.an` 的文件类型绑定
- `VERSION = {'0','0','6','\\0'}`：与 on-disk 布局版本绑定（`AotFile::Open` 会校验）

## 3) `.an` 的运行期查询接口（高频）

### 3.1 读 header/字符串/文件名

- `GetAotHeader()`：返回 `AotHeader*`
- `GetString(offset)`：从 `strtabOffset + offset` 取字符串
- `GetFileName()/GetCommandLine()/GetClassContext()`：把 header 中的 `*Str` 偏移翻译成字符串

### 3.2 panda file 层

- `FileHeaders()`：返回 `PandaFileHeader` 的 span（从 `filesOffset` 开始）
- `FindPandaFile(fileName)`：按 fileName 查找 `PandaFileHeader`

### 3.3 class/method 层

- `GetClassHeaders(fileHeader)`：给定某个 panda file header，取其 class headers span
- `GetClassHashTable(fileHeader)`：返回 class hash table 的 span（供 runtime 注入到 `.abc`）
- `GetMethodHeader(i)`：按 index 取 method header（注意它是“全局方法表”的索引）
- `GetMethodCode(methodHeader)`：把 methodHeader 的 `codeOffset` 映射到 `code_` 区间

## 4) `AotClass` / `AotPandaFile`：更面向“使用”的封装

### 4.1 `AotClass`

封装 “某个 class 在 AOT 文件中的视图”：

- `FindMethodCodeEntry(index)`：返回“可执行入口”（注意会叠加 `CodeInfo::GetCodeOffset(RUNTIME_ARCH)`）
- `FindMethodCodeSpan(index)`：返回“真正的机器码 span”（由 `CodeInfo(code).GetCodeSpan()` 解包）
- `FindMethodHeader(index)`：结合 bitmap 判断方法是否存在

### 4.2 `AotPandaFile`

封装 “某个 panda file 在 AOT 文件中的视图”：

- 构造时会 `LoadClassHashTable()`（后续 runtime 可把它灌到 `.abc` 上加速 class lookup）
- `GetClass(classId)`：在排序的 class headers 中二分查找目标 class
- `GetMethodCodeInfo(methodHeader)`：把 method 的 code blob 解成 `CodeInfo`（供 StackWalker/去优化/异常等解码）

## 5) 与 04 章执行引擎的连接点

- **运行时加载 `.an`**：`AotManager::AddFile` 会调用 `AotFile::Open`，并在 `runtime != nullptr` 时做 patch/GOT 初始化。
- **编译器侧 snapshot index**：`runtime/compiler.cpp` 会从 `AotManager` 拿 snapshot index（把 `panda_file::File` 映射为 AOT 索引空间）。
- **解释器/compiled 的交界**：当 PC 落在 AOT code range 内时，`StackWalker`/异常 unwind/deopt 依赖 `CodeInfo/StackMap` 解码。




