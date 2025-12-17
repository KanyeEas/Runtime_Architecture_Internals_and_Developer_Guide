# `runtime/interpreter/frame.h`（逐行精读｜Frame layout 与 FrameHandler）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：789 行  
> 本文件角色：定义解释器帧 `Frame`、以及访问 vregs/acc 的 `FrameHandler`：  
> - 给出 **静态/动态语言的兼容布局**（payload + mirror）  
> - 定义 **deopt/OSR/stackless** 等关键 flags  
> - 提供 **StaticFrameHandler/DynamicFrameHandler** 用统一 API 返回 `StaticVRegisterRef/DynamicVRegisterRef`

## 0. 最重要的布局注释（L31–L66）

文件开头把 frame layout 画得非常清楚：
- **静态语言**：Frame + payload vregs[n] + mirror vregs[n]  
  mirror 的起点偏移 = `nregs * sizeof(VRegister)`（L61–L63）
- **动态语言**：Frame + payload vregs[n]（无 mirror）

关键结论（L64–L66）：
- 用 `FrameHandler` 访问 vregs，`GetVReg` 返回 `VRegisterRef`（静态/动态不同）
- `AccVRegister` 仍然是 “value+tag”（与 vreg 的 tagless 相对）

## 1. flags：执行引擎最常用的不变量（L74–L94, L228–L326）

最关键的几个：
- **IS_DEOPTIMIZED**（L80–L83）：deopt 后的 frame，**禁止 OSR**（否则 deopt 后栈空间未释放可能触发栈溢出）
  - `DisableOsr()` 直接 `SetDeoptimized()`（L283–L286）
- **IS_STACKLESS / IS_INITOBJ / IS_INVOKE**：用于 stackless interpreter 的 unwind/语义修复
- **IS_DYNAMIC**：决定是否存在 mirror vregs（影响 `GetActualSize` 与 handler 行为）

## 2. 分配大小与真实 vreg 数：`GetAllocSize` / `GetActualSize`（L222–L348）

- **GetAllocSize(size, extSz)**（L222–L226）：
  - 分配 `sizeof(Frame) + sizeof(VRegister)*size + extSz` 并按默认帧对齐对齐
  - 注意这里的 `size` 通常传 “actual vreg slots” 而不是 `nregs`（见 entrypoints/runtime_interface 的调用）
- **GetActualSize<IS_DYNAMIC>(nregs)**（L340–L348）：
  - dynamic：actual size = nregs
  - static：actual size = nregs * 2（payload + mirror）

> 这就是 “为什么静态语言 frame 的 nregs 逻辑数量不变，但实际分配要翻倍” 的最直接证据。

## 3. ABI/工具链友好：一组稳定 offset（L350–L405）

`GetMethodOffset/GetPrevFrameOffset/GetNumVregsOffset/GetVregsOffset/GetAccOffset/...` 提供 stable offsets。  
这些 offset 会被：
- StackWalker（边界帧/栈遍历）
- 汇编桥（C2I/I2C、deopt/osr）
- debug/工具
直接消费，属于“不能轻易改”的 ABI 表面。

## 4. `FrameHandler`：统一访问接口（L428–L631）

`FrameHandler` 是对 `Frame*` 的薄封装，提供同名方法转发（GetAcc/GetMethod/GetPrevFrame/flags 等），并暴露 `GetVRegisters()`：
- **L623–L627**：`GetVRegisters()` 通过 `frame + Frame::GetVregsOffset()` 取 vregs 起点。

## 5. `StaticFrameHandler` vs `DynamicFrameHandler`（L632–L681）

### 5.1 Static：payload + mirror（L632–L653）

- `GetVReg(i)` 返回 `StaticVRegisterRef(&payload[i], &mirror[i])`（L636–L640）
- mirror 起点就是 `&payload[frame->GetSize()]`（L648–L652）

### 5.2 Dynamic：只有 payload（L655–L669）

- `GetVReg(i)` 返回 `DynamicVRegisterRef(&payload[i])`
- `GetAccAsVReg()` 返回 `acc.AsVRegRef<true>()`

### 5.3 `GetFrameHandler<IS_DYNAMIC>`（L671–L681）

编译期分派到静态/动态 handler：这使得解释器主循环可以用模板参数消除分支。

## 6. `ExtFrame<ExtData>`：语言扩展数据的“前置布局”（L683–L702）

注释画出 ExtFrame 的真实内存布局：
- ExtData 在前
- Frame 在后（紧贴 ExtData + padding）
- vregs VLA 在 Frame 之后

并给出从 `Frame*` 找回扩展数据的方法：`ExtFrame<LangSpecData>::FromFrame(base_frame)->GetExtData()`。

> 这与 04 的 `entrypoints.cpp::CreateFrameWithSize` 中 “extSz 由 LanguageContext 提供” 的实现形成闭环。



