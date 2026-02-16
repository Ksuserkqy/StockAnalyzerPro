from dotenv import load_dotenv
import os
import json
from flask import Flask, render_template, request, Response
from utils.models.deepseek import chat

load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='static')


@app.route('/')
def home():
    """主页"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """
    聊天接口 - 流式返回 SSE 格式数据
    
    Request: 
        {
            "prompt": "用户问题",
            "thinking": true/false (可选, 默认true)
        }
    """
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    thinking = data.get('thinking', True)
    
    if not prompt:
        return {'error': '问题不能为空'}, 400
    
    def generate():
        """生成SSE流"""
        try:
            for chunk in chat(prompt, stream=True, thinking=thinking):
                yield chunk
        except Exception as e:
            error_msg = f"event: error\ndata: {json.dumps({'error': str(e), 'message': '处理请求时发生错误'}, ensure_ascii=False)}\n\n"
            yield error_msg
    
    return Response(generate(), mimetype='text/event-stream', 
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Access-Control-Allow-Origin': '*'
                    })


@app.route('/api/chat-sync', methods=['POST'])
def chat_sync_endpoint():
    """
    同步聊天接口 - 直接返回最终结果（不使用SSE）
    
    Request:
        {
            "prompt": "用户问题",
            "thinking": true/false (可选, 默认true)
        }
    """
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    thinking = data.get('thinking', True)
    
    if not prompt:
        return {'error': '问题不能为空'}, 400
    
    try:
        result = chat(prompt, stream=False, thinking=thinking)
        return {'success': True, 'result': result}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)
