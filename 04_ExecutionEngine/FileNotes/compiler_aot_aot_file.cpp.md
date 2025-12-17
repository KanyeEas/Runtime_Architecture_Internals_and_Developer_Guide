# `compiler/aot/aot_file.cpp`（逐行精读｜加载/校验/patch/GOT）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：`.an` 的 loader：把 AOT ELF 动态库加载到进程，校验环境/GC/版本，并完成 GOT/patch table 初始化，使 AOT 机器码能在运行时正确调用 runtime entrypoints/intrinsics。

## 0) 一个关键事实：`.an` 是“带符号表的 ELF 动态库”

这就是为什么 `AotFile::Open` 会：

- `Load(fileName)` 得到 `LibraryHandle`
- `ResolveSymbol(handle, "aot"/"aot_end"/"code"/"code_end")` 得到两段内存区间

## 1) `AotFile::Open`：加载与一致性校验（最关键的入口）

### 1.1 载入并解析两个 section 区间

- `aot..aot_end`：元数据（headers/strtab/bitmap 等）
- `code..code_end`：机器码与 CodeInfo

如果区间非法（`code_end < code` 或 `aot_end <= aot`），直接报错。

### 1.2 头部校验：避免“错架构/错 GC/错版本”导致灾难

按顺序校验：

- `magic` 必须等于 `.an\\0`
- `version` 必须等于 `AotFile::VERSION`
- `environmentChecksum`（除非 `forDump`）必须等于 `RuntimeInterface::GetEnvironmentChecksum(RUNTIME_ARCH)`
- `gcType`（除非 `forDump`）必须等于运行时传入的 `gcType`

> VM 架构意义：AOT code 对对象布局、barrier、调用约定都有硬假设；这几条不满足必须拒绝加载，而不是“勉强运行”。  

## 2) `InitializeGot(RuntimeInterface*)`：让 AOT code 能“找得到 runtime”

核心思路：

- GOT/patch table 被放在 `code_` 前方的固定区域（按 intrinsic id 与 slot 编码组织）。
- 该函数扫描 table，根据 slot type 做初始化：
  - `PLT_SLOT`：填 `CallStaticPltResolver`（弱符号兜底），并把 resolver 的“self 指针”写进去（用于定位回 table）
  - `CLASS_SLOT/STRING_SLOT/VTABLE_INDEX` 等：初始化为 0（运行时再懒解析/patch）
  - `COMMON_SLOT`：清零

> 你把它理解为：**AOT code 的外部引用不是直接写死地址，而是经由 GOT/slot，在运行时完成重定位/patch**。

## 3) `PatchTable(RuntimeInterface*)`：填充 intrinsics 的真实地址

- 以 `RuntimeInterface::IntrinsicId::COUNT` 为长度，逐个写入 `GetIntrinsicAddress(...)`。
- 这让 AOT code 执行 `Intrinsic` 指令时能直接跳到 runtime 提供的实现（有些是 runtime call，有些是 leaf/fast path）。

## 4) `AotClass/AotPandaFile` 的实现要点

- `AotPandaFile::GetClass(classId)`：在 class header span 上二分查找，确保 class headers 按 classId 有序。
- `AotClass::FindMethodCodeEntry/Span`：通过 method bitmap 判断方法是否存在，再把 `codeOffset` 映射为 code span，并由 `CodeInfo` 解出真正的可执行区间。

## 5) 与 04 章其他组件的交叉点（新同学要会连）

- **entrypoints**：AOT code 通过 GOT/patch table 间接调用 runtime 的慢路径。
- **StackWalker/deopt/异常**：AOT 的 `CodeInfo` 与 stack map 是“跨 compiled frame 还原语义帧”的基础数据。
- **FileManager/Runtime 启动加载**：`AotFile::Open` 的调用方是 `AotManager::AddFile`（见下一份 FileNotes）。




