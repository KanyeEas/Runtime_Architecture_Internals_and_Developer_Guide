# `runtime/class_linker_context.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：类加载上下文（ClassLoader/Context）基类：负责“已加载类缓存 + 并发协调 + panda files 枚举 + GC roots”  
> 重要提醒：本文件 include 了 GC 相关头（`gc.h/gc_root.h`），但这里只是 **root 列表的容器与更新接口**；屏障/移动/标记等细节属于 Stage2/02（Memory）。

## 1. 文件定位（ClassLinkerContext 的职责边界）

`ClassLinkerContext` 是 ClassLinker 的“加载隔离域”抽象：
- **缓存**：descriptor → `Class*` 的映射（`loadedClasses_`）。
- **并发控制**：
  - `classesLock_` 保护 `loadedClasses_`。
  - `mutexTable_` 为每个 `Class*` 提供一个 `ClassMutexHandler`（递归 mutex + condvar），用于协调同一类的并发加载/初始化（典型：多个线程同时触发某 class 的初始化）。
- **可扩展**：插件可继承并覆写 `LoadClass/EnumeratePandaFiles/GetPandaFilePaths/...` 实现语言特定加载策略。
- **GC roots**：维护 `roots_` 并支持 update（供移动 GC 更新引用）。

## 2. 头部与依赖（L1–L34）

- **L15–L16**：include guard：`PANDA_RUNTIME_CLASS_LINKER_CONTEXT_H_`。
- **L18**：`<atomic>`（本文件字段未直接使用 atomic，但依赖链与宏注解会使用）。
- **L19–L22**：macros/mutex/bit_utils：锁与注解（`GUARDED_BY/ACQUIRE/RELEASE`）。
- **L20**：`object_pointer.h`：对象指针工具（与 GC root 更新相关）。
- **L23**：`mem/refstorage/reference.h`：引用存储相关类型（间接支撑 root/handles）。
- **L24**：`runtime/include/class.h`：`Class` 类型与 descriptor。
- **L25**：panda 容器。
- **L26–L28**：GC：`gc.h/gc_root.h/object_helpers.h`：
  - `ObjectVisitor`/`GCRootUpdater` 等类型被 `VisitGCRoots/UpdateGCRoots` 使用。

## 3. `ClassMutexHandler`（L35–L71）

### 3.1 目的
作为一个小封装：把 `RecursiveMutex + ConditionVariable` 组合起来，提供：
- `Lock/Unlock`
- `Wait/Signal/SignalAll`

用于 “按 Class 粒度” 做并发协调（见后续 `mutexTable_`）。

### 3.2 逐行要点
- **L36**：类定义（注释 NOLINT：不要求显式定义 special members）。
- **L40–L48**：`Lock/Unlock` 直接转发给 `clsHandlerMtx_`，并用线程安全注解 `ACQUIRE/RELEASE`。
- **L50–L53**：`Wait()`：对 condvar 调用 `Wait(&mutex)`（典型条件变量用法）。
- **L55–L63**：`Signal/SignalAll`：唤醒等待者。
- **L65–L66**：禁止 copy/move。
- **L69–L70**：内部字段：递归 mutex + condvar。

> 递归 mutex 的选择暗示：同一线程可能在某些加载/解析路径中重入（例如递归解析依赖类），需要避免死锁。

## 4. `ClassLinkerContext`（L73–L233）

### 4.1 构造与 lang_（L80–L103）
- **L81**：`explicit ClassLinkerContext(SourceLang lang)`：上下文与语言绑定。
- **L99–L102**：`GetSourceLang()`：返回 lang_。

### 4.2 类缓存：Find/Insert/Remove（L83–L131）

#### FindClass（L83–L92）
- **L85**：`LockHolder lock(classesLock_)`：保护 `loadedClasses_`。
- **L86–L91**：在 `loadedClasses_` 里按 descriptor 查找，命中返回 `Class*`。

#### InsertClass（L110–L123）
这里的逻辑值得注意（也提示了潜在的锁顺序问题，后续实现文件里需要验证）：
- **L112**：先锁 `classesLock_`。
- **L113**：调用 `FindClass(klass->GetDescriptor())`：
  - `FindClass` 自己也会锁 `classesLock_`，这里依赖 `classesLock_` 是 `RecursiveMutex`（见 L226）才能重入。
- **L118**：断言插入类的语言与 context 一致（防跨语言污染）。
- **L119**：插入 `loadedClasses_`（key 是 descriptor 指针，以 Mutf8Hash/Equal 比较内容）。
- **L120–L121**：再锁 `mapLock_` 并 `mutexTable_[klass];`：
  - `operator[]` 会默认构造一个 `ClassMutexHandler`，为该 class 预置同步器。
- **L122**：返回 nullptr（语义：如果发现已存在则返回 existing class，否则插入成功返回 nullptr；调用方需据此判断“是否替换为已存在 class”）。

#### RemoveClass（L125–L131）
- 持 `classesLock_` 删除 loadedClasses_ 中 descriptor。
- 持 `mapLock_` 删除 mutexTable_ 中对应条目。

### 4.3 可扩展的加载算法：IsBootContext/LoadClass（L94–L108）
- **L94–L97**：默认不是 boot context。
- **L104–L108**：默认 `LoadClass` 返回 nullptr，插件可 override。

### 4.4 枚举：EnumerateClasses / EnumeratePandaFiles / Chain（L133–L151）

- **EnumerateClasses**（L133–L143）：
  - 在 `classesLock_` 下遍历 loadedClasses_，回调返回 false 则提前终止。
- **EnumeratePandaFiles**（L145）：
  - 默认空实现；派生类应提供“本 context 关联的 panda_file 集合”。
- **EnumeratePandaFilesInChain**（L147–L151）：
  - 用于“链式上下文”（例如 parent loader chain），默认只枚举本 context。

### 4.5 统计与调试输出（L153–L166，L200–L205）
- `NumLoadedClasses()`：返回 map size（带锁）。
- `VisitLoadedClasses(flag)`：遍历所有 loaded classes 并调用 `DumpClass` 输出（log stream）。
- `Dump(std::ostream&)`：打印 loader 地址与 loaded class 数。

### 4.6 GC roots 管理（L168–L193）

#### VisitGCRoots（L168–L173）
- 遍历 `roots_` 并对每个 root 调用 visitor。

#### AddGCRoot（L175–L186）
- 在 `classesLock_` 下做去重（线性扫描 roots_）。
- 不存在则 push_back 并返回 true；重复则 false。

#### UpdateGCRoots（L188–L193）
- 对每个 `root` 调用 `gcRootUpdater(&root)`：
  - 这是一种典型“移动 GC 更新 root 指针”的接口设计。

> 注意：这里没有屏障/压缩逻辑本身，只是调用 updater；updater 的实现属于 GC 子系统（Stage2/02）。

### 4.7 Panda file paths 与 parent loader（L195–L210）
- `GetPandaFilePaths()`：默认返回空 vector，派生类应返回路径列表（AOT class context 等会使用）。
- `FindClassLoaderParent(parent)`：默认 false（链式上下文的 parent 关系由派生类决定）。

### 4.8 per-Class MutexTable：GetClassMutexHandler（L212–L216）
- 在 `mapLock_` 下 `mutexTable_.at(cls)`，返回该 class 的 `ClassMutexHandler*`。
- 该同步器通常被 class initialization / link steps 用于等待/唤醒（已在 `FileNotes/runtime_class_linker.cpp.md` 的并发加载/InsertClass/LoadClass 互斥段落对齐到使用点）。

### 4.9 私有字段（L224–L233）
- **L226**：`classesLock_` 是 `RecursiveMutex`：支撑 InsertClass 里 FindClass 的重入锁。
- **L227–L228**：`loadedClasses_`：
  - key：`const uint8_t*` descriptor（MUTF8）
  - hash/eq：`utf::Mutf8Hash/utf::Mutf8Equal`（按内容而非指针）
  - 宏 `GUARDED_BY(classesLock_)` 标注。
- **L229**：`mapLock_`：保护 `mutexTable_`。
- **L230**：`mutexTable_`：`Class* -> ClassMutexHandler`。
- **L231**：`roots_`：`ObjectHeader*` 的 root 列表。
- **L232**：`lang_`：默认 PANDA_ASSEMBLY。



