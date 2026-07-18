from fastapi import FastAPI


app = FastAPI(
    title="银发安心服务平台"
)


@app.get("/")
def home():
    return {
        "message":"platform running"
    }


@app.get("/health")
def health():
    return {
        "status":"ok"
    }
