# `runtime/include/vtable_builder_base-inl.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：vtable 构建“骨架流程”的 inline 实现（对应 `vtable_builder_base.h` 的声明）。  
> 关键点：这里定义了 **Build 顺序** 与 **copied default methods 的枚举策略（倒序遍历 itable）**。

## 1. 文件定位（它实现了什么）

`VTableBuilderBase<VISIT_SUPERITABLE>` 的核心流程都在这里：

- 接口类：只统计 vmethods 数量，并标记是否存在 default 方法（`hasDefaultMethods_`）。
- 普通类：按顺序执行：
  1) 从 baseClass 的 vtable 注入 base entries（可被覆盖）  
  2) 枚举本类 non-static 方法并交给策略钩子 `ProcessClassMethod`  
  3) 从 itable 中枚举接口 default 方法并交给策略钩子 `ProcessDefaultMethod`，生成 copied methods 列表  
  4) `UpdateClass` 写回 flags 与 vtable_index，并由 `VTableInfo::UpdateClass` 写回最终表

## 2. 头部（L1–L20）

- **L15–L16**：include guard：`PANDA_RUNTIME_VTABLE_BUILDER_BASE_INL_H`。
- **L18**：包含 `vtable_builder_base.h` 获取 `VTableInfo/MethodInfo/VTableBuilderBase` 声明。
- **L20**：`namespace ark {`。

## 3. 冲突上报接口声明（L22–L27）

这里仅声明 `OnVTableConflict` 两个重载（实现应在 `.cpp` 中）：
- **L22–L23**：冲突对象为 `MethodInfo*`（构建中间表示）。
- **L25–L26**：冲突对象为 `Method*`（运行时方法对象）。

构建策略（variance 等）发现冲突后会调用它，并通过 `ClassLinkerErrorHandler` 抛给上层。

## 4. `VTableInfo` 的操作实现（L28–L48）

### 4.1 `AddEntry`（L28–L32）
- 插入 `{info -> MethodEntry(index)}`，index 取当前 `vmethods_.size()`（插入前的 size）。
- `ASSERT(res.second)`：保证不存在重复 key（key 是 `MethodInfo*` 地址）。

### 4.2 `AddCopiedEntry`（L34–L39）
- 在 `copiedMethods_` 中插入 `{info -> CopiedMethodEntry(index)}`，index 取当前 `copiedMethods_.size()`。
- 返回 entry 的引用，便于外层继续设置 status。

### 4.3 `UpdateCopiedEntry`（L41–L48）
- 用 repl 替换 orig 的 key，但保留 entry 的 index/status：
  - 先 find orig
  - copy 出旧 entry
  - erase orig
  - emplace_hint(repl, entry)

> 这个操作是“冲突消解/覆盖替换”的基础设施：策略可以把某个 copied method 的代表从 orig 换成 repl，但保持稳定序号不变。

## 5. 接口类的 fast-path：`BuildForInterface`（L50–L81）

### 5.1 从 panda_file 构建（L50–L65）
- **L53**：断言确实是接口。
- **L54–L64**：枚举方法：
  - static 方法跳过（接口静态方法不进入 vtable/itable 派发集合）
  - 若非 abstract → `hasDefaultMethods_=true`（接口存在 default 方法）
  - `++numVmethods_`：统计接口“虚方法槽位数”

### 5.2 从 `Span<Method>` 构建（L67–L81）
- 逻辑与上面一致，只是来源换成 runtime Method 数组。

> 注意：接口 fast-path 没有构建 `VTableInfo` 映射（不需要 base 覆盖/默认方法 copied 处理）；真正派发结构由类实现侧在 itable/IMT/vtable 上承载。

## 6. 注入 base vtable：`AddBaseMethods`（L83–L94）

- **L86–L88**：用 arena 分配 `ArenaForwardList<MethodInfo>` 保存 base 方法的 `MethodInfo` 对象（保证地址稳定，供 map key 使用）。
- **L89–L93**：若 baseClass 非空：
  - 遍历 `baseClass->GetVTable()`（这是最终 vtable 里的 `Method*` 指针数组）
  - 对每个 method 构造 `MethodInfo(method, 0, true)`（`isBase_=true`）
  - 立刻 `vtable_.AddEntry(&emplace_front(...))`

> 关键语义：base 方法先进入 vtable_，后续本类方法通过策略钩子只能覆盖 `IsBase()` 的条目（variance 策略如此）。

## 7. 枚举本类方法：`AddClassMethods`（L96–L135）

### 7.1 从 panda_file 构建（L97–L115）
- 分配 `classMethods` forward_list。
- `EnumerateMethods`：
  - 只收集 non-static 方法
  - `MethodInfo(mda, numVmethods_++, ctx)`：
    - `numVmethods_++` 作为 vmethodIndex（注意：这是“本类虚方法序号”，用于后续设置 `Method::vtable_index`）
- 第二遍遍历 `classMethods`：
  - 对每个 `info` 调用 `ProcessClassMethod(&info)`
  - 任一失败 → false（冲突/不合法覆盖等）

### 7.2 从 runtime methods 构建（L118–L135）
- 同样收集 non-static methods，构造 `MethodInfo(&method, numVmethods_++)`。
- 再调用 `ProcessClassMethod`。

> 注意：使用 forward_list 的原因通常是“构造时地址稳定 + 便于 arena 分配 + 迭代顺序不敏感”（策略主要按 name bucket 匹配而不是按声明顺序）。

## 8. 默认接口方法：`AddDefaultInterfaceMethods`（L137–L174）

这是理解 copied methods 的关键：

### 8.1 遍历范围裁剪：`VISIT_SUPERITABLE`（L143–L145）
- `traverseUpTo = VISIT_SUPERITABLE ? 0 : superItableSize`
  - 当 `VISIT_SUPERITABLE=false`（variance builder 继承的是 `VTableBuilderBase<false>`）：只遍历 **子类新增的 itable 区间**（不回溯到 super 的 itable 部分）。
  - 当 `VISIT_SUPERITABLE=true`：遍历整个 itable（包括 super）。

### 8.2 倒序遍历 itable（L146–L163）
- `for (size_t i = itable.Size(); i != traverseUpTo;) { i--; ... }`
  - 倒序遍历意味着：**后加入的接口（通常更接近子类）优先**，有利于覆盖/冲突消解（具体策略在 `ProcessDefaultMethod`）。
- 对每个 interface：
  - 若 `!iface->HasDefaultMethods()` → 跳过（避免扫描大量无 default 的接口）
  - 枚举 `iface->GetVirtualMethods()`：
    - 跳过 abstract
    - 为每个 default 方法构造 `MethodInfo(&method)`（注意：此处来源是 runtime Method*）
    - 调用 `ProcessDefaultMethod(itable, i, info)`：
      - 返回 false：表示冲突不可恢复，构建失败

### 8.3 生成稳定有序的 `orderedCopiedMethods_`（L165–L173）
- `orderedCopiedMethods_.resize(vtable_.CopiedMethods().size())`
- 遍历 `vtable_.CopiedMethods()`（unordered map）：
  - 把 `{Method*, Status}` 转成 `CopiedMethod` 对象
  - 按 `entry.GetIndex()` 放到数组中：`orderedCopiedMethods_[index] = copied`

> 关键点：copiedMethods_ 是 unordered_map，但 index 由插入时的 size 决定，因此最终通过 index 恢复了稳定顺序。

## 9. `Build` 主流程（L176–L212）

### 9.1 panda_file 版本（L176–L193）
- 若 `cda->IsInterface()`：走 interface fast-path，返回 true。
- 否则：
  - `AddBaseMethods(baseClass)`
  - `AddClassMethods(cda, ctx)`（失败则返回 false）
  - `AddDefaultInterfaceMethods(itable, baseClass ? baseClass->GetITable().Size() : 0)`（失败则返回 false）
  - 成功返回 true

### 9.2 runtime methods 版本（L195–L212）
- `isInterface` 时同样走 interface fast-path。
- 否则顺序同上，只是 `AddClassMethods` 的输入换成 `Span<Method> methods`。

## 10. `UpdateClass` 写回（L214–L229）

- 如果 `klass->IsInterface()`：
  - `hasDefaultMethods_` 为 true 时设置 `klass->SetHasDefaultMethods()`（影响后续 itable default 遍历剪枝）。
  - 给接口的每个 virtual method 写 `method.SetVTableIndex(idx++)`（接口方法也需要 vtable_index 作为“接口方法序号”，供 itable 派发 `entry.GetMethods()[vtableIndex]` 使用）。
- 无论是否接口：
  - `vtable_.UpdateClass(klass)`：把 vtable/candidates/copied 写回 class（实现不在本文件，需在后续动态纳入里追踪）。


