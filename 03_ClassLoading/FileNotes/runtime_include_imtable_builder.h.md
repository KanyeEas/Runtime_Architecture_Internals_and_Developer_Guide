# `runtime/include/imtable_builder.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：`IMTableBuilder` 声明：从 `ITable` 构建 IMT（Interface Method Table），并写回 `Class`。  
> 说明：具体算法在 `runtime/imtable_builder.cpp`（本文件仅声明接口与字段）。

## 1. 依赖与定位（L18–L22）

- **L19**：`class_data_accessor.h`：从 panda_file 的接口方法枚举信息构建 IMT（接口/类两种 Build overload）。
- **L20**：`class-inl.h`：写回 `Class` 的 IMT 区域（`klass->GetIMT()`/offset 等）需要 inline 访问。

## 2. `IMTableBuilder` 的职责（L27–L59）

IMT 的作用：为接口调用提供一个“快速哈希表/索引表”，避免每次遍历 itable。大致流程：
- Build：遍历 itable 的接口方法，把每个方法按某种 id/hash 放入 IMT 的槽位；
- UpdateClass：把 IMT 写入 `Class`（内存位于 Class object 的 IMT 区间）；
- Dump：调试输出。

## 3. API 逐项解释

### 3.1 OVERSIZE_MULTIPLE（L29）
`OVERSIZE_MULTIPLE = 2`：构建 IMT 时可能会把表大小扩大一定倍数以降低冲突（具体策略见 `.cpp`）。

### 3.2 Build（L31–L34）
两种入口：
- `Build(const ClassDataAccessor *cda, ITable itable)`：从 panda_file 的 class 信息 + itable 构建（用于正常加载路径）。
- `Build(ITable itable, bool isInterface)`：从已构造的 itable + 是否接口构建（用于 `BuildClass` 等合成类路径）。

### 3.3 UpdateClass（L35）
把构建结果写回 klass（通常包含：写 `imtSize_`、把 `Method*` 填入 `klass->GetIMT()` 的 span）。

### 3.4 AddMethod（L37）
把某个接口方法加入 imtable：
- `imtable`：目标 span（Method* 数组）
  - `imtableSize`：槽数量
  - `id`：方法 id/hash
  - `method`：实际 Method*（多为接口方法或其解析后的实现）
返回 bool：通常表示是否成功放入/是否需要扩表（具体逻辑见 `.cpp`）。

### 3.5 Get/Set IMTSize（L41–L49）
`imtSize_` 是 builder 的内部状态，最终会用于写回 Class 的 IMT 区域。

## 4. 私有字段（L57–L59）

- `imtSize_`：IMT 大小（槽数量），默认 0。


