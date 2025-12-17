# Flow：ETS Context 的 native 链式加载 vs managed 回退

## 0) 在端到端主线图中的位置

- 总入口：[ClassLoading_EndToEnd](ClassLoading_EndToEnd.md)（“ETS：context 的 native→managed 两段式加载”框）

## 1) 为什么 ETS 要这么做

ETS 的非 boot 类加载由 managed `RuntimeLinker` 驱动（类似 class loader），但 VM 内部线程（JIT/AOT 等）不能随意 re-enter managed。  
因此 `EtsClassLinkerContext::LoadClass` 采用“两段式”：
- **native 优先**：仅对白名单 linker（coreAbcRuntimeLinker/coreMemoryRuntimeLinker）复刻链式查找逻辑
- **必要时 managed 回退**：只允许在 managed 线程/协程中调用 `RuntimeLinker.loadClass(final)`

## 2) Mermaid：两段式加载

```mermaid
sequenceDiagram
  participant Ctx as EtsClassLinkerContext
  participant Chain as RuntimeLinker链(parent+shared libs)
  participant CL as ClassLinker(core)
  participant Managed as managed RuntimeLinker.loadClass

  Ctx->>Ctx: FindClass(descriptor)
  alt 命中缓存
    Ctx-->>Ctx: return Class*
  else 未命中
    Ctx->>Chain: TryLoadingClassFromNative
    alt 链遍历成功且找到/或有错误
      Chain->>CL: GetClass/LoadClass（boot 走 filter+bootPandaFiles）
      CL-->>Ctx: Class* 或 error
    else 链遍历失败（非白名单linker）
      Ctx->>Ctx: 仅 managed 线程允许回退
      alt 非 managed 线程
        Ctx-->>Ctx: CLASS_NOT_FOUND / nullptr
      else managed 线程
        Ctx->>Managed: loadClass(runtimeLinker, className, nullptr)
        Managed-->>Ctx: class object / exception
        Ctx-->>Ctx: Class* / nullptr
      end
    end
  end
```

## 3) 证据链

- [FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp.md)
- [FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp.md)（CreateApplicationRuntimeLinker）

## 下一步（新人推荐）

- 想看“为什么非 managed 线程禁止回退”的决策树版本 → [../Newbie_MinDebug_Playbook](../Newbie_MinDebug_Playbook.md)（实验 2）
- 想把 “GetClass/LoadClass 主线” 与 ETS 特化对齐 → [GetClass_and_LoadClass](GetClass_and_LoadClass.md)


