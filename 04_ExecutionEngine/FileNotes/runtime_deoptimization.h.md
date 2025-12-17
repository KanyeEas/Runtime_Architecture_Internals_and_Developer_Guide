# `runtime/deoptimization.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：42 行  
> 本文件角色：定义去优化（deopt）对外 API：**把编译帧（CFrame）回退为解释器执行**，以及批量失效 compiled entrypoint。

## 0. 依赖（L18–L19）

- `exceptions.h`：deopt 常与异常路径绑定（pending exception/找 catch）。
- `stack_walker.h`：deopt 的核心输入是 `StackWalker*`，即“在栈上定位到需要回退的 CFrame 并能读取其 state”。

## 1. `Deoptimize`：从 CFrame 回到解释器（L23–L30）

签名（**L29–L30**）：
- `stack`：必须指向 CFrame（编译帧）。
- `pc`：
  - 非空：解释器从该 pc 开始执行（调用方提供）。
  - 为空：由 deopt 从 CFrame/stackmap 计算得到 pc（实现见 `deoptimization.cpp`）。
- `hasException`：
  - true：表示当前线程已有异常需要在解释器侧继续传播。
  - false：deopt 过程中会清理异常（实现见 `.cpp`）。
- `destroyMethod`：可选：在 deopt 前主动把某个 method 标记 destroyed 并失效其 entrypoint（用于某些极端 invalidation 场景）。

注意：返回类型是 `[[noreturn]]`，意味着它不会“正常 return”，而是通过汇编桥/栈调整跳走（见 `.cpp` 的 `DeoptimizeAfter*Frame`）。

## 2. `DropCompiledFrame`：丢弃 CFrame 并 return 给调用者（L32–L36）

- 与 `Deoptimize` 不同：drop 不重建解释器状态，而是“把该 cframe 从栈上弹掉”，恢复返回地址并执行 return（汇编桥实现）。

## 3. `InvalidateCompiledEntryPoint`：批量失效（L38）

把一组 `Method*` 的 compiled entrypoint 失效（用于 CHA/IC 等假设失效后强制回退）。

> 对应实现（`deoptimization.cpp`）还会：
> - 在所有线程栈上扫描并标记 `cframe.ShouldDeoptimize=true`
> - 把 method entrypoint 切回解释器
> - 移除 OSR code
> - 修正 compilation status




