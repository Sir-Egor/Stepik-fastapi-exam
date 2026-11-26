from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, HTTPException

from typing import Annotated

from async_app.db_depends import get_db
from async_app.schemas import Product as SchemaProduct, ProductCreate, Review as ReviewSchema
from async_app.models import Product as ModelProduct
from async_app.models.users import User as UserModel
from async_app.models.reviews import Review as ReviewModel
from async_app.auth import get_current_seller

from async_app.routers.categories import category_exists

# Создаём маршрутизатор для товаров
router = APIRouter(
    prefix="/products",
    tags=["products"],
)

async def product_exists(db: AsyncSession, product_id: int, is_active: bool = True, detail = "Product not found or inactive") -> ModelProduct:
    
    stmt = select(ModelProduct).where(ModelProduct.id == product_id).limit(1)    
    if is_active:
        stmt = stmt.where(ModelProduct.is_active == True)
    
    product = (await db.scalars(stmt)).one_or_none()
    
    print("Product: ", product)
    
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    
    await category_exists(db=db, category_id=product.category_id, detail="Product category not found")
    
    return product

def compare_seller_product(seller: UserModel, product: ModelProduct):
    if seller.id != product.seller_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You can only edit your own products"
        )
         
@router.get("/", response_model=list[SchemaProduct])
async def get_all_products(db: Annotated[AsyncSession, Depends(get_db)]) -> list[SchemaProduct]:
    return (await db.scalars(select(ModelProduct).where(ModelProduct.is_active == True))).all()

@router.get("/category/{category_id}", response_model=list[SchemaProduct])
async def get_products_by_category(category_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> list[SchemaProduct]:
    
    await category_exists(db, category_id)
    
    stmt = select(ModelProduct).where(ModelProduct.is_active == True, ModelProduct.category_id == category_id)
        
    return (await db.scalars(stmt)).all()

@router.get("/products/{product_id}/reviews", response_model=list[ReviewSchema])
async def get_product_reviews(product_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Возвращает отзывы о товаре
    """
    await product_exists(db, product_id)
      
    stmt = select(ReviewModel).where(ReviewModel.is_active == True, ReviewModel.product_id == product_id)
        
    return (await db.scalars(stmt)).all()

@router.get("/{product_id}", response_model=SchemaProduct)
async def get_product(product_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> SchemaProduct:
    return await product_exists(db, product_id)

@router.post("/", response_model=SchemaProduct, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate,
                         db: Annotated[AsyncSession, Depends(get_db)], 
                         current_user: UserModel = Depends(get_current_seller)
) -> SchemaProduct:
    """
    Создаёт новый товар, привязанный к текущему продавцу (только для 'seller').
    """
    await category_exists(db, product.category_id)
    
    new_product = ModelProduct(**product.model_dump(exclude_unset=True), seller_id=current_user.id)
    
    db.add(new_product)
    await db.commit()
    
    return new_product

@router.put("/{product_id}", response_model=SchemaProduct)
async def update_product(product_id: int,
                         product_update: ProductCreate,
                         db: Annotated[AsyncSession, Depends(get_db)], 
                         current_user: UserModel = Depends(get_current_seller)
) -> SchemaProduct:
    
    product = await product_exists(db, product_id)
    
    compare_seller_product(current_user, product)
    
    await db.execute(update(ModelProduct).where(ModelProduct.id == product_id).values(**product_update.model_dump(exclude_unset=True)))
    await db.commit()
    
    return product


@router.delete("/{product_id}")
async def delete_product(product_id: int,
                         db: Annotated[AsyncSession, Depends(get_db)], 
                         current_user: UserModel = Depends(get_current_seller)
) -> dict:
    
    product = await product_exists(db, product_id)
    
    compare_seller_product(current_user, product)
    
    await db.execute(update(ModelProduct).where(ModelProduct.id == product_id).values(is_active = False))
    await db.commit()
    
    return {"status": "success", "message": "Product marked as inactive"}