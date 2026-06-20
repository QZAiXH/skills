# cs-feat-impl Reference

## 1. TDD 完整示例

### 示例场景：实现购物车结账功能

**从 design 提取的行为切片**：
1. 用户可以用有效购物车结账
2. 空购物车无法结账
3. 结账后购物车清空

#### 切片 1：用户可以用有效购物车结账

**RED 阶段**：

```typescript
// tests/checkout.test.ts
describe('checkout', () => {
  test('用户可以用有效购物车结账', async () => {
    // 测试公开接口，描述行为
    const cart = createCart();
    cart.add(createProduct({ id: '1', price: 100 }));
    
    const result = await checkout(cart, mockPaymentMethod);
    
    expect(result.status).toBe('confirmed');
    expect(result.orderId).toBeDefined();
  });
});
```

运行测试 → 失败（`checkout` 函数不存在）

**GREEN 阶段**：

```typescript
// src/checkout.ts
export async function checkout(cart: Cart, payment: PaymentMethod) {
  // 最少代码：硬编码返回让测试通过
  return {
    status: 'confirmed',
    orderId: 'ORDER-001',
  };
}
```

运行测试 → 通过 ✅

**REFACTOR 阶段**：

此时只有一个测试，没有重复代码，无需重构。

---

#### 切片 2：空购物车无法结账

**RED 阶段**：

```typescript
test('空购物车无法结账', async () => {
  const cart = createCart(); // 空购物车
  
  await expect(
    checkout(cart, mockPaymentMethod)
  ).rejects.toThrow('购物车为空');
});
```

运行测试 → 失败（没有抛出错误）

**GREEN 阶段**：

```typescript
export async function checkout(cart: Cart, payment: PaymentMethod) {
  // 添加最少代码让新测试通过
  if (cart.items.length === 0) {
    throw new Error('购物车为空');
  }
  
  return {
    status: 'confirmed',
    orderId: 'ORDER-001',
  };
}
```

运行所有测试 → 通过 ✅

**REFACTOR 阶段**：

发现 `orderId` 硬编码，但还没有测试要求它是唯一的，暂不改。

---

#### 切片 3：结账后购物车清空

**RED 阶段**：

```typescript
test('结账后购物车清空', async () => {
  const cart = createCart();
  cart.add(createProduct({ id: '1', price: 100 }));
  
  await checkout(cart, mockPaymentMethod);
  
  expect(cart.items.length).toBe(0);
});
```

运行测试 → 失败（购物车没有清空）

**GREEN 阶段**：

```typescript
export async function checkout(cart: Cart, payment: PaymentMethod) {
  if (cart.items.length === 0) {
    throw new Error('购物车为空');
  }
  
  // 添加清空逻辑
  const orderId = generateOrderId();
  cart.clear();
  
  return {
    status: 'confirmed',
    orderId,
  };
}
```

运行所有测试 → 通过 ✅

**REFACTOR 阶段**：

现在可以重构了：
1. 提取 `generateOrderId()` 函数
2. 考虑是否需要提取验证逻辑

```typescript
function validateCart(cart: Cart): void {
  if (cart.items.length === 0) {
    throw new Error('购物车为空');
  }
}

export async function checkout(cart: Cart, payment: PaymentMethod) {
  validateCart(cart);
  
  const orderId = generateOrderId();
  cart.clear();
  
  return {
    status: 'confirmed',
    orderId,
  };
}
```

运行所有测试 → 通过 ✅

---

## 2. 测试好坏对比

### 坏例子 1：测试实现细节

```typescript
// ❌ 坏：mock 内部协作者
test('checkout 调用 paymentService.process', async () => {
  const mockPayment = jest.mock(paymentService);
  await checkout(cart, payment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});
```

**问题**：
- 测试了内部实现（调用了哪个服务）
- 如果重构改用其他支付方式，测试会失败，但行为没变
- 测试名描述 HOW（调用什么）而非 WHAT（达成什么结果）

**好的做法**：

```typescript
// ✅ 好：测试行为结果
test('结账成功后订单状态为已确认', async () => {
  const result = await checkout(cart, payment);
  expect(result.status).toBe('confirmed');
});
```

---

### 坏例子 2：测试私有方法

```typescript
// ❌ 坏：暴露私有方法仅为测试
export function validateCart(cart: Cart) { /* ... */ }

test('validateCart 在空购物车时抛出错误', () => {
  expect(() => validateCart(emptyCart)).toThrow();
});
```

**问题**：
- `validateCart` 是实现细节，不应暴露
- 如果重构时合并到 `checkout` 内部，测试需要删除
- 测试了"怎么做"而非"做什么"

**好的做法**：

```typescript
// ✅ 好：通过公开接口测试
test('空购物车无法结账', async () => {
  await expect(checkout(emptyCart, payment)).rejects.toThrow();
});

// validateCart 保持私有
function validateCart(cart: Cart) { /* ... */ }
```

---

### 坏例子 3：绕过接口验证

```typescript
// ❌ 坏：直接查数据库验证
test('createUser 保存到数据库', async () => {
  await createUser({ name: 'Alice' });
  const row = await db.query('SELECT * FROM users WHERE name = ?', ['Alice']);
  expect(row).toBeDefined();
});
```

**问题**：
- 绕过了 `getUser` 等接口
- 如果数据库结构变了，测试失败，但接口行为没变
- 测试了存储细节而非业务行为

**好的做法**：

```typescript
// ✅ 好：通过接口验证
test('创建的用户可以被检索', async () => {
  const user = await createUser({ name: 'Alice' });
  const retrieved = await getUser(user.id);
  expect(retrieved.name).toBe('Alice');
});
```

---

## 3. 何时停下来回 design 谈

### 信号 1：边界条件未定义

```typescript
// 写到这里发现：design 没说并发结账怎么处理
test('同一购物车不能并发结账', async () => {
  const cart = createCart();
  // design 没说这种情况，停！
});
```

**处理**：停下来跟用户说："design 没覆盖并发结账场景，是要加锁、抛错、还是允许？需要回 design 补充。"

---

### 信号 2：需要 mock 内部协作者

```typescript
// 写到这里发现：没法不 mock paymentService 就测试
test('结账调用支付服务', async () => {
  const mockPayment = jest.mock(paymentService); // 被迫 mock
  // ...
});
```

**处理**：停下来跟用户说："checkout 的接口设计导致无法不 mock 就测试。要么改接口（依赖注入），要么接受集成测试。"

---

### 信号 3：补丁分支冲动

```typescript
export async function checkout(cart: Cart, payment: PaymentMethod) {
  validateCart(cart);
  
  // 写到这里想加：if (cart.user.isVIP) { /* 特殊处理 */ }
  // 但 design 里没提 VIP 逻辑，停！
}
```

**处理**：停下来跟用户说："发现需要 VIP 用户特殊处理，但 design 没提。要补进方案、砍掉、还是明确为后续 feature？"

---

## 4. REFACTOR 阶段的边界

### 在影响范围内：可以重构

```typescript
// 场景：本次改了 checkout 函数
export async function checkout(cart: Cart, payment: PaymentMethod) {
  // 发现这段重复了
  if (cart.items.length === 0) {
    throw new Error('购物车为空');
  }
  if (cart.items.some(item => item.quantity <= 0)) {
    throw new Error('商品数量无效');
  }
  
  // ✅ 可以提取（在本次影响范围内）
}

// 重构后
function validateCart(cart: Cart) {
  if (cart.items.length === 0) {
    throw new Error('购物车为空');
  }
  if (cart.items.some(item => item.quantity <= 0)) {
    throw new Error('商品数量无效');
  }
}

export async function checkout(cart: Cart, payment: PaymentMethod) {
  validateCart(cart);
  // ...
}
```

---

### 不在影响范围内：记成"顺手发现"

```typescript
// 场景：本次改了 checkout，但发现同文件的 addToCart 有问题
export function addToCart(cart: Cart, product: Product) {
  // 这个函数有 bug：没检查库存
  // 但本次 feature 不涉及 addToCart
  
  // ❌ 不能顺手修：超出范围
  // ✅ 应该记录：
  // > 顺手发现：checkout.ts:45 addToCart 没检查库存。不在本次范围，记录待后续 issue。
}
```

---

### 需要改接口：记成"顺手发现"走 cs-refactor

```typescript
// 场景：本次改了 checkout，发现 Cart 接口设计有问题
interface Cart {
  items: Item[];      // ❌ 暴露内部数组，外部可以直接修改
  add(item: Item): void;
}

// 理想设计应该是：
interface Cart {
  readonly items: readonly Item[];  // 只读
  add(item: Item): void;
}

// 但这需要改 Cart 的所有使用方，超出"只搬不改行为"边界
// ✅ 记成"顺手发现"：
// > 顺手发现：cart.ts:10 Cart.items 应该设为只读，防止外部直接修改。
//   需要改接口签名 + 所有调用方，本 feature 不做，记录走 cs-refactor。
```

---

## 5. 垂直切片 vs 水平切片对比

### 水平切片（❌ 禁止）

```
第 1 步：写所有测试
  - test: 用户可以结账
  - test: 空购物车无法结账
  - test: 结账后清空购物车
  - test: 结账失败抛出错误
  
第 2 步：实现所有功能
  - function checkout() { /* 一次性写完所有逻辑 */ }
```

**问题**：
- 测试基于想象（还没写实现就写测试）
- 容易测实现细节（因为还不知道实现会是什么样）
- 出问题无法定位（不知道是哪个测试对应哪段代码）
- 无法享受 TDD 的设计反馈（一次性写完再改很痛苦）

---

### 垂直切片（✅ 正确）

```
第 1 个切片：
  RED   → test: 用户可以结账
  GREEN → function checkout() { return { status: 'confirmed' }; }
  
第 2 个切片：
  RED   → test: 空购物车无法结账
  GREEN → 添加 if (cart.items.length === 0) throw ...
  REFACTOR → 无需重构
  
第 3 个切片：
  RED   → test: 结账后清空购物车
  GREEN → 添加 cart.clear()
  REFACTOR → 提取 validateCart() 函数
```

**优势**：
- 每个测试基于真实实现（刚写完的代码）
- 测试自然地测行为（因为知道行为是什么）
- 问题立即暴露（测试失败 → 就是刚写的代码有问题）
- 设计反馈及时（接口不好测 → 立即调整）

---

## 6. 行为切片的粒度判断

### 太大的切片（需要拆分）

```yaml
# ❌ 太大：包含多个独立行为
- action: 实现完整的结账流程
  behavior: |
    用户可以结账
    支持多种支付方式
    结账后发送邮件通知
    更新库存
    生成发票
```

**问题**：一个 RED-GREEN-REFACTOR 循环要写 5+ 个测试，太长。

**拆分后**：

```yaml
- action: 基础结账
  behavior: 用户可以用有效购物车结账
  
- action: 支付方式
  behavior: 支持信用卡和支付宝支付
  
- action: 邮件通知
  behavior: 结账成功后发送确认邮件
  
- action: 库存更新
  behavior: 结账后扣减商品库存
  
- action: 发票生成
  behavior: 结账成功后生成电子发票
```

---

### 太小的切片（需要合并）

```yaml
# ❌ 太小：不值得独立一个测试
- action: 创建订单 ID
  behavior: 生成唯一订单 ID
  
- action: 设置订单状态
  behavior: 订单状态初始为 pending
  
- action: 保存订单
  behavior: 订单保存到数据库
```

**问题**：这三个都是"用户可以结账"这一个行为的内部实现细节。

**合并后**：

```yaml
- action: 基础结账
  behavior: 用户可以用有效购物车结账（订单有唯一 ID、状态为 pending、可被检索）
```

---

### 恰当的切片（✅）

```yaml
- action: 基础结账
  behavior: 用户可以用有效购物车结账
  exit_signal: 测试通过，可获得订单 ID 和状态
  
- action: 空购物车校验
  behavior: 空购物车无法结账
  exit_signal: 测试通过，抛出预期错误
  
- action: 购物车清空
  behavior: 结账后购物车清空
  exit_signal: 测试通过，购物车为空
```

**判据**：
- 每个切片 = 一个用户可感知的行为变化
- 每个切片对应 1-2 个测试
- 切片之间相对独立（可以分别验证）

---

## 7. 汇报模板详解

### 完整汇报示例

```markdown
## 实现完成汇报

### 动了哪些文件
M  src/checkout.ts
A  src/cart/validate.ts
M  tests/checkout.test.ts

### 改了哪些函数 / 类型（按步骤分组）
**步骤 1：基础结账**
- src/checkout.ts:10  checkout  新增
- tests/checkout.test.ts:5  "用户可以用有效购物车结账"  新增

**步骤 2：空购物车校验**
- src/checkout.ts:15  checkout  修改（添加校验）
- src/cart/validate.ts:1  validateCart  新增
- tests/checkout.test.ts:15  "空购物车无法结账"  新增

**步骤 3：购物车清空**
- src/checkout.ts:20  checkout  修改（添加清空逻辑）
- tests/checkout.test.ts:25  "结账后购物车清空"  新增

### TDD 推进记录
**步骤 1：基础结账**
- RED: 写测试"用户可以用有效购物车结账"，测试 checkout 返回确认状态和订单 ID
- GREEN: 实现 checkout 函数，硬编码返回确认状态
- REFACTOR: 无

**步骤 2：空购物车校验**
- RED: 写测试"空购物车无法结账"，测试空购物车抛出错误
- GREEN: 添加 if (cart.items.length === 0) throw 逻辑
- REFACTOR: 提取 validateCart() 到独立文件

**步骤 3：购物车清空**
- RED: 写测试"结账后购物车清空"，测试 cart.items.length 为 0
- GREEN: 添加 cart.clear() 调用
- REFACTOR: 将硬编码订单 ID 改为 generateOrderId()

### 是否触碰到方案外的文件？
是。新建了 src/cart/validate.ts，用于提取校验逻辑。
已同步更新 design 第 2.1 节，补充 validateCart 接口。

### 是否引入了方案 doc 里没有的新概念 / 抽象？
否。所有函数和类型都在 design 第 0 节术语表中。

### 代码质量反射检查自检
- 触发信号：checkout.ts 从 50 行增长到 80 行
- 处理：提取 validateCart 到独立文件（已完成）
- 其他信号：无触发

### 测试质量自检
- [x] 所有测试都测公开接口（checkout 是公开接口）
- [x] 测试描述 WHAT 不描述 HOW（测试名为"用户可以..."而非"checkout 调用..."）
- [x] 没有 mock 内部协作者（validateCart 是私有函数，测试不 mock）
- [x] 测试会在重构后继续通过（重构后所有测试仍通过）
- [x] 每个测试只验证一个行为

### 验收场景自检
对照 design 第 3 节关键场景清单：
- "用户可以结账" → tests/checkout.test.ts:5 单测通过 ✅
- "空购物车无法结账" → tests/checkout.test.ts:15 单测通过 ✅
- "结账后购物车清空" → tests/checkout.test.ts:25 单测通过 ✅
- "结账失败不扣款" → 类型系统保证（payment 接口幂等） ✅

反向核对项：
- "不能绕过 checkout 直接清空购物车" → cart.clear() 是私有方法 ✅
```

---

## 8. 常见问题 Q&A

### Q1: 什么时候可以一次写多个测试？

**A**: 从不。严格的 TDD 是一次只写一个测试。特例：
- 如果多个测试测同一个边界条件的不同输入（如"负数"、"零"、"NaN"），可以用参数化测试，但仍算一个测试用例。

---

### Q2: REFACTOR 阶段可以改测试吗？

**A**: 可以，但只能改测试的**结构**（提取辅助函数、共享 setup），不能改测试的**意图**（测什么行为）。

```typescript
// ✅ 可以：提取共享 setup
beforeEach(() => {
  cart = createCart();
  payment = mockPaymentMethod();
});

// ❌ 不可以：改变测试意图
test('用户可以结账', async () => {
  // 原来测 status，现在改测 orderId
  expect(result.orderId).toBeDefined(); // 这不是重构，是改需求
});
```

---

### Q3: 如果测试很难写怎么办？

**A**: 这是设计反馈。测试难写 = 接口设计有问题：
- 需要 mock 太多东西 → 依赖太多，考虑依赖注入或拆分职责
- 需要访问私有状态 → 接口没暴露足够信息，考虑返回值设计
- 需要复杂的 setup → 函数做太多事，考虑拆分

**不要**为了测试而暴露私有方法，应该重新设计接口。

---

### Q4: 什么时候可以跳过 RED 阶段？

**A**: 从不。如果"测试一写就通过"，说明：
- 功能已经存在（不是新功能）
- 测试写错了（测的不是新行为）

先删掉新写的实现代码，确认测试失败，再重新写实现。

---

### Q5: 性能优化算 REFACTOR 吗？

**A**: 看情况：
- 算法层面优化（O(n²) → O(n)）但接口不变 → 是 REFACTOR
- 需要改接口（如改成异步、分页）→ 不是 REFACTOR，是新需求，走新的 RED-GREEN-REFACTOR

---

### Q6: 可以先写一部分实现再写测试吗？

**A**: 不可以。这叫"测试后补"（test-after），不是 TDD。后果：
- 测试会迁就实现（测实现细节而非行为）
- 失去设计反馈（接口已经固化）
- 测试覆盖率虚高（测了代码但没测行为）

如果已经写了实现，应该删掉重新按 TDD 来。
