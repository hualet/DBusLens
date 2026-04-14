# Bustle 系统 D-Bus 1 分钟采样分析报告

采样时间：2026-04-14 16:10 左右（Asia/Shanghai）

采样目标：system bus

采样时长：命令运行 60 秒；`profile` 中实际观测到的消息时间跨度约 `57.02s`

原始文件：

- `pcap`: `/tmp/dbus_system_20260414_161007.pcap`
- `profile`: `/tmp/dbus_system_20260414_161007.profile`

## 采集方式

使用命令：

```bash
dbus-monitor --system --pcap
dbus-monitor --system --profile
```

离线分析使用：

```bash
bustle --count /tmp/dbus_system_20260414_161007.pcap
bustle --time /tmp/dbus_system_20260414_161007.pcap
```

## 采集限制

本机 system bus 策略拒绝了 `org.freedesktop.DBus.Monitoring.BecomeMonitor`，`dbus-monitor` 回退到传统 eavesdropping 模式。

这意味着：

- 抓到的是“可旁路观察到”的 system bus 流量，不一定覆盖全部系统消息
- 结果适合做热点和节奏判断，不适合当作系统总线全量基线

## 基础统计

总消息数：47

消息类型分布：

- `sig`: 47

`bustle --count` 结果：

- `org.freedesktop.DBus.Properties.PropertiesChanged`: 30
- `org.deepin.dde.Power1.BatteryDisplayUpdate`: 2
- `com.deepin.system.Power.BatteryTimeToFullChanged`: 2
- `com.deepin.system.Power.BatteryDisplayUpdate`: 2
- `com.deepin.system.Power.BatteryPercentageChanged`: 1

`bustle --time` 无有效输出，原因是本次样本中没有可形成请求/应答配对的 method call，基本全是广播 signal。

平均消息速率约为 `0.82 msg/s`（按 57.02 秒内 47 条估算）。

## 热点来源

按发送方统计：

- `:1.13`: 16
- `org.freedesktop.DBus`: 10
- `:1.88`: 8
- `:1.62`: 7
- `:1.57`: 6

按接口统计：

- `org.freedesktop.DBus.Properties`: 30
- `org.freedesktop.DBus`: 10
- `com.deepin.system.Power`: 5
- `org.deepin.dde.Power1`: 2

按成员统计：

- `PropertiesChanged`: 30
- `NameOwnerChanged`: 9
- `BatteryDisplayUpdate`: 4
- `BatteryTimeToFullChanged`: 2
- `NameAcquired`: 1
- `BatteryPercentageChanged`: 1

按对象路径统计：

- `/org/freedesktop/DBus`: 10
- `/org/freedesktop/NetworkManager/Devices/3`: 8
- `/org/freedesktop/NetworkManager/AccessPoint/1745`: 8
- `/com/deepin/system/Power`: 8
- `/org/deepin/dde/Power1`: 5
- `/org/freedesktop/UPower/devices/battery_BAT0`: 3
- `/org/freedesktop/UPower/devices/DisplayDevice`: 3
- `/org/deepin/dde/Power1/battery_BAT0`: 2

## 行为分析

### 1. 样本以状态广播为主，不是请求型流量

47 条消息全部都是 `signal`。这说明本分钟 system bus 上最活跃的不是同步调用，而是服务对自身状态变化的广播。

### 2. 最主要的噪声源是属性变更广播

`PropertiesChanged` 占 30/47，约 63.8%。如果要做 DBusLens 的降噪或聚类，`org.freedesktop.DBus.Properties.PropertiesChanged` 应优先单独处理，否则会淹没真正有诊断价值的控制面调用。

### 3. 主要业务来源集中在网络和电源

根据对象路径推断：

- `:1.13` 很大概率对应 `NetworkManager`
- `:1.57` 很大概率对应 `UPower`
- `:1.62` 和 `:1.88` 对应 deepin 电源相关服务

这是基于对象路径和接口的推断，不是通过全量 owner 映射直接确认。

### 4. NetworkManager 呈现稳定周期性更新

`/org/freedesktop/NetworkManager/AccessPoint/1745` 和 `/org/freedesktop/NetworkManager/Devices/3` 在约每 6 秒出现一组 `PropertiesChanged`，节奏比较稳定，像是无线网络状态或信号强度刷新。

### 5. 电源相关流量呈事件突发

在约第 11 秒和第 27 秒附近有两次较明显的电源状态 burst，涉及：

- `BatteryDisplayUpdate`
- `BatteryTimeToFullChanged`
- `BatteryPercentageChanged`
- 多条 `PropertiesChanged`

这种模式更像底层电池状态刷新后，由多个上层服务同步广播 UI/系统状态。

### 6. 总线自身也有少量生命周期事件

`org.freedesktop.DBus.NameOwnerChanged` 共 9 条，说明在采样窗口内有若干服务连接状态变更，但数量不高，不像异常抖动。

## 结论

这 1 分钟 system bus 样本整体比较平稳，没有看到明显的异常风暴或高频请求放大问题。

当前最显著的特征是：

- 属性变更广播占比高
- 网络状态刷新是稳定周期背景流量
- 电源相关服务会在状态变化时形成短时突发

如果 DBusLens 要做首轮价值输出，建议优先支持：

1. 按 `signal/method call/reply/error` 分类聚合
2. 对 `PropertiesChanged` 做折叠、采样或单独频道展示
3. 对 sender/path/interface/member 建立 TopN 统计
4. 对周期性广播和突发广播做分段识别

## 建议的下一步采样

- 再抓一次 `session bus`，对比桌面会话侧噪声结构
- 把采样窗口扩大到 5 到 10 分钟，确认 NetworkManager 的周期是否稳定
- 在执行明确操作时定向抓取，例如切 Wi‑Fi、插拔电源、亮灭屏，以建立“事件 -> D-Bus 序列”对照样本
