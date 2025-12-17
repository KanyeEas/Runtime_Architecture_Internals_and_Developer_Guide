# `plugins/ets/runtime/ani/ani_interaction_api.cpp`（逐行精读｜interaction API 实现中心）

> 章节归属：Stage2 / 05_NativeBridge  
> 文件规模：6719 行  
> 本文件角色：实现 ANI 的 `__ani_interaction_api` 函数指针表（`INTERACTION_API`），覆盖：
> - method/function 调用（含 varargs 与 `ani_value[]` 两种入参）
> - class/module/namespace 查找与解析
> - object/field/array/tuple/any 等基础操作
> - native bind（把 C 函数绑定到 ETS 方法/函数）
> - error/pending exception 处理与 scope/reference 管理
>
> 结构上，它把大量 API 聚合到一个静态表：
> - `const __ani_interaction_api INTERACTION_API = { ... }`（L6305 左右）
> - `GetInteractionAPI()` 返回 `&INTERACTION_API`（L6709–L6712）

## 0. 顶层依赖：为什么这里会包含 class linker、handle scope、stubs、coroutine scopes（L23–L45）

- **L33**：`ets_class_linker_extension.h`：FindClass/InitializeClass 需要类加载器扩展能力（语言相关）。
- **L34**：`ets_handle_scope.h`：local ref / handle scope 与 GC root 管理。
- **L36–L37**：`ets_stubs(.inl)`：某些 Any/Interop 相关调用可能走 stubs（高性能桥/内建）。
- **L44**：`runtime/coroutines/coroutine_scopes.h`：`ScopedCoroutineNativeCall` 在 method 调用时标记“native call 区间”，用于 GC/safepoint/调度约束。

> 结论：ANI interaction API 并不是简单的 “参数解包 + 调用方法”，它必须严谨处理：
> - 线程/coroutine 状态切换（native ↔ managed）
> - handle scope / local ref 生命周期
> - 类初始化与异常传播

## 1. 环境校验宏：`CHECK_ENV` 的语义是“先拒绝 pending exception”（L49–L63）

- `CHECK_ENV_THAT_CAN_HAVE_PENDING_ERROR(env)`：只做 env!=nullptr 检查。
- `CHECK_ENV(env)`：除 env 非空外，还检查：
  - `PandaEnv::FromAniEnv(env)->HasPendingException()`
  - 若 true 则返回 `ANI_PENDING_ERROR`

> 这给出一个重要 ABI 约束：**多数 ANI API 在存在 pending exception 时会直接拒绝执行**。  
> 这与 JNI 的“异常待处理时多数 API 仍可查询但不应继续调用”的规则类似，但这里用明确的返回码强制执行。

## 2. “进入 managed”统一门面：`ScopedManagedCodeFix` + `ScopedCoroutineNativeCall`（贯穿全文件）

在高频入口处都能看到两个 RAII：

- `ScopedManagedCodeFix s(env)`：把 `ani_env*` 映射到 `PandaEnv`/`EtsCoroutine` 并建立可在本作用域安全操作 VM 的条件；同时提供：
  - `ToInternalType(ani_ref/ani_object/ani_class/...)`
  - `AddLocalRef(...) / LocalRef<T>` 等 local reference 操作
  - `HasPendingException()` / `GetThrowable()` / `ClearException()` 等
- `ScopedCoroutineNativeCall c(s.GetCoroutine())`：用于触发 coroutine manager 的 native call 事件（L246–L247）

> 实战阅读技巧：在每个 API 的函数体里，先找这两行，就能快速定位“跨边界点”。

## 3. 类初始化：`InitializeClass` 是所有静态调用/静态字段访问的共同前置（L117–L136）

核心规则：

- 若 `klass->IsInitialized()` → OK
- 否则通过 `EtsClassLinker::InitializeClass(coroutine, klass)` 初始化
- 初始化失败：
  - 若 coroutine 有 pending exception → `ANI_PENDING_ERROR`
  - 否则 `ANI_ERROR`

> 该逻辑会在：
> - 静态方法调用（`DoGeneralMethodCall` 的 `ani_static_method/ani_function` 分支）
> - 静态字段 get/set（`ClassGetStaticField*`）  
> 被统一复用。

## 4. 参数解包：shorty 驱动的 `GetArgValues`（L138–L227）

ANI 提供两种入参形式：

- `.../va_list`：`GetArgValues(s, method, va_list, object)`（L138–L177）
- `ani_value[]`：`GetArgValues(s, method, const ani_value *args, object)`（L208–L227）

共同机制：

- 使用 `panda_file::ShortyIterator` 遍历方法 shorty（L147–L150 / L219–L223）
- 跳过 return type，然后逐个参数转换成 runtime `Value`：
  - `REFERENCE`：取 `ani_ref` 并转成 `EtsObject*` → `ObjectHeader*`
  - `U1/U16`、`I8/I16/I32`、`I64`、`F32/F64`：按 ABI 规则从 varargs/union 里提取并 bit_cast 成 `Value` 的存储形式
- 若 `object != nullptr`（实例方法）：把 `this` 的 coretype 作为第一个参数（L143–L145 / L216–L218）

> 这解释了为什么很多调用入口只需要传 `method + args`：最终统一成 `Value[]` 喂给 `EtsMethod::Invoke`。

## 5. 调用骨架：`DoGeneralMethodCall` / `GeneralMethodCall` / `GeneralFunctionCall`（L240–L291）

### 5.1 虚方法解析（L229–L238）

- 对 `ani_method`（实例方法）调用先 `ResolveVirtualMethod`：
  - 若 method 是 static → FATAL（非法 ANI 用法）
  - 否则通过对象 class 的 vtable resolve 得到真实 `EtsMethod*`

### 5.2 统一 invoke（L240–L276）

- RAII：`ScopedCoroutineNativeCall`
- 选择 `EtsMethod* m`：
  - `ani_method`：virtual resolve
  - `ani_static_method` / `ani_function`：`ToInternalMethod` + `InitializeClass`
- `values = GetArgValues(...)`
- `m->Invoke(s, values.data(), &res)`：把调用委托给 `EtsMethod`（语言/解释器/编译器路径都可能在这里分流）
- 把 `EtsValue` 转回对应 ANI 返回类型

> 这是整份文件最核心的“骨架”：后面的 `Object_CallMethod_*`、`Class_CallMethod_*`、`Function_Call_*` 等大量 API 只是“把不同签名映射到这个骨架”。

## 6. 字段访问：类型校验 +（静态字段）类初始化（L293–L406）

代表性模式：

- `GetPrimitiveTypeField/SetPrimitiveTypeField`：
  - `CHECK_ENV` + ptr 校验
  - `EtsField*` → 校验 `GetEtsType() == expected`（`AniTypeInfo<T>::ETS_TYPE_VALUE`）
  - `ScopedManagedCodeFix` 后读取/写入 object 的 primitive field
- `ClassGetStaticField/ClassSetStaticField`：
  - 先 `InitializeClass(s, etsField->GetDeclaringClass())`
  - 再读写静态字段
- `ClassGetStaticFieldByName/ClassSetStaticFieldByName`：
  - 通过 `GetStaticFieldIDByName(name, nullptr)` 查字段
  - `ANI_NOT_FOUND` / `ANI_INVALID_TYPE` / `InitializeClass` 失败等均映射为明确返回码

## 7. FindClass/FindModule/FindNamespace：把 ClassNotFoundError 翻译成 `ANI_NOT_FOUND`（L408–L441 等）

`DoFind` 的关键点（L410–L433）：

- 通过 `classLinker->GetClass(descriptor, true, GetClassLinkerContext(...))`
- 若 `pandaEnv->HasPendingException()`：
  - 若异常类型是 `LINKER_CLASS_NOT_FOUND_ERROR`：
    - 清除异常并返回 `ANI_NOT_FOUND`
  - 其他异常：返回 `ANI_PENDING_ERROR`
- 校验 `klass->IsModule()` 与模板参数 `IS_MODULE` 一致，否则 `ANI_NOT_FOUND`
- 成功则 `s.AddLocalRef(reinterpret_cast<EtsObject*>(klass), result)`

> 这里是“native ↔ class loading”交界面：  
> ANI 把某些 linker 异常降级为“没找到”，而不是把异常透传到 native 调用方。

## 8. 通过 name/signature 查方法：mangle + overload disambiguation（L443–L573）

核心逻辑在 `DoGetClassMethodUnderManagedScope`：

- 若 `signature==nullptr`，但同名方法不唯一 → `ANI_AMBIGUOUS`（临时规则，注释说明未来移除）
- 若 `signature!=nullptr`：`Mangle::ConvertSignatureToProto` 解析签名，失败则 `ANI_INVALID_DESCRIPTOR`
- 先尝试 `GetStaticMethod/GetInstanceMethod`；否则再走 overload 列表
- overload 为 0 → `ANI_NOT_FOUND`；>1 → `ANI_AMBIGUOUS`

随后各类 `ObjectCallMethodByName/ClassCallMethodByName`：

- 做 env/ptr 校验
- 找到 `EtsMethod*` 后先 `Check(ReturnType)`（return type mismatch 直接 FATAL）
- 最终回到 `DoGeneralMethodCall`

## 9. 对象创建：`AllocObject` + `DoNewObject`（L595–L627）

### 9.1 `AllocObject`（L595–L608）

- 禁止创建：
  - abstract / interface
  - string class / array class（注释提到未来可能允许，关联 issue #22280）
- `EtsObject::Create(coro, klass)`：分配对象
- 通过 `s.AddLocalRef(obj, result)` 返回 ani_object（local ref）

### 9.2 `DoNewObject`（L610–L627）

- 先 `AllocObject` 获取 local ref `object`
- `InitializeClass(s, klass)`
- 调用构造方法：`DoGeneralMethodCall`（返回值用任意 primitive 类型占位，忽略）
- `*result = object.Release()`：把 local ref 交给调用方（遵循 ANI 的 reference 语义）

## 10. Any/动态调用族：HandleScope + VMHandle + `EtsCall*`（例：L6204–L6302）

`Any_Call/Any_CallMethod/Any_New` 体现了 dynamic interop 的调用形态：

- `HandleScope<ObjectHeader*> scope(coroutine)`：确保临时对象作为 GC root
- 把 `ani_ref* argv` 转为 `VMHandle<ObjectHeader>` 数组
- 调用 `EtsCall/EtsCallThis/EtsCallNew`
- 若有 pending exception → `ANI_PENDING_ERROR`；否则 `AddLocalRef(res, result)`

> 这部分是 “native 对动态值/函数对象” 的调用路径，与 04 章的 interpreter stubs/entrypoints 在理念上类似：要明确 GC root 与异常传播。

## 11. `INTERACTION_API` 静态表：全部 API 的最终落点（L6305–L6706）

- **L6305**：`const __ani_interaction_api INTERACTION_API = { ... }`
- 表内按外部 ABI 约定的顺序列出大量函数指针（含 New/Object/Type/Find/Array/Ref/Error/Any/Promise 等）。
- **L6709–L6712**：`GetInteractionAPI()` 返回 `&INTERACTION_API`
- **L6714–L6717**：`IsVersionSupported(version)`：当前仅支持 `ANI_VERSION_1`

> 这里与 `ets_napi_env.cpp` 完全对上：`ani_env {ani::GetInteractionAPI()}` 实际就是把 env 的 `c_api` 指向这张表。

## 12. 阅读/排障指引（建议）

面对 6k+ 行大文件，建议以“骨架函数”为索引快速定位：

- **调用**：`DoGeneralMethodCall`、`GetArgValues`、`ResolveVirtualMethod`
- **类初始化**：`InitializeClass`
- **查找**：`DoFind`（把 ClassNotFoundError → ANI_NOT_FOUND）
- **new**：`AllocObject`、`DoNewObject`
- **Any**：`Any_Call/Any_CallMethod/Any_New`
- **表**：`INTERACTION_API`（确认某个 ABI slot 对应哪个实现）



