# `runtime/bridge/bridge.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：52 行  
> 本文件角色：**声明解释器↔编译代码互调的 ABI（I2C/C2I）**，并提供若干“桥接/桩函数”指针获取接口。

## 0. 头文件结构（L16–L27）

- **L16–L17**：include guard。
- **L19–L20**：只引入基础类型与导出宏（`PANDA_PUBLIC_API`），这是典型的“ABI 声明头”风格：不把重依赖引入到所有调用点。
- **L24–L26**：前置声明 `Method`/`Frame`/`ManagedThread`，强调：桥接函数签名跨模块使用，需要保持稳定。

## 1. I2C：Interpreter → Compiled（L28–L33）

- **L28–L29**：`InterpreterToCompiledCodeBridge` / `InterpreterToCompiledCodeBridgeDyn`  
  - `extern "C"`：避免 C++ name mangling，使汇编/代码生成能用固定符号名链接。
  - `Dyn` 版本用于动态语言（或 method/class 信息不完备的场景），其返回值/参数约定可能不同（详见 `bridge.cpp` 中对 dynamic 的分支，以及 `StackWalker::IsDynamicMethod` 的判定）。
- **L30–L32**：`InvokeCompiledCodeWithArgArray*`  
  - 这组更像“通用调用入口”：用参数数组调用 compiled code（静态版用 `int64_t*`，动态版用 `uint64_t*` + `argc`）。
  - 典型用途：从解释器/运行时辅助路径（或某些 stub）以统一方式调用已编译入口。

## 2. C2I：Compiled → Interpreter（L34–L37）

- **L34**：`InvokeInterpreter(thread, pc, frame, lastFrame)`  
  - **这是“从编译态回解释器继续执行”的 C++ 骨架入口**，`bridge.cpp` 里会负责：
    - 切换 `thread` 当前帧 & FrameKind（`IsCurrentFrameCompiled=false`）
    - 调 `interpreter::Execute(...)`
    - 从 `acc` 取回返回值（静态/动态分支不同）
    - `FreeFrame(frame)`，并处理“内联帧/找 catch”相关循环
- **L36–L37**：`CompiledCodeToInterpreterBridge*`  
  - 这两个是 **汇编层面的“边界帧 stub”**（真正的入口符号），`GetCompiledCodeToInterpreterBridge*` 会返回它们的地址，用于写入 method 的 entrypoint 或在栈遍历时识别边界。

## 3. 其它桩函数（L38–L40）

- **L38**：`AbstractMethodStub()`：抽象方法调用时的统一失败路径（通常抛异常/触发 abort）。
- **L39**：`DefaultConflictMethodStub()`：默认接口方法冲突（03 章 IMT/ITable 冲突语义的执行侧落点）。

## 4. “取地址”接口（L41–L49）

- **L41**：`GetCompiledCodeToInterpreterBridge(const Method *method)`  
  - 依据 `method` 是否动态语言返回 `CompiledCodeToInterpreterBridge` 或 `...Dyn`。
- **L43–L46**：无参版本直接返回静态/动态的 stub 地址。
- **L47–L49**：返回抽象方法/冲突方法 stub 地址。

> 结论：`bridge.h` 的设计核心是“**稳定 ABI + 可按语言/模式选择不同边界 stub**”，以支撑解释器/编译器/汇编桥/栈遍历对同一边界的共识。




