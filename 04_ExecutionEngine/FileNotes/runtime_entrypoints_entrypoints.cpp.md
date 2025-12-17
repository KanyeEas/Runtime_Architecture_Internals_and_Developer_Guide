# `runtime/entrypoints/entrypoints.cpp`（逐行精读｜执行引擎相关函数簇）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：2160 行（巨大文件；本笔记按“与执行引擎直接闭环”的函数簇分段记录）  
> 本文件角色：entrypoints 的集合实现：compiled code 的慢路径、解释器入口桩、异常/找 catch、以及 deopt 入口。

## 0. entrypoint 的统一“护栏”：CHECK_STACK_WALKER / BEGIN_ENTRYPOINT（L86–L100）

- **L86–L95**：`CHECK_STACK_WALKER`  
  - Debug 下可启用 `Runtime::GetOptions().IsVerifyEntrypoints()`，对每个 entrypoint 做一次 `StackWalker::Verify()`（提前暴露栈/边界帧问题）。
- **L97–L100**：`BEGIN_ENTRYPOINT()` = `CHECK_STACK_WALKER` +（可选）log  
  - 设计意图：entrypoint 是“跨边界函数”，越早发现 stack walker/边界帧破坏越好。

## 1. `InterpreterEntryPoint`：compiled → 解释器执行（L102–L136）

核心语义：
- **L106–L115**：抽象方法调用检查：若 `callee->IsAbstract()`，抛 `AbstractMethodError` 并处理 pending exception。
- **L117–L122**：栈溢出检查失败则 `HandlePendingException(UnwindPolicy::SKIP_INLINED)`（说明这里会触发 unwind/找 catch）。
- **L124–L130**：切换线程当前帧：
  - 保存 `prevFrame = thread->GetCurrentFrame()`
  - `thread->SetCurrentFrame(frame)`
  - 保存并切换 `IsCurrentFrameCompiled=false`，再调用 `interpreter::Execute(thread, pc, frame)`
  - 执行结束后恢复 `isCompiledCode`
- **L131–L135**：恢复 current frame 的特殊处理：  
  如果 `prevFrame->GetMethod()` 的值等于 `COMPILED_CODE_TO_INTERPRETER`（这是 **解释器边界帧** 的标记值），则 current frame 要跳过边界帧，设置为 `prevFrame->GetPrevFrame()`；否则恢复到 `prevFrame`。

> 这与 04 的 `stack_walker.h` 中 `IsBoundaryFrame<FrameKind::INTERPRETER>` 的判定是一致的：边界帧的 method slot 存的是特殊常量而非真实 Method*。

## 2. Frame 分配/释放：CreateFrame* / FreeFrame（L673–L772）

### 2.1 `CreateFrameWithSize`：ext frame + language ext size（L673–L685）

- **L675–L678**：ext frame data size（`extSz`）：
  - 若 method 存在：通过 `LanguageContext(*method).GetFrameExtSize()` 获取语言相关扩展大小
  - 否则使用默认值
- **L679–L684**：分配与 placement-new：
  - `allocSz = Frame::GetAllocSize(size, extSz)`
  - 通过 VM HeapManager `AllocateExtFrame(allocSz, extSz)`
  - 在分配到的内存上 placement-new `Frame(...)`

> 关键点：这条路径使用的是 heap manager 的 ext frame 分配（与 thread 的 stack frame allocator 不同）。

### 2.2 `CreateFrameWithActualArgsAndSize` / `CreateNativeFrameWithActualArgsAndSize`（L687–L713）

- **L690–L699**：`CreateFrameWithActualArgsAndSize`  
  - 使用 `ManagedThread::GetCurrent()->GetStackFrameAllocator()->Alloc(allocSz)` 分配
  - 用 `Frame::FromExt/FromExt` 做 ext/主体指针换算并 placement-new
- **L701–L713**：native 版本类似，也用 stack frame allocator（同样 placement-new）

> 这里体现了一个工程约定：某些 frame 走“栈帧分配器”（更像线程栈上分配），某些走 heap manager 的 ext frame（更像 VM 管理的特殊区域）。这会影响 FreeFrame 的释放策略。

### 2.3 动态语言 vreg 初始化：`CreateFrameWithActualArgs` 模板（L721–L738）

- **L729–L736**：当 `IS_DYNAMIC==true`：
  - 从 `LanguageContext` 获取 `initial tagged value`
  - 把所有 vregs 初始化为该 tagged 值
  - `frame->SetDynamic()`

> 这是动态语言“vregs 自带 tag/初始值”语义的一个直接证据点（对应 04 的 [Frame_VReg_Acc（DataStructure）](../DataStructures/Frame_VReg_Acc.md)）。

### 2.4 便捷入口：CreateFrameForMethod*（L740–L764）

- 计算 `nregs = numArgs + numVregs`（动态版相同）
- “带 actual args”版本会用 `max(numActualArgs, method->GetNumArgs())` 扩展参数区。

### 2.5 `FreeFrame`：释放策略（L766–L772）

- **L768–L772**：通过 `ManagedThread::GetCurrent()->GetStackFrameAllocator()->Free(frame->GetExt())` 释放。

> 注意：这意味着 **调用者必须保证该 frame 是从 stack frame allocator 分配得到的**。  
> 本文件中 `CreateFrameWithSize` 走 heap manager 的 ext frame 分配，这类 frame 的释放通常走另一条路径（例如解释器 runtime interface 内部释放或专用释放入口）。因此在排障时，“谁分配谁释放”是第一优先级检查点。

## 3. 异常 entrypoints 与“找 catch / unwind”骨架（L1088–L1274, L1761–L1827）

### 3.1 典型异常入口：Throw*Entrypoint（L1088–L1178）

共同模式：
- `BEGIN_ENTRYPOINT()`
- 断言当前无 pending exception
- 构造/设置异常对象（`ThrowXxxException()` 或 `thread->SetException(...)`）
- `HandlePendingException(UnwindPolicy::SKIP_INLINED)`

> `SKIP_INLINED` 体现策略：异常 unwind 时通常需要按“物理帧”退栈，不在这里展开内联帧（内联细节由 StackWalker/编译器信息处理）。

### 3.2 `AbstractMethodErrorEntrypoint` / method conflict：需要处理 CFrame catch（L1125–L1137, L1260–L1274）

- 先创建 `StackWalker(thread, SKIP_INLINED)`，抛异常后如果当前在 CFrame（`stack.IsCFrame()`），调用 `FindCatchBlockInCFrames(thread, &stack, nullptr)`。

> 这说明：对于“从编译态抛出”的异常，catch 查找可能先在编译帧侧处理（CFrames），再必要时回到解释器侧（IFrames）。

### 3.3 IFrame 侧找 catch：`FindCatchBlockInIFramesStackless`（L1761–L1802）

这是“解释器帧栈上扫描”的核心骨架：
- 用 `interpreter::RuntimeInterface::FindCatchBlock(*method, exception, inst)` 查当前 method 是否有 catch。
- 若没找到：
  - 如果当前 frame 不是 stackless 或者 prev 为空或 prev 是解释器边界帧，则停止并返回 `pcOffset`（通常是 INVALID_OFFSET）。
  - 否则执行“方法退出”事件、通知、`HandleReturnFrame`、设置 current frame、释放当前 frame（`RuntimeInterface::FreeFrame`），然后继续扫描上一帧。

> 关键点：这里会 **边扫描边释放 stackless frames**，所以“FreeFrame 顺序”与“边界帧识别”必须正确（否则会释放错、或跨越边界释放到编译帧）。

### 3.4 IFrame 侧找 catch（封装版）：`FindCatchBlockInIFrames`（L1804–L1827）

- 先 `CHECK_STACK_WALKER`（再次强调 entrypoints 的栈一致性要求）。
- 调 `FindCatchBlockInIFramesStackless(...)` 得到 `pcOffset`：
  - 若 INVALID：特定架构下调用 `ark::FindCatchBlockInCallStack(currThread)`，并返回原 pc。
  - 否则：
    - 把异常对象写入 `currFrame->GetAcc()`（通过 LanguageContext）
    - `currThread->ClearException()`
    - 返回 `instructions + pcOffset`（作为新的 pc）

> 这提供了“异常对象如何进入解释器 acc 并从 catch 块继续执行”的直接证据链。

## 4. `DeoptimizeEntrypoint`：compiled → deopt（L1180–L1201）

- **L1184–L1188**：把 `deoptimizeType` 解码为 `compiler::DeoptimizeType type` + `instId`（原因与指令 ID）。
- **L1190–L1192**：记录 deopt reason 事件（用 StackWalker 取当前方法名）。
- **L1194–L1200**：
  - `stack = StackWalker::Create(thread)`（必须能定位 CFrame）
  - 若 `type >= CAUSE_METHOD_DESTRUCTION`：取 top method 作为 `destroyMethod`
  - 调 `Deoptimize(&stack, nullptr, false, destroyMethod)`：不会返回（详见 04 的 `deoptimization.cpp` FileNotes）。

> 这条路径把“编译器产生的去优化理由”接入 runtime 的 Deoptimize 核心实现，是 04 章 deopt 闭环的关键入口之一。



