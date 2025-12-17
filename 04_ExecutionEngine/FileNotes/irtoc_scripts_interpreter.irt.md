# `irtoc/scripts/interpreter.irt`（逐行精读｜IRTOC/LLVM Fast Interpreter 的“真实解释器语义”）

> 章节归属：Stage2 / 04_ExecutionEngine（Execution Engine）  
> 文件规模：约 3.3k 行（Ruby DSL，生成 IRTOC graph / handler）  
> 本文件角色：定义 fast interpreter 的完整语义：
> - **内部 calling convention**：固定寄存器保存 `tr/pc/frame/acc/dispatch`（不同 arch 不同）
> - **dispatch**：computed-goto 风格（`tail_call(addr)`）到 `HANDLE_FAST_*`
> - **异常/OSR/stackless call-return**：全部在脚本里以宏的形式编码
> - **为每个 bytecode opcode 生成一个 `HANDLE_FAST_<handler_name>` 函数**
>
> 强依赖：
> - `include_relative 'common.irt'`：regmap/Constants（Frame/Thread/Method 的 offset 与 tag）
> - build 产物证据：`build/irtoc/irtoc_interpreter/interpreter.irt.fixed`（规范化脚本）、`irtoc_code.cpp`（Graph 构造）

---

## 0. 固定寄存器与校验（L18–L40）

- **L18–L23**：`fixed_regmap`：为 fast interpreter 选择“永驻寄存器”：
  - x86_64：`dispatch/pc/frame/acc/acc_tag`
  - arm64：额外有 `moffset/method_ptr`（避免频繁从 frame 计算 mirror 偏移/方法指针）
- **L23**：`handler_regmap = $full_regmap + fixed_regmap`：handler 使用“全寄存器 + 固定寄存器”。
- **L25–L36**：sanity checks（arm64 才做）：确保 fixed regs 不与 panda/arch/args/caller regs 冲突。
- **L38–L40**：`InterpreterValidation.spills_count_max=32`：与后续 `validation.yaml` 对齐，限制 spills 数。

> 结论：fast interpreter 的核心是“把解释器状态（pc/frame/acc）放到固定寄存器”，减少内存访存。

---

## 1. decode + dispatch：computed-goto 的 IRTOC 版本（L156–L413）

### 1.1 decode

- **L158–L206**：`readbyte/as_vreg_idx/as_id` 等宏：按 operand width 从 `pc` 读取立即数/vreg index。
  - `as_vreg_idx` 直接把“编码在指令流里的寄存器编号”转为 vreg index（用于 frame slot address 计算）。

### 1.2 dispatch 宏（最关键）

核心在 **`macro(:dispatch)`**（L406–L413）：

- **L407**：`opc := readbyte(pc, 0)`：取 opcode
- **L408**：`offset := Mul(u8toword(opc), WordSize())`：计算 `dispatch_table[opc]` 的地址偏移
- **L409**：`addr := Load(table, offset)`：读出 handler 函数指针
- **L410–L412**：把 `pc/table` LiveOut 到固定寄存器
- **L412**：`tail_call(addr)`：**以 TAIL_CALL intrinsic 进入 handler**

> 这就是 computed-goto 的等价形式：不是 `switch`，也不是函数返回再循环，而是“尾调用跳转到下一 handler”。

---

## 2. Frame/VReg/Acc：与 C++ 语义一致，但更“显式”（L248–L389）

### 2.1 bytecode offset（deopt/异常/调试依赖）

- **L248–L255**：`ins_offset`/`update_bytecode_offset`：通过 `pc - frame->instructions` 计算并写回 `frame->bcOffset`。

### 2.2 vreg 地址计算（静态语言 mirror/tag）

- **L259–L267**：`frame_vreg_ptr`/`vreg_ptr`：`frame + VREGISTERS_OFFSET + vreg_idx * VREGISTER_SIZE`
- **L294–L306**：`get_tag/set_tag`：tag 存在 mirror 区（`vreg_ptr + moffset`）
- **L312–L320**：`set_primitive/set_object`：把 tag 与 payload 同步写入

### 2.3 acc 的“写回/恢复”是不变量

- **L331–L358**：`save_acc/save_acc_var`：把 `%acc/%acc_tag` 写回到 frame 的 acc slot（value + mirror）
- **L360–L366**：`restore_acc/restore_acc_tag`：从 frame 读回
- **L373–L379**：`set_acc_primitive/set_acc_object`：acc 的 tag 语义（primitive vs object）

> 这直接解释了 fast interpreter 中频繁出现的 “call runtime 前 save_acc，回来再 restore_acc”：为了让 GC/stackwalker/hook 能看到一致状态。

---

## 3. 异常处理：`find_catch_block` + `move_to_exception`（L509–L536）

### 3.1 stackless IFrames 找 catch（runtime 侧）

- **L509–L523**：`find_catch_block`：
  - 调 `FindCatchBlockInIFrames(tr, frame, pc)` 返回 handler_pc
  - 若返回 `pc`（未找到）：`Intrinsic(:INTERPRETER_RETURN)` 退出到上层（由 runtime 继续处理 CFrames）
  - 否则读出 EH frame（`THREAD_FRAME_OFFSET`）与其 acc，返回 handler_pc

> 这就是我们在 C++ 解释器中总结的“两段式异常”：先 stackless IFrames，找不到再交给 call-stack/CFrames（见 `runtime/exceptions.cpp`）。

### 3.2 进入异常入口（dispatch_table 的“末尾 handler”）

- **L525–L536**：`move_to_exception`：
  - 把 table/frame/(moffset/method_ptr)/tr/pc 全部 LiveOut
  - **L534**：`addr := Load(table, Panda::dispatch_table.handler_names.size * 8)`：取 dispatch_table 的最后一个 slot
  - `tail_call(addr)`：跳到 **`HANDLE_FAST_EXCEPTION`**

> 这与 build 产物 `irtoc_interpreter_utils.h` 完全对齐：dispatch_table[391]（最后一个）是 `HANDLE_FAST_EXCEPTION`（或 `_LLVM` 版本）。

---

## 4. safepoint + OSR：回边插桩 + fake-return（L559–L644, L2152–L2185）

### 4.1 safepoint（线程 flag 驱动）

- **L560–L571**：`safepoint(acc_type, is_save_acc)`：
  - 如果 thread flag 非 0，则可选 `save_acc_var`，调用 `SafepointEntrypointInterp(tr)`，并恢复 acc

### 4.2 回边插桩：OSR 触发点就在分支里

典型出现在 `handle_jmp_*` 系列：

- **L610–L644**：`instrument_branches(imm, acc_type, method_ptr)`：
  - `imm <= 0` 表示回边：先做 safepoint
  - hotness<=0：调用 `CallCompilerSlowPathOSR(...)`
  - 若 OSR 成功：**L620** 调 `handle_fake_return()`（强制从当前 frame 退出到 caller）
  - 通过一组 Phi 把 `acc/frame/pc` 更新为 “正常继续执行”或“fake-return 后的状态”

### 4.3 fake-return：让解释器循环“像 return 一样退出”去进入 OSR

- **L2152–L2185**：`handle_fake_return`：
  - 若当前不是 stackless：直接 `Intrinsic(:INTERPRETER_RETURN)`（退出到 runtime）
  - 否则：
    - 取 `fake_frame = prev_frame`，`fake_pc = prev_frame->nextInst`
    - 若 `IS_INITOBJ`：acc 从 prev_frame 的 acc 取 object；否则从当前 frame restore_acc
    - `THREAD_FRAME_OFFSET = fake_frame`，并 `FreeFrameInterp(cur_frame, tr)`
    - 若存在 pending exception：把 pc 设置到 fake_frame 上并 `move_to_exception`

> 这段是 OSR 的关键难点：OSR 成功后并不是“直接跳到 OSR code”，而是让解释器通过“伪造 return 弹栈”回到某个稳定边界，再由上层进入 OSR。

---

## 5. 调用/返回：`generic_call`/`generic_return`（L780–L877）

### 5.1 `generic_call`：两条路

- **L780–L840**：`generic_call(id, size, is_initobj, callee, nargs, copy_lambda)`：
  1) **callee 已编译**（L787–L801）
     - 读 `callee->compiled_entrypoint`
     - `IsCompiled(entrypoint)` 为真：
       -（非 initobj）保存 acc
       - 调 `InterpreterToCompiledCodeBridge(pc, frame, callee, tr)`（I2C）
       - 恢复 `Thread` 的 `FrameKind` 与 `THREAD_FRAME_OFFSET`
       - 检查 exception；从 frame restore acc；pc 前进
  2) **callee 未编译**（L803–L839）
     - 取 `pc_int = get_instructions(callee)`，`num_vregs = get_numvregs(callee)`
     - 分配新 frame：`create_frame(frame_size, callee)` 并标记 `Frame::IS_STACKLESS`
     - `copy_lambda` 负责把实参拷贝到新 frame 的 vregs（含 acc 参与的 call_acc 变体）
     - 设置 `prev_frame/next_instruction/instructions`，并把 `THREAD_FRAME_OFFSET` 指向新 frame

> 这解释了为什么 fast interpreter 同样依赖 “stackless frame 弹栈”：未编译调用会走解释器栈帧链；已编译调用则走 I2C。

### 5.2 `generic_return`：stackless 弹栈 or 退出到 runtime

- **L859–L877**：
  - 若 `IS_STACKLESS`：取 prev_frame/next_pc，copy 返回值到 prev_frame，更新 `THREAD_FRAME_OFFSET`，free_frame，回到 caller 继续执行
  - 否则：`save_acc(); Intrinsic(:INTERPRETER_RETURN)`（返回到 runtime 边界）

---

## 6. method resolution：`get_callee`（L2000–L2031）

- **L2001**：`update_bytecode_offset`：确保 frame->bcOffset 与 pc 对齐（deopt/异常/调试依赖）
- **L2003–L2010**：
  - initobj：走 cache_entry，但不走 slowpath（nil）
  - 非 initobj：`callee_ptr(id, need_save=true)`，需要时 restore acc；callee 为空则 `move_to_exception`
- **L2012–L2027**（非 initobj 的 receiver/虚调用）：
  - 若非 static：读取 receiver（可能来自 acc 或 vreg，取决于 imm）
  - receiver 为 null：抛 NPE 并 `move_to_exception`
  - virt call：`ResolveVirtualMethod(callee, frame, receiver_ref, pc, method_ptr)`

---

## 7. handler 生成：`Panda.instructions.each`（L2407–...）

脚本末尾会遍历 ISA 描述，为每个 opcode 生成 `HANDLE_FAST_<handler_name>`：

- 通过 `handler_name = i.handler_name.gsub(/_PROF\\d+/, '')` 去掉 profile suffix
- 构造函数时会：
  -（dynamic 指令）先 `save_acc`（源码注释标注为 *planned removal*：这不是本章遗漏，而是上游实现的已知演进点）
  - debug 模式下做 tag/assert 校验（大量 `assert_has_object_eq/ne`）
  - `case handler_name` 里调用对应的 `handle_xxx` 宏（例如 mov/lda/call/branch 等）

> 这就是为什么 `build/runtime/include/irtoc_interpreter_utils.h` 能枚举出 392 个 `HANDLE_FAST_*`：它们由这里自动生成。

---

## 证据链（build/ 对照）

- dispatch table（392 项 + EXCEPTION slot）：`build/runtime/include/irtoc_interpreter_utils.h`
- 规范化脚本：`build/irtoc/irtoc_interpreter/interpreter.irt.fixed`
- 生成的 Graph 构造：`build/irtoc/irtoc_interpreter/irtoc_code.cpp`
- runtime 入口调用：`runtime/interpreter/interpreter_impl.cpp`


