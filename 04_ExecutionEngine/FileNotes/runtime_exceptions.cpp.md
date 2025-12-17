# `runtime/exceptions.cpp`（逐行精读｜异常抛出 + 跨 IFrame/CFrame 找 catch）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 本文件角色：
> - 实现各种 `Throw*` 辅助函数（把异常对象设置到 `thread->Exception`，并打事件）
> - 实现 **异常 unwind 的“跨编译帧”部分**：`FindCatchBlockInCallStack/FindCatchBlockInCFrames/HandlePendingException`
>
> 与解释器生成的 `EXCEPTION_HANDLER`（`interpreter-inl_gen.h`）关系：  
> `EXCEPTION_HANDLER` 先在 stackless IFrames 中找 catch；若找不到则 `return FindCatchBlockInCallStack(thread)`，把责任移交到本文件的 CFrame 遍历逻辑。

## 0. 关键依赖（L16–L35）

- **L20**：`runtime/bridge/bridge.h`：异常回退可能跨越 c2i/i2c 边界。
- **L21**：`runtime/deoptimization.h`：在 CFrames 里找到 catch block 后，通过 `Deoptimize` 回到解释器 catch pc。
- **L22**：`runtime/entrypoints/entrypoints.h`：释放/创建 frame 等工具函数（例如 `FreeFrame`）。
- **L26**：`runtime/include/stack_walker.h`：遍历 call stack（IFrame/CFrame/inline）。

## 1. Throw 系列：语言上下文驱动（L38–L210）

总体模式：

- 获取 `thread` 与 `LanguageContext`（**L44–L48**）
- `ThrowException(ctx, thread, descriptor, msg)`（**L38–L42**）
- 对部分异常打 `SetExceptionEvent(type, thread)`（例如 NPE/越界/算术等）

### 1.1 NullPointerException（L50–L61）

- **L50–L55**：无参版本使用当前线程与其语言上下文。
- **L57–L61**：实际 throw + 事件（NULL_CHECK）。

### 1.2 ArrayIndexOutOfBounds / NegativeArraySize / Arithmetic（L69–L132）

- 统一用 `PandaString msg` 拼接上下文信息（idx/length/size），作为异常 message。

## 2. `DropCFrameIfNecessary`：把“不能继续执行的编译帧”丢掉（L211–L241）

该函数用于 `FindCatchBlockInCFrames` 的循环中，在某些情况下强制退出 compiled frame：

- Next frame 不是 CFrame（**L214–L222**）
- Next frame 是 native cframe（**L224–L231**）
- method 是 static constructor（**L233–L239**）

三种情况都会：

- 释放 `origFrame`（如果存在）
- `DropCompiledFrame(stack)`（最终通过桥接/汇编把当前 compiled frame 弹掉并返回到 caller）

> 直觉：这些 frame 类型要么不能在这里做“deopt 回解释器 catch”，要么需要按 ABI 正常退出 compiled 函数。

## 3. `FindCatchBlockInCFrames`：在 compiled 栈上搜索 catch（L250–L303）

核心循环（**L252–L293**）：

- 取 `pc = stack->GetBytecodePc()`，以及 `method = stack->GetMethod()`。
- 通过 `method->FindCatchBlock(exceptionClass, pc)` 查询 catch offset（**L259–L260**）。
- 若找到：
  - 释放 `origFrame`
  - 调用 `Deoptimize(stack, method->GetInstructions() + pcOffset)`（**L267**）并 `UNREACHABLE()`  
    语义：通过 deopt 把当前 compiled frame（以及可能的内联信息）转换为解释器帧，并把 pc 设到 catch block。
- 若没找到：
  - `thread->GetVM()->HandleReturnFrame()`：通知 VM 栈回退（**L271**）
  - `DropCFrameIfNecessary(...)`：处理 “native/static ctor/边界” 等情况（**L273**）
  - 若 `stack->IsInlined()`：继续在同一物理 frame 的下一个 inline method 中找（**L275–L277**）
  - 处理 bypass bridge（**L279–L292**）：当 boundary frame 指示是 BYPASS，说明动态语言可能做了 c2c call，需要正确 return 才能退出 active compiled function。

## 4. `FindCatchBlockInCallStack`：从 IFrame 进入 CFrame 搜索（L311–L330）

- **L313–L316**：`stack = StackWalker::Create(thread)`，并读取 `origFrame = stack.GetIFrame()`；断言当前不是 CFrame。
- **L318–L320**：若 `origFrame->IsInvoke()`，直接 return：  
  注释写明“Exception will be handled in the Method::Invoke's caller”——即 invoke 边界有自己的异常转交约定。
- **L322–L327**：`stack.NextFrame()` 后，若没有 frame / 不是 cframe / cframe 是 native，则 return（交给更外层处理或 native 框架处理）。
- **L328–L329**：通知 VM 回退，并调用 `FindCatchBlockInCFrames(thread, &stack, origFrame)`。

## 5. `HandlePendingException`：从 compiled 顶部处理 pending exception（L449–L463）

- **L451–L454**：要求当前线程存在 pending exception。
- **L457**：`CleanupCompiledFrameResources(thread->GetCurrentFrame())`：先清理 compiled frame 资源（deopt/异常都可能需要）。
- **L459–L462**：创建 `StackWalker(policy)`，断言当前是 CFrame，然后直接 `FindCatchBlockInCFrames(thread, &stack, nullptr)`。

> 这条路径常出现在：
> - deopt 之后需要处理异常（`runtime/deoptimization.cpp` 调用 `HandlePendingException()`）
> - compiled code 抛异常后回到 runtime 的 slow path




