from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from async_app.models.categories import Category as CategoryModel
from async_app.schemas import Category as CategorySchema, CategoryCreate, CategoryUpdate
from async_app.db_depends import get_db

router = APIRouter(
    prefix="/categories",
    tags=["categories"]
)

async def category_exists(db: AsyncSession, category_id: int, is_active: bool = True, detail: str = "Category not found") -> CategoryModel:
    
    stmt = select(CategoryModel.id).where(CategoryModel.id == category_id).limit(1)
    if is_active:
        stmt = stmt.where(CategoryModel.is_active == True)
    
    category = (await db.scalars(stmt)).one_or_none()

    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    
    return category

@router.get("/", response_model=list[CategorySchema], description="Список всех категорий")
async def read_all_categories(db: AsyncSession = Depends(get_db)) -> list[CategorySchema]:
    return (await db.scalars(select(CategoryModel))).all()

@router.get("/active", response_model=list[CategorySchema], description="Список всех активных категорий")
async def read_active_categories(db: AsyncSession = Depends(get_db)) -> list[CategorySchema]:
    return (await db.scalars(select(CategoryModel).where(CategoryModel.is_active == True))).all()

@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: AsyncSession = Depends(get_db)):
    
    if category.parent_id is not None:
        await category_exists(db, category.parent_id, detail="Parent category not found")

    new_category = CategoryModel(**category.model_dump())
    db.add(new_category)
    await db.commit()
    
    return new_category

@router.put("/{category_id}", response_model=CategorySchema)
async def update_category(category_id: int, category: CategoryUpdate, db: AsyncSession = Depends(get_db)) -> CategorySchema:
    
    if category.parent_id == category_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Your own ID and parent's ID cannot be the same!")
              
    await category_exists(db, category_id)
    if category.parent_id is not None:
        await category_exists(db, category.parent_id, detail="Parent category not found")
    
    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(**category.model_dump(exclude_unset=True)))
    await db.commit()
    
    stmt_result = await db.scalars(select(CategoryModel).where(CategoryModel.id == category_id).limit(1))
    return stmt_result.one()

@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(category_id: Annotated[int, Path(ge=0)], db: AsyncSession = Depends(get_db)) -> dict:
    
    await category_exists(db, category_id)
    
    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(is_active=False))
    await db.commit()
    
    return {'status': "success", "message": "Category marked as inactive"}
