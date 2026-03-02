# SSE (Server-Sent Events) 使用示例

## 完整流程示例（带推理模式）

```
event: start
data: {"model":"deepseek-chat","reasoning":"enabled"}

event: reasoning
data: {"content":"用户询问股票600519..."}

event: reasoning
data: {"content":"这是贵州茅台的股票代码..."}

event: reasoning
data: {"content":"需要调用工具获取实时数据..."}

event: tool_call
data: {"id":"call_1","type":"mcp","name":"get_stock_info","arguments":{"code":"600519"}}

event: tool_result
data: {"tool_call_id":"call_1","result":{"price":1680.50,"change":1.2}}

event: message
data: {"content":"贵州茅台"}

event: message
data: {"content":"当前价格"}

event: message
data: {"content":"为1680.50元"}

event: end
data: {
  "finish_reason": "stop",
  "stats": {
    "tool_calls": 1,
    "tool_results": 1,
    "tokens": {
      "prompt": 234,
      "completion": 156,
      "total": 390
    },
    "timing_ms": {
      "first_byte": 120,
      "total": 2850
    }
  }
}
```

## 基本用法

```python
from utils.models import deepseek

# 非流式输出（只返回最终内容，不包含推理过程和工具调用记录）
result = deepseek.chat("分析一下 600519", stream=False)
print(result)  # 直接得到最终回答文本

# 启用 SSE 格式流式输出（默认启用推理模式）
for chunk in deepseek.chat("分析一下 600519", stream=True, sse=True):
    print(chunk, end='', flush=True)

# 禁用推理模式
for chunk in deepseek.chat("分析一下 600519", stream=True, sse=True, thinking=False):
    print(chunk, end='', flush=True)
```

**非流式 vs 流式对比：**

| 特性 | 非流式 (stream=False) | 流式 (stream=True) |
|------|---------------------|-------------------|
| 返回方式 | 直接返回字符串 | 生成器逐步返回 |
| 推理过程 | ❌ 不可见 | ✅ 可见（thinking=enabled） |
| 工具调用 | ❌ 不可见 | ✅ 可见 |
| 统计信息 | ❌ 无 | ✅ 有 |
| 实时性 | ❌ 等待全部完成 | ✅ 实时输出 |
| 使用场景 | API 后端、批量处理 | 交互式聊天、用户体验 |

## SSE 消息格式

### 1. 流开始
```
event: start
data: {"model":"deepseek-chat","reasoning":"enabled"}

```

**reasoning 字段说明：**
- `enabled`: 启用推理模式，会输出 `reasoning` 事件
- `disabled`: 禁用推理模式，不输出思维链

### 2. 推理内容（仅在 reasoning=enabled 时）
```
event: reasoning
data: {"content":"用户询问股票信息，需要调用工具..."}

```

### 3. 消息内容
```
event: message
data: {"content":"根据最新数据"}

```

### 4. 工具调用
```
event: tool_call
data: {"id":"call_abc123","type":"mcp","name":"get_stock_info","arguments":{"code":"600519"}}

```

### 5. 工具执行结果（成功）
```
event: tool_result
data: {"tool_call_id":"call_abc123","result":{"price":1234.56,"change":2.3}}

```

### 6. 工具执行结果（失败）
```
event: tool_result
data: {"tool_call_id":"call_abc123","error":"网络连接失败"}

```

### 7. 错误信息
```
event: error
data: {"finish_reason":"length","message":"工具调用次数过多，已停止"}

```

### 8. 流结束
```
event: end
data: {
  "finish_reason": "stop",
  "stats": {
    "tool_calls": 1,
    "tool_results": 1,
    "tokens": {
      "prompt": 234,
      "completion": 156,
      "total": 390
    },
    "timing_ms": {
      "first_byte": 120,
      "total": 2850
    }
  }
}

```

**finish_reason 说明：**
- `stop`: 正常结束
- `length`: 达到最大长度/次数限制

**stats 字段说明：**
- `tool_calls`: 工具调用总次数
- `tool_results`: 工具结果总次数（包括成功和失败）
- `tokens`: Token 使用统计
  - `prompt`: 输入 token 数
  - `completion`: 输出 token 数
  - `total`: 总 token 数
- `timing_ms`: 时间统计（毫秒）
  - `first_byte`: 首字节时间（从请求开始到收到第一个数据）
  - `total`: 总耗时（从请求开始到流结束）

## 测试命令

```bash
# 测试 SSE 格式（Python，默认启用推理模式）
python -m utils.models.deepseek

# 使用 curl 测试（假设你已经创建了 Web API）
curl -N http://localhost:8000/chat/endpoint \
  -H "Content-Type: application/json" \
  -d '{"prompt":"分析600519","thinking":true}'

# 禁用推理模式
curl -N http://localhost:8000/chat/endpoint \
  -H "Content-Type: application/json" \
  -d '{"prompt":"分析600519","thinking":false}'

# 使用 httpie 测试
http --stream POST localhost:8000/api/chat prompt="分析600519" thinking:=true
```

## 事件完整流程

### 启用推理模式 (thinking=True)

```
1. start      → 流开始 {"model":"deepseek-chat","reasoning":"enabled"}
2. reasoning  → 推理过程（多次）
3. tool_call  → 工具调用
4. tool_result → 工具结果
5. message    → 消息内容（多次）
6. end        → 流结束 {"finish_reason":"stop"}
```

### 禁用推理模式 (thinking=False)

```
1. start      → 流开始 {"model":"deepseek-chat","reasoning":"disabled"}
2. message    → 消息内容（多次）
3. tool_call  → 工具调用（如需要）
4. tool_result → 工具结果（如有工具调用）
5. message    → 继续消息内容（多次）
6. end        → 流结束 {"finish_reason":"stop"}
```
