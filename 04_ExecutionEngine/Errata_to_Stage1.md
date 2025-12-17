# 阶段一校正记录（Stage2 -> Stage1 Errata）

> 在阶段二逐行精读中发现 Stage1 描述不准确时：
> 1) 在此记录校正点与依据（文件/函数/行段）
> 2) 回写修正 Stage1 对应文档

## 校正点列表
- **[EE-04-001] `ExecuteImpl` 的真实实现来自生成头 `interpreter-inl_gen.h`，而不是写在 `interpreter-inl.h` 中**
  - **原 Stage1 表述问题**：只提到 “dispatch 大量在 `interpreter-inl.h`”，容易让读者误以为 `ExecuteImpl/ExecuteImplDebug` 主循环也在该文件内。
  - **事实/依据**：
    - `runtime/interpreter/interpreter_impl.cpp` 明确 `#include "interpreter-inl_gen.h"`（见文件顶部 include 段）。
    - 源码树中对应模板为 `runtime/interpreter/templates/interpreter-inl_gen.h.erb`：生成 `ExecuteImpl/ExecuteImplDebug`、dispatch table、`EXCEPTION_HANDLER` 等 label。
    - `runtime/interpreter/arch/macros.h` 提供 `DISPATCH(table, opcode)` computed-goto 宏（`goto*`），生成的主循环围绕该宏组织。
  - **回写动作**：在 Stage1 的 “2.1 最小调用链” 增补 “生成文件/模板链” 的定位说明，并把 `interpreter-inl.h` 的角色改写为“handlers 实现”。

- **[EE-04-002] 异常处理在解释器侧是“两段式”：stackless IFrames →（必要时）CFrames**
  - **事实/依据**：
    - `runtime/interpreter/templates/interpreter-inl_gen.h.erb` 的 `EXCEPTION_HANDLER` 先调用 `handler.FindCatchBlockStackless()`。
    - 若返回 `INVALID_OFFSET`，则在 AARCH64/AARCH32/X86_64 上 `return FindCatchBlockInCallStack(thread)`。
    - `runtime/exceptions.cpp` 实现 `FindCatchBlockInCallStack/FindCatchBlockInCFrames`，并在 CFrames 找到 catch 后调用 `Deoptimize(stack, method->GetInstructions()+pcOffset)` 回到解释器 catch pc。
  - **回写动作**：在 Stage1 的异常/throw 相关段落补充这条链路与关键锚点文件。
