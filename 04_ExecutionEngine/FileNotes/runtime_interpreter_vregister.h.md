# `runtime/interpreter/vregister.h`（逐行精读｜vreg 与 tag 语义）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：575 行  
> 本文件角色：定义解释器虚拟寄存器（vreg）的最小抽象：  
> - `VRegister`：tagless payload（64-bit）  
> - `StaticVRegisterRef`：payload + mirror(tag)（静态语言）  
> - `DynamicVRegisterRef`：payload 内含 TaggedValue（动态语言）

## 0. 顶部的“tag 兼容性”注释（L34–L49）

文件开头用位域图解释了一种“兼容静态/动态”的 tag 编码模型：最低位是 IsObject 标记。  
但工程实现上选择了更明确的方式：
- **静态语言**：tag 不在 payload，而在 frame 的 mirror vregs（见 `frame.h`）
- **动态语言**：payload 直接存 TaggedValue raw data，用 `IsHeapObject()` 判断对象

> 读这个文件要记住：注释描述的是“概念兼容性”，真实实现以 `StaticVRegisterRef`/`DynamicVRegisterRef` 的 HasObject 为准。

## 1. `VRegisterIface`：统一的 set/get 族（L72–L179）

这是一个 CRTP 接口层，提供：
- `Set(int32/uint32/int64/uint64/float/double/ObjectHeader*)`
- `Get/GetLong/GetFloat/GetDouble/GetReference`
- `GetAs<T>`（对不同类型做 bit_cast 或静态转换）

关键点：
- **Set(ObjectHeader*)** 会做 `mem::ValidateObject`（L118–L123）：解释器把对象指针写入 vreg 时，必须满足 root/heap 可达性基本约束（排障时很重要）。

## 2. `VRegister`：tagless payload（L187–L220）

- 只有 `int64_t v_`，存放“bit 表示”的值。
- `GetValueOffset()` 提供稳定 offset（给汇编/生成代码/调试工具用）。

## 3. `VRegisterRef<T>`：把“tag 语义”交给派生类（L222–L381）

`VRegisterRef` 封装 payload 指针，并把以下语义下发给派生类实现：
- `HasObject()`
- `MovePrimitive/MoveReference/Move`
- `SetPrimitive(...)` / `SetReference(...)`

并在 debug 下提供 `DumpVReg()`：
- 若 HasObject：打印 obj 指针值
- 否则打印 i64/f32/f64/hex 多视图（排障很直观）

## 4. `StaticVRegisterRef`：mirror(tag) 判定对象（L383–L488）

- 额外持有 `mirror_` 指针。
- **HasObject()**：`mirror_->GetValue() == GC_OBJECT_TYPE`（L422–L425）
- SetPrimitive 会把 mirror 置为 PRIMITIVE_TYPE；SetReference 会把 mirror 置为 GC_OBJECT_TYPE。

> 这是静态语言（如 Java/ETS 的 core part）“vreg 类型信息”保存方式的直接证据：tag 不在 payload，而在 mirror。

## 5. `DynamicVRegisterRef`：payload 内 TaggedValue 判定对象（L490–L571）

- **HasObject()**：`TaggedValue(payload_->GetAs<uint64_t>()).IsHeapObject()`（L513–L517）
- `SetReference(ObjectHeader*)`：构造 TaggedValue(obj) 并写 raw data（L561–L565）
- primitive 的 set 不写 mirror（因为没有 mirror）。

> 这与 04 的 OSR/bridge/deopt 中 “动态语言 acc/vreg 取值要用 TaggedValue 判断对象” 完全一致。



