# 阶段一校正记录（Stage2 -> Stage1 Errata）

> 在阶段二逐行精读中发现 Stage1 描述不准确时：
> 1) 在此记录校正点与依据（文件/函数/行段）
> 2) 回写修正 Stage1 对应文档

## 校正点列表
- **Stage1 第 03 章“语言扩展实现文件/入口”列表不完整（需要补齐证据链）**：
  - **问题**：Stage1 重点描述了 `ClassLinker`、`ClassLinkerExtension` 抽象与 ETS 插件，但没有把以下 4 个“实际入口/默认实现”文件纳入关键证据链，导致读者很难从 Stage1 直接定位到“roots 自举/默认 AppContext LoadClass/ETS façade”的实现落点。
  - **依据（实现落点）**：
    - `runtime/class_linker_extension.cpp`：Boot/AppContext 的默认 `LoadClass` 策略、`created/new/obsolete classes` 容器语义、以及 **CNFE→NCDFE** 的异常包装（按 `pf,id` 取类失败时）。
    - `runtime/core/core_class_linker_extension.cpp`：core（PANDA_ASSEMBLY）语言的 roots 自举实现（primitive/array/synthetic），以及 **String 子类在 roots 阶段写入 GC ref-fields 元数据** 与 `CreateClass` 的 NonMovable 分配+managed/runtime 绑定。
    - `plugins/ets/runtime/ets_class_linker.h` / `plugins/ets/runtime/ets_class_linker.cpp`：ETS 对外 façade（把 `Class*` 语义包装成 `EtsClass*`），并包含 async 注解 → impl method 的解析链路与异常语义。
  - **处理**：Stage2 已将上述文件纳入 `03_ClassLoading/Manifests/files.yaml` 并补齐逐行 `FileNotes/`；同时已回写修正 Stage1 的 `03_Class_Loading_and_Linking.md`，把这些文件作为“语言扩展实现/入口”的必读落点补充进去。
