# `plugins/ets/isa/isa.yaml`（逐行精读｜ETS ISA 扩展：name-based field/method 指令）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：349 行（相对精炼）  
> 本文件角色：定义 ETS 的 prefix 指令扩展（`ets.*`），把“按名字访问 field/method”作为 bytecode 一级语义暴露出来。  
> 执行引擎角度的关键点：这些指令在 IRTOC fast interpreter 中有专门的 `HANDLE_FAST_ETS_*`，并且大量走 runtime slowpath（lookup_field_by_name / lookup_method_by_name / throw ETS 专用异常）。

---

## 1) prefix 与 namespace（L14–L21）

- **L14–L17**：声明 `prefixes: ets`  
  这意味着 ETS 指令使用 `pref_op_*` 编码格式，并在 dispatch table 中以 `HANDLE_FAST_ETS_*_PREF_*` 命名。
- **L18–L21**：`namespaces: ets`，`quickening: false`（ETS 指令不走 quickening）。

---

## 2) 指令族 A：`ets.ldobj.name*`（L26–L77）

### 2.1 规范语义（pseudo）

关键语义（L38–L55）：

- v（对象）为 null → NPE
- `resolve_field_by_name(field_id)`：
  - 命中 field → 读字段；对小于 32 位的字段做 extend to i32（`ets.ldobj.name` 特有）
  - 未命中 → `resolve_getter_by_name`，存在则调用 getter，否则抛 ETS 专用异常

### 2.2 指令定义（sig/format）

- `ets.ldobj.name v:in:ref, field_id`：
  - `format: pref_op_v_8_id_32`
  - acc: out:b32
- `ets.ldobj.name.64 ...`：acc: out:b64
- `ets.ldobj.name.obj ...`：acc: out:ref

### 2.3 与 IRTOC handler 的对齐（工程锚点）

在 `build/runtime/include/irtoc_interpreter_utils.h` 中可见对应 handler 名称：

- `HANDLE_FAST_ETS_LDOBJ_NAME_PREF_V8_ID32`
- `HANDLE_FAST_ETS_LDOBJ_NAME_64_PREF_V8_ID32`
- `HANDLE_FAST_ETS_LDOBJ_NAME_OBJ_PREF_V8_ID32`

它们的语义实现来自 `irtoc/scripts/interpreter.irt` 中的 `handle_ets_ldobj_name_*` 宏（在 build 的 `interpreter.irt.fixed` 中可直接看到同名宏展开）。

---

## 3) 指令族 B：`ets.stobj.name*`（L78–L131）

语义类似，但是写字段：

- field 命中：按字段位宽（<32）截断后写入
- field 不存在：找 setter 并调用，否则抛 ETS 专用异常

acc 是输入（`acc: in:b32/b64/ref`）。

---

## 4) 指令族 C：`ets.call.name*`（L132–L190）

### 4.1 规范语义（pseudo）

- args[0]（receiver）为 null → NPE
- `resolve_method_by_name(method_id)`
  - abstract → AbstractMethodError
  - else → `acc = call(method, args)`
  - not found → ETS no_such_method_error

### 4.2 三种形态（short / long / range）

- `ets.call.name.short method_id, v1, v2`：最多 2 个额外参数（含 receiver 一共 ≤ 3/4 类似）
- `ets.call.name method_id, v1..v4`：最多 4 个寄存器参数
- `ets.call.name.range method_id, v`：range 版本

### 4.3 与 IRTOC handler 的对齐

对应 handler 名称（在 `irtoc_interpreter_utils.h` 可见）：

- `HANDLE_FAST_ETS_CALL_NAME_SHORT_PREF_V4_V4_ID16`
- `HANDLE_FAST_ETS_CALL_NAME_PREF_V4_V4_V4_V4_ID16`
- `HANDLE_FAST_ETS_CALL_NAME_RANGE_PREF_V8_ID16`

其实现通常会“先 name-based lookup，再复用 `generic_call` 走 I2C/stackless 两条路”。

---

## 5) ETS 的 nullvalue/equals/typeof/nullcheck（L191–L349）

这些指令为 ETS 语义提供额外原语：

- `ets.ldnullvalue / ets.movnullvalue / ets.isnullvalue`
- `ets.equals / ets.strictequals`
- `ets.typeof / ets.istrue / ets.nullcheck`

执行引擎视角：
- 很多会走 runtime entrypoint（例如 `EtsGetTypeofEntrypoint`、`EtsIstrueEntrypoint`、`EtsNullcheck` 等），并需要正确的异常路径处理（`move_to_exception`）。


