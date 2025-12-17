# `runtime/include/method.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：运行时 `Method` 元数据对象（签名/访问标志/派发索引/入口点/热点与验证状态/ProfilingData 复用指针）  
> 交叉依赖：执行引擎（解释器/桥接/Frame）与 Memory（ObjectHeader/屏障）都被它直接 include；本章聚焦“契约与状态”，细节实现分别跳转到 04/02。

## 1. 文件定位（Method 在运行时类型系统里的地位）

`Class` 是“类元数据对象”，而 `Method` 是“方法元数据对象”。它需要同时服务：
- **类链接（03）**：vtable/itable/IMT 构建与派发索引（`vtableIndex`）、default interface method 标记等。
- **执行引擎（04）**：解释器与编译代码入口点切换（`compiledEntryPoint_`）、Invoke/InvokeDyn/InvokeContext、Frame 创建与销毁。
- **JIT/PGO（04/06）**：hotness counter、profile saver 触发、ProfilingData 挂载。
- **验证（06）**：verification stage 位存储在 `accessFlags_` 的 bitfield 中。

本文件中最关键的设计点是：**把大量状态塞进 `accessFlags_` 的 bitfield + 少量原子指针缓存**，以便在多线程/多执行模式下快速读写。

## 2. 头部与依赖（L1–L64）

### L15–L37：include guard 与依赖
- **L15–L16**：include guard：`PANDA_RUNTIME_METHOD_H_`。
- **L23**：`intrinsics_enum.h`：intrinsic id（JIT/解释器的内建函数识别）。
- **L24–L25**：arch/logger：与运行时日志/平台相关工具。
- **L26–L30**：`libarkfile/*`：从 panda_file 读取 code/method 元数据（`CodeDataAccessor/MethodDataAccessor/modifiers`）。
- **L31**：`runtime/bridge/bridge.h`：获取 C2I bridge：`GetCompiledCodeToInterpreterBridge`/Dyn（执行引擎依赖点）。
- **L32**：`compiler_interface.h`：与编译器交互（入口点设置等）。
- **L33**：`class_helper.h`：`ClassWordSize/OBJECT_POINTER_SIZE` 等（指针模型）。
- **L34–L35**：arena 容器与智能指针。
- **L36**：`interpreter/frame.h`：Frame 结构与 `Frame::GetAllocSize`（执行引擎依赖点）。
- **L37**：`value.h`：静态语言调用的 `Value` 参数/返回值类型。

### L41–L54：AccVRegisterT 条件类型别名
- **L45–L54**：在 `PANDA_ENABLE_GLOBAL_REGISTER_VARIABLES` 打开时，使用不同的 accumulator 类型别名 `AccVRegisterT`（为性能/ABI 优化做开关）。

### L56–L64：FrameDeleter
- **L56–L64**：`FrameDeleter` 是一个持有 `ManagedThread*` 的自定义 deleter，用于 `PandaUniquePtr<Frame, FrameDeleter>` 在退出时释放 frame（其 operator() 实现不在此文件）。

## 3. `Method::Proto` / `Method::ProtoId`（L84–L172）

### 3.1 Proto：方法签名的“展开版本”
- **L84–L137**：`class Proto`：
  - `ShortyVector`：`panda_file::Type` 序列（shorty[0] 是返回类型）。
  - `RefTypeVector`：引用类型的 descriptor 字符串视图（与 shorty 中 REFERENCE 对应位置关联）。
  - `Proto(pf, protoId)`：可从 panda_file 的 proto item 构建（实现不在此文件）。
  - `GetReturnType()`：返回 shorty_[0]（约定：shorty 的第 0 位是返回值类型）。
  - `GetReturnTypeDescriptor()`、`GetSignature()`：导出 API（实现不在此文件）。
  - 具备 copy/move 语义，便于作为值对象使用。

### 3.2 ProtoId：签名的“惰性标识版本”
- **L139–L172**：`class ProtoId`：
  - 持有 `const panda_file::File&` 与 `EntityId protoId_`。
  - `operator==(ProtoId)`/`operator==(Proto)`：允许把 ProtoId 与 Proto 或其他 ProtoId 比较（比较规则由实现决定，通常会解析 proto item）。
  - 设计意图：在不展开 shorty/refTypes 的情况下，以轻量 id 表示签名（被 vtable builder 用于 override/compat 判断）。
  - 禁止 copy operator 与 move（保留引用语义；但允许 copy ctor）。

## 4. Method 的构造与拷贝构造（L174–L209）

### 4.1 主构造函数（L174–L176）
`Method(Class *klass, const File *pf, EntityId fileId, EntityId codeId, accessFlags, numArgs, shorty)`：
- 把“归属类/文件定位/code 定位/访问标志/参数个数/shorty”绑定到 method 对象上。
- 具体初始化细节在实现处逐行确认（不在本头文件范围内）。

### 4.2 拷贝构造（只允许 `explicit Method(const Method*)`）（L178–L208）
这里的拷贝构造非常关键：它展示了 Method 的多线程内存序契约。

- **L180–L183**：以 `memory_order_acquire` 读取 `accessFlags_`，确保依赖于 flags 的其它读取在 acquire 之后可见。
- **L186–L190**：浅拷贝 `pandaFile_ / fileId_ / codeId_ / shorty_ / saverTryCounter_`。
- **L193–L196**：复制 `nativePointer`（relaxed），因为后续会做 release store（compiledEntryPoint_）来发布必要依赖。
- **L198–L202**：设置 `compiledEntryPoint_`：
  - native 方法：复用原 `GetCompiledEntryPoint()`；
  - 非 native：重置为 `GetCompiledCodeToInterpreterBridge(method)`（即默认走解释器桥接入口）。
  - 使用 `memory_order_release` 发布。
- **L204–L206**：把 `numVregs_` 与 `instructions_` 以 release 发布（为并发读缓存提供同步点）。
- **L207**：初始化编译状态为 `NOT_COMPILED`（写入 accessFlags bitfield）。

> 结论：Method 的拷贝不是“简单 memcpy”，而是按访问标志/入口点/缓存字段的并发约束进行重建。

## 5. code 缓存：`GetNumVregs` / `GetInstructions`（L222–L259）

这两者都是“惰性初始化缓存”：
- **GetNumVregs**：
  - 若 `codeId_` 无效 → 0
  - acquire 读 `numVregs_`，若为 `NUM_VREGS_UNKNOWN` 则从 `CodeDataAccessor::GetNumVregs` 读取并以 release 写回。
- **GetInstructions**：
  - 若 `codeId_` 无效 → nullptr
  - acquire 读 `instructions_`，若为空则从 `CodeDataAccessor::GetInstructions` 读取并以 release 写回。

> 这套模式确保：并发线程读取同一个 Method 的指令/寄存器数时不会数据竞争，同时避免每次都访问 panda_file。

## 6. Invoke 系列（L261–L318）

本段定义了 Method 作为“可执行实体”的几种入口（实现分散在 `.cpp` 或其他 inl）：

- **L265**：`Value Invoke(thread, args, proxyCall)`：静态语言调用入口（args 必须匹配签名）。
- **L279**：`InvokeDyn`：动态语言调用入口（TaggedValue 参数，args[0] 约定为 callee function object）。
- **L285**：`InvokeEntry`：更底层入口，显式给出 frame/pc 等（用于 bridge/解释器重入）。
- **L295**：`InvokeContext`：ECMAScript generator 等“恢复执行上下文”入口。
- **L310–L317**：native 方法 frame 进入/退出：`EnterNativeMethodFrame` 与 `ExitNativeMethodFrame`。

> 交叉引用（执行引擎章节 04）：这些入口最终会在解释器执行、I2C/C2I bridge、以及 native 调用路径之间切换。

## 7. 入口点与编译状态（L411–L483）

### 7.1 compiled entrypoint（L411–L437）
- `GetCompiledEntryPoint()`：acquire 读 `compiledEntryPoint_`。
- `SetCompiledEntryPoint(ep)`：release 写 `compiledEntryPoint_`。
- `SetInterpreterEntryPoint()`：若非 native，把 entrypoint 重置为 `GetCompiledCodeToInterpreterBridge(this)`（默认解释器入口）。

### 7.2 HasCompiledCode（L439–L444）
通过比较 entrypoint 是否等于 “C2I bridge（静态/动态）” 来判定是否已安装编译代码入口。

### 7.3 编译状态 bitfield（L446–L482）
编译阶段（NOT_COMPILED/WAITING/COMPILATION/COMPILED/FAILED）被编码在 `accessFlags_` 的某个位段中：
- `GetCompilationStatus()`：从 `accessFlags_` 中取 mask+shift。
- `SetCompilationStatus(new)`：读旧值（acquire），改位段后以 release store。
- `AtomicSetCompilationStatus(old,new)`：CAS 循环，只有当当前状态等于 old 才更新。

> 这说明：Method 的 compilation stage 是一个并发可更新状态机，JIT/AOT/OSR 线程会通过 CAS 协调。

## 8. accessFlags 与各种谓词（L520–L666）

大量 `IsStatic/IsNative/IsPublic/...` 都采用同一模式：
- acquire 读 `accessFlags_`，按 `ACC_*` 位判断。
- 更新类 flag（例如 `SetProfiled/SetDestroyed/SetHasSingleImplementation/SetIntrinsic/SetIsDefaultInterfaceMethod`）采用 `fetch_or/fetch_and` 的 `acq_rel`。

关键点：
- `SetIntrinsic` 会先以 relaxed 写 `intrinsicId_`，再以 `fetch_or(acq_rel)` 设置 `ACC_INTRINSIC`，用后者作为发布屏障。
- `IsDestroyed/IsProfiled` 等标志对外暴露 method 的生命周期/运行时状态（供 profiler/verification 等使用）。

## 9. 派发索引与 native/profiling 指针复用（L693–L743，L1000–L1035）

### 9.1 vtableIndex（L693–L701）
- `SetVTableIndex/GetVTableIndex` 存在 `Storage16Pair` 的 `vtableIndex` 字段中（非原子）。
- vtable builder 的 `UpdateClass` 会为接口与类方法写回这个索引：
  - 接口：接口方法序号（供 itable 的 `methods_[vtableIndex]` 取实现）
  - 类：vtable 序号（供 vtable 派发）

### 9.2 nativePointer 与 profilingData 复用 union（L703–L717，L863–L903，L1000–L1005）
- `PointerInMethod` union：要么是 `nativePointer`（native/proxy），要么是 `profilingData`（非 native/proxy）。
- `SetNativePointer/GetNativePointer` 仅允许在 `IsNative() || IsProxy()` 下调用，并用 relaxed 原子访问（没有额外同步保证）。
- `GetProfilingData*`：
  - native/proxy 返回 nullptr
  - 否则 acquire 读 `profilingData`

> 设计含义：同一块指针槽复用两种语义，靠 `ACC_NATIVE/ACC_PROXY` 进行“类型判别”。

## 10. default interface method / constructor 标志（L731–L760）

- `SetIsDefaultInterfaceMethod()`：`fetch_or(ACC_DEFAULT_INTERFACE_METHOD, acq_rel)`。
- `IsDefaultInterfaceMethod()`：acquire 读 flag。
- `IsConstructor()`：acquire 读 `ACC_CONSTRUCTOR`。
- `IsInstanceConstructor()`：constructor 且非 static。
- `IsStaticConstructor()`：constructor 且 static。

这些标志会直接影响：
- vtable builder 在 `ResolveVirtualMethod` 的接口分支中，是否走 IMT/ITable（代码里明确排除 default interface methods）。
- 类初始化与 `<clinit>` 识别（static constructor）。

## 11. layout 偏移暴露（L762–L823）

大量 `Get*Offset()` 使用 `MEMBER_OFFSET` 计算字段偏移：
- accessFlags/numArgs/vtableIndex/hotnessCounter/classWord/compiledEntryPoint/pandaFile/codeId/nativePointer/shorty/numVregs/instructions 等。

用途：解释器/桥接/汇编快路径可直接用偏移访问 method 元数据。

## 12. 唯一 id、profiling、验证（L833–L935，L905–L933）

### 12.1 UniqId（L834–L850）
- `CalcUniqId(file,fileId)`：把 `file->GetUniqId()` 左移 32 bit，再 OR 上 `fileId offset`。
- `GetUniqId()`：返回上述组合 id（synthetic method 另有重载入口）。

### 12.2 Profiling（L856–L903）
- `InitProfilingData/StartProfiling/StopProfiling`：导出接口（实现不在此文件）。
- `IsProfiling/IsProfilingWithoutLock`：以 profilingData 是否为 nullptr 判断。

### 12.3 VerificationStage（L78–L80，L905–L933）
- verification stage 也存放在 `accessFlags_` 的 bitfield 中（mask+shift）。
- `SetVerificationStage(new)`：CAS loop 更新位段（acq_rel）。
- `Verify/TryVerify`：导出验证入口（实现不在此文件，见 verification 章节）。

## 13. 私有字段布局（L1000–L1035）

`Method` 的核心字段如下：
- `accessFlags_`：原子 uint32，承载大量位段（访问标志 + compilation/verification stage + runtime flags）。
- `numArgs_`：参数数量。
- `Storage16Pair`：`vtableIndex`（uint16）+ `hotnessCounter`（int16）。
- `classWord_`：以 `ClassHelper::ClassWordSize` 存储的类指针（可能是压缩指针模型）。
- `compiledEntryPoint_`：原子入口点指针（解释器 bridge 或 JIT/AOT 代码）。
- `pandaFile_/fileId_/codeId_/shorty_`：指向 panda_file 的定位信息与签名 shorty。
- `pointer_` union：nativePointer / profilingData。
- `intrinsicId_`：intrinsic 编号（原子）。
- `instructions_` / `numVregs_`：惰性缓存（原子，可在 const 方法中写）。

文件尾 `static_assert(!std::is_polymorphic_v<Method>)` 强制 `Method` 不是多态类型（保证布局稳定、可用于 offset 快路径）。



