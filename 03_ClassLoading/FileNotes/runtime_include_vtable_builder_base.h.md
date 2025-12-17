# `runtime/include/vtable_builder_base.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：虚表（vtable）/接口派发表（IMT/ITable）构建的基础设施声明（含关键数据结构 + 抽象处理钩子）  
> 实现位置：大量 inline 实现在 `runtime/include/vtable_builder_base-inl.h`；冲突处理与策略在 `vtable_builder_variance*` 等派生实现中。

## 1. 文件定位（为什么它必须归属 03）

类链接（ClassLinker）不仅要解析类/方法/字段，还必须为**方法派发**准备好运行时结构：

- **vtable**：类的虚方法表（按 `Method::vtable_index` 索引）。
- **IMT（Interface Method Table）**：接口方法快速派发槽（按 `methodId % imtSize` 映射）。
- **ITable**：接口到方法数组的映射（用于 IMT miss 的慢路径）。
- **copied methods**：从接口默认方法（default interface methods）复制到类的方法集合中，以统一派发/可见性处理。

本文件提供 vtable 构建的“通用骨架”，并把“覆盖规则/协变兼容/冲突判定”等策略交给派生类实现（见 `vtable_builder_variance-inl.h`）。

## 2. 头部与依赖（L1–L36）

- **L1–L14**：License。
- **L15–L16**：include guard：`PANDA_RUNTIME_VTABLE_BUILDER_BASE_H`。
- **L18**：`macros.h`：`ASSERT/LIKELY/UNLIKELY/DEFAULT_*` 等。
- **L19**：hash：用于 `MethodNameHash`（按方法名哈希）。
- **L20**：utf：用于名称/descriptor 处理（间接使用）。
- **L21–L24**：`libarkfile/*-inl.h` + `file_items.h`：访问 panda_file 中的 class/method/proto 元数据（`ClassDataAccessor/MethodDataAccessor/ProtoDataAccessor`）。
- **L25**：`runtime/class_linker_context.h`：LoadContext（同名方法兼容性检查需要 context）。
- **L26**：`class-inl.h`：`Class::GetVTable()`、`Method` 访问器等 inline 实现被直接用到（注意：这让 vtable builder 成为 03 的“强 include 中心”）。
- **L27**：`class_linker.h`：错误码 `ClassLinker::Error`、以及链接期错误处理接口。
- **L28–L29**：`panda_containers/smart_pointers`：Arena 容器/分配器。
- **L30**：`vtable_builder_interface.h`：抽象接口 `VTableBuilder` 与 `CopiedMethod` 定义。
- **L32–L36**：`namespace ark` 与 `ClassLinker/ClassLinkerContext` 前向声明。

## 3. `MethodInfo`：统一包装（panda_file method vs runtime Method）（L37–L153）

该类型是“构建阶段的中间表示”：同一个逻辑方法可能来自：
- **未 materialize 的 panda_file::MethodDataAccessor**（类还在链接/构建中）
- **已存在的 runtime `Method*`**（比如 baseClass 的 vtable 方法、接口 default 方法对象等）

### 3.1 构造：来自 panda_file（L39–L48）
- **L39**：参数：`MethodDataAccessor& mda`、`index`（vmethodIndex）、`ctx`（LoadContext）。
- **L40**：保存 `pf_` 指针（panda file）。
- **L41**：缓存 `name_`（通过 `GetStringData(mda.GetNameId())`）。
- **L42**：保存 `protoId_`（注意这里是 panda_file 的 `EntityId`，后续通过 `Method::ProtoId(*pf_, protoId_)` 转成运行时 wrapper）。
- **L43**：保存 `accessFlags_`。
- **L44**：保存 `classId_`（声明该方法的类 id）。
- **L45–L46**：保存 `ctx_` 与 `vmethodIndex_`。

### 3.2 构造：来自 runtime `Method*`（L50–L61）
用于处理 baseClass 的 vtable 方法 / default 方法等：
- **L51**：`pf_ = method->GetPandaFile()`。
- **L52**：`name_ = method->GetName()`（已是 StringData）。
- **L53**：`protoId_ = method->GetProtoId().GetEntityId()`（仍回到 EntityId）。
- **L54**：`accessFlags_ = method->GetAccessFlags()`。
- **L55**：`isBase_`：标记该方法是否来自 baseClass（用于覆盖判定：只允许 override base）。
- **L56**：`classId_ = method->GetClass()->GetFileId()`。
- **L57**：保存 `method_`（此时可直接访问 Method*）。
- **L58**：`ctx_` 取自 `method->GetClass()->GetLoadContext()`。
- **L59**：`vmethodIndex_`（默认 0，可由调用者指定）。

### 3.3 访问器（L63–L132）
关键点：
- **L68–L71**：`GetClassName()`：若有 `method_` 则用 runtime class descriptor；否则从 panda_file 的 `classId_` 取字符串数据（descriptor）。
- **L73–L76**：`GetProtoId()`：统一返回 `Method::ProtoId`（封装了 pf+entityId）。
- **L113–L121**：`IsInterfaceMethod()`：若 runtime `method_` 存在，则用 `method_->GetClass()->IsInterface()`；否则用 `ClassDataAccessor` 判断 classId 是否接口。
- **L123–L126**：`IsBase()`：覆盖判定时只关心 base 标记。
- **L128–L131**：`GetLoadContext()`：返回 ctx（影响 proto 兼容性检查）。

### 3.4 语义约束（L133–L153）
- **L135**：删除 `operator==`：避免被 unordered_map 等误用为值语义等价（这里只依赖指针/哈希）。
- **L137–L139**：允许 copy ctor，但禁用 copy operator 与 move（结合 Arena 容器使用习惯）。
- **L141–L152**：私有字段：pf/name/protoId/accessFlags/isBase/classId/method/ctx/vmethodIndex。

## 4. `VTableInfo`：构建中的 vtable + copied methods 映射（L155–L260）

这个结构是“builder 的工作区”：
- `vmethods_`：`MethodInfo* -> MethodEntry`（存 index + candidate override）。
- `copiedMethods_`：`MethodInfo* -> CopiedMethodEntry`（存 copied index + status）。

### 4.1 容器选择（L157–L160）
- 使用 `ArenaUnorderedMap`，key 是 `MethodInfo const*`（注意：key 的“身份”是 MethodInfo 对象地址）。
- 分配器来自 builder 内部 `ArenaAllocator`（见后面的 `allocator_`）。

### 4.2 `MethodEntry`：候选覆盖（L162–L188）
核心语义：
- **index_**：该条目在 vtable/copy 列表中的稳定序号。
- **candidate_**：如果派生类方法覆盖了 base 方法，则 candidate_ 指向“替换方法”；否则为空。
- **CandidateOr(orig)**：若 candidate 非空返回 candidate，否则返回 orig（用于生成最终 vtable）。

### 4.3 `CopiedMethodEntry`：默认方法复制状态（L190–L211）
核心语义：
- **index_**：copied method 在 copiedMethods_ 中的稳定序号。
- **status_**：`CopiedMethod::Status`（ORDINARY/ABSTRACT/CONFLICT）用于标记冲突/抽象等情况（具体何时置位由派生策略决定）。

### 4.4 `MethodNameHash`（L251–L256）
- 对 `MethodInfo->GetName().data` 做 `GetHash32String`。
- 注意：哈希只基于 name，不含 proto；因此同名不同签名的方法会落在同 bucket，需要通过 `SameNameMethodInfoIterator` 进一步按 proto 过滤。

### 4.5 对外接口声明（L233–L248）
这些函数大多在 `vtable_builder_base-inl.h` inline 实现：
- `AddEntry`：插入 vmethods_，index = 当前 size。
- `AddCopiedEntry/UpdateCopiedEntry`：管理 copiedMethods_ 的插入与替换。
- `UpdateClass`：把最终 vtable/copy 写回到 `Class` 对象（会设置 `Method::vtable_index` 等）。
- `DumpMappings/DumpVTable`：调试输出。

## 5. `FilterBucketIterator` + `SameNameMethodInfoIterator`（L262–L316）

### 5.1 为什么需要它
因为 `ArenaUnorderedMap` 的 key 是 `MethodInfo*`，但 `MethodNameHash` 只按 name 哈希，所以：
- 同 bucket 内可能包含“同名不同 proto 的方法”；
- 甚至 key 不同但 name 相同的方法需要一起遍历用于 override/冲突检测。

### 5.2 `FilterBucketIterator`（L262–L309）
- 构造函数：用 `umap.bucket(key)` 定位 bucket，然后从该 bucket 的 begin 到 end 迭代。
- `Advance()`：跳过不满足 pred 的元素。
- `IsEmpty()`：valid_ 或迭代到 end。
- `Value()/Next()`：访问与前进。

### 5.3 `SameNameMethodInfoIterator`（L311–L316）
- pred：`other->first->GetName() == info->GetName()`（注意：`other` 是 bucket iterator 指向的 pair，`first` 为 `MethodInfo*`）。
- 返回过滤后的 bucket iterator：用于派生策略（例如 variance builder）遍历“同名方法集合”。

## 6. `VTableBuilderBase<VISIT_SUPERITABLE>`：基础构建骨架（L318–L369）

> 关键：本类只提供“流程骨架”，真正的覆盖/冲突/协变兼容策略通过两个纯虚钩子注入：  
> - `ProcessClassMethod`（处理一个本类虚方法）  
> - `ProcessDefaultMethod`（处理一个接口默认方法，决定是否 copied/冲突）

### 6.1 对外接口（L322–L341）
- **L322**：`Build(cda, baseClass, itable, ctx)`：从 panda_file 元数据构建（实现见 `vtable_builder_base-inl.h`）。
- **L324**：`Build(methods, baseClass, itable, isInterface)`：从 runtime `Span<Method>` 构建（用于某些语言/合成类路径）。
- **L326**：`UpdateClass(klass)`：把结果写回 Class（实现见 inl）。
- **L328–L336**：`GetNumVirtualMethods/GetVTableSize`：提供构建统计给 ClassLinker。
- **L338–L341**：`GetCopiedMethods`：返回构建出的 copied methods 列表（有序数组）。

### 6.2 受保护构造与策略钩子（L343–L347）
- **L344**：构造函数需要 `ClassLinkerErrorHandler*`（冲突报错通过它上抛）。
- **L346**：`ProcessClassMethod`：由派生类实现（例如 variance override 规则）。
- **L347**：`ProcessDefaultMethod`：由派生类实现（处理默认方法冲突/覆盖）。

### 6.3 工作区字段（L349–L354）
- **allocator_**：内部 ArenaAllocator（internal space）。
- **vtable_**：`VTableInfo` 工作区。
- **numVmethods_**：计数本类虚方法数量（接口：计数非 static 方法；普通类：计数 non-static methods 作为 vmethods）。
- **orderedCopiedMethods_**：最终对外暴露的 copied methods 数组（按 entry.GetIndex() 放置）。
- **errorHandler_**：错误上报通道。

### 6.4 私有流程步骤声明（L355–L368）
这些步骤的 inline 实现在 `vtable_builder_base-inl.h`：
- `BuildForInterface(...)`：接口特殊处理：只计数 & 记录是否存在 default 方法（不构建 vtable 映射）。
- `AddBaseMethods(baseClass)`：把 baseClass vtable 方法作为“base entries”塞入 vtable_（isBase_=true）。
- `AddClassMethods(...)`：枚举本类虚方法，逐个调用 `ProcessClassMethod`。
- `AddDefaultInterfaceMethods(itable, superItableSize)`：从 itable 中倒序遍历接口默认方法并调用 `ProcessDefaultMethod`，同时生成 `orderedCopiedMethods_`。
- `hasDefaultMethods_`：接口构建路径下标记是否存在 default 方法（用于 UpdateClass 写回 `ACC_HAS_DEFAULT_METHODS`）。

## 7. 与 `vtable_builder_base-inl.h` 的关键对应关系（实现入口）

本文件声明的核心流程在 `vtable_builder_base-inl.h` 中实现（建议优先阅读以下段落）：
- `BuildForInterface`：L50–L81（统计 numVmethods_ 与 hasDefaultMethods_）。
- `AddBaseMethods`：L83–L94（把 baseClass 的 vtable 方法注入 vtable_）。
- `AddClassMethods`：L96–L135（枚举 non-static methods 并调用 `ProcessClassMethod`）。
- `AddDefaultInterfaceMethods`：L137–L174（倒序遍历 itable，处理 default 方法并生成 copied methods 数组）。
- `Build`：L176–L212（整体顺序：interface fast path，否则 base→class→default）。
- `UpdateClass`：L214–L229（接口：写回 vtable_index；普通类：`vtable_.UpdateClass` 写回）。

## 8. 本文件引出的“同章强相关文件”（动态纳入候选）

由 `#include` 与强耦合可判定为 03 强相关（将纳入 manifest）：
- `runtime/include/vtable_builder_interface.h`
- `runtime/include/vtable_builder_base-inl.h`
- `runtime/include/vtable_builder_variance-inl.h`（策略实现，P0）
- `runtime/include/itable.h`、`runtime/include/method.h`、`runtime/include/class-inl.h`
- `runtime/include/class_linker.h`、`runtime/class_linker_context.h`


