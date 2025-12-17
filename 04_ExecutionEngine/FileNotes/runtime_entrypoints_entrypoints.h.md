# `runtime/entrypoints/entrypoints.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：50 行  
> 本文件角色：声明 “compiled code/运行时辅助路径可调用的入口点（entrypoints）”，尤其是 **Frame 创建/释放** 与少量异常入口。

## 0. 依赖（L18–L20）

- **L18**：`entrypoints_gen.h`：由 YAML/模板生成的 entrypoints 列表（大量慢路径函数声明在生成文件里）。
- **L19**：`runtime/include/thread.h`：需要 `ManagedThread` 类型（FreeFrameInterp 等）。

## 1. Frame 创建族（L25–L41）

这一组是“解释器帧/栈帧分配”最核心的 ABI：

- **L25**：`CreateFrameWithSize(size, nregs, method, prev)`  
  - 典型：创建一个 `Frame`，显式指定分配 size 与 vreg 数量。
- **L27–L28**：`CreateFrameWithActualArgsAndSize(size, nregs, numActualArgs, method, prev)`  
  - 典型：动态语言/变参场景（实际参数个数可能大于 method 声明参数）。
- **L30–L32**：`CreateNativeFrameWithActualArgsAndSize(...)`（PANDA_PUBLIC_API）  
  - 为 native 调用路径准备的 frame 创建（细节见 `entrypoints.cpp` 的实现分配器选择）。
- **L34–L40**：按 method 直接创建（静态/动态）以及 “带 actual args” 的便捷入口：
  - `CreateFrameForMethod` / `CreateFrameForMethodDyn`
  - `CreateFrameForMethodWithActualArgs` / `...Dyn`

> 这些函数的真实分配策略、ext frame 数据、以及动态语言 vreg 初始化，全部在 `entrypoints.cpp` 给出证据（见对应 FileNotes）。

## 2. Frame 释放族（L42–L45）

- **L42**：`FreeFrame(frame)`（PANDA_PUBLIC_API）  
  - 解释器执行/异常 unwind/deopt 等大量路径都会用到（04 章 bridge/deopt/FindCatchBlock 都依赖它）。
- **L44**：`FreeFrameInterp(frame, current)`  
  - 专门用于解释器路径的释放辅助（在 `entrypoints.cpp` 中可看到与 `RuntimeInterface::FreeFrame` 的关系）。

## 3. 异常入口（L46）

- **L46**：`ThrowInstantiationErrorEntrypoint(Class *klass)`  
  - 一个“从 compiled code 触发异常”的代表入口：创建并抛出 `InstantiationError`，并走 `HandlePendingException` unwind（实现见 `entrypoints.cpp`）。



