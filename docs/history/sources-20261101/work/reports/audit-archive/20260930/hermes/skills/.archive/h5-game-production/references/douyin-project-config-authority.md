# 抖音项目 AppID 配置权威与 Lite 模式排查

## 适用场景

- 抖音开发者工具持续显示 Lite/游客模式。
- 工具内修改 AppID 后，下次构建又恢复 `touristappid`。
- `project.private.config.json` 已有真实 AppID，但严格检查或开发工具仍识别为游客项目。

## 配置权威链

不要先假定开发者工具 UI 是权威源。按顺序检查：

1. 构建脚本如何生成 `douyin-minigame/project.config.json`。
2. 是否存在 ignored `release.config.json` 或同类本地覆盖层。
3. 构建是否只写 `project.private.config.json`，却仍把主配置写成 `touristappid`。
4. 每次 `npm test` / `npm run douyin:build` 是否重写主配置。
5. 重新构建后，直接读取两个生成文件并比较 AppID。
6. 运行严格检查，确认游客 AppID warning 消失。
7. 让已经打开的开发工具重新编译；只有后续截图显示模式/项目身份变化，才能声称工具侧切换成功。

## 推荐实现

```js
const localAppId = releaseConfig?.douyin?.appid;
const projectConfig = {
  compileType: 'game',
  appid: localAppId || 'touristappid',
  projectname: releaseConfig?.douyin?.projectname || 'MINIGAME',
};
```

构建时：

- 主 `project.config.json`：必须写入开发工具实际读取的 AppID。
- ignored `project.private.config.json`：同步写入本机项目标识。
- 没有本地发布配置的 CI/新克隆：安全回退 `touristappid`。
- 广告位、令牌、账号资料继续只放 ignored 配置；AppID 是项目标识，不等同于密码，但是否跟踪仍按仓库政策决定。

## 回归测试

至少覆盖两种环境：

1. **无本地覆盖层**：生成游客项目，保持可移植开发构建。
2. **有本地发布配置**：主配置和私有配置都等于提供的抖音 AppID。

测试结束后的恢复构建必须尊重当前本地配置，不能无意把已打开项目重新写回游客模式。

## 验收证据

```text
build 定向测试通过
全量测试通过
douyin strict：AppID 检查 PASS、0 warning
主 project.config.json AppID == 本地覆盖值
私有 project.private.config.json AppID == 本地覆盖值
开发工具重新编译后无 AppID 配置错误
```

## 常见错误

- 只手改生成文件：下一次构建必然覆盖。
- 只写私有配置：开发工具可能仍以主配置判断项目身份。
- 把“游戏刷新成功”误报为“已退出 Lite 模式”：必须看标题栏/项目详情的后续画面。
- 后台点击原生标题栏后没有复截图：输入事件不是成功证据。
- 为了隐藏 AppID 把所有项目标识都留成游客值：这会让正式项目无法在开发工具中绑定；真正需要保密的是令牌、Secret、广告配置和账号资料。
