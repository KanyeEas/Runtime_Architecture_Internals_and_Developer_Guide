# `compiler/aot/aot_headers.h`（逐行精读｜AOT 元数据布局）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：定义 `.an` 文件（AOT ELF 内的 `aot` section）头部与索引表的**二进制布局**，是 AOT loader（`AotFile::Open`）与运行期索引/校验的共同基础。

## 1) `AotHeader`：`.an` 的“总目录”

`struct AotHeader` 是 `.an` 的元数据入口，关键字段分三类：

- **文件识别与一致性**：
  - `magic`：固定为 `.an\\0`（见 `AotFile::MAGIC`）
  - `version`：版本号（见 `AotFile::VERSION`）
  - `environmentChecksum`：必须匹配 `RuntimeInterface::GetEnvironmentChecksum(RUNTIME_ARCH)`（防止架构/ABI 不一致）
  - `gcType`：必须匹配运行时 GC（防止 barrier/对象布局假设不一致）
- **索引表偏移**：
  - `filesOffset/classesOffset/methodsOffset/bitmapOffset/strtabOffset` 等：把 `.an` 的各段组织成“可随机访问的表”
- **可观测信息**：
  - `fileNameStr/cmdlineStr/classCtxStr`：指向 strtab 的偏移，方便诊断（你能打印“编译时命令行/类上下文”）

## 2) `PandaFileHeader` / `ClassHeader` / `MethodHeader`：分层索引

这三层把 `.an` 的内容按 `panda file -> class -> method` 分组：

- `PandaFileHeader`：
  - `fileNameStr` + `fileChecksum`：用于把 `.abc` 与 `.an` 中的条目对应起来
  - `classesCount/classesOffset/methodsCount/methodsOffset`：二级索引入口
  - `classHashTableSize/classHashTableOffset`：让 runtime 侧给 `.abc` 注入 class hash table（见 `FileManager::LoadAbcFile`）
- `ClassHeader`：
  - `classId`：panda file 中的 class id
  - `methodsCount/methodsOffset`：指向 method 列表
  - `methodsBitmapOffset/methodsBitmapSize`：用 bitmap 表示“哪些方法被编进 AOT”（节省空间 + 快速判断）
- `MethodHeader`：
  - `methodId`
  - `codeOffset/codeSize`：指向 `code` section 里的机器码片段（进一步由 `CodeInfo` 解包出真正可执行 span）

## 3) 静态断言：保证布局可移植/可解析

`static_assert` 强调：

- `AotHeader` 按 `uint32_t` 对齐，且 size 是 `uint32_t` 的整数倍  
  → 这使得不同编译器/平台解析时更稳定，避免 padding 造成偏移错乱。




