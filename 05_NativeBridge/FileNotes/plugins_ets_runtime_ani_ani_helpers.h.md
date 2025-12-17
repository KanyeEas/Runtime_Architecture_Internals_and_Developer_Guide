# `plugins/ets/runtime/ani/ani_helpers.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：声明 ANI/NAPI 侧的“入口点”符号获取函数：
> - `GetANIEntryPoint()`
> - `GetANICriticalEntryPoint()`
>
> 它们通常供编译器/运行时在生成 native 调用桥时查询（对应汇编 entrypoint：`ets_napi_entry_point_*.S`）。

## 1. 两个入口点（L19–L22）

- **L20**：`GetANIEntryPoint()`：普通 NAPI entrypoint（会做 local ref frame、NativeCodeBegin/End 等管理，见 `.cpp` 的 `EtsNapiBegin/EtsNapiEnd`）。
- **L21**：`GetANICriticalEntryPoint()`：critical native entrypoint（减少开销/限制更多，见 `.cpp` 的 `EtsNapiBeginCritical`）。



