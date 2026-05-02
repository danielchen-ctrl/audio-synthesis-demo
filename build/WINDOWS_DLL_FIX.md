# Windows 打包 - Python DLL 问题修复

## 问题描述

打包后的应用启动时报错：
```
Failed to load Python DLL 'D:\_internal\python311.dll'
LoadLibrary: 找不到指定的模块。
```

## 根本原因

PyInstaller 在 Windows 上打包时，会将 `python3xx.dll` 放在 `_internal` 目录下，但 PyInstaller 的 bootloader（启动器）期望在可执行文件的**同级目录**找到这个 DLL。

## 解决方案

### 方法 1: 自动修复（推荐）

使用更新后的构建脚本，它会自动将 Python DLL 复制到正确位置：

```powershell
cd D:\ui_auto_test\audio-synthesis-demo
.\build\build_win.ps1 -CleanBuild
```

构建脚本会在步骤 4.5 自动执行 DLL 修复。

### 方法 2: 手动修复

如果已经打包完成，可以手动运行修复脚本：

```powershell
cd D:\ui_auto_test\audio-synthesis-demo
.\build\fix_python_dll.ps1 -DistDir "dist\SceneDialogueDemo"
```

### 方法 3: 直接复制（临时方案）

```powershell
cd D:\ui_auto_test\audio-synthesis-demo\dist\SceneDialogueDemo
Copy-Item "_internal\python311.dll" -Destination "." -Force
Copy-Item "_internal\python3.dll" -Destination "." -Force
```

## 验证修复

### 1. 检查 DLL 位置

```powershell
cd D:\ui_auto_test\audio-synthesis-demo\dist\SceneDialogueDemo
Get-Item "python*.dll"
```

**预期输出**：
```
python3.dll    - 约 60 KB
python311.dll  - 约 5.5 MB
```

### 2. 测试应用启动

```powershell
.\SceneDialogueDemo.exe
```

**预期结果**：
- 应用窗口正常打开
- 无错误弹窗

### 3. 功能测试

在应用中：
1. 选择职业：医疗健康
2. 设置参数：2人，500字
3. 点击"生成对话"
4. 验证对话文本生成成功

## 文件结构（修复后）

```
dist/SceneDialogueDemo/
├── SceneDialogueDemo.exe           # 主程序
├── python3.dll                     # Python基础DLL（必须在根目录）
├── python311.dll                   # Python 3.11 DLL（必须在根目录）
└── _internal/                      # 内部资源
    ├── python3.dll                 # 副本（可选，不影响运行）
    ├── python311.dll               # 副本（可选，不影响运行）
    ├── base_library.zip            # Python标准库
    ├── static/                     # Web界面
    ├── template_bank/              # 模板库
    ├── domain_kb/                  # 知识库
    └── bin/
        └── ffmpeg.exe              # 音频处理工具
```

## 技术细节

### PyInstaller Bootloader 查找顺序

1. 可执行文件同级目录（`SceneDialogueDemo.exe` 所在目录）
2. `_internal` 目录（但 bootloader 通常在步骤1失败后就不再尝试）
3. 系统 PATH

### 为什么需要手动复制

PyInstaller 的 `binaries` 配置项在打包时会将文件放到 `_internal` 目录，除非：
- 使用 `--onefile` 模式（但会导致启动慢）
- 手动修改 `Analysis.binaries` 列表的目标路径

我们的解决方案是在打包完成后，自动复制 DLL 到根目录。

## 其他可能的 DLL 错误

### 1. "找不到 VCRUNTIME140.dll"

**解决方法**：安装 Visual C++ Redistributable
```
https://aka.ms/vs/17/release/vc_redist.x64.exe
```

### 2. "找不到 MSVCP140.dll"

**解决方法**：同上，安装 Visual C++ Redistributable

### 3. "找不到 api-ms-win-*.dll"

**解决方法**：
1. 更新 Windows 系统
2. 或安装 KB2999226 补丁

## 避免问题的最佳实践

### 打包前检查清单

- [ ] Python 版本：3.8-3.11（推荐 3.11）
- [ ] PyInstaller 版本：6.0+
- [ ] 系统：Windows 10/11
- [ ] 磁盘空间：至少 2GB

### 打包命令

```powershell
# 完整清理打包（推荐）
.\build\build_win.ps1 -CleanBuild

# 快速增量打包（仅当代码小改时）
.\build\build_win.ps1

# 跳过虚拟环境（使用系统 Python）
.\build\build_win.ps1 -SkipVenv
```

### 分发前测试

1. **在干净的测试机器上运行**
   - 不要在开发机器上测试
   - 测试机不应安装 Python

2. **检查文件完整性**
   ```powershell
   # 检查 ZIP 完整性
   Expand-Archive SceneDialogueDemo_win_x64.zip -DestinationPath "test_extract"
   cd test_extract\SceneDialogueDemo
   .\SceneDialogueDemo.exe
   ```

3. **验证资源文件**
   - 确认 `_internal/static/` 存在
   - 确认 `_internal/template_bank/` 存在
   - 确认 `_internal/bin/ffmpeg.exe` 存在

## 故障排除

### 应用启动后立即崩溃

**检查控制台输出**（spec文件中 `console=True`）：
```powershell
.\SceneDialogueDemo.exe
# 查看错误信息
```

### 应用启动慢（10秒以上）

**原因**：杀毒软件扫描

**解决方法**：
1. 将应用目录添加到杀毒软件白名单
2. 使用 UPX 压缩（在 spec 文件中已启用）

### 音频生成失败

**检查 ffmpeg**：
```powershell
cd dist\SceneDialogueDemo\_internal\bin
.\ffmpeg.exe -version
```

## 更新记录

- **2026-02-03**: 添加自动 DLL 修复脚本
- **2026-02-03**: 更新构建脚本集成 DLL 修复
- **2026-02-02**: 初始文档创建

## 参考链接

- PyInstaller 文档: https://pyinstaller.org/en/stable/
- Python DLL 问题: https://github.com/pyinstaller/pyinstaller/issues/4629
- Windows Redistributables: https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
