from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from async_app.db_depends import get_db
from async_app.config import SECRET_KEY, ALGORITHM
from async_app.schemas import UserCreate, User as UserSchema, RefreshTokenRequest
from async_app.models import User as UserModel
from async_app.auth import hash_password, verify_password, create_token

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

def get_401_exception(detail: str):
    return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_user_by_refresh_token(db: AsyncSession, refresh_token: str) -> UserModel:
    """
    Получает пользователя используя его refresh_token. Проверяет валидность токена и пользователя.
    """
    credentials_exception = get_401_exception("Could not validate refresh token")
    
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("token_type")
    
        # Проверяем, что токен действительно refresh
        if email is None or token_type != "refresh":
            raise credentials_exception
    
    except jwt.ExpiredSignatureError:
        # refresh-токен истёк
        raise credentials_exception
    except jwt.PyJWTError:
        # подпись неверна или токен повреждён
        raise credentials_exception
    
    # Проверяем, что пользователь существует и активен
    result = await db.scalars(
        select(UserModel).where(
            UserModel.email == email,
            UserModel.is_active == True
        )
    )
        
    user = result.first()
    if user is None:
        raise credentials_exception
    
    return user  
    
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserSchema)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)) -> UserSchema:
    """
    Создает пользователя в базе данных
    """
    result = await db.scalars(select(UserModel).where(UserModel.email == user.email))
    if result.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Email already registered")
        
    db_user = UserModel(
        email=user.email,
        hashed_password=hash_password(user.password),
        role=user.role
    )
    
    db.add(db_user)
    await db.commit()
    return db_user

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Аутентифицирует пользователя и возвращает JWT с email, role и id.
    """
    result = await db.scalars(
        select(UserModel).where(UserModel.email == form_data.username, UserModel.is_active == True))
    user = result.first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise get_401_exception("Incorrect email or password")
    
    user_dict = {"sub": user.email, "role": user.role, "id": user.id}
    
    access_token = create_token(user_dict, TOKEN_TYPE_ACCESS)
    refresh_token = create_token(user_dict, TOKEN_TYPE_REFRESH)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh-token")
async def refresh_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Обновляет refresh-токен, принимая старый refresh-токен в теле запроса.
    """
    user = await get_user_by_refresh_token(db, body.refresh_token)

    new_refresh_token = create_token({"sub": user.email, "role": user.role, "id": user.id}, TOKEN_TYPE_REFRESH)

    return {"refresh_token": new_refresh_token, "token_type": "bearer"}

@router.post("/refresh-access-token")
async def refresh_access_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Обновляет access-токен, принимая refresh-токен в теле запроса.
    """
    user = await get_user_by_refresh_token(db, body.refresh_token)

    access_token = create_token({"sub": user.email, "role": user.role, "id": user.id}, TOKEN_TYPE_ACCESS)
        
    return {"access_token": access_token, "token_type": "bearer"}

