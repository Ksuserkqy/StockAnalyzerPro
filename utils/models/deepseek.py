import os, json
from dotenv import load_dotenv; load_dotenv()
from openai import OpenAI
import utils.mcp.init as mcp

client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")

def chat(prompt, stream=False, mcp_max_call=5):
    tools = mcp.tool_list()
    system_prompt = (
        "你是专业的A股分析助手。\n"
        "当用户询问具体股票的实时价格/涨跌幅/成交量等最新行情时，必须优先调用相关工具获取最新数据后再分析，"
        "禁止凭空猜测实时行情。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    for _ in range(mcp_max_call):
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=False,
        )
        msg = resp.choices[0].message

        # 1) 没有 tool_calls -> 直接结束
        if not getattr(msg, "tool_calls", None):
            return msg.content

        # 2) 有 tool_calls -> 逐个执行并回填
        messages.append(msg)  # 把 assistant 的 tool_calls 消息加入上下文

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tool_args = json.loads(tc.function.arguments or "{}")
            # 调 MCP 工具
            mcp_result= mcp.tool_call(tool_name, tool_args)

            # 回填给模型（role=tool 必须带 tool_call_id）
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(mcp_result, ensure_ascii=False),
                }
            )

    return "（工具调用次数过多，已停止）"

if __name__ == "__main__":
    # print(chat("你好").choices[0].message.content)
    print(chat("分析一下 600519 当前实时行情，并给出短线观点"))

# Run: python -m utils.models.deepseek