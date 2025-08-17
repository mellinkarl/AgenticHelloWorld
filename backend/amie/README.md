# 在当前目录下新建一个虚拟环境目录 .venv
python3 -m venv .venv

# 激活 (macOS/Linux, bash/zsh)
source amie/.venv/bin/activate

# 安装 环境
pip install -r requirements.in

# 激活
source .venv/bin/activate

# fire 后端 「PYTHONDONTWRITEBYTECODE for not genertae __pycache__」
PYTHONDONTWRITEBYTECODE=1 uvicorn amie.app.main:app --reload --host 127.0.0.1 --port 8000
PYTHONDONTWRITEBYTECODE=1 uvicorn amie.app.main:app --reload --host 127.0.0.1 --port 8000


## Swagger UI: 
http://127.0.0.1:8000/docs

## ReDoc: 
http://127.0.0.1:8000/redoc

# POST 调用
curl -X POST "http://127.0.0.1:8000/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "gcs_url": "gs://bucket/file.pdf",
           "metadata": { "author": "Alice", "field": "AI" }
         }'

# 返回值大概是：
# { "request_id": "uuid-1234" }

# GET 查询
curl "http://127.0.0.1:8000/state/uuid-1234"



# TODO：
本地环境（dev_mode=True）用 SqliteSaver("checkpoint.db")

部署环境默认用 MemorySaver()

