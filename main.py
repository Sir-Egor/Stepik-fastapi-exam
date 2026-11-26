from fastapi import FastAPI
from async_app.routers import categories, products, users, review

app = FastAPI(
    title="FastAPI Интернет-магазин",
    version="0.1.0"
)

app.include_router(categories.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(review.router)

@app.get("/")
async def root() -> str:
    return "Заглушка"
