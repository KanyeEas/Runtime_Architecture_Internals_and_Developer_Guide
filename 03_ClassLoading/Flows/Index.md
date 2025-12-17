# 03_ClassLoading / Flows

> 本目录以“运行时调用链”为主线组织说明。每条 flow 都指向对应的 `FileNotes/` 作为可审计证据。

## Flow 清单（建议顺序）

0. [ClassLoading_EndToEnd](ClassLoading_EndToEnd.md)：**端到端主线（新人脊柱图）**：文件装载→GetClass→LoadClass→builders/layout/link→并发去重→初始化交界（每个框都可下潜）
1. [GetClass_and_LoadClass](GetClass_and_LoadClass.md)：从 `GetClass` 到 `LoadClass` 的总链路（boot vs app）
2. [Builders_and_LinkMethods](Builders_and_LinkMethods.md)：vtable/itable/IMT 的构建与写回（LinkMethods）
3. [LayoutFields_and_LinkFields](LayoutFields_and_LinkFields.md)：字段布局算法与 offset 写回（LinkFields）
4. [Concurrency_and_ClassLock](Concurrency_and_ClassLock.md)：并发类加载（InsertClass 去重）+ 递归加载防护（CLASS_CIRCULARITY）+ ClassLock（per-class condvar）
5. [ETS_Context_Native_vs_Managed_Load](ETS_Context_Native_vs_Managed_Load.md)：ETS context 的 native 优先链式加载与 managed 回退
6. [FileManager_ABC_AN](FileManager_ABC_AN.md)：`.abc/.an` 如何进入 ClassLinker/AotManager

> 新人调试入口（不属于 flow，但强烈建议收藏）：[Newbie_MinDebug_Playbook](../Newbie_MinDebug_Playbook.md)


