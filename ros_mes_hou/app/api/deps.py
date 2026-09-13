#后端认证
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.core.security import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # 安全修复：已删除（软删除）的账号不允许继续使用旧 token 访问系统
    user = db.query(models.User).filter(
        models.User.Username == username,
        models.User.del_flag == False,
    ).first()

    if user is None:
        raise credentials_exception

    # 安全修复：被锁定的账号即使持有有效 token 也拒绝访问
    if user.Islock:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账号已被锁定，请联系管理员",
        )

    return user


def get_current_admin(
    current_user: models.User = Depends(get_current_user),
):
    """管理员权限依赖：仅 Type_ID == 1（管理员）可通过。

    用于用户管理等敏感接口，防止普通操作员越权调用。
    """
    if current_user.Type_ID != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
