# FileNote：`runtime/class_lock.cpp`（ClassLock 的真实行为：线程状态 + per-class condvar）

## 1) 构造：把 managed class object 映射到 `Class*`，并加锁

关键步骤（`ClassLock::ClassLock(const ObjectHeader *obj)`）：

- `cls_ = Class::FromClassObject(obj)`：从 class object 取 runtime `Class*`
- `clsLinkerCtx = cls_->GetLoadContext()`
- `clsMtx_ = clsLinkerCtx->GetClassMutexHandler(cls_)`：拿到 per-class 的 `ClassMutexHandler`
- `ScopedChangeThreadStatus(..., IS_BLOCKED)`：把当前线程状态标为 blocked
- `clsMtx_->Lock()`：进入 recursive mutex

## 2) Wait/Notify：对外语义就是 condvar

- `Wait()`：`ScopedChangeThreadStatus(..., IS_WAITING)` + `clsMtx_->Wait()`
- `Notify()`：`Signal()`
- `NotifyAll()`：`SignalAll()`
- 析构：`Unlock()`

## 3) 你应该如何把它放进 ClassLoading 的心智模型

`ClassLock` 体现了 runtime 内确实存在“按 Class 粒度的 condvar 机制”，但要避免误判：

- **当前 class loading 的去重主线并未使用 ClassLock**（也未直接使用 `GetClassMutexHandler`）
- 所以并发加载同一类时，优先用“重复构建 + InsertClass 去重”的模型理解

对应总述：
- [Flows/Concurrency_and_ClassLock](Flows/Concurrency_and_ClassLock.md)


