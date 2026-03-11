#Rafael dos Santos Tavares

from fastapi import FastAPI
from routers import ClienteRouter, FuncionarioRouter, ProdutoRouter
from settings import HOST, PORT, RELOAD
import uvicorn

# import das classes com as rotas/endpoints
app = FastAPI()
# mapeamento das rotas/endpoints

app.include_router(FuncionarioRouter.router)
app.include_router(ClienteRouter.router)
app.include_router(ProdutoRouter.router)

# rota padrão
@app.get("/", tags=["Root"], status_code=200)
def root():
    return {"detail":"API Pastelaria", "Swagger UI": "http://127.0.0.1:8000/docs", "ReDoc": "http://127.0.0.1:8000/redoc" }

if __name__ == "__main__":
    uvicorn.run('main:app', host=HOST, port=int(PORT), reload=RELOAD)