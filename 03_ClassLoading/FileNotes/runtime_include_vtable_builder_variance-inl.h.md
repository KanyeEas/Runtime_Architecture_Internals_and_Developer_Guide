# `runtime/include/vtable_builder_variance-inl.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：vtable 构建的“覆盖/协变/冲突”策略实现（为 `VarianceVTableBuilder` 提供 inline 定义）  
> 直接依赖：`vtable_builder_variance.h`（类声明）、`vtable_builder_base-inl.h`（基础流程+VTableInfo 操作）、`ClassLinker::Error`（冲突错误码）。

## 1. 文件定位（这份策略解决什么问题）

`VTableBuilderBase` 只给出“构建流程骨架”，并通过两个钩子把策略交给派生类：
- `ProcessClassMethod`：当一个“本类虚方法”出现时，如何判定它是否覆盖（override）base 方法？如果覆盖，如何替换候选？如果不覆盖，是否作为新 entry 加入 vtable？
- `ProcessDefaultMethod`：当发现接口 default 方法时，是否需要生成 copied method？如何处理“多接口默认实现冲突”？

本文件实现的策略特点：
- **按 name 分桶**遍历（同名方法集合），避免全表扫描（依赖 `SameNameMethodInfoIterator`）。
- 覆盖判定不仅基于“proto 直接相等”，还可以通过 `ProtoCompatibility(ctx)` 做更宽松/协变的兼容判断（模板参数）。
- 冲突通过 `OnVTableConflict` 上报，并返回 false 终止构建。

## 2. 头部（L1–L21）
- **L1–L14**：License。
- **L15–L16**：include guard：`PANDA_RUNTIME_VTABLE_BUILDER_VARIANCE_INL_H`。
- **L18**：包含 `vtable_builder_variance.h`（`VarianceVTableBuilder` 声明）。
- **L19**：包含 `vtable_builder_base-inl.h`（`VTableInfo` 的 inline 操作、`OnVTableConflict` 声明等）。
- **L21**：`namespace ark {`。

## 3. 覆盖关系判定：`IsOverriddenBy` / `IsOverriddenOrOverrides`（L23–L43）

### 3.1 `IsOverriddenBy(ctx, base, derv)`（L23–L32）
- **L28–L30**：快路径：若 `base` 与 `derv` 来自同一 panda_file 且 entityId 相等，则视为“同一原型”→ true。
- **L31**：否则调用 `ProtoCompatibility(ctx)(base, derv)`：
  - `ProtoCompatibility` 是一个可调用对象类型（functor），由模板参数注入。
  - 语义：判断 `derv` 是否能覆盖 `base`（例如支持协变返回类型/特殊语言规则）。

### 3.2 `IsOverriddenOrOverrides(ctx, p1, p2)`（L34–L43）
- **L39–L41**：同 file 同 entity → true。
- **L42**：否则：`ProtoCompatibility(ctx)(p1, p2) || ProtoCompatibility(ctx)(p2, p1)`：
  - 用于“冲突检测”：只要两边存在覆盖关系（任意方向），就认为两者存在可冲突的覆盖/被覆盖联系。

## 4. 处理本类虚方法：`ProcessClassMethod`（L45–L77）

目标：把“本类方法 info”加入 vtable_，或者替换某个 base 方法 entry 的 candidate。

- **L48**：取 `ctx = info->GetLoadContext()`，用于 proto 兼容性判定。
- **L49**：`compatibleFound=false`：标记是否找到了可覆盖的 base 方法。
- **L51–L71**：遍历 `SameNameMethodInfoIterator(vtable_.Methods(), info)`：
  - 只会在同 bucket 内筛出“同名方法”集合，避免遍历整个 map。
  - **L54–L56**：跳过非 base 方法（只允许覆盖 base 条目；本类内部同名方法的处理走 `AddEntry`）。
  - **L57**：覆盖判定需要同时满足：
    - `IsOverriddenBy(ctx, itInfo->GetProtoId(), info->GetProtoId())`
    - `OverridePred()(itInfo, info)`：第二个模板参数注入额外谓词（例如访问控制/可见性/语言特定规则）。
  - **L58–L62**：若 base 方法是 final：冲突 `OVERRIDES_FINAL`，构建失败返回 false。
  - **L63–L67**：若该 base entry 已经有 candidate（说明出现多个 override）：冲突 `MULTIPLE_OVERRIDE`，失败返回 false。
  - **L68–L70**：设置 candidate 为当前 info，并置 `compatibleFound=true`。
- **L73–L75**：如果没有找到任何可覆盖的 base 方法：把当前方法作为新 entry 加入 `vtable_`（扩展 vtable）。
- **L76**：成功返回 true。

> 这里的关键约束：  
> - 只覆盖 base（`IsBase()`）的方法条目；避免“同一类内同名方法”互相覆盖造成不稳定。  
> - 同一 base 条目最多允许一个 candidate，否则视为多重覆盖错误。

## 5. 默认接口方法冲突扫描：`ScanConflictingDefaultMethods`（L79–L119）

返回类型：`std::optional<MethodInfo const *>`
- **返回 `std::nullopt`**：表示“跳过本 default method”（因为它被类中的非接口方法覆盖了，或不应加入 copied）。
- **返回 `nullptr`**：表示“没有冲突，允许首次加入 copied methods”。
- **返回 非空指针**：表示“发现冲突的接口 default 方法”，调用者应上报冲突。

扫描分三段：

### 5.1 检查是否被类中的非接口方法覆盖（L85–L94）
- **L86**：对每个同名条目，取 “candidate 或 orig”（`CandidateOr`）代表最终会出现在 vtable 的方法。
- **L87–L88**：若该条目是 interface 方法则跳过（我们关心类方法对 default 的覆盖）。
- **L90–L92**：若 default 的 proto 被该类方法覆盖（`IsOverriddenBy(ctx, info, itinfo)`），则返回 `std::nullopt`：表示 default 不需要 copied（类方法优先）。

### 5.2 检查与 vtable 中的接口方法冲突（L95–L105）
- 只关心 interface 方法条目。
- **L100**：断言冲突方法来自不同接口类（防自冲突）。
- **L101–L103**：若两者存在覆盖/被覆盖关系（任意方向），返回冲突接口方法指针（非空）。

### 5.3 检查与已加入的 copied methods 冲突（L106–L117）
- 遍历 `vtable_.CopiedMethods()` 中同名条目。
- 跳过非接口方法与同一接口类的 default（避免重复）。
- 若覆盖/被覆盖关系成立，返回冲突指针。

### 5.4 无冲突（L118）
- 返回 `nullptr`：表示可加入。

## 6. 处理默认接口方法：`ProcessDefaultMethod`（L121–L141）

- **L125**：先调用 `ScanConflictingDefaultMethods(methodInfo)`。
- **L126–L128**：若返回 `std::nullopt`：跳过（视为成功，继续处理其它 default 方法）。
- **L129**：否则取 `conflict`（可能为 nullptr 或指向冲突方法）。
- **L130**：`iface` 仅用于调试（`[[maybe_unused]]`）。
- **L132–L136**：若 `conflict == nullptr`：说明首次加入 → `vtable_.AddCopiedEntry(methodInfo)` 并返回 true。
- **L138–L140**：否则上报冲突 `MULTIPLE_IMPLEMENT`（多个默认实现冲突），返回 false 终止构建。

## 7. 文件尾（L143–L145）
- **L143**：结束命名空间。
- **L145**：结束 include guard。

## 8. 与基础流程的拼装点（读者路线）

要理解本文件的实际效果，需要把它放回 `VTableBuilderBase::AddClassMethods/AddDefaultInterfaceMethods` 的调用链：
- `AddBaseMethods` 把 baseClass vtable 放入 `vtable_.Methods()`（每个条目 `isBase_=true`）。
- `AddClassMethods` 对每个本类虚方法调用 `ProcessClassMethod`：
  - 覆盖 base → 设置 candidate（不增加 vtable 大小）
  - 新增方法 → `AddEntry` 扩展 vtable
- `AddDefaultInterfaceMethods` 对每个 default 方法调用 `ProcessDefaultMethod`：
  - 无冲突 → `AddCopiedEntry`
  - 冲突 → `OnVTableConflict(MULTIPLE_IMPLEMENT)` 并终止


