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

## Flask Web 应用示例

```python
from flask import Flask, Response, request
from utils.models import deepseek
import json

app = Flask(__name__)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    prompt = data.get('prompt', '')
    thinking = data.get('thinking', True)  # 默认启用推理模式
    
    def generate():
        for chunk in deepseek.chat(prompt, stream=True, sse=True, thinking=thinking):
            yield chunk
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)
```

## 前端 JavaScript 示例

```javascript
const evtSource = new EventSource('/api/chat?prompt=分析600519');

// 监听流开始
evtSource.addEventListener('start', (event) => {
  const data = JSON.parse(event.data);
  console.log('Model:', data.model);
  console.log('Reasoning:', data.reasoning);
  
  // 根据 reasoning 状态显示/隐藏推理区域
  if (data.reasoning === 'enabled') {
    showReasoningPanel();
  }
});

// 监听推理内容（思维链）
evtSource.addEventListener('reasoning', (event) => {
  const data = JSON.parse(event.data);
  appendReasoning(data.content);
});

// 监听消息内容
evtSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  appendText(data.content);
});

// 监听工具调用
evtSource.addEventListener('tool_call', (event) => {
  const data = JSON.parse(event.data);
  showToolCall(data.id, data.name, data.arguments);
});

// 监听工具结果
evtSource.addEventListener('tool_result', (event) => {
  const data = JSON.parse(event.data);
  if (data.result !== undefined) {
    showToolResult(data.tool_call_id, data.result);
  } else if (data.error !== undefined) {
    showToolError(data.tool_call_id, data.error);
  }
});

// 监听错误
evtSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  showError(data.message);
});

// 监听流结束
evtSource.addEventListener('end', (event) => {
  const data = JSON.parse(event.data);
  console.log('Stream ended:', data.finish_reason);
  console.log('Statistics:', data.stats);
  console.log(`Tools: ${data.stats.tool_calls} calls, ${data.stats.tool_results} results`);
  console.log(`Tokens: ${data.stats.tokens.total} (prompt: ${data.stats.tokens.prompt}, completion: ${data.stats.tokens.completion})`);
  console.log(`Timing: ${data.stats.timing_ms.total}ms (first byte: ${data.stats.timing_ms.first_byte}ms)`);
  evtSource.close();
});

// 连接错误处理
evtSource.onerror = (err) => {
  console.error('SSE Connection Error:', err);
  evtSource.close();
};
```

### React Hooks 示例

```javascript
import { useEffect, useState } from 'react';

function ChatComponent({ prompt, thinking = true }) {
  const [messages, setMessages] = useState([]);
  const [reasoning, setReasoning] = useState([]);
  const [toolCalls, setToolCalls] = useState([]);
  const [status, setStatus] = useState('idle');
  const [reasoningEnabled, setReasoningEnabled] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams({
      prompt,
      thinking: thinking.toString()
    });
    const evtSource = new EventSource(`/api/chat?${params}`);

    evtSource.addEventListener('start', (e) => {
      const data = JSON.parse(e.data);
      setStatus('streaming');
      setReasoningEnabled(data.reasoning === 'enabled');
    });

    evtSource.addEventListener('reasoning', (e) => {
      const data = JSON.parse(e.data);
      setReasoning(prev => [...prev, data.content]);
    });

    evtSource.addEventListener('message', (e) => {
      const data = JSON.parse(e.data);
      setMessages(prev => [...prev, data.content]);
    });

    evtSource.addEventListener('tool_call', (e) => {
      const data = JSON.parse(e.data);
      setToolCalls(prev => [...prev, { ...data, status: 'pending' }]);
    });

    evtSource.addEventListener('tool_result', (e) => {
      const data = JSON.parse(e.data);
      setToolCalls(prev => prev.map(tc => 
        tc.id === data.tool_call_id 
          ? { ...tc, status: 'completed', result: data.result || data.error }
          : tc
      ));
    });

    evtSource.addEventListener('end', (e) => {
      const data = JSON.parse(e.data);
      setStatus('completed');
      console.log('Stats:', data.stats);
      evtSource.close();
    });

    evtSource.onerror = () => {
      setStatus('error');
      evtSource.close();
    };

    return () => evtSource.close();
  }, [prompt, thinking]);

  return (
    <div>
      <div>Status: {status}</div>
      {reasoningEnabled && (
        <div className="reasoning-panel">
          <h3>💭 推理过程</h3>
          <pre>{reasoning.join('')}</pre>
        </div>
      )}
      <div className="messages">
        <h3>📝 回答</h3>
        <p>{messages.join('')}</p>
      </div>
      {toolCalls.length > 0 && (
        <div className="tool-calls">
          <h3>🔧 工具调用</h3>
          {toolCalls.map((tc, i) => (
            <div key={i}>
              {tc.name}: {tc.status}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

## FastAPI 示例

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from utils.models import deepseek

app = FastAPI()

@app.post("/api/chat")
async def chat(prompt: str):
    def generate():
        for chunk in deepseek.chat(prompt, stream=True, sse=True):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## 注意事项

1. **内容类型**：响应的 `Content-Type` 必须设置为 `text/event-stream`
2. **连接保持**：SSE 是长连接，需要确保服务器支持
3. **跨域处理**：如果前端和后端不同域，需要配置 CORS
4. **错误处理**：客户端应监听 `error` 事件并适当重连
5. **结束信号**：收到 `[DONE]` 后应关闭连接

## 测试命令

```bash
# 测试 SSE 格式（Python，默认启用推理模式）
python -m utils.models.deepseek

# 使用 curl 测试（假设你已经创建了 Web API）
curl -N http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"分析600519","thinking":true}'

# 禁用推理模式
curl -N http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"分析600519","thinking":false}'

# 使用 httpie 测试
http --stream POST localhost:5000/api/chat prompt="分析600519" thinking:=true
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
