# `runtime/file_manager.cpp`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：FileManager 实现：`.abc`/`.an` 的加载策略与 ClassLinker/AotManager 的连接点。

## 1. 依赖与命名空间（L16–L21）

- **L16**：对应头：`runtime/include/file_manager.h`
- **L17**：`runtime/include/runtime.h`：获取 `Runtime::GetCurrent()`、options、classLinker。
- **L18**：filesystem：`os::GetAbsolutePath`。
- **L20**：`namespace ark {`。

## 2. `LoadAbcFile`（L22–L39）

流程：
- **L24–L28**：`OpenPandaFile(location, "", openMode)`；失败则 log 并返回 false。
- **L29**：取 `runtime = Runtime::GetCurrent()`。
- **L30–L36**：当启用 `.an` 且非 ArkAot 模式：
  - `TryLoadAnFileForLocation(location)`：尝试加载对应 AOT 文件
  - 通过 `runtime->GetClassLinker()->GetAotManager()->FindPandaFile(location)` 查找 aotFile
  - 若存在：把 `aotFile->GetClassHashTable()` 回填给 panda file（`pf->SetClassHashTable(...)`）
    - 目的：加速 class id/hash 相关查找（属于 class linker 的 boot/filter 路径性能优化）
- **L37**：`runtime->GetClassLinker()->AddPandaFile(std::move(pf))`：
  - 触发：pandaFiles_/bootPandaFiles_ 注册、boot bloom filter 预热、notification/debug 注册（见 `class_linker.cpp`）。
- **L38**：成功返回 true。

## 3. `TryLoadAnFileForLocation`（L41–L64）

给定 `.abc` 路径，推导 `.an` 位置与文件名前缀：
- **L43–L47**：从 `abcPath` 找最后一个 `'/'` 与 `'.'`，任一不存在直接返回 true（不视为错误）。
- **L48–L50**：`abcFilePrefix = abcPath.substr(posStart, posEnd-posStart)`（注意包含 `/`，例如 `/foo/bar.abc` → `/bar`）。
- **L51–L58**：若配置 `boot-an-location`，优先在该目录下尝试 `TryLoadAnFileFromLocation`：
  - 成功直接 true
- **L60–L63**：否则/失败后，在 abc 文件同目录继续尝试一次。
- **L63**：整体返回 true（设计上：找不到 `.an` 不算错误）。

## 4. `TryLoadAnFileFromLocation`（L66–L90）

- **L69–L71**：拼出 `anFilePath = anFileLocation + abcFilePrefix + ".an"`。
- **L72–L77**：`access(filename, F_OK)` 不存在则 DEBUG log 并返回 false。
- **L78–L89**：调用 `LoadAnFile(anFilePath, force=false)`：
  - `res && res.Value()`：INFO log 成功并返回 true
  - `!res`：INFO log 并打印 `res.Error()`
  - `res` 但 Value=false：INFO log unknown reason
  - 最终 false

> 这段说明：`.an` 加载失败会被记录，但不阻断 `.abc` 的加载路径（上层仍可能继续运行解释器/非 AOT）。

## 5. `LoadAnFile`（L92–L101）

真正的 AOT 文件加载入口：
- **L94**：构造 `PandaRuntimeInterface runtimeIface`（作为 AOT manager 的运行时回调接口）。
- **L95**：`runtime = Runtime::GetCurrent()`。
- **L96–L97**：根据 runtime options + runtime type 推导 `gcType`，并断言非 INVALID。
- **L98**：`realAnFilePath = os::GetAbsolutePath(anLocation)`：用绝对路径作为 AOT file key。
- **L99–L100**：`AotManager::AddFile(realAnFilePath, &runtimeIface, gcType, force)`：
  - 返回 `Expected<bool,std::string>`：成功与否 + 错误字符串。

> 关键点：AOT 文件加载与 GC 类型强绑定（因为 AOT 代码/metadata 可能依赖特定 barrier/对象模型策略）。


