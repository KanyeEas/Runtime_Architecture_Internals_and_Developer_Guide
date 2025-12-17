# 03_ClassLoading - Index

## 这份 Index 的用法（面向新同学）

你可以把它当成“学习路线图”而不是文件清单：
- **只想 30 分钟看懂大概**：走「30min 路线」——看图 + 看主线故事，不下潜逐行
- **要能排查常见问题（找不到类/接口派发/ETS loader）**：走「2h 路线」
- **要能修改代码或定位复杂 bug**：走「1d 路线」——再下潜 `FileNotes/`

建议同时打开：
- [FileNotes/_Glossary](FileNotes/_Glossary.md)（术语速查）
- [README](README.md)（本章故事线 + 关键流程图）
- [Flows/ClassLoading_EndToEnd](Flows/ClassLoading_EndToEnd.md)（端到端脊柱图：新人 0 号入口）
- [Newbie_MinDebug_Playbook](Newbie_MinDebug_Playbook.md)（新人可复现排障手册）

## 30min 路线：建立整体模型（不读 FileNotes 也能懂）

0. [Flows/ClassLoading_EndToEnd](Flows/ClassLoading_EndToEnd.md)（端到端脊柱图：先把整条链路串起来）
1. [README](README.md)（先看 5 张 Mermaid 图：组件总览、GetClass、LoadClass、ETS LoadClass、Context 关系）
2. [Diagrams/Index](Diagrams/Index.md)（如果你想复制图到分享/设计文档）
3. [Flows/Index](Flows/Index.md)（看每条调用链的“入口/出口/关键决策点”）
4. [DataStructures/Index](DataStructures/Index.md)（只看每张卡片“它是什么/不变量/谁写谁读”）

## 2h 路线：能排查问题（建议按你遇到的场景选读）

### 场景 A：找不到类 / 异常类型不对（CNFE vs NCDFE）
- [FileNotes/runtime_class_linker_extension.cpp](FileNotes/runtime_class_linker_extension.cpp.md)（WrapClassNotFoundExceptionIfNeeded + AppContext 默认 LoadClass）
- [FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md)（GetClass/LoadClass 主链路，含 boot filter）
- [Flows/GetClass_and_LoadClass](Flows/GetClass_and_LoadClass.md)（把入口、分支、回退策略串起来）

### 场景 B：接口派发 / 默认方法 / MULTIPLE_IMPLEMENT / IMT 为空
- [DataStructures/ITable_and_IMT](DataStructures/ITable_and_IMT.md)（先记住 IMT 是“可选加速结构”）
- [FileNotes/plugins_ets_runtime_ets_itable_builder.cpp](FileNotes/plugins_ets_runtime_ets_itable_builder.cpp.md)（ETS resolve 策略与冲突）
- [FileNotes/runtime_imtable_builder.cpp](FileNotes/runtime_imtable_builder.cpp.md)（IMT size 策略 + 冲突即清空槽）
- [Flows/Builders_and_LinkMethods](Flows/Builders_and_LinkMethods.md)（builder 的 Build/Resolve/UpdateClass 顺序）

### 场景 C：ETS 应用加载器（native 先尝试 / managed 回退条件）
- [FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp.md)（两段式加载与链式遍历）
- [Flows/ETS_Context_Native_vs_Managed_Load](Flows/ETS_Context_Native_vs_Managed_Load.md)（一张图解释为什么不能在非 managed 线程回退）

## 1d 路线：下潜逐行（按依赖顺序，不容易迷路）

建议按“先元数据契约 → 再派发表/布局算法 → 再 ClassLinker 管线 → 再 ETS 插件落地”的顺序阅读：

### 1) 元数据契约与对象/指针模型
- [FileNotes/runtime_include_class.h](FileNotes/runtime_include_class.h.md)（`runtime/include/class.h`）
- [FileNotes/runtime_include_class-inl.h](FileNotes/runtime_include_class-inl.h.md)（`runtime/include/class-inl.h`）
- [FileNotes/runtime_include_method.h](FileNotes/runtime_include_method.h.md)（`runtime/include/method.h`）
- [FileNotes/runtime_include_field.h](FileNotes/runtime_include_field.h.md)（`runtime/include/field.h`）
- [FileNotes/runtime_include_itable.h](FileNotes/runtime_include_itable.h.md)（`runtime/include/itable.h`）
- [FileNotes/runtime_include_class_helper.h](FileNotes/runtime_include_class_helper.h.md)（`runtime/include/class_helper.h`）

### 2) Context：缓存、并发协调与 GC roots（基类与 ETS 特化）
- [FileNotes/runtime_class_linker_context.h](FileNotes/runtime_class_linker_context.h.md)（`runtime/class_linker_context.h`）
- [FileNotes/plugins_ets_runtime_ets_class_linker_context.h](FileNotes/plugins_ets_runtime_ets_class_linker_context.h.md)（`plugins/ets/runtime/ets_class_linker_context.h`）
- [FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp.md)（`plugins/ets/runtime/ets_class_linker_context.cpp`）

### 3) 派发表构建：vtable / itable / imt（含冲突策略）
- [FileNotes/runtime_include_vtable_builder_interface.h](FileNotes/runtime_include_vtable_builder_interface.h.md)（`runtime/include/vtable_builder_interface.h`）
- [FileNotes/runtime_include_vtable_builder_base.h](FileNotes/runtime_include_vtable_builder_base.h.md)（`runtime/include/vtable_builder_base.h`）
- [FileNotes/runtime_include_vtable_builder_base-inl.h](FileNotes/runtime_include_vtable_builder_base-inl.h.md)（`runtime/include/vtable_builder_base-inl.h`）
- [FileNotes/runtime_include_vtable_builder_variance.h](FileNotes/runtime_include_vtable_builder_variance.h.md)（`runtime/include/vtable_builder_variance.h`）
- [FileNotes/runtime_include_vtable_builder_variance-inl.h](FileNotes/runtime_include_vtable_builder_variance-inl.h.md)（`runtime/include/vtable_builder_variance-inl.h`）
- [FileNotes/runtime_include_itable_builder.h](FileNotes/runtime_include_itable_builder.h.md)（`runtime/include/itable_builder.h`：接口契约）
- [FileNotes/runtime_include_imtable_builder.h](FileNotes/runtime_include_imtable_builder.h.md)（`runtime/include/imtable_builder.h`：接口契约）
- [FileNotes/runtime_imtable_builder.cpp](FileNotes/runtime_imtable_builder.cpp.md)（`runtime/imtable_builder.cpp`：IMT 构建/冲突即清空槽）
- [FileNotes/plugins_ets_runtime_ets_itable_builder.h](FileNotes/plugins_ets_runtime_ets_itable_builder.h.md)（`plugins/ets/runtime/ets_itable_builder.h`）
- [FileNotes/plugins_ets_runtime_ets_itable_builder.cpp](FileNotes/plugins_ets_runtime_ets_itable_builder.cpp.md)（`plugins/ets/runtime/ets_itable_builder.cpp`：ETS itable 线性化 + vtable 驱动 resolve）

### 4) ClassLinker 主管线：加载/链接/布局/缓存/过滤
- [FileNotes/runtime_include_class_linker.h](FileNotes/runtime_include_class_linker.h.md)（`runtime/include/class_linker.h`：API 与内部管线分解）
- [FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md)（`runtime/class_linker.cpp`：完整实现闭环，按函数簇分段）
- [FileNotes/runtime_include_class_linker_extension.h](FileNotes/runtime_include_class_linker_extension.h.md)（`runtime/include/class_linker_extension.h`：extension 抽象 + roots/contexts/new roots）
- [FileNotes/runtime_class_linker_extension.cpp](FileNotes/runtime_class_linker_extension.cpp.md)（`runtime/class_linker_extension.cpp`：Boot/AppContext 默认 LoadClass + new/obsolete/created classes 容器语义）

### 5) Core（PANDA_ASSEMBLY）：默认语言 Extension 的 roots 自举实现
- [FileNotes/runtime_core_core_class_linker_extension.cpp](FileNotes/runtime_core_core_class_linker_extension.cpp.md)（`runtime/core/core_class_linker_extension.cpp`：primitive/array/synthetic roots + String 子类 GC 元数据 + CreateClass）

### 6) ETS：LanguageContext/Extension/Facade 的落地（把策略变成实现）
- [FileNotes/plugins_ets_runtime_ets_language_context.h](FileNotes/plugins_ets_runtime_ets_language_context.h.md)（`plugins/ets/runtime/ets_language_context.h`）
- [FileNotes/plugins_ets_runtime_ets_language_context.cpp](FileNotes/plugins_ets_runtime_ets_language_context.cpp.md)（`plugins/ets/runtime/ets_language_context.cpp`）
- [FileNotes/plugins_ets_runtime_ets_class_linker_extension.h](FileNotes/plugins_ets_runtime_ets_class_linker_extension.h.md)（`plugins/ets/runtime/ets_class_linker_extension.h`）
- [FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp.md)（`plugins/ets/runtime/ets_class_linker_extension.cpp`）
- [FileNotes/plugins_ets_runtime_ets_class_linker.h](FileNotes/plugins_ets_runtime_ets_class_linker.h.md)（`plugins/ets/runtime/ets_class_linker.h`：ETS façade API）
- [FileNotes/plugins_ets_runtime_ets_class_linker.cpp](FileNotes/plugins_ets_runtime_ets_class_linker.cpp.md)（`plugins/ets/runtime/ets_class_linker.cpp`：ETS façade + async 注解解析）

### 7) 文件加载到 ClassLinker/AOT：.abc/.an
- [FileNotes/runtime_include_file_manager.h](FileNotes/runtime_include_file_manager.h.md)（`runtime/include/file_manager.h`）
- [FileNotes/runtime_file_manager.cpp](FileNotes/runtime_file_manager.cpp.md)（`runtime/file_manager.cpp`）

## 阅读提示（避免新手常见误解）

- **IMT 不是必然存在**：接口方法过多会直接 `imtSize=0`，派发回退到 itable（见 [FileNotes/runtime_imtable_builder.cpp](FileNotes/runtime_imtable_builder.cpp.md)）。
- **“加载”与“初始化”是两件事**：LoadClass 创建并链接 `Class/Method/Field`，InitializeClass 才触发 `<clinit>`/语言侧初始化（本章覆盖接口点；执行细节在 04/执行引擎与 06/验证等章节会更深入）。
- **Context 决定“可见域”**：同名 descriptor 在不同 context 可以有不同的 `Class*`；ETS 还有 parent/shared libs 链（见 [README](README.md) 的 Context 图）。

## 文件清单
- 见 `Manifests/files.yaml`（逐行精读清单）
- 见 `Manifests/tree_inventory.txt`（seed 全量扫描清单）
