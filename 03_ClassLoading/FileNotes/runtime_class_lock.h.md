# FileNote：`runtime/class_lock.h`（per-class lock/condvar 的 RAII 包装）

## 0) 这份 FileNote 覆盖什么

本文件定义 `ClassLock`：一个围绕 `ClassLinkerContext::ClassMutexHandler` 的 RAII 封装，提供 `Wait/Notify/NotifyAll`。

注意：它是“通用工具/潜在接入点”，**当前 `runtime/class_linker.cpp` 的类加载去重主线并未使用它**；并发去重主要依赖 `InsertClass`（见 [Flows/Concurrency_and_ClassLock](Flows/Concurrency_and_ClassLock.md)）。

## 1) 核心接口

- `ClassLock(const ObjectHeader *obj)`：从 managed class object 提取 `Class*` 并加锁
- `Wait()`：condvar wait
- `Notify()/NotifyAll()`：signal/signalAll
- `~ClassLock()`：解锁

## 2) 证据链

- 实现：`runtime/class_lock.cpp`
- 依赖：`runtime/class_linker_context.h`（`ClassMutexHandler` 与 `GetClassMutexHandler`）


