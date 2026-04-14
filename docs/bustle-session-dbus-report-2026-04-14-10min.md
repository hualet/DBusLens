# Bustle Session D-Bus 10 分钟采样分析报告

采样时间：2026-04-14 16:16 到 16:26（Asia/Shanghai）

采样目标：session bus

采样时长：命令运行 600 秒；`profile` 中实际观测到的消息时间跨度约 `599.71s`

原始文件：

- `pcap`: `/tmp/dbus_session_20260414_161624.pcap`
- `profile`: `/tmp/dbus_session_20260414_161624.profile`

## 采集方式

使用命令：

```bash
dbus-monitor --session --pcap
dbus-monitor --session --profile
```

离线分析使用：

```bash
bustle --count /tmp/dbus_session_20260414_161624.pcap
bustle --time /tmp/dbus_session_20260414_161624.pcap
```

## 采集结果概览

总消息数：40821

消息类型分布：

- `mc`：17392
- `mr`：16739
- `sig`：6402
- `err`：288

平均消息速率约为 `68.07 msg/s`。

与此前 1 分钟 `system bus` 样本相比，`session bus` 的流量量级高出两个数量级以上，而且以应用层交互方法调用为主，不是单纯状态广播。

## Bustle 统计摘要

`bustle --count` Top 项：

- `com.cpis.panel.AcquireEngineStat`: 6679
- `com.cpis.panel.Move`: 2393
- `com.cpis.panel.AcquireWindowRect`: 2392
- `com.cpis.panel.SizeChanged`: 1217
- `org.freedesktop.DBus.Properties.Get`: 895
- `org.deepin.dde.TrayManager1.Changed`: 859
- `com.deepin.dde.TrayManager.Changed`: 859
- `com.cpis.panel.UpdateUi`: 761
- `org.deepin.dde.XEventMonitor1.CursorMove`: 676
- `com.deepin.api.XEventMonitor.CursorMove`: 676

`bustle --time` 总耗时 Top 项：

- `org.fcitx.Fcitx.InputContext1.ProcessKeyEvent`: 总计 `3204.3250 ms`，260 次，均值 `12.3243 ms`
- `com.cpis.panel.KeyDown`: 总计 `1525.1980 ms`，135 次，均值 `11.2978 ms`
- `org.fcitx.Fcitx.InputContext1.FocusIn`: 总计 `1398.5500 ms`，264 次，均值 `5.2975 ms`
- `com.cpis.engine.Clear`: 总计 `885.4190 ms`，6 次，均值 `147.5698 ms`
- `org.fcitx.Fcitx.InputContext1.FocusOut`: 总计 `847.7720 ms`，5 次，均值 `169.5544 ms`

## 热点来源

按发送方统计：

- `:1.338`: 15220
- `:1.192`: 12583
- `:1.49`: 2176
- `org.freedesktop.DBus`: 1606
- `:1.517`: 1390
- `:1.195`: 1191
- `:1.129`: 1149
- `:1.522`: 1113
- `:1.229`: 954
- `:1.228`: 859

按目标统计：

- `:1.192`: 12574
- `com.cpis.panel`: 12559
- `<none>`: 6328
- `org.freedesktop.DBus`: 2128
- `:1.195`: 1168
- `:1.129`: 1149
- `:1.338`: 878
- `org.kde.StatusNotifierItem-23919-1`: 834
- `:1.517`: 834

按接口统计：

- 空接口：17027
- `com.cpis.panel`: 14589
- `org.freedesktop.DBus`: 2214
- `org.deepin.dde.XEventMonitor1`: 954
- `com.deepin.api.XEventMonitor`: 954
- `org.freedesktop.DBus.Properties`: 937
- `org.deepin.dde.TrayManager1`: 859
- `com.deepin.dde.TrayManager`: 859
- `com.cpis.engine`: 630
- `org.fcitx.Fcitx.InputContext1`: 624
- `com.canonical.dbusmenu`: 532

按对象路径统计：

- `/com/cpis/panel`: 14589
- `/org/freedesktop/DBus`: 2216
- `/StatusNotifierItem`: 1113
- `/org/deepin/dde/XEventMonitor1`: 954
- `/com/deepin/api/XEventMonitor`: 954
- `/org/deepin/dde/TrayManager1`: 859
- `/com/deepin/dde/TrayManager`: 859
- `/com/cpis/engine`: 630
- `/org/freedesktop/portal/inputcontext/22`: 607
- `/MenuBar`: 532

## 行为分析

### 1. session bus 的主流量来自输入法候选面板链路

最显著的热点是 `com.cpis.panel` 和相关 `com.cpis.engine` 调用，包括：

- `AcquireEngineStat`
- `Move`
- `AcquireWindowRect`
- `Show`
- `Resize`
- `KeyDown`
- `KeyUp`

从消息模式看，这是一个高频 UI 跟随链路：输入上下文变化、光标位置变化、候选窗重定位、面板刷新，形成持续的 request/reply 往返。

### 2. 这不是“随机噪声”，而是明显的交互闭环

和 system bus 以 `PropertiesChanged` 广播为主不同，session bus 中 `mc + mr` 共 34131 条，占比约 83.6%。这说明绝大多数流量是应用间同步交互，而不是被动广播。

换句话说，session bus 的性能问题更可能来自：

- 高频短调用过多
- 单次交互链过长
- 输入法/面板/桌面组件之间的往返放大

### 3. 输入事件和候选面板更新高度耦合

除了 `com.cpis.panel` 之外，还能看到：

- `org.fcitx.Fcitx.InputContext1.ProcessKeyEvent`: 260 次
- `org.fcitx.Fcitx.InputContext1.FocusIn`: 264 次
- `org.deepin.dde.XEventMonitor1.CursorMove`: 676 次
- `com.deepin.api.XEventMonitor.CursorMove`: 676 次

这说明 session bus 样本覆盖到了真实桌面交互过程，而且鼠标/输入法/候选面板之间的联动非常频繁。

### 4. `AcquireEngineStat` 是最值得优先关注的高频调用

`AcquireEngineStat` 单独就有 6679 次，约每秒 11.1 次。虽然其平均耗时不高，`bustle --time` 给出的均值约 `0.1077 ms`，但调用次数极高，已经是明显的总线热点。

如果 DBusLens 要做热点识别，“低延迟但极高频”的调用不能被忽略。

### 5. 真正的时延热点在 Fcitx 输入上下文调用

从累计耗时看，最值得注意的不是 `AcquireEngineStat`，而是：

- `ProcessKeyEvent`：均值约 `12.32 ms`
- `KeyDown`：均值约 `11.30 ms`
- `FocusIn`：均值约 `5.30 ms`
- `Clear` / `FocusOut`：单次开销很高，均值分别约 `147.57 ms` 和 `169.55 ms`

这类调用更可能直接影响输入体验，尤其在焦点切换和输入处理链上。

### 6. 还存在次级的桌面壳层流量

样本中还出现了几个明显但次级的会话总线热点：

- TrayManager `Changed`
- StatusNotifier `NewIcon` / `GetHostServiceName`
- `dbusmenu.LayoutUpdated` / `GetLayout`
- `org.freedesktop.DBus.Properties.Get`

这些流量说明桌面托盘、菜单和状态图标也在持续活跃，但量级仍低于输入法面板链路。

### 7. 时间分布显示“前台交互窗口”非常明显

这 10 分钟并不是均匀忙碌：

- 开始约 0 到 23 秒是明显高峰
- 之后有一段低活跃区
- 约 64 到 127 秒、183 秒之后又出现稳定重复段

这更像真实用户在桌面上的间歇性操作，而不是单个后台服务持续刷流量。

## 与 1 分钟 system bus 样本对比

`system bus` 样本特征：

- 47 条消息
- 全部是 `signal`
- 主要是 `PropertiesChanged`
- 热点在 NetworkManager 和电源服务

`session bus` 样本特征：

- 40821 条消息
- 以 `method call + method return` 为主
- 热点集中在输入法、候选面板、托盘和桌面交互组件
- 能清晰观察到“输入事件 -> 面板更新 -> UI 广播”的交互回路

两者差异非常大，说明 DBusLens 后续在产品设计上最好明确区分：

1. system bus 的“状态广播视图”
2. session bus 的“交互调用链视图”

## 对 DBusLens 的直接建议

优先级最高的能力应该是：

1. 支持 method call / return / signal / error 四类消息分别统计
2. 自动计算“高频热点”和“高累计耗时热点”两个榜单
3. 能把同一调用链上的 `mc -> mr/err` 配对出来
4. 针对高频服务如 `com.cpis.panel` 提供折叠视图，否则时间轴会被淹没
5. 支持按 sender、destination、path、member 维度做 TopN 聚合
6. 对空闲期和交互爆发期做时间分段

## 建议的下一步采样

- 在你明确操作时定向抓一次 session bus，例如连续输入、切换输入法、呼出托盘菜单
- 单独过滤 `com.cpis.panel` 和 `org.fcitx.Fcitx.InputContext1`，做更细的调用链统计
- 在完全空闲的桌面状态下再抓 10 分钟，建立基线，便于和“主动操作”样本对比
