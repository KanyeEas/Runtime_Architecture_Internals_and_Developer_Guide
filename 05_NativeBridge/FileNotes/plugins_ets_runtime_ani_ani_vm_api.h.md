# `plugins/ets/runtime/ani/ani_vm_api.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：声明 ANI VM API 的导出入口：`ark::ets::ani::GetVMAPI()`。  
> 该函数返回指向外部 ABI 结构体 `__ani_vm_api` 的指针，供 C 侧通过函数指针表调用 `DestroyVM/GetEnv/Attach/Detach` 等操作（定义见 `ani_vm_api.cpp`）。

## 1. 外部 ABI 前置声明（L19）

- **L19**：`struct __ani_vm_api;`  
  注释说明这是来自外部 header 的接口类型；本仓库只做前置声明以避免引入外部头导致 ABI 污染。

## 2. 对外导出函数（L21–L23）

- **L21–L23**：`const __ani_vm_api *GetVMAPI();`  
  语义：返回静态表地址（通常是 `static const __ani_vm_api VM_API = {...}` 的地址）。



