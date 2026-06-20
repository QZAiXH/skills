# cs-diagnose Reference

## 反馈循环构建详细指南

### 方法 1：失败测试

**适用场景**：有测试框架，能触达 bug 的代码路径

**步骤**：
1. 确定最接近 bug 的测试层次（单元/集成/e2e）
2. 写一个测试复现问题现象
3. 确认测试失败且失败原因与 bug 一致
4. 测量运行时间，优化到 <30 秒

**示例**（JavaScript/Jest）：
```javascript
// __tests__/auth-token-leak.test.js
describe('Auth token handling', () => {
  it('should not leak token in error messages', async () => {
    const result = await authenticateUser({ token: 'secret123' });
    expect(result.error).not.toContain('secret123');
  });
});
```

**优点**：确定性强、易于 CI 集成、修复后自动变回归测试

---

### 方法 2：HTTP 脚本

**适用场景**：bug 在 API 层、有 dev 服务器

**步骤**：
1. 启动 dev 服务器
2. 写 curl/httpie 脚本发送触发 bug 的请求
3. 断言响应（状态码、body 内容、header）
4. 包装成 bash 脚本，返回 0（通过）或 1（失败）

**示例**：
```bash
#!/usr/bin/env bash
# test-api-bug.sh
response=$(curl -s -w "\n%{http_code}" http://localhost:3000/api/users)
body=$(echo "$response" | head -n -1)
status=$(echo "$response" | tail -n 1)

if [[ $status != "200" ]]; then
  echo "FAIL: Expected 200, got $status"
  exit 1
fi

if echo "$body" | grep -q "null"; then
  echo "FAIL: Response contains null"
  exit 1
fi

echo "PASS"
exit 0
```

**优点**：真实环境、快速、容易并行化

---

### 方法 3：CLI 调用

**适用场景**：bug 在 CLI 工具、有固定输入能触发

**步骤**：
1. 准备触发 bug 的输入文件/参数
2. 运行 CLI，捕获输出
3. 与已知好快照 diff，或 grep 特定错误模式

**示例**：
```bash
#!/usr/bin/env bash
# test-cli-bug.sh
./bin/tool process input.json > actual-output.txt 2>&1

if diff -u expected-output.txt actual-output.txt; then
  echo "PASS"
  exit 0
else
  echo "FAIL: Output mismatch"
  exit 1
fi
```

**优点**：简单、隔离、易复现

---

### 方法 4：无头浏览器

**适用场景**：bug 在前端、需要真实浏览器环境

**步骤**：
1. 用 Playwright/Puppeteer 写脚本
2. 自动化用户操作
3. 断言 DOM/console/network

**示例**（Playwright）：
```javascript
// test-ui-bug.spec.js
const { test, expect } = require('@playwright/test');

test('submit button should not show blank modal', async ({ page }) => {
  await page.goto('http://localhost:3000/form');
  await page.fill('#username', 'testuser');
  await page.click('#submit');
  
  const modal = page.locator('.modal');
  await expect(modal).toBeVisible();
  await expect(modal).not.toHaveText('');
});
```

**优点**：真实用户体验、可截图、可录制

---

### 方法 10：HITL 脚本

**适用场景**：人工操作无法避免（如需要真实设备、外部系统）

**使用模板**：见 `scripts/hitl-loop.template.sh`

**步骤**：
1. 复制模板到 issue 目录，重命名为 `{slug}-feedback-loop.sh`
2. 编辑"edit below/above"之间的步骤
3. 每个用户操作用 `step "指令"`
4. 需要捕获的结果用 `capture VAR "问题"`
5. 运行脚本，AI 解析最后输出的 KEY=VALUE

**何时使用**：
- 需要物理设备交互（扫码、NFC）
- 需要第三方服务响应（支付回调、邮件确认）
- 需要特定硬件/OS 特性（摄像头、通知）

**优点**：结构化人工参与、输出可被 AI 解析

**缺点**：慢、不确定性高、不能完全自动化

---

## 假设生成模板

### 好假设示例

**假设 1**：认证中间件在处理过期 token 时抛出异常而不是返回 401
- **预测**：如果这是根因，那么在日志中看到未捕获异常；手动发送过期 token 会看到 500 错误而不是 401
- **优先级**：高，理由：错误消息提到"unexpected token error"

**假设 2**：前端没有处理 401 响应，导致空白弹窗
- **预测**：如果这是根因，那么 network 面板会显示 401 响应，但 console 没有对应错误处理；mock 401 响应会复现空白弹窗
- **优先级**：中，理由：现象符合但需验证后端是否真的返回 401

**假设 3**：并发请求时 token 刷新逻辑竞态，导致部分请求用旧 token
- **预测**：如果这是根因，那么添加并发请求压力会提高复现率；单请求不复现，并发 10 个请求必现
- **优先级**：低，理由：报告显示稳定复现，不像竞态条件

### 坏假设示例（需改进）

❌ **假设**：可能是认证有问题
- **问题**：太模糊，无法验证
- **改进**：具体到哪个组件、什么问题、怎么验证

❌ **假设**：代码有 bug
- **问题**：废话，没有预测
- **改进**：说明是什么 bug、预测什么行为

❌ **假设**：用户输入不合法导致错误
- **问题**：有具体性但没有可验证预测
- **改进**：添加"如果这是根因，那么输入 X 会触发，输入 Y 不会触发"

---

## 仪器化验证技巧

### 定向日志最佳实践

```javascript
// BAD: 无标记，难清理
console.log('user:', user);
console.log('token:', token);

// GOOD: 带唯一标记
console.log('[DEBUG-a4f2] user:', user);
console.log('[DEBUG-a4f2] token:', token);

// 清理时：
// grep -r "\[DEBUG-a4f2\]" . --include="*.js" --include="*.ts"
```

**标记命名**：`[DEBUG-{随机 4 字符}]`，避免与生产日志冲突

**日志位置**：在假设预测的关键分叉点
- 条件判断前后
- 函数入口/出口
- 状态改变点
- 异步边界（Promise 前后、callback 入口）

### 性能剖析

**Node.js**：
```bash
node --prof app.js          # 生成 isolate-*.log
node --prof-process isolate-*.log > profile.txt
```

**浏览器**：
- Chrome DevTools > Performance > Record
- 关注 Main 线程、Long Tasks、Layout Shifts

**数据库**：
```sql
EXPLAIN ANALYZE SELECT ...;  -- PostgreSQL
EXPLAIN FORMAT=JSON SELECT ...;  -- MySQL
```

**对比基线**：
1. 在已知好版本跑相同剖析
2. 对比输出，找新增的热点

### Debugger 使用

**优先于日志**：单个断点看到完整上下文 > 十条日志拼凑

**条件断点**：只在特定条件暂停
```javascript
// Chrome DevTools 条件断点表达式
user.id === 'problematic-id'
```

**日志点**（Logpoints）：断点位置打印但不暂停，类似日志但不改代码

---

## 常见 bug 模式与诊断策略

### 竞态条件

**特征**：
- 不稳定复现
- 并发/异步环境
- 与时序相关

**诊断策略**：
1. 提高并发度（循环 100 次、并行化）
2. 添加 sleep 改变时序窗口
3. 仪器化：微秒时间戳 + 线程/协程 ID
4. 假设重点：共享状态、锁顺序、异步依赖

**修复验证**：跑 1000 次确认复现率降至 0

### 性能回归

**特征**：
- 功能正确但慢
- 用户报告"变慢了"
- 可能与数据量/负载相关

**诊断策略**：
1. 建立基线（已知好版本的性能指标）
2. 测量当前（相同条件）
3. 对比差异（哪个操作变慢？慢多少？）
4. Git bisect 定位引入回归的 commit
5. Profiler 找热点

**修复验证**：恢复到基线 ±10% 内

### 数据损坏

**特征**：
- 持久化数据不一致
- 看似随机的错误数据
- "好好的突然坏了"

**诊断策略**：
1. 隔离环境（测试数据库）
2. 数据快照对比（损坏前后）
3. 仪器化所有写入点
4. 追踪因果链（谁写了什么、何时、为何）
5. 假设重点：事务边界、回滚缺失、并发写

**修复验证**：确认约束满足、无孤儿记录、外键完整

### Null/Undefined 错误

**特征**：
- "Cannot read property 'x' of undefined"
- "null is not an object"
- 边界条件

**诊断策略**：
1. 回溯调用链（谁传了 null/undefined？）
2. 检查数据源（API 返回、数据库查询、用户输入）
3. 假设重点：缺失边界检查、错误假设"一定有值"、异步未 await

**修复验证**：对空值、空数组、空字符串都测试一遍

---

## 修复验证清单（扩展）

### 基础验证

- [ ] Phase 1 反馈循环通过（bug 不再复现）
- [ ] Phase 2 的精确症状不再出现
- [ ] 手动按用户报告的复现步骤走一遍

### 回归验证

- [ ] diagnosis.md "影响面"列出的模块都冒烟测试
- [ ] 相关测试套件全部通过
- [ ] 没有引入新的测试失败

### 性能验证（如适用）

- [ ] 性能指标恢复到基线 ±10%
- [ ] Profiler 显示热点消除
- [ ] 响应时间/吞吐量符合预期

### 数据完整性验证（如适用）

- [ ] 数据库约束满足
- [ ] 外键完整性检查通过
- [ ] 无孤儿记录或悬空引用

### 前端验证（如适用）

- [ ] 浏览器 console 无新错误
- [ ] Network 面板请求/响应正常
- [ ] 多浏览器测试（如 bug 浏览器特定）

### 并发验证（如竞态条件）

- [ ] 并发循环 1000 次无复现
- [ ] 压力测试下行为稳定

---

## 文档记录要点

### diagnosis.md 写作原则

**目标读者**：3 个月后的自己、团队其他成员、未来遇到类似问题的人

**写作风格**：
- **具体**：`auth.js:42` 不是"认证模块某处"
- **有因果**："因为 X，导致 Y"，不只列现象
- **时间戳**：每个 Phase 完成时间，体现时间成本
- **保留失败路径**：尝试过但不work的方法也记录，避免重复踩坑

**避免**：
- "可能"、"大概"、"应该"——要确定性结论
- 只记成功路径——失败的也要记
- 长篇技术细节——关键发现 + 指向代码位置即可

### fix-note.md 与 diagnosis.md 的分工

**diagnosis.md**：
- 完整诊断过程（6 个 Phase）
- 所有假设（包括被证伪的）
- 仪器化细节
- 探索路径（包括死胡同）

**fix-note.md**：
- 简洁修复记录
- 最终根因和方案
- 验证结果
- 关联到完整诊断

**类比**：diagnosis 是实验日志本，fix-note 是论文摘要

---

## 工具箱

### 反馈循环脚本模板

见 `scripts/hitl-loop.template.sh`

### 性能基线脚本示例

```bash
#!/usr/bin/env bash
# perf-baseline.sh
# 测量关键操作的性能基线

echo "=== Performance Baseline ==="
echo "Date: $(date)"
echo "Commit: $(git rev-parse HEAD)"
echo ""

# API 响应时间
echo "API /users response time:"
for i in {1..10}; do
  curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:3000/api/users"
done | awk '{sum+=$1; count++} END {print sum/count " ms"}'

# 数据库查询
echo "Database query time:"
psql -c "EXPLAIN ANALYZE SELECT * FROM users WHERE active = true;" | grep "Execution Time"

# 前端加载
echo "Frontend bundle size:"
du -sh dist/bundle.js
```

### Git bisect 辅助

```bash
#!/usr/bin/env bash
# bisect-helper.sh
# 用于 git bisect run

# 运行测试或反馈循环
if ./test-bug.sh; then
  exit 1  # bug 不存在，这是 good commit
else
  exit 0  # bug 存在，这是 bad commit
fi
```

使用：
```bash
git bisect start
git bisect bad HEAD              # 当前有 bug
git bisect good v1.2.3           # 这个版本没有
git bisect run ./bisect-helper.sh
# 自动找到引入 bug 的 commit
```

---

## 与其他技能的衔接

### cs-diagnose → cs-trick

**时机**：诊断中发现的技术技巧值得复用

**示例**：
- 构建反馈循环的特定方法（如"用 Docker 隔离复现环境"）
- 仪器化技巧（如"追踪 React 渲染性能的 DevTools 配置"）
- 库的特定用法（如"Prisma 查询性能剖析"）

**动作**：在 Phase 6 复盘时问用户"这个技巧是否沉淀到 cs-trick？"

### cs-diagnose → cs-learn

**时机**：踩到的坑值得警示

**示例**：
- "异步函数不 await 导致 race condition"
- "Jest 默认并行运行测试，共享状态导致不稳定"
- "生产日志级别过高，关键信息没记录"

**动作**：Phase 6 复盘时问"这个坑是否沉淀到 cs-learn？"

### cs-diagnose → cs-arch

**时机**：暴露了架构问题

**示例**：
- "无合适测试层次锁定 bug"
- "模块间耦合导致影响面扩散"
- "共享状态管理混乱"

**动作**：Phase 6 复盘时问"是否更新 architecture 文档或提交改进建议？"

### cs-diagnose → improve-codebase-architecture

**时机**：架构改变能预防此类 bug，但不在本次修复范围

**示例**：
- "重构模块边界"
- "引入依赖注入"
- "添加测试抽象层"

**动作**：Phase 6 记录预防措施，问用户"是否提交架构改进任务？"修复**后**提，不是修复**前**

---

## 常见问题

### Q: 何时用 cs-diagnose 而不是 cs-issue？

A: 5 分钟规则——读代码 5 分钟内能确定根因就 cs-issue，否则 cs-diagnose。或者：需要构建专门反馈循环、生成多假设、仪器化验证的就 cs-diagnose。

### Q: Phase 1 花了很久还没有循环，该放弃吗？

A: 不。Phase 1 是整个诊断的基础，没有循环后续都是猜测。如果 10 种方法都试了还不行，停下来跟用户要更多输入（环境访问、artifact、生产仪器化许可）。

### Q: 用户不在，假设列表没人 review 怎么办？

A: 按你的排序推进，但在 diagnosis.md 记录"用户未 review，按 AI 排序推进"。等用户回来时如果发现方向错了，至少有记录能回退。

### Q: 修复后循环通过，但用户说还有问题？

A: 两种可能：(1) 循环没覆盖用户真实场景——回 Phase 1 改进循环；(2) 有第二个独立 bug——开新 issue 目录。不要在同一个 diagnosis.md 混两个 bug。

### Q: diagnosis.md 写太长（>500 行）怎么办？

A: 正常。疑难 bug 诊断本来就复杂，完整记录比强行压缩更重要。如果真的超过 800 行，考虑拆分：diagnosis.md 保留主线，细节放 `{slug}-instrumentation-details.md` 或 `{slug}-hypothesis-experiments.md`。

### Q: 诊断发现需要重构才能干净修，怎么办？

A: 停下来跟用户对齐：(1) 先用 workaround 修复、后续重构（两个 PR）；(2) 在本次一并重构（一个大 PR）；(3) 暂不修、直接开重构任务。记录在 diagnosis.md "修复方案"节，等用户决定。
