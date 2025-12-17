# `runtime/include/class-inl.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：`Class` 的内联实现（模板/性能关键路径/布局计算/派发解析）  
> 与 `class.h` 的关系：`class.h` 定义契约与字段布局；本文件给出大量 **inline/constexpr** 实现（查找、派发、布局计算、字段访问）。

## 1. 文件定位（本文件“真正做了什么”）

本文件把 `Class` 上最性能敏感的逻辑放在 header 内联实现里，主要包括：

- **类型与布局**：`GetTypeSize`、`GetComponentSize`、`ComputeClassSize`、`GetVTableOffset`、`GetIMTOffset`。
- **类型关系**：`IsSubClassOf`、`IsAssignableFrom`（含 union 语义）、`Implements`。
- **字段与方法查找**：二分搜索 + 可变谓词过滤、沿继承链查找、接口方法查找（itable）。
- **派发解析**：`ResolveVirtualMethod`（vtable / IMT / ITable）。
- **字段访问**：通过 `ObjectAccessor` 做 primitive/object 的读写与原子 RMW（含 read/write barrier / memory_order）。

> 交叉引用：  
> - `ObjectAccessor` 与屏障/GC：`runtime/include/object_accessor-inl.h`（跨章依赖 Stage2/02）。  
> - `ITable` 的结构：`runtime/include/itable.h`（03 章动态纳入）。  
> - vtable/itable 的构建：`runtime/include/vtable_builder_*`（03 章 P0）。

## 2. 头部与依赖（L1–L26）

- **L1–L14**：License 头。
- **L15–L16**：include guard：`PANDA_RUNTIME_CLASS_INL_H_`。
- **L18**：包含 `class.h`，获取 `Class` 的声明与字段布局契约。
- **L19**：`class_helper.h`：提供 `OBJECT_POINTER_SIZE/POINTER_SIZE` 等与 ABI/平台相关的常量与辅助。
- **L20**：`field.h`：字段元数据在查找与访问时使用。
- **L21**：`object_header.h`：类对象（managed object）映射、对象大小等（跨章：对象头/GC）。
- **L22**：`coretypes/tagged_value.h`：TAGGED 类型大小与对齐假设（ComputeClassSize 用到）。
- **L23**：`object_accessor-inl.h`：字段读写、屏障、原子操作的实际执行者（跨章实现）。
- **L25–L26**：`namespace ark {` 开始。

## 3. 查找基础设施：比较器 + 谓词组合 + 二分搜索（L27–L83）

### 3.1 `NameComp`（L27–L38）
- **L27**：模板 `NameComp<Item>`：按 name 排序/相等比较。
- **L30–L33**：`equal(Item&, StringData)`：判断 `GetName()` 相等（用于 lower_bound 后的“同 key 线性扫描”）。
- **L34–L37**：`operator()(Method&, StringData)`：用于 `lower_bound` 的严格弱序比较（`<`）。

### 3.2 `EntityIdComp`（L40–L51）
- **L40**：模板 `EntityIdComp<Item>`：按 `EntityId offset` 排序/相等比较。
- **L43–L46**：`equal`：比较 `GetFileId().GetOffset()` 与 `id.GetOffset()`。
- **L47–L50**：`operator()`：按 offset 做 `<`。

### 3.3 类型别名（L53–L55）
- **L53**：`MethodNameComp`：`NameComp<Method>`。
- **L54**：`MethodIdComp`：`EntityIdComp<Method>`。

### 3.4 `PredComp`（L56–L66）
- **L56–L60**：`PredComp(item)` 基例：没有额外谓词时恒真。
- **L62–L66**：可变参递归：所有谓词都必须满足（短路 AND）。

### 3.5 `BinSearch`（L68–L83）
这是整个“按 key 二分 + 同 key 多重匹配”的核心模板：
- **L69–L71**：对 `Span<Item>` 做 `lower_bound`，定位到第一个不小于 key 的位置。
- **L72–L81**：从该位置向后线性扫描：
  - **L74–L76**：一旦 key 不再相等就退出（因为同 key 连续）。
  - **L77–L79**：若谓词全通过则返回 item 地址。
- **L82**：找不到返回 `nullptr`。

## 4. 类型大小与数组元素大小（L85–L120）

### 4.1 `Class::GetTypeSize`（L85–L111）
- **L86**：inline 实现（perf critical）。
- **L88–L110**：按 `TypeId` switch：
  - U1/I8/U8 → 1 字节
  - I16/U16 → 2 字节
  - I32/U32/F32 → 4 字节
  - I64/U64/F64 → 8 字节
  - TAGGED → `TaggedValue::TaggedTypeSize()`（要求为 8，见后面 static_assert）
  - REFERENCE → `ClassHelper::OBJECT_POINTER_SIZE`（与压缩指针相关）
  - default → `UNREACHABLE()`（类型 id 不应出现）

### 4.2 `Class::GetComponentSize`（L113–L120）
- **L115–L117**：非数组类 `componentType_ == nullptr` → 0。
- **L119**：数组类返回 componentType 的 `GetType()` 对应 size。

## 5. 类型关系（继承/赋值兼容/union）（L122–L237）

### 5.1 `IsClassClass`（L122–L125）
- **L124**：通过 `GetManagedObject()->ClassAddr<Class>() == this` 判断：managed 侧 ClassObject 的“类地址”是否指回当前 `Class*`。

### 5.2 `IsSubClassOf`（L127–L140）
- **L129–L137**：从 `this` 沿 `GetBase()` 线性上溯，遇到目标 `klass` 返回 true。
- **L139**：走到顶仍未命中 → false。

### 5.3 Assignable：union/ref 的拆分（L142–L237）
这部分是 CheckCast/IsInstance/类型检查快路径的“基础语义”。

- **L142–L145**：前置声明：`IsAssignableFromUnion`、`IsAssignableFromRef`（模板参数控制是否允许 super 链遍历）。
- **L146–L174**：`IsAssignableFromUnionImpl<IS_STRICT, IS_UNION_SUPER>`：
  - **L151–L156**：内部 `isAssignable` lambda：如果两侧任意一侧为 union → 递归 union 语义，否则走 `IsAssignableFromRef<true>`（完整语义）。
  - **L157–L173**：遍历 union constituent types：
    - `IS_UNION_SUPER` 为 true：检查 “consClass 是否能赋值给 ref”（super=consClass）
    - 否则：检查 “ref 是否能赋值给 consClass”（super=ref）
    - `IS_STRICT` 为 true：任一不满足则立刻 false；否则 OR 聚合。
- **L177–L193**：`IsAssignableFromUnion(sub, super)`：
  - super 非 union：转为 `IsAssignableFromUnionImpl<true,false>(super, sub)`（严格）。
  - sub 非 union：转为 `IsAssignableFromUnionImpl<false,true>(sub, super)`（非严格）。
  - 双方都是 union：遍历 sub 的 constituent，任一能严格赋值到 super 则 true；否则仍返回 true（该分支的最终语义需要结合上层使用点复核）。
- **L195–L216**：`IsAssignableFromRef<ALLOW_SUPER_TRAVERSAL>`：
  - 相同指针 → true。
  - super 是 Object 根类 → sub 只要不是 primitive 即可。
  - super 是 interface → sub->Implements(super)。
  - sub 是 array → 要求 super 也是 array 且 component 可赋值。
  - 否则：
    - `ALLOW_SUPER_TRAVERSAL=true`：要求 sub 非 interface 且沿父类链是子类。
    - `ALLOW_SUPER_TRAVERSAL=false`：直接 false（用于 `IsAssignableFromRefNoSuper` 的慢路径契约）。
- **L219–L228**：`Class::IsAssignableFrom(klass)`：
  - 快速等价判断
  - union 任一侧为 union → union 语义
  - 否则 ref 完整语义（允许 super traversal）
- **L230–L237**：`IsAssignableFromRefNoSuper`：
  - union：仍走完整 union（注释说明 correctness）
  - 否则 ref 语义禁用 super traversal（配合 entrypoint fast path 的“已遍历父类链”前置条件）。

## 6. 接口实现与 itable（L239–L248）
- **L241–L245**：遍历 `itable_.Get()` 的每个 entry，比较 `GetInterface()` 是否等于目标接口。
- **L247**：未命中返回 false。

## 7. 字段查找（L250–L348，及后续按 name 封装）

### 7.1 `GetFields<FILTER>`（L250–L263）
- STATIC → `GetStaticFields()`；INSTANCE → `GetInstanceFields()`；ALL → `GetFields()`；否则 unreachable。

### 7.2 `FindDeclaredField(Pred)`（L265–L274）
- 对选定字段 span 做 `find_if`，命中返回地址，否则 nullptr。

### 7.3 `BinarySearchField`（L276–L284）
- 对按 `FieldId` 排序的 span 做 `lower_bound`，并额外检查相等。

### 7.4 `FindDeclaredField(EntityId)`（L286–L310）
- FILTER=ALL：先在 staticFields 二分，再在 instanceFields 二分。
- 否则：只在对应字段集合二分。
- 找不到 → nullptr。

### 7.5 `FindFieldInInterfaces / FindField`（L312–L348）
- **FindFieldInInterfaces**：沿 `kls` 的继承链，枚举每个类的 interfaces，对每个 iface 递归 `iface->FindField`。
- **FindField**：先沿 superclass 链做 declared 查找；若未命中且 FILTER 是 STATIC/ALL，才去 interfaces 查（符合“实例字段不从接口继承”的语义）。

## 8. 方法集合与方法查找（L350–L456，及后续 wrapper）

### 8.1 `GetMethods<FILTER>`（L350–L366）
- STATIC → `GetStaticMethods()`；INSTANCE → `GetVirtualMethods()`；ALL → `GetMethods()`；COPIED → `GetCopiedMethods()`。

### 8.2 `FindDirectMethod`（L368–L403）
- FILTER=ALL/STATIC：先在 static methods 上用 `BinSearch`。
- FILTER=ALL/INSTANCE：再在 virtual methods 上用 `BinSearch`。
- FILTER=COPIED：copied methods “来自默认接口方法且无序”，因此退化为线性扫描并做 key+pred 检查。

### 8.3 `FindClassMethod`（L405–L423）
- 沿 `GetBase()` 上溯，每层对 `FindDirectMethod` 查找。
- 若 FILTER=ALL/INSTANCE：额外查 copied methods（把默认接口方法也纳入“类方法”的可见集合）。

### 8.4 `FindInterfaceMethod`（L425–L456）
- 静态断言：接口不应该有 copied methods。
- 若 `this` 本身是 interface：
  - 先在自身 direct methods 中找（FILTER 指定 static/instance/all）。
- 若 FILTER=STATIC：直接返回 nullptr（“从 itable 解析接口静态方法”语义上不成立）。
- 否则遍历 `itable_`：
  - 对每个 entry 的 interface，查其 instance direct methods。
- 若 `this` 是 interface：最后回退到 `GetBase()` 里查 public 的 instance 方法（注意谓词：强制 `method.IsPublic()`）。

## 9. 由声明到便捷 API 的封装（约 L458–L706，分布在文件中段）

这一段主要把 `class.h` 里声明的 `Get*ByName/Get*ById` 等封装为对 `Find*` 的调用：
- Field：把 `mutf8Name` 转 `StringData`，再 `Find*Field`。
- Method：按 `FindFilter`（STATIC/INSTANCE/ALL）+ `KeyComp`（Name/EntityId）+ `Proto` 谓词组合查找。

（这一段代码行数很多但语义重复：**构造 key + 调 Find* + 返回指针**。逐行笔记时会按“函数块”覆盖。）

## 10. 派发解析：`ResolveVirtualMethod`（L708–L748）

关键语义：在非接口类上，解析一个 `Method*`（可能来自接口）在当前类的实际派发目标。

- **L713**：断言当前类不是 interface。
- **L715–L739**：当被解析的 method 属于 interface 且不是默认接口方法：
  - 先尝试 IMT（若 imtSize != 0）：`GetIMTableIndex(methodIdOffset)` 取槽；非空则直接返回。
  - 否则扫描 itable：匹配 entry.GetInterface()，再按 `method->GetVTableIndex()` 从 entry.GetMethods() 取目标。
- **L739–L745**：否则走 vtable：用 `method->GetVTableIndex()` 直接索引 vtable。
- 返回 resolved（可能为 nullptr，取决于 itable 是否命中）。

> 交叉引用：`GetIMTableIndex/IMT 冲突解决/默认方法 copied` 的构建逻辑在 vtable builder（03 章 P0）。

## 11. Class 对象尾部布局：ComputeClassSize/VTableOffset/IMTOffset（L750–L824）

### 11.1 `ComputeClassSize`（L750–L796）
这是 `class.h::ComputeClassSize` 的 constexpr 实现，定义了 `Class` 对象的“尾部扩展区”布局与对齐策略：

- 从 `sizeof(Class)` 开始，先按 `OBJECT_POINTER_SIZE` 对齐。
- 累加：
  - vtable（`vtableSize * POINTER_SIZE`）
  - imt（`imtSize * POINTER_SIZE`）
  - 静态引用字段（`numRefSfields * OBJECT_POINTER_SIZE`）
- 然后尝试用较小尺寸字段填充对齐空洞（Pad 逻辑）：
  - 先处理 64-bit 对齐空洞：优先扣掉 32/16/8 的字段计数
  - 再处理 32-bit、16-bit 的对齐空洞
- 最后把剩余各尺寸静态字段与 tagged 字段的 payload size 加上。

这段逻辑决定：
- `GetVTableOffset()` 的值（即“扩展区起点”）
- `GetStaticFieldsOffset()` 的值（在 vtable/imt 之后）
- GC/反射/类对象布局与 offset 的一致性

### 11.2 `Pad`（L798–L804）
在 padding 空洞足够大且还有字段可用时，减少 padding 与字段数（“用字段填洞”）。

### 11.3 `GetVTableOffset`（L806–L809）
- 直接返回 `ComputeClassSize(0,0,0,...)`：即只有 `sizeof(Class)` + 对齐后的起点。

### 11.4 `GetVTable()/GetIMTOffset`（L811–L824）
- `GetVTable()`：在 `GetClassSpan()` 上从 `GetVTableOffset()` 起取 `vtableSize_` 个 `Method*`。
- `GetIMTOffset()`：紧跟 vtable：`GetVTableOffset() + vtableSize_ * sizeof(uintptr_t)`。

## 12. 字段访问：把 `Class*` 映射到 managed object 并调用 ObjectAccessor（L826–L1023）

这里实现了 `class.h` 声明的各种 `Get/Set/CAS/RMW`：

- primitive：直接 `ObjectAccessor::Get/SetFieldPrimitive`。
- object：关键点在于 **Class 的字段实际上存储在 managed ClassObject 里**：
  - **L856–L860** 等处：先取 `auto object = GetManagedObject()`，断言 `object < this < object+ObjectSize()`（保证 `this` 指针位于 managed object 的地址范围内）。
  - 把 `Class*` 的 offset 转成 “相对 managed object 的 offset”：`offset + (this - object)`。
  - 再对 managed object 进行真正的读写/屏障/原子操作。

并且：
- 对 volatile 字段会选择 `ObjectAccessor::SetObject<true,...>` 分支。
- 对 class state 做断言：`IsInitializing/IsInitialized/IsErroneous`（注释说明 GC 可能跳过 Erroneous classes；避免昂贵的原子化 state+field 检查）。

> 跨章跳转：`ObjectAccessor` 的 read/write barrier、原子语义、对象模型细节在 Stage2/02（Memory）逐行解释。

## 13. 文件尾（L1025–L1028）
- **L1025**：结束命名空间。
- **L1027–L1028**：结束 include guard。

## 14. 动态纳入候选（同章强相关）

由本文件 `#include` 与语义耦合可判定为 03 章强相关（将追加到 `03_ClassLoading/Manifests/files.yaml`）：
- `runtime/include/class_helper.h`（布局/对齐常量）
- `runtime/include/field.h`、`runtime/include/method.h`、`runtime/include/itable.h`

跨章但强依赖（本章只做依赖说明与跳转，不重复逐行）：
- `runtime/include/object_header.h`
- `runtime/include/object_accessor-inl.h`


