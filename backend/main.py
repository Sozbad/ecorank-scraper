from fastapi import FastAPI, Request
from gpt_agent_search import handle_search

app = FastAPI()

@app.get("/search")
async def search_handler(request: Request):
    product = request.query_params.get("productName")
    return handle_search(product)
