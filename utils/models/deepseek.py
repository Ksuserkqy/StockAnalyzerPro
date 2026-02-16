import os, json, time
from dotenv import load_dotenv; load_dotenv()
from openai import OpenAI
import utils.mcp.init as mcp

client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")

def _chat_stream(prompt, mcp_max_call=20, thinking=True):
    """流式输出（生成器）- 返回 SSE 格式"""
    tools = mcp.tool_list()
    system_prompt = (
        "你是专业的A股分析助手。\n"
        "当用户询问具体股票的实时价格/涨跌幅/成交量等最新行情时，必须优先调用相关工具获取最新数据后再分析，你最多只能调用1个工具"
        "禁止凭空猜测实时行情。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    
    # 统计信息
    stats = {
        'tool_calls': 0,
        'tool_results': 0,
        'tokens': {'prompt': 0, 'completion': 0, 'total': 0},
        'timing_ms': {'first_byte': 0, 'total': 0}
    }
    start_time = time.time() * 1000  # 转换为毫秒
    first_byte_time = None
    
    for call_round in range(mcp_max_call):
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=True,
            extra_body={"thinking": {"type": "enabled"}} if thinking else {}
        )
        
        # 第一轮时发送 start 事件
        if call_round == 0:
            start_data = {
                'model': 'deepseek-chat',
                'reasoning': 'enabled' if thinking else 'disabled'
            }
            yield f"event: start\ndata: {json.dumps(start_data, ensure_ascii=False)}\n\n"
        
        # 流式输出处理
        content_chunks = []
        reasoning_chunks = []  # 用于存储推理内容（如果有）
        tool_calls_dict = {}  # {index: {id, name, arguments}}
        last_chunk = None  # 保存最后一个 chunk 以获取 token 信息
        
        for chunk in resp:
            # 记录首字节时间
            if first_byte_time is None:
                first_byte_time = time.time() * 1000
                stats['timing_ms']['first_byte'] = int(first_byte_time - start_time)
            
            last_chunk = chunk
            delta = chunk.choices[0].delta
            
            # 处理推理内容（reasoning_content，如果模型支持）
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_chunks.append(delta.reasoning_content)
                yield f"event: reasoning\ndata: {json.dumps({'content': delta.reasoning_content}, ensure_ascii=False)}\n\n"
            
            # 处理内容增量
            if hasattr(delta, 'content') and delta.content:
                content_chunks.append(delta.content)
                # SSE 格式输出
                yield f"event: message\ndata: {json.dumps({'content': delta.content}, ensure_ascii=False)}\n\n"
            
            # 处理工具调用增量
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {
                            'id': '',
                            'name': '',
                            'arguments': ''
                        }
                    
                    if tc_delta.id:
                        tool_calls_dict[idx]['id'] = tc_delta.id
                    if hasattr(tc_delta.function, 'name') and tc_delta.function.name:
                        tool_calls_dict[idx]['name'] = tc_delta.function.name
                    if hasattr(tc_delta.function, 'arguments') and tc_delta.function.arguments:
                        tool_calls_dict[idx]['arguments'] += tc_delta.function.arguments
        
        # 流结束，提取 token 信息
        if last_chunk and hasattr(last_chunk, 'usage') and last_chunk.usage:
            usage = last_chunk.usage
            stats['tokens']['prompt'] = getattr(usage, 'prompt_tokens', 0)
            stats['tokens']['completion'] = getattr(usage, 'completion_tokens', 0)
            stats['tokens']['total'] = getattr(usage, 'total_tokens', 0)
        
        # 计算总时间
        stats['timing_ms']['total'] = int(time.time() * 1000 - start_time)
        
        # 判断是否有工具调用
        if not tool_calls_dict:
            # 没有工具调用，直接返回
            end_data = {
                'finish_reason': 'stop',
                'stats': stats
            }
            yield f"event: end\ndata: {json.dumps(end_data, ensure_ascii=False)}\n\n"
            return
        
        # 有工具调用，构建消息并执行工具
        full_content = ''.join(content_chunks)
        tool_calls_list = []
        for idx in sorted(tool_calls_dict.keys()):
            tc = tool_calls_dict[idx]
            tool_calls_list.append({
                'id': tc['id'],
                'type': 'function',
                'function': {
                    'name': tc['name'],
                    'arguments': tc['arguments']
                }
            })
        
        # 添加 assistant 消息（带工具调用）
        assistant_msg = {
            'role': 'assistant',
            'content': full_content or None,
            'tool_calls': tool_calls_list
        }
        # 如果启用了推理模式，必须添加 reasoning_content（即使为空）
        if thinking:
            assistant_msg['reasoning_content'] = ''.join(reasoning_chunks) if reasoning_chunks else ''
        
        messages.append(assistant_msg)
        
        # 执行工具并回填结果
        for i, tc in enumerate(tool_calls_list, 1):
            tool_call_id = tc['id']
            tool_name = tc['function']['name']
            tool_args = json.loads(tc['function']['arguments'] or "{}")
            
            # 统计工具调用
            stats['tool_calls'] += 1
            
            # 输出工具调用信息
            tool_call_info = {
                'id': tool_call_id,
                'type': 'mcp',
                'name': tool_name,
                'arguments': tool_args,
                'index': i,
                'total': len(tool_calls_list)
            }
            yield f"event: tool_call\ndata: {json.dumps(tool_call_info, ensure_ascii=False)}\n\n"
            
            # 执行工具
            try:
                mcp_result = mcp.tool_call(tool_name, tool_args)
                
                # 统计工具结果
                stats['tool_results'] += 1
                
                # 输出工具执行结果
                tool_result_info = {
                    'tool_call_id': tool_call_id,
                    'name': tool_name,
                    'success': True,
                    'result': mcp_result
                }
                yield f"event: tool_result\ndata: {json.dumps(tool_result_info, ensure_ascii=False)}\n\n"
                
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc['id'],
                    'content': json.dumps(mcp_result, ensure_ascii=False),
                })
            except Exception as e:
                # 统计工具结果（即使失败也算）
                stats['tool_results'] += 1
                
                # 输出工具执行错误
                tool_error_info = {
                    'tool_call_id': tool_call_id,
                    'name': tool_name,
                    'success': False,
                    'error': str(e)
                }
                yield f"event: tool_result\ndata: {json.dumps(tool_error_info, ensure_ascii=False)}\n\n"
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc['id'],
                    'content': json.dumps({'error': str(e)}, ensure_ascii=False),
                })
        
        # 继续下一轮（流式）
        continue
    
    # 到达最大轮数
    stats['timing_ms']['total'] = int(time.time() * 1000 - start_time)
    
    error_info = {
        'finish_reason': 'length',
        'message': '工具调用次数过多，已停止'
    }
    yield f"event: error\ndata: {json.dumps(error_info, ensure_ascii=False)}\n\n"
    end_data = {
        'finish_reason': 'length',
        'stats': stats
    }
    yield f"event: end\ndata: {json.dumps(end_data, ensure_ascii=False)}\n\n"


def _chat_non_stream(prompt, mcp_max_call=20, thinking=True):
    """非流式输出 - 直接返回最终结果"""
    tools = mcp.tool_list()
    system_prompt = (
        "你是专业的A股分析助手。\n"
        "当用户询问具体股票的实时价格/涨跌幅/成交量等最新行情时，必须优先调用相关工具获取最新数据后再分析，你最多只能调用1个工具"
        "禁止凭空猜测实时行情。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    
    for call_round in range(mcp_max_call):
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=False,
            extra_body={"thinking": {"type": "enabled"}} if thinking else {}
        )
        
        msg = resp.choices[0].message

        # 1) 没有 tool_calls -> 直接结束
        if not getattr(msg, "tool_calls", None):
            return msg.content

        # 2) 有 tool_calls -> 逐个执行并回填，继续下一轮
        messages.append(msg)  # 把 assistant 的 tool_calls 消息加入上下文

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tool_args = json.loads(tc.function.arguments or "{}")
            # 调 MCP 工具
            mcp_result = mcp.tool_call(tool_name, tool_args)

            # 回填给模型（role=tool 必须带 tool_call_id）
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(mcp_result, ensure_ascii=False),
                }
            )

    return "（工具调用次数过多，已停止）"


def chat(prompt, stream=False, mcp_max_call=20, thinking=True):
    """
    与 AI 助手对话
    
    Args:
        prompt: 用户输入的问题
        stream: 是否使用流式输出（True 时返回 SSE 格式）
        mcp_max_call: 最大工具调用次数
        thinking: 是否启用推理模式
    """
    if stream:
        return _chat_stream(prompt, mcp_max_call, thinking)
    else:
        return _chat_non_stream(prompt, mcp_max_call, thinking)


if __name__ == "__main__":
    stream = True
    if not stream:
        result = chat("分析一下 600519 当前实时行情，并给出短线观点，不超过100个token", stream=False, thinking=True)
        print(result)
    else:
        for chunk in chat("分析一下 600519 当前实时行情，并给出短线观点", stream=True):
            print(chunk, end='', flush=True)

# Run: python -m utils.models.deepseek