# `runtime/interpreter/acc_vregister.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：80 行  
> 本文件角色：定义 accumulator（acc）寄存器：**payload + tag（mirror）**，并提供静态/动态语言两种 `VRegRef` 视图。

## 1. `AccVRegister` 的结构（L25–L76）

- **L29**：acc 是两段 `VRegister`：
  - `payload_`：值（int/float/double/object pointer/raw tagged 等）
  - `mirror_`：tag（静态语言使用；动态语言可不使用）
- **L31–L49**：`GetValue/SetValue` 只操作 payload；`GetTag/SetTag` 只操作 mirror。

## 2. `AsVRegRef`：统一暴露“是否有对象”的语义（L51–L61）

- **动态**（L51–L55）：`AsVRegRef<true>()` → `DynamicVRegisterRef(&payload_)`
- **静态**（L57–L61）：`AsVRegRef<false>()` → `StaticVRegisterRef(&payload_, &mirror_)`

> 这与 04 的 bridge/deopt/OSR 里“读取 acc 的返回值”分支完全一致：  
> - dynamic：看 TaggedValue 是否 heap object  
> - static：看 mirror 的 GC_OBJECT_TYPE

## 3. 偏移：`GetMirrorOffset`（L63–L66）

给汇编/IRTOC/调试工具提供稳定 offset（ABI 友好）。



