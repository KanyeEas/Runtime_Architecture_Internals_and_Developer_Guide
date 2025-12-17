# `runtime/include/file_manager.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：FileManager API 声明：负责把 `.abc`（panda file）与 `.an`（AOT 文件）加载进 Runtime/ClassLinker/AotManager。

## 1. 头部与依赖（L16–L22）

- **L16–L17**：include guard：`PANDA_FILE_MANAGER_H_`。
- **L19**：`libarkfile/file.h`：panda file open 接口与类型定义。
- **L20**：`runtime/compiler.h`：提供 `Expected<bool, std::string>` 等编译/运行时桥接类型（以及 AOT 相关接口）。
- **L21**：`panda_string.h`：用于拼路径与返回前缀。

## 2. `FileManager` 的职责与 API（L25–L35）

- **L27**：`LoadAbcFile(location, openMode)`：
  - 打开 `.abc` 并注册到 `Runtime::GetCurrent()->GetClassLinker()->AddPandaFile(...)`（实现在 `.cpp`）。
- **L29**：`TryLoadAnFileForLocation(abcPath)`：
  - 给定 `.abc` 路径，推导同名 `.an` 并尝试加载（优先 boot-an-location）。
- **L31–L32**：`TryLoadAnFileFromLocation(anFileLocation, abcFilePrefix, pandaFileLocation)`：
  - 在指定目录下拼 `.an` 文件并尝试加载；成功与否返回 bool。
- **L34**：`LoadAnFile(anLocation, force=false)`：
  - 通过 `AotManager::AddFile(...)` 加载 `.an`，返回 Expected（携带错误字符串）。

> 结论：FileManager 是“文件→ClassLinker/AotManager”的 glue layer：  
> - `.abc` 走 `AddPandaFile`（触发 boot/filter/notification/debug）  
> - `.an` 走 `AotManager::AddFile` 并可回填 class hash table 给 panda file。


