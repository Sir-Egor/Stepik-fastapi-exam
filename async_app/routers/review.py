from fastapi import APIRouter, Depends, status, HTTPException

from sqlalchemy import select, update
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

from async_app.auth import get_current_buyer
from async_app.db_depends import get_db
from async_app.schemas import Review as ReviewSchema, ReviewCreate
from async_app.models.users import User as UserModel
from async_app.models.reviews import Review as ReviewModel
from async_app.models.products import Product as ProductModel
from async_app.routers.products import product_exists

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"]
)

async def get_rewiews(db: AsyncSession, id: int|None = None) -> list[ReviewModel]:
    stmt = select(ReviewModel).where(ReviewModel.is_active == True)
    
    if id is not None:
        stmt = stmt.where(ReviewModel.id == id)
    
    return (await db.scalars(stmt)).all()

async def get_rewiew(db: AsyncSession, id: int) -> ReviewModel:
    review = await get_rewiews(db, id)
    
    if len(review) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
        
    return review[0]

async def update_product_rating(db: AsyncSession, product_id: int):
    result = await db.execute(
        select(func.avg(ReviewModel.grade)).where(
            ReviewModel.product_id == product_id,
            ReviewModel.is_active == True
        )
    )
    avg_rating = result.scalar() or 0.0
    product = await db.get(ProductModel, product_id)
    product.rating = avg_rating
    await db.commit()


@router.get("", response_model=list[ReviewSchema])
async def read_rewiews(db: AsyncSession = Depends(get_db)):
    """
    Возвращает все отзывы
    """
    return await get_rewiews(db)

@router.post("", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(review: ReviewCreate, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_buyer)):
    """
    Создаёт новый отзыв
    """
    await product_exists(db, review.product_id)
    
    new_review = ReviewModel(**review.model_dump(exclude_unset=True), user_id=current_user.id)

    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)
    
    await update_product_rating(db, new_review.product_id)
    
    return new_review

@router.delete("/{review_id}")
async def delete_review(review_id: int, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_buyer)) -> dict:
    
    review = await get_rewiew(db, review_id)   
    if current_user.role != "admin" and review.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The user has not created a review")
    
    await db.execute(update(ReviewModel).where(ReviewModel.id == review_id).values(is_active = False))
    await db.commit()
    
    await update_product_rating(db, review.product_id)
    
    return {"status": "success", "message": "Review marked as inactive"}
