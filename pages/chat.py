import json
from utils.models.deepseek import chat
from flask import Blueprint, request, jsonify, Response, stream_with_context, g

chat_page = Blueprint('chat', __name__)

@chat_page.route('/endpoint', methods=['POST'])
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
                    })


@chat_page.route('/endpoint-sync', methods=['POST'])
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