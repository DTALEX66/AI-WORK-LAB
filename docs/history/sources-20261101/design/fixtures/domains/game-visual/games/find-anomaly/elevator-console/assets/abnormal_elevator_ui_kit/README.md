# 异常电梯控制台 UI 组件包

## 定位
这不是海报图，而是移动端小游戏可落地的 UI 组件拆分包。核心风格是“老旧但可用的异常电梯安防终端”。

## 包含组件
1. 手机主界面结构：CCTV / 异常提示 / 倒计时 / 状态条 / 底部操作区
2. 工业触控键：默认、推荐、按下、禁用、危险确认、次级入口
3. 状态反馈：稳定度、电力、威胁等级、信号强度
4. 异常提示：异常类型、发生位置、详情入口
5. 更多操作抽屉：切换摄像头、楼层广播、重置电力、锁定项
6. 日志面板：时间线式系统日志
7. 危险确认面板：急停长按/滑动防误触

## 手机小游戏规范
- 基准尺寸：375 × 812
- 主操作触控高度：≥ 52px
- 底部高频按钮放在拇指可达区
- 急停必须二次确认，不直接触发
- 主界面只保留 4 个高频操作，低频功能收进“更多操作”
- 不使用落地页式大卡片，不使用大圆角彩色网页按钮
- CCTV 画面占首屏 38–44%，用于氛围与信息识别

## 按钮状态命名
- default：默认
- pressed：按下
- recommended：推荐操作
- disabled：禁用
- cooldown：冷却中
- confirmRequired：需要危险确认
- confirming：确认中
- locked：锁定

## 可交付给前端的 Props
```ts
type ControlKeyProps = {
  variant: "neutral" | "recommended" | "danger" | "secondary";
  state: "default" | "pressed" | "disabled" | "cooldown" | "confirmRequired" | "confirming" | "locked";
  size: "main" | "wide" | "compact";
  label: string;
  subLabel?: string;
  icon?: "door" | "up" | "stop" | "scan" | "log" | "more";
  led?: boolean;
  cooldown?: number;
};
```

## 文件说明
- `abnormal-elevator-ui-kit.html`：完整组件预览页
- `abnormal-elevator-ui.css`：组件样式
- `component-tokens.json`：颜色、尺寸、状态命名
