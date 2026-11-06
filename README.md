# 中键短语

长按鼠标中键约 0.4 秒，在光标旁弹出短语列表。鼠标移到一条短语上松开，全短语会粘贴进当前文本框。松手时不在任何一行上则取消。

短按中键仍会补发一次点击，可以继续配合 QuickLauncher。中键拖拽（例如浏览器自动滚动）会被这个工具占用。

## 直接使用

到 [Releases](https://github.com/ZHAOYAWHY/midphrase/releases) 下载 `中键短语.exe`，双击运行。不需要安装 Python。

Windows 可能提示未知发布者，选择仍要运行。部分杀毒软件会把单文件程序误报为风险，可添加信任。

托盘图标右键可以编辑短语、导入、导出、切换显示方式，以及退出。

## 短语

- 简介：列表上看到的短名称
- 全短语：松开后实际粘贴的文字
- 显示方式：简介、全短语、简介+全短语

数据保存在 `%APPDATA%\PhraseWheel\phrases.json`。

## 导入导出

导出为 UTF-8 文本。一行一条，简称和全短语之间用一个 Tab。以 `#` 开头的行是说明，导入时会忽略。

## 从源码运行

需要 Windows 和 Python 3。

```bat
py -3 -m midphrase
```

也可以双击 `启动短语轮盘.bat`。已经在运行时再开一次不会重复挂钩。

## 打包单文件

```bat
py -3 -m pip install pyinstaller
构建单文件.bat
```

生成 `dist\midphrase.exe`。

