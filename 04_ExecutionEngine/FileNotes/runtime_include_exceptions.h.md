# `runtime/include/exceptions.h`（逐行精读｜异常 API 与跨帧查找入口）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 本文件角色：定义运行时抛异常/处理异常的核心 API，并暴露“在 call stack 中寻找 catch block”的入口：
> - `FindCatchBlockInCallStack(ManagedThread*)`
> - `FindCatchBlockInCFrames(...)`
> - `HandlePendingException(UnwindPolicy)`
>
> 这些函数与解释器生成的 `EXCEPTION_HANDLER`（`interpreter-inl_gen.h`）构成异常路径闭环。

## 0. 依赖（L18–L22）

- **L22**：依赖 `runtime/include/stack_walker.h`：异常路径需要遍历 IFrame/CFrame，并在需要时 deopt 回解释器。

## 1. 抛异常：统一入口（L26–L78）

- **L26–L27**：`ThrowException(ctx, thread, name, msg)`：把“异常类别/消息”交给 `LanguageContext` 生成异常对象并设置到 thread 上。
- **L29–L36**：`ThrowNullPointerException` / `ThrowStackOverflowException`：常见运行时错误。
- **L38–L49**：越界类异常：数组/字符串等。
- **L76–L79**：OOM：既支持指定 thread，也支持使用当前线程。

> 这些函数通常被：
> - 解释器 handler 调用（例如 `interpreter-inl.h::HandleNewarr` 对负 size）
> - entrypoints（编译代码 slow path）调用

## 2. “找 catch block”的跨帧入口（L80–L86）

- **L80**：`FindCatchBlockInCallStack(thread)`：当解释器 stackless frame 中找不到 catch 时，回退到这个函数继续处理（典型：需要在 CFrames/编译帧中找）。
- **L82–L86**：`DropCFrameIfNecessary` / `FindCatchBlockInCFrames`：服务于 CFrame 遍历与必要的 deopt/退栈。

## 3. 处理 pending exception：从 CFrame 开始 unwind（L107–L108）

- **L107**：`HandlePendingException(UnwindPolicy policy = UnwindPolicy::ALL)`：当 thread 已有 pending exception，且当前位于 compiled 侧时，使用 `StackWalker` 从 CFrame 开始查找 catch，并在找到时 deopt 回解释器 catch pc（实现见 `runtime/exceptions.cpp`）。




