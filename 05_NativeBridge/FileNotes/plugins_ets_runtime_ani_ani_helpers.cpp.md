# `plugins/ets/runtime/ani/ani_helpers.cpp`（逐行精读｜entrypoint/参数重排/GC 安全/async）

> 章节归属：Stage2 / 05_NativeBridge  
> 文件规模：487 行  
> 本文件角色：实现 ANI/NAPI 调用桥的“关键粘合层”：
>
> - 提供 `GetANIEntryPoint/GetANICriticalEntryPoint`：返回汇编入口（`EtsNapiEntryPoint/EtsNapiCriticalNativeEntryPoint`）
> - 计算与准备 native 调用参数（`EtsNapiCalcStackArgsSpaceSize`、`PrepareArgsOnStack`）
> - 在进入 native 代码前/后做状态切换与引用帧管理（`EtsNapiBegin/EtsNapiEnd/EtsNapiObjEnd`）
> - 实现 `EtsAsyncCall`：把 async 调用封装成 `EtsPromise` 并通过 `CoroutineManager` 发射
>
> 这部分直接关系到：
> - StackWalker 能否正确遍历 “NAPI frame 的参数区”
> - GC root（ObjectHeader*）在 native 调用期间是否可达
> - local references 生命周期（Push/Pop local frame）

## 0. `ArgWriter`：把 ObjectHeader 指针变成 `EtsReference*`（L47–L79）

- `ArgWriter` 继承 `arch::ArgWriter<RUNTIME_ARCH>`，用于把参数写到 out regs/stack。
- 特化 `Write<ObjectHeader**>`（L55–L67）：
  - 输入是 `EtsObject**`（实参地址），转成 `EtsReference*`：
    - undefined object → `EtsReference::GetUndefined()`
    - 否则 `EtsReferenceStorage::NewEtsStackRef(objPtr)`（把“栈上对象指针地址”包装成 stack ref）
  - 最终写入的是 `EtsReference*`，而不是裸 `ObjectHeader*`。

> 这解释了为什么后续 `PrepareArgsOnStack` 会把 class/this 指针“放到某个稳定的栈槽里”，并创建 stack ref：这是为了 GC/stack walker 一致性。

## 1. entrypoint 符号导出（L82–L95）

- `extern "C" void EtsNapiEntryPoint();` 与 `EtsNapiCriticalNativeEntryPoint();` 来自架构相关汇编文件。
- `GetANIEntryPoint/GetANICriticalEntryPoint` 只是把这两个符号地址转成 `const void*` 返回。

## 2. `EtsNapiCalcStackArgsSpaceSize`：按 shorty 计算 stack 参数空间（L96–L147）

- 使用 `arch::ArgCounter`：
  - 非 critical：额外计入 `ani_env*` 与 `ObjectHeader*`（class 或 this）两个前置参数（L101–L104）
  - 然后遍历 method shorty，按类型计数（U1/U16/I32/I64/F32/F64/REF...）
- 返回 `counter.GetStackSpaceSize()`，供 entrypoint 分配 outStackArgs 空间。

## 3. `PrepareArgsOnStack`：把输入 ABI 重排为 ANI ABI（L255–L314）

输入：
- `inRegsArgs`：callee 的寄存器参数区（包含 Method*、this/class 等）
- `inStackArgs`：callee 的栈参数区

输出：
- `outStackArgs`（以及根据其推导出的 `outRegsArgs`）：
  - 先写 `ani_env*`
  - 再写 “class 或 this”（以 `EtsReference*` 表达）
  - 再拷贝原 method args（通过 `ARCH_COPY_METHOD_ARGS`）

关键细节：

- **L259**：`outRegsArgs = inRegsArgs - FP_BYTES - GP_BYTES`：输出 regs 区位于输入 regs 区之前（栈布局约定）。
- **L275–L304**：处理 class/this：
  - static：
    - 若 `etsMethod->IsFunction()`：把 `Method*` 所在槽替换为 `nullptr`（L280–L284），避免 GC 遍历参数时误把 method 指针当对象指针导致崩溃。
    - 否则把 `Method*` 槽替换为 class object 指针（L286–L294），并创建 stack ref。
  - instance：
    - 从 `argReader` 读 this 指针地址，并创建 stack ref（L300–L303）
- **L306–L310**：写入 `ani_env*` 与 class/this ref，然后 `ARCH_COPY_METHOD_ARGS`。

> 这段注释/逻辑非常高密度：本质是在构造一个 “StackWalker/GC 可理解的、统一的 NAPI/ANI 帧参数布局”。

## 4. `EtsNapiBegin`：进入 native 前的“正确栈 + local ref frame + NativeCodeBegin”（L316–L350）

- 先调用 `PrepareArgsOnStack` 得到 `outRegsArgs`（L325–L326）。
- **L327–L331（关键注释）**：强调必须先完成参数重排，之后才能安全 walk stack（例如 safepoint/GC）。
- 若 `method->GetNativePointer()==nullptr`：抛 unresolved method 异常（L332–L334）。
- `MethodEntryEvent`（L336）。
- Push local ref frame：
  - `MAX_LOCAL_REF = 4096`
  - `pandaEnv->GetEtsReferenceStorage()->PushLocalEtsFrame(MAX_LOCAL_REF)`（L339–L342）
- 若不是 fast native：`thread->NativeCodeBegin()`（L344–L347）
- 返回 `outRegsArgs`：供汇编入口继续调用 native。

## 5. `EtsNapiEnd/EtsNapiObjEnd`：退出 native（L358–L398）

共同点：

- 非 fast native：`NativeCodeEnd()`（L364–L366 / L381–L384）
- `MethodExitEvent`（L368 / L386）
- Pop local ref frame：`PopLocalEtsFrame(EtsReference::GetUndefined())`（L371–L373 / L395）

差异：

- `EtsNapiEnd`：仅做状态与 frame 清理。
- `EtsNapiObjEnd`：还要把返回的 `EtsReference*` 解引用为 `EtsObject*`（仅在无 pending exception 时）（L390–L393），再返回对象指针。

## 6. `EtsAsyncCall`：async → Promise + LaunchImmediately（L415–L481）

高层语义：

- 解析 async impl method：`vm->GetClassLinker()->GetAsyncImplMethod(method, currentCoro)`（L420–L425）
- 若 coroutine switch 被禁用：抛 INVALID_COROUTINE_OPERATION_ERROR（L427–L431）
- 做一次“arg fix”以满足 StackWalker（static 时把 Method* 槽替换为 class object 指针，L439–L446）
- 创建 `EtsPromise`（L451–L455），并把 promise 放入 global storage（L456）
- 读出所有参数到 `PandaVector<Value> args`（L459–L467），避免后续 GC 破坏入参
- `LaunchImmediately(evt, impl, args, workerId, ASYNC_CALL, false)`（L470–L474）
- 成功则返回 promise 的对象指针（`ToObjPtr(promiseHandle.GetPtr())`）

> 这段把 “native 调用触发 async” 与 “协程调度/事件完成” 打通，是 NativeBridge 章节的重要组成部分。



