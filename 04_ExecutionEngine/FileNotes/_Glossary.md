# 04_ExecutionEngine / FileNotes 术语速查（Glossary）

> 读 04 章时最常迷路的是：**Frame/VReg/Acc 与 entrypoint/bridge/deopt/OSR 的边界**。  
> 这里把关键名词统一解释，并尽量给出本章内的跳转（不强制跨章）。

## 执行状态与帧

- **PC（program counter）**：当前解释执行到的字节码位置（指令地址/偏移）。解释器主循环不断“取指→执行→更新 PC”。
- **Frame（解释器帧）**：解释器的“执行上下文”，通常包含：
  - 当前 Method/Bytecode 的引用
  - vreg 数组（虚拟寄存器）
  - accumulator（acc）
  - 上一帧链接（用于返回/异常 unwind）
  - FrameKind（解释器/编译态边界识别）
- **VRegister（vreg）**：虚拟寄存器槽位，承载局部变量/临时值。常见实现是 64-bit payload +（静态语言）mirror/tag。
- **Acc（accumulator）**：累加器寄存器，很多指令以 acc 作为隐式输入/输出（类似“栈顶但不是栈 VM”）。

## entrypoint / bridge

- **entrypoint（方法入口点）**：`Method` 上保存的“下一次调用该方法应该跳到哪里”的指针：
  - 解释器入口（或 C2I bridge）
  - 已编译代码入口（JIT/AOT）
  - native 入口（ANI 等，跨章 05）
- **I2C（Interpreter-to-Compiled）**：解释器调用编译代码的桥接。
- **C2I（Compiled-to-Interpreter）**：编译代码回退解释器的桥接（deopt/异常/慢路径常见）。
- **FrameKind**：区分当前栈帧属于解释器还是编译代码（StackWalker/Deopt 需要靠它做正确遍历/重建）。

## deopt / OSR / stack walking

- **deoptimization（去优化）**：当编译代码依赖的假设失效或需要回退时，把“编译态执行状态”恢复成“解释器可继续执行的 Frame/VRegs/PC/Acc”。
- **OSR（On-Stack Replacement）**：在方法/循环执行中途，把解释器帧切换到“OSR 编译版本”继续跑（常见触发点：循环回边）。
- **StackWalker**：统一栈遍历抽象：既能遍历解释器帧，也能遍历编译帧；服务于调试、异常、profiling、以及 deopt/OSR 边界判断。

## 编译器接口（接口视角）

- **PandaRuntimeInterface（runtime/compiler.*）**：runtime 侧提供给 compiler 的接口：解析类/方法/字段、取代码、设置 compiled entrypoint、安装 OSR code 等。
- **CompilerInterface（runtime/include/compiler_interface.h）**：更底层的“编译产物与 runtime 交互”接口（例如写入 entrypoint/查询状态位等）。





