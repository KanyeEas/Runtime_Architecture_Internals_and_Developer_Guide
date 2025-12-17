# 03_ClassLoading 章节完工审查（VM 架构师验收）

> 审查目标：把 03 章交付为“**新人可直接排障** + **架构断言可追溯到源码**”的稳定文档集。  
> 审查方法（复用 04 章经验）：见 `../00_Methodology_Wiki_Review_Checklist.md`（单一脊柱图入口 → Flow 拆链路 → DataStructures 抽不变量 → FileNotes 给证据链 → 最小调试手册给可复现实验 → 逐断言回源码核验 → 出具完工审查报告）。

## 0) 审查范围

- Stage2 入口：`README.md`、`Index.md`
- Flows：`Flows/*`
- DataStructures：`DataStructures/*`
- 新人最小排障：`Newbie_MinDebug_Playbook.md`
- 逐行证据链：`FileNotes/*`（以 `Manifests/files.yaml` 为准）
- Stage1 校正：`Errata_to_Stage1.md`

## 1) 结论概览

- **正确性（P0 断言）**：03 章的核心断言（GetClass 决策树、LoadClass 主管线、builders/layout/link 顺序、Context 并发去重、ETS 两段式加载、CNFE→NCDFE 包装）都能回到源码核验，结论总体 **可靠**。
- **可用性（新人路径）**：README/Index 已具备“场景驱动”的学习与排障路线；本轮补齐了：
  - `Flows/ClassLoading_EndToEnd.md`：**单一端到端脊柱图入口**
  - `Newbie_MinDebug_Playbook.md`：**可复现的最小调试手册**
- **仍可优化**：
  - 把少量“描述性结论”进一步改成“条件矩阵”（触发条件→第一落点→第二落点→必看日志）
  - 在“加载↔初始化”的跨章交界处加更显式互链（03→04）

## 2) P0 断言核验清单（带源码证据点）

### 2.1 GetClass 决策树（boot vs app）

- **证据源**：`runtime/class_linker.cpp`、`runtime/class_linker_extension.cpp`
- **核验点**：
  - `FindLoadedClass` 缓存命中优先
  - union/array descriptor 的特判路径
  - boot context：bloom filter gate（PossiblyContains）+ boot panda files 查 classId
  - app context：委托 `context->LoadClass`（ETS 在此特化）

### 2.2 LoadClass 主管线（创建/填充/链接/布局/去重）

- **证据源**：`runtime/class_linker.cpp`
- **核验点**：
  - `SetupClassInfo` 创建 builders，并计算 class size 输入
  - `ext->CreateClass` 创建 `Class`（ETS：NonMovable EtsClass + runtime Class 绑定）
  - `LoadMethods/LoadFields` 填充元数据
  - `LinkMethods`：vtable/itable/imtable 的构建与写回顺序
  - `LinkFields`：`LayoutFields` 写 offset/objectSize/refFields*
  - `InsertClass`：并发去重（冲突回收新对象）

### 2.3 ITable/IMT 与冲突策略

- **证据源**：
  - core：`runtime/imtable_builder.cpp`、`runtime/include/vtable_builder_*`
  - ETS：`plugins/ets/runtime/ets_itable_builder.cpp`
- **核验点**：
  - IMT 可被禁用（例如方法数量策略导致 `imtSize==0`）
  - 槽冲突策略（冲突即清空槽/标记 conflict）
  - ETS resolve（线性化 + vtable 驱动 resolve）
  - vtable build 关键步骤（继承父类槽 + 本类 override 匹配 + default interface -> copied methods）

### 2.4 ETS 两段式加载（native→managed gate）

- **证据源**：`plugins/ets/runtime/ets_class_linker_context.cpp`
- **核验点**：
  - native 链式遍历 parent/shared-libs
  - 仅当线程满足条件（managed/coro）才允许进入 managed 回退（`RuntimeLinker.loadClass(final)`）
  - 非 managed 线程禁止回退（避免 VM 内部线程 re-enter managed）

### 2.5 “找不到类”异常类型（CNFE vs NCDFE）

- **证据源**：`runtime/class_linker_extension.cpp`
- **核验点**：
  - `WrapClassNotFoundExceptionIfNeeded`：CNFE 在某些情境下包装为 NCDFE

### 2.6 `.abc/.an` 文件进入 ClassLinker/AotManager

- **证据源**：`runtime/file_manager.cpp`
- **核验点**：
  - `.abc` 装载失败直接 `LOG(ERROR, PANDAFILE)`
  - `enable-an` 时尝试 `.an` 伴随 `TryLoadAnFileForLocation`

## 3) 文档交付形态验收（摘要）

- `README.md`：场景决策树与主流程图完整；建议把“端到端脊柱图/最小调试手册/完工审查”作为显性入口挂在导航区。
- `Flows/*`：覆盖 GetClass/LoadClass、builders/link、layout/link、ETS 两段式、FileManager 输入链；**已统一补齐**“0) 在端到端主线图中的位置/下一步”导航（后续新增 flow 请保持该格式）。
- `DataStructures/*`：卡片结构清晰；**已补齐**“0) 位置/下一步”并在关键卡片增加 03→04 交界互链（仍建议后续把 InitializeClass/<clinit> 的跨章衔接做成更显性的单独小节）。



