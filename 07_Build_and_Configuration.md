# Chapter 7：构建与配置（GN / CMake / Options & Generated Artifacts）

> 本章把“怎么把这套 VM 编出来，以及运行时/编译器/插件的 options 与生成代码怎么串起来”整理成一张可操作的地图。工程同时支持 **GN** 与 **CMake** 两套构建体系，它们共享同一套“YAML → 代码生成/合并 → 编译链接”的思路。

---

### 1. 构建入口总览

| 体系 | 顶层入口 | 特点 | 你最常改的地方 |
|---|---|---|---|
| GN（OHOS/集成构建） | `BUILD.gn`（顶层） + 各子模块 `*/BUILD.gn` | 通过 gni 控制宏与平台；大量“生成目标”集中在 `*_header_deps` | `runtime/BUILD.gn`、`compiler/BUILD.gn`、`plugins/*/BUILD.gn` |
| CMake（独立/host 工具链） | `CMakeLists.txt`（顶层） + 各子模块 `*/CMakeLists.txt` | `panda_gen_files` 汇总所有生成步骤；`RegisterPlugins.cmake` 自动注册插件 | `runtime/CMakeLists.txt`、`cmake/PostPlugins.cmake`、`cmake/TemplateBasedGen.cmake` |

---

### 2. 生成系统的核心：`panda_gen_files` + PostPlugins

#### 2.1 CMake：`panda_gen_files` 是“所有生成物”的 umbrella target

顶层 `CMakeLists.txt` 明确创建：
- `add_custom_target(panda_gen_files COMMENT "Generate all sources")`

然后在多个模块/脚本里不断 `add_dependencies(panda_gen_files ...)`，使得：
> 只要依赖 `panda_gen_files`，就能保证所有 YAML 合并、模板生成、插件 merge 文件都已产生。

#### 2.2 PostPlugins：把“插件追加内容”拼接到核心生成物

`cmake/RegisterPlugins.cmake` 提供 **merge_plugins machinery**：
- core 侧先 `declare_plugin_file("xxx.h")` 声明一个可被插件填充的“聚合文件”
- 插件侧用 `add_merge_plugin(PLUGIN_NAME "xxx.h" INPUT_FILE "...")` 把内容追加进去

`cmake/PostPlugins.cmake` 在最后阶段做两件事：
- 把各插件贡献的片段 `cat ... > generated/xxx.h` 生成聚合文件
- include 一系列 `*PostPlugins.cmake`，分别为 runtime/compiler/verification 等模块生成最终可编译的头/源

这解释了为什么工程里会出现大量 `...PostPlugins.cmake`：它们就是“生成链路的拼装点”。

---

### 3. YAML → Options/Header：runtime options 如何生成

#### 3.1 runtime/options.yaml 是源，最终会 merge 成 `runtime_options_gen.h`

在 CMake 侧：
- `runtime/RuntimeOptionsPostPlugins.cmake`：
  - 收集 `runtime_options_gen` 的 `RUNTIME_OPTIONS_YAML_FILES`
  - 调用 `templates/merge.rb` 合并成 `runtime_options_gen.yaml`
  - 再调用 `panda_gen_options(...)` 生成 `runtime_options_gen.h`

`panda_gen_options` 的实现位于 `cmake/TemplateBasedGen.cmake`，本质是：
- 使用 `templates/options/options.h.erb` + `templates/common.rb` 把 YAML 渲染为 C++ header
- 生成目录一般在 `${CMAKE_CURRENT_BINARY_DIR}/panda_gen_options/generated/...`

#### 3.2 GN 侧的同构概念

顶层 `BUILD.gn` 中可看到类似的合并步骤（例如 `merge_runtime_options_yamls`）：
- 把 `runtime/options.yaml` 与各插件的 `plugin_runtime_options_yamls` 合并
- 输出到 `$target_gen_dir/runtime_options.yaml`（再被后续生成规则消耗）

> 结论：无论 GN 还是 CMake，options 都来自 YAML，且支持被插件“追加/覆盖”。

---

### 4. runtime/BUILD.gn：头文件生成依赖非常集中

`runtime/BUILD.gn` 有一个非常关键的 group：`arkruntime_header_deps`，其中罗列了 runtime 编译前必须生成的一批目标，例如：
- entrypoints / intrinsics / interpreter-inl 的 ISA 生成物
- `libarkruntime_options_gen_h`（runtime options header）
- verification 的生成物（verifier messages、absint 模板等）
- logger options 等（来自 `libarkbase` 的生成）

这能帮助你快速判断：
> “我改了某个 YAML/模板/插件注入片段后，为什么编译会失败？”——通常是某个生成目标没被触发或 include dir 没加对。

---

### 5. runtime/CMakeLists.txt：链接层面的“真实源文件清单”

`runtime/CMakeLists.txt` 里 `set(SOURCES ...)` 是 runtime 静态/共享库的**源文件真值表**：
- 解释器：`interpreter/interpreter.cpp`
- entrypoints：`entrypoints/entrypoints.cpp`
- 内存管理：`mem/*` + `mem/gc/*`（含 G1/Gen/STW/Epsilon）
- bridge 汇编：按架构追加 `bridge/arch/*/*.S`
- tooling：`tooling/*`（debugger/inspector/sampler）
- profilesaver & jit profiling：`jit/*`、`profilesaver/*`
- class linker / runtime 主体：`class_linker*.cpp`、`runtime.cpp` 等

建议用它做“裁剪/定位”：
- 如果你想确认某个文件是否参与 runtime 构建，先看这里（再对照 GN 的 calculated sources）。

---

### 6. 常见配置落点（你改选项时该去哪）

- **运行时 options**：`runtime/options.yaml`（经合并生成 `runtime_options_gen.h`）
- **编译器 options**：`compiler/compiler.yaml`（同样有 CompilerOptionsPostPlugins 的生成链路）
- **插件 options**：各插件目录下的 `runtime_options.yaml` 或 `plugin_options.yaml`（最终进入合并/生成）
- **logger options**：`libarkbase/panda_gen_options/generated/logger_options.h`（由 libarkbase 的生成链路产出）

---

### 7. 阶段 2（后续扩展建议）

- 给“YAML 合并 → header 生成 → include dirs”画一张跨 GN/CMake 的统一图，并明确每种生成物的输出路径
- 把 `plugins/` 的 RegisterPlugin/merge_plugins 机制写成一篇“如何为新语言/新运行时扩展添加生成代码”的 cookbook
- 补齐 `compiler/*PostPlugins.cmake` 与 `runtime/*PostPlugins.cmake` 的生成物清单（intrinsics/entrypoints/ISA templates 等）


