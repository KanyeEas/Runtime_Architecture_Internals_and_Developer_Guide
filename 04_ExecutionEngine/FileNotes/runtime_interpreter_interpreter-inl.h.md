# `runtime/interpreter/interpreter-inl.h`（逐行精读｜opcode handlers 与 stackless 调用）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 本文件角色：提供解释器 **指令语义实现（handlers）** 与若干高频 helper。  
> 注意：解释器的“主循环（dispatch table + computed goto）”并不在本文件里，而是由 `runtime/interpreter/templates/interpreter-inl_gen.h.erb` 生成到 `interpreter-inl_gen.h`（见 `interpreter_impl.cpp` 的 `#include "interpreter-inl_gen.h"`）。

## 0. includes：为什么这里会包含 bridge/runtime_interface/jit profiling（L30–L62）

这一组 include 直接暴露了本文件在执行引擎中的交叉点：

- **L39**：`runtime/bridge/bridge.h`：`CallCompiledCode()` 通过 i2c bridge 跳到 compiled entrypoint（见 L3571–L3597）。
- **L57**：`runtime/interpreter/runtime_interface.h`：大量 Resolve/Throw/CreateObject/CreateArray/FindCatchBlock 等都通过 `RuntimeIfaceT` 间接调用 runtime。
- **L59**：`runtime/jit/profiling_data.h`：分支统计/inline cache 更新/OSR hotness 等需要 profiling data（见 HandleVirtualCall/UpdateBranchStatistics 等）。
- **L63**（注释）：强调 handlers 必须 `ALWAYS_INLINE`：配合生成的 dispatch 主循环，避免 handler 调用开销。

## 1. 解释器模板入口声明（L67–L73）

- **L67–L73**：声明 `ExecuteImpl/ExecuteImplDebug/ExecuteImplInner` 模板。  
  真正的 `ExecuteImpl/ExecuteImplDebug` 定义来自生成头 `interpreter-inl_gen.h`；本文件末尾只实现了 `ExecuteImplInner` 的 “stub 调用器”（见 L4133–L4140）。

## 2. `FrameHelperDefault`：把“建帧策略”参数化（L75–L97）

- **L77–L82**：`GetNumberActualArgsDyn`：动态语言 call 指令里 `imm + 1`（+1 表示 function object 自身）。
- **L91–L96**：`CreateFrame(...)`：统一用 `RuntimeIfaceT::CreateFrameWithActualArgsAndSize(...)` 创建 frame。  
  这让 `InstructionHandler` 的 call handler 不需要关心不同 runtime 的 frame 分配细节。

> 结论：解释器把 “frame 分配/拷参” 做成可替换策略（FrameHelper），而不是把 runtime 细节硬编码到每条 call 指令里。

## 3. `InstructionHandler`：所有 opcode 的语义实现体（L99–L4131）

### 3.1 基本数据搬运：mov/lda/sta（示例：L132–L377）

典型模式（以 `mov/lda/sta` 为例）：

- 读 vreg 编号：`inst.GetVReg<FORMAT, idx>()`
- 通过 `FrameHandler` 读/写 vreg：`GetFrameHandler().GetVReg(i)`
- 通过 `AccVRegister` 读/写 acc：`GetAcc()/GetAccAsVReg()`
- 完成后 `MoveToNextInst<FORMAT, CAN_THROW>()`（CAN_THROW 决定是否清 `opcodeExtension`）

示例：

- **L133–L141**：`HandleMov`：primitive move（静态语义）。
- **L155–L163**：`HandleMovObj`：reference move。
- **L166–L174**：`HandleMovDyn`：动态语义 move（tagged value）。
- **L226–L249**：`HandleLda/LdaWide/LdaObj`：从 vreg 读到 acc。
- **L343–L377**：`HandleSta/StaWide/StaObj/StaDyn`：从 acc 写回 vreg（动态用 `Move(...)` 保留 tag）。

### 3.2 分支与 OSR 触发点：`jmp/cond jmp`（示例：L379–L459 & 更靠后的位置）

- **L379–L387**：`HandleJmp`：对 offset 调 `InstrumentBranches(offset)`。  
  若返回 false → `JumpToInst(offset)`；若返回 true → 说明在回边触发了 OSR（基类会伪造 `RETURN_VOID` 指令使主循环退出）。
- 条件跳转（例如 **L438–L457**）同理：在 taken 分支可能调用 `InstrumentBranches`。

> 这把 OSR 与 safepoint 检查天然绑定到“回边/循环”，是解释器常见的 OSR 触发策略。

### 3.3 对象/数组/字段：null check + Resolve + barrier（示例：L2000–L2053, L2369–L2532, L3121–L3203）

这些 handler 的共同结构：

- 取对象/数组引用，若为 null：调用 `RuntimeIfaceT::ThrowNullPointerException()` 并 `MoveToExceptionHandler()`。
- 解析 `Field/Method/Class`：通过 `ResolveField/ResolveMethod/ResolveType`（内部带 interpreter cache）。
- 执行读/写：
  - 原始字段：`GetFieldPrimitive/SetFieldPrimitive`
  - 引用字段：`GetFieldObject/SetFieldObject<NEED_{READ,WRITE}_BARRIER>`
  - 数组：`array->Get/Set<..., NEED_WRITE_BARRIER>`

示例：

- **L2000–L2028**：`newarr`：size<0 → NegativeArraySize；`ResolveType<true>`（可能触发类初始化）；`RuntimeIfaceT::CreateArray`；失败进入异常 handler。
- **L2031–L2053**：`newobj`：`ResolveType<true>`；`RuntimeIfaceT::CreateObject`。
- **L2369–L2386**：`stobj.v.64`：先 NPE 检查，再 `ResolveField`，再 `StorePrimitiveFieldReg(...)`。
- **L2418–L2473**：`ldstatic*`：`ResolveField<true>` + `GetClass(field)`（断言类已 initialized/initializing）+ 读静态字段。
- **L3121–L3203**：数组 load/store 的统一检查：
  - `CheckLoadArrayOp/CheckStoreArrayOp`：NPE + bounds +（对象数组）ArrayStoreException

### 3.4 解释器解析缓存：`ResolveMethod/ResolveField/ResolveType`（L3210–L3281）

这组函数是“解释器性能”的关键：

- 以 `(instAddress, currentMethod)` 为 key 查询 `thread->GetInterpreterCache()`（**L3214–L3218**, **L3235–L3239**, **L3261–L3266**）。
- 在可能触发 runtime/GC 的 Resolve 调用前，把 acc 写回 frame（**L3220**, **L3246**, **L3268**），调用后再从 frame 恢复 acc（**L3222**, **L3248**, **L3271**）。  
  这是为了保证 acc 在 GC 时可达，以及保持全局寄存器/状态一致。

### 3.5 调用路径：解释器内调用 vs i2c 跳转（核心：L3470–L3610）

#### 3.5.1 建帧与拷参：`CreateAndSetFrame`（L3470–L3516）

- 计算 `nregs` 与 `numActualArgs`（动态语言会取 `max(declaredArgs, actualArgs)`）。
- 调 `FrameHelper::CreateFrame(...)` 分配 frame；若为 null 则 throw StackOverflow 并跳异常 handler（**L3497–L3502**）。
- 把 caller acc 写到新 frame（**L3505**），动态语言标记 `frame->SetDynamic()`（**L3506–L3508**）。
- `CopyArguments(...)`：把 call 指令携带的 vregs/acc 按格式搬到 callee frame 参数区（**L3510–L3512**）。
- `RuntimeIfaceT::SetCurrentFrame(current, *frame)`（**L3513**）：切换当前解释器 frame。

#### 3.5.2 Call 前置：`HandleCallPrologue`（L3518–L3536）

- 记录 method entry 日志。
- 回边 safepoint 检查：`TestAllFlags()` 时把 acc 写回 frame，调用 `RuntimeIfaceT::Safepoint()`，再恢复 acc（**L3528–L3532**）。
- 若 method 没有 compiled code：`UpdateHotness<true>(method)`（**L3533–L3535**），为 JIT/OSR 触发提供统计。

#### 3.5.3 解释器 stackless 调用：`CallInterpreterStackless`（L3538–L3569）

- 创建新 frame 并标记 `frame->SetStackless()`（**L3553**）。
- `INITOBJ` 特殊：
  - `frame->SetInitobj()`（**L3554–L3556**）
  - 动态语言下还会 `frame->DisableOsr()`（**L3557–L3560**）：注释说明 `return.*` 对 INITOBJ frame 有特殊逻辑，因此禁用 OSR 避免状态转移复杂化。
- 更新 `InstructionHandlerState`（pc=callee instructions）并触发 `EVENT_METHOD_ENTER`（**L3566–L3569**）。

#### 3.5.4 i2c：`CallCompiledCode`（L3571–L3597）

- 把 acc 写回 caller frame（**L3574**）后调用：
  - 动态：`InterpreterToCompiledCodeBridgeDyn(...)`
  - 静态：`InterpreterToCompiledCodeBridge(...)`
- bridge 返回后恢复 thread 状态：
  - `SetCurrentFrameIsCompiled(false)`
  - `SetCurrentFrame(this->GetFrame())`（**L3582–L3584**）
- 若有 pending exception → `MoveToExceptionHandler()`；否则把 acc 从 frame 取回并 `MoveToNextInst<FORMAT, true>()`（**L3585–L3590**）。

> 这段把 “解释器 ↔ 编译代码” 的 ABI/状态切换写得非常清晰：解释器在边界处必须把 acc/frame 写回、恢复，并把异常统一转入异常 handler label。

### 3.6 return：普通 return vs stackless return（L2534–L2606）

- **L2534–L2559**：`return/return.64/return.obj/return.void` 只负责把返回值写入 `frame->acc`（或不写），并不负责弹栈。  
  “弹栈/返回到 caller”由生成的主循环在识别到 return 指令后决定是否 `return` 或继续 dispatch（见 `interpreter-inl_gen.h.erb` 的 return 分支）。
- **L2561–L2601**：`HandleReturnStackless()` 才是 stackless frame 的“弹栈实现”：
  - 发 method exit event（**L2571–L2577**）
  - `UpdateInstructionHandlerState(prevPc, prevFrame)`（**L2578–L2580**）
  - 恢复 dispatch table、`SetCurrentFrame(prev)`（**L2582–L2584**）
  - 若有异常：`MoveToExceptionHandler()`；否则把 acc 从 callee frame 传回并恢复 inst（**L2585–L2590**）
  - INITOBJ 特判：静态语言下若 callee 是 initobj，则 acc 取 `prev->acc`（**L2592–L2596**）
  - `RuntimeIfaceT::FreeFrame(thread, frame)`（**L2598**）

### 3.7 throw + 找 catch：stackless IFrame 内 unwind（L2834–L2894）

- **L2834–L2851**：`HandleThrow`：把异常对象写入 `thread->SetException(exception)`，更新 throw profiling，然后 `MoveToExceptionHandler()`。
- **L2853–L2894**：`FindCatchBlockStackless()`：
  - 对当前 stackless frame 调 `FindCatchBlock(exception, pc)`（最终走 `RuntimeIfaceT::FindCatchBlock`，见 L2901–L2905）。
  - 若找到，返回 `pcOffset`（catch block offset）。
  - 若没找到：
    - 当 frame 不是 stackless / 没有 prev / prev 是 boundary frame（**L2867–L2869**），直接返回 INVALID_OFFSET（交给更外层，即 `FindCatchBlockInCallStack`）。
    - 否则：发 method exit event，更新 state 到 prev frame 的 pc，并 `FreeFrame(frame)`，继续向上找（**L2872–L2892**）。

> 这与生成文件的 `EXCEPTION_HANDLER` 精确对接：  
> 先 `FindCatchBlockStackless()`（只处理 stackless IFrames），若 INVALID 则 `return FindCatchBlockInCallStack(thread)` 进入 `runtime/exceptions.cpp` 的 CFrame 搜索与 deopt 回退。

## 4. 文件尾部：`ExecuteImplInner` 通过 stub 调用生成的 `ExecuteImpl`（L4133–L4140）

- **L4133**：声明 `extern "C" ExecuteImplStub(thread, pc, frame, jumpToEh, impl)`。
- **L4138–L4139**：把模板函数地址 `&ExecuteImpl<...>` 当作 `void* impl` 传入 stub。  
  含义：`ExecuteImplStub` 可能是为了 ABI/调用约定/汇编桥接而存在（例如统一寄存器保存/恢复），从而把真正的 C++ 主循环包装在一个固定签名的入口中。




