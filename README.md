```bash
    python -m venv .venv
    source .venv/bin/activate (Mac)
    .\.venv\Scripts\activate (Windows)
    pip install -r requirements.txt
    python main.py
```

### 拉取最新版代码
```bash
    git pull origin main
```

### 第一次运行环境准备
1. 新建Python虚拟环境
```bash
    python -m venv .venv
```

2. 激活虚拟环境
- MacOS/Linux:
```bash
    source .venv/bin/activate
```
- Windows:
```bash
    .\.venv\Scripts\activate
``` 

3. 安装依赖
```bash
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
    pip config set global.trusted-host mirrors.aliyun.com
    pip install -r requirements.txt
```
4. 运行程序
```bash
    python main.py
```

### 后续运行
1. 激活虚拟环境
- MacOS/Linux:
```bash
    source .venv/bin/activate
```
- Windows:
```bash
    .\.venv\Scripts\activate
``` 

2. 运行程序
```bash
    python main.py
```

**By 烤全羊KQY**

![whisper](static/whisper.png)

2026-02-02