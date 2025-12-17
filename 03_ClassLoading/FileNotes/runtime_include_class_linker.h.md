# `runtime/include/class_linker.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：`ClassLinker` 对外 API + 内部类加载/链接/初始化管线声明（语言无关容器），并集成 AOT 上下文、boot class filter 等。  
> 关键：这份头文件基本给出了 **ClassLoading 的“全链路函数分解图”**，实现主要在 `runtime/class_linker.cpp`。

## 1. 文件定位（ClassLinker 在 Runtime 中的角色）

文件注释（L50–L53）明确：
- `ClassLinker` 是线程安全、语言无关的“类操作容器”；
- 实例由 `Runtime` 持有，等价于单例；
- 通过 `extensions_`（按语言数组索引）把“语言相关策略”委托给 `ClassLinkerExtension`。

在 Stage2/03 的结构上：
- `Class`/`Method`/`Field` 定义元数据契约；
- `vtable/itable/imtable builder` 负责派发表结构构建；
- `ClassLinkerContext` 负责“上下文隔离 + 缓存 + 并发协调 + roots”；
- `ClassLinker` 把这些拼装成一个可并发执行的加载/链接/初始化管线。

## 2. 头部与依赖（L1–L48）

- **L15–L16**：include guard：`PANDA_RUNTIME_CLASS_LINKER_H_`。
- **L24**：`compiler/aot/aot_manager.h`：AOT 管理器集成到 ClassLinker（`.an` 文件加载与 class context）。
- **L25–L27**：Arena allocator、mutex、BloomFilter：用于内部数据结构与 boot class filter。
- **L29–L31**：panda_file accessor：`ClassDataAccessor`、`File`、`EntityId`。
- **L32**：`class_linker_context.h`：上下文。
- **L33–L35, L41**：`class.h/field.h/method.h`：元数据对象。
- **L35–L36**：`itable_builder.h/imtable_builder.h`：派发表构建器（与 vtable builder 同层）。
- **L37**：`language_context.h`：语言枚举与索引映射（`GetLangArrIndex`）。
- **L38–L40**：panda 容器与字符串。
- **L42**：`vtable_builder_interface.h`：`VTableBuilder` 抽象接口。
- **L46–L47**：`using compiler::AotManager;`：暴露类型别名。
- **L48**：`ClassLinkerErrorHandler` 前向声明（错误上报通道）。

## 3. `ClassLinker::Error`（L56–L67）

统一的错误枚举，覆盖：
- not found（class/field/method）
- no class def / circularity
- override/final、multiple override、multiple implement（直接对应 vtable builder 冲突）
- invalid lambda/overload（语言/字节码约束）

这些错误最终通过 `ClassLinkerErrorHandler::OnError` 上抛（见文件末尾 L448+）。

## 4. 构造/析构/初始化（L69–L76）

- **L69**：构造函数：注入 `InternalAllocator` + 一组 `ClassLinkerExtension`（unique_ptr vector，随后会整理到 `extensions_` 数组）。
- **L71–L72**：析构：需要释放 extensions、copied names、pandaFiles_ 等。
- **L73**：`Initialize(bool compressedStringEnabled=true)`：总体初始化（roots/boot files/filter 等）。
- **L75**：`InitializeRoots(thread)`：初始化 class roots（语言相关 root 集合）。

## 5. 核心入口：GetClass / LoadClass / BuildClass（L77–L106，L303–L306，L373–L378）

### 5.1 GetClass（L77–L85）
三套入口：
- 按 descriptor + context（最常见）
- 按 (pf,id) + context（已知定义文件与 id）
- 按 caller method + id（用于 “相对调用者的 resolve”，context 可从 caller 推导）

### 5.2 LoadClass（L89–L93 / L373–L378）
公开 wrapper（L89–L93）把 `pf+classId` 转成 `descriptor` 并调用私有 `LoadClass(pf*, classId, descriptor, context, ...)`。

私有 overload（L373–L378）与 `LoadClass(ClassDataAccessor*, descriptor, base, interfaces, context, ext, ...)` 共同组成加载管线：
- 解析 base class
- 解析 interfaces
- LoadFields/LoadMethods
- SetupClassInfo（builders + size + numSfields）
- LinkEntitiesAndInitClass（链接并触发初始化）

### 5.3 BuildClass（L303–L306）
这是“从已构造的 methods/fields/interfaces/base 直接构建 Class”的入口（用于合成类、数组/union 类等场景）。

## 6. Method/Field 获取 API（L95–L112）

`GetMethod/GetField` 既提供 “按 (pf,id)” 的入口，也提供 “按 caller method + id” 的入口，内部会走：
- `GetMethod(klass, MethodDataAccessor, handler)`：从具体 class + accessor 构造 Method 元数据
- `GetField(klass, FieldDataAccessor, isStatic, handler)`：构造 Field 元数据

并且私有区还区分：
- `GetFieldById` vs `GetFieldBySignature`（L355–L360），暗示：字段 resolve 可能需要兼容性/签名匹配规则。

## 7. Panda files 注册与枚举（L113–L146，L416–L426）

### 7.1 AddPandaFile（L113–L115）
注册一个 panda_file 到 ClassLinker（可选指定 context）。

### 7.2 EnumeratePandaFiles（L116–L129）
- **L119**：`pandaFilesLock_` 保护 `pandaFiles_`。
- **L121–L123**：`skipIntrinsics` 时跳过 “filename 为空”的 file（典型：内建 intrinsics file）。
- **L125–L127**：cb 返回 false 则停止。

### 7.3 Boot panda files（L131–L146）
boot files 用独立的 `bootPandaFilesLock_` 与 `bootPandaFiles_` 管理。

> 这两套锁与容器解释了：ClassLinker 既维护全量 panda files，又维护 boot subset（用于启动/过滤/快速查找等）。

## 8. AOT 集成（L147–L157，L339–L341，L427）

- **L147–L150**：`GetAotManager()` 直接返回 `aotManager_`。
- **L152–L157**：`GetClassContextForAot(useAbsPath)`：
  - 用 `AotClassContextCollector` 遍历 pandaFiles_，把路径拼成 class context 字符串。
- **L339–L341**：`TryReLinkAotCodeForBoot`：boot 场景下尝试重新链接 AOT code（临时方案 Issue 29288）。
- **L427**：`aotManager_` 为 unique_ptr。

## 9. Extensions：语言分发（L234–L258，L432）

- `HasExtension/GetExtension/ResetExtension`：按 language index 访问 `extensions_`。
- `ObjectToClass`（L260–L267）：
  - 要求 object 是 ClassObject（`IsClassClass()`）
  - 根据 object 的 source lang 选择 extension 并调用 `FromClassObject`。
- `GetClassObjectSize`（L269–L274）：
  - 不能从 cls 读 source lang（注释说明可能未初始化 #12894）
  - 因此通过显式 `lang` 参数选择 extension 计算 class object size。

`extensions_` 字段（L432）：
- `std::array<std::unique_ptr<ClassLinkerExtension>, LANG_COUNT>`：每种语言最多一个 extension，实现“语言无关容器 + 语言相关策略”的分层。

## 10. 加载/链接/布局：ClassInfo 与内部管线（L343–L446）

### 10.1 `ClassInfo`（L344–L350）
这是 class linker 在构建一个类时的临时工作包：
- `vtableBuilder` / `itableBuilder` / `imtableBuilder`：三类派发表 builder
- `size`：类对象 size（通常是 `Class::ComputeClassSize` 的结果 + static field 布局）
- `numSfields`：静态字段数量（用于把 fields span 切分成 static/instance）

### 10.2 `LinkEntitiesAndInitClass`（L352–L353）
把 “字段/方法/表结构/类状态机” 串成最终可用的 `Class`：
- 典型包含：LinkFields/LinkMethods、派发表构建、设置 offsets、可能触发 class init。

### 10.3 Fields/Methods 分段（L388–L406）
函数命名已经把管线拆成几段：
- `LoadFields/LoadMethods`：从 panda_file accessor 读取元数据并创建 `Field/Method` 对象数组
- `LinkFields/LinkMethods`：链接阶段（resolve type、计算 offset、构建派发表、设置 vtableIndex 等）
- `SetupClassInfo`：创建/配置 builders、计算 size/numSfields
- `LayoutFields`：静态函数，计算 offset 并写入 `Field::offset_`（Field 的契约点）

### 10.4 Array/Union 类（L363–L371）
ClassLinker 内置对数组类与 union 类的加载入口（与 `ClassHelper` 的 descriptor/union 工具相呼应）：
- `LoadArrayClass/LoadUnionClass`
- `LoadConstituentClasses`：解析 union constituent types
- `CreateArrayClass/CreateUnionClass`：真正创建合成类对象

## 11. Boot class filter（BloomFilter）（L408–L443）

- `AddBootClassFilter`：把 boot files 的 class descriptor 加入 bloom filter。
- `LookupInFilter`：返回 FilterResult（DISABLED/POSSIBLY_HAS/IMPOSSIBLY_HAS）。
- 常量：
  - `NUM_BOOT_CLASSES = 400000`
  - `FILTER_RATE = 0.01`
- 字段：
  - `bootClassFilter_` + `bootClassFilterLock_`

> 这是一种启动优化：快速判断某 descriptor “不可能在 boot class 中”，从而减少查找成本。

## 12. `ClassLinkerErrorHandler`（L448–L458）

纯虚接口：
- `OnError(error, message)`：由上层实现（Runtime/语言插件/工具）决定如何处理错误。

## 13. 动态纳入结果（本文件引出的同章强相关文件）

本文件直接包含/强耦合的 03 章文件 **已全部纳入逐行**（见 `03_ClassLoading/Manifests/files.yaml`），核心落点如下：
- `runtime/class_linker.cpp`：ClassLinker 主实现（按函数簇分段逐行）
- `runtime/include/class_linker_extension.h` + `runtime/class_linker_extension.cpp`：extension 抽象 + 默认实现（Boot/AppContext/new/created/obsolete）
- `runtime/core/core_class_linker_extension.cpp`：core（PANDA_ASSEMBLY）roots 自举 + CreateClass
- `runtime/include/itable_builder.h`、`runtime/include/imtable_builder.h`、`runtime/imtable_builder.cpp`：接口派发表构建与 IMT 策略
- `runtime/file_manager.*`：`.abc/.an` 文件加载与注册（AddPandaFile 上游）



