# 03_ClassLoading / DataStructures

> 本目录是“可复用的结构卡片”。每张卡片只写三件事：**结构是什么**、**关键字段/不变量**、**在哪里被写入/消费**（回链到 FileNotes）。

## 结构卡片清单（建议顺序）

1. [Class](Class.md)：Class 元数据对象（大小/表区布局/状态机/字段与方法容器）
2. [Method](Method.md)：Method 元数据（签名/入口点/热点与编译状态/派发索引）
3. [Field](Field.md)：Field 元数据（type 位段/offset/所属类）
4. [ITable_and_IMT](ITable_and_IMT.md)：接口派发结构（ITable entries、IMT 冲突策略）
5. [ClassLinkerContext](ClassLinkerContext.md)：上下文缓存 + per-Class mutex + GC roots
6. [ETS_Plugin_Summary](ETS_Plugin_Summary.md)：ETS 的 LanguageContext/Extension/Context/ITableBuilder 的职责分工

> 新人推荐：先看 [../Flows/ClassLoading_EndToEnd](../Flows/ClassLoading_EndToEnd.md) 建立主线，再按卡片补不变量。


