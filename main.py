"""
Software Engineering - Week 3 Mini Project
Blog Platform API built with FastAPI
Features:
- JWT User Authentication & Password Hashing
- Full Post CRUD Operations
- Comments & Like Functionality
- Pagination & Title Search
- Rate Limiting via SlowAPI
- Auto-Generated Interactive Swagger Documentation (/docs)
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
import jwt
from passlib.context import CryptContext
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# -----------------------------------------------------------------------------
# CONFIGURATION & SECURITY
# -----------------------------------------------------------------------------
SECRET_KEY = "super-secret-jwt-key-for-blog-api"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Blog Platform API",
    description="Complete Blog Platform API with JWT Authentication, Post CRUD, Comments, Likes, and Rate Limiting.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# -----------------------------------------------------------------------------
# IN-MEMORY DATABASES
# -----------------------------------------------------------------------------
db_users = {}
db_posts = {}
db_comments = {}
db_likes = {}  # post_id -> set of usernames

# -----------------------------------------------------------------------------
# SCHEMAS (INPUT VALIDATION)
# -----------------------------------------------------------------------------
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=6)

class Token(BaseModel):
    access_token: str
    token_type: str

class PostCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    content: str = Field(..., min_length=5)

class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    author: str
    likes_count: int
    created_at: str

class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1)

class CommentResponse(BaseModel):
    id: int
    post_id: int
    author: str
    text: str
    created_at: str

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username not in db_users:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# -----------------------------------------------------------------------------
# 1. AUTHENTICATION ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/auth/register", status_code=status.HTTP_201_CREATED, tags=["Authentication"])
@limiter.limit("5/minute")
def register_user(request: Request, user: UserRegister):
    if user.username in db_users:
        raise HTTPException(status_code=400, detail="Username already registered")
    db_users[user.username] = {
        "username": user.username,
        "email": user.email,
        "password": hash_password(user.password)
    }
    return {"message": "User registered successfully"}

@app.post("/auth/login", response_model=Token, tags=["Authentication"])
@limiter.limit("10/minute")
def login_user(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = db_users.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

# -----------------------------------------------------------------------------
# 2. POST CRUD ENDPOINTS (WITH SEARCH & PAGINATION)
# -----------------------------------------------------------------------------
@app.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED, tags=["Posts"])
def create_post(post: PostCreate, current_user: str = Depends(get_current_user)):
    post_id = len(db_posts) + 1
    new_post = {
        "id": post_id,
        "title": post.title,
        "content": post.content,
        "author": current_user,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    db_posts[post_id] = new_post
    db_likes[post_id] = set()
    return {**new_post, "likes_count": 0}

@app.get("/posts", response_model=List[PostResponse], tags=["Posts"])
def get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    search: Optional[str] = None
):
    posts_list = list(db_posts.values())
    if search:
        posts_list = [p for p in posts_list if search.lower() in p["title"].lower() or search.lower() in p["content"].lower()]
    
    paginated = posts_list[skip : skip + limit]
    return [
        {**p, "likes_count": len(db_likes.get(p["id"], set()))}
        for p in paginated
    ]

@app.get("/posts/{post_id}", response_model=PostResponse, tags=["Posts"])
def get_single_post(post_id: int):
    post = db_posts.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {**post, "likes_count": len(db_likes.get(post_id, set()))}

@app.put("/posts/{post_id}", response_model=PostResponse, tags=["Posts"])
def update_post(post_id: int, updated_data: PostCreate, current_user: str = Depends(get_current_user)):
    post = db_posts.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["author"] != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to edit this post")
    
    post["title"] = updated_data.title
    post["content"] = updated_data.content
    return {**post, "likes_count": len(db_likes.get(post_id, set()))}

@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Posts"])
def delete_post(post_id: int, current_user: str = Depends(get_current_user)):
    post = db_posts.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["author"] != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")
    
    del db_posts[post_id]
    if post_id in db_likes:
        del db_likes[post_id]
    return None

# -----------------------------------------------------------------------------
# 3. LIKES & COMMENTS ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/posts/{post_id}/like", tags=["Likes"])
def toggle_like_post(post_id: int, current_user: str = Depends(get_current_user)):
    if post_id not in db_posts:
        raise HTTPException(status_code=404, detail="Post not found")
    
    likes_set = db_likes[post_id]
    if current_user in likes_set:
        likes_set.remove(current_user)
        return {"message": "Unliked post", "total_likes": len(likes_set)}
    else:
        likes_set.add(current_user)
        return {"message": "Liked post", "total_likes": len(likes_set)}

@app.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED, tags=["Comments"])
def add_comment(post_id: int, comment: CommentCreate, current_user: str = Depends(get_current_user)):
    if post_id not in db_posts:
        raise HTTPException(status_code=404, detail="Post not found")
    
    comment_id = len(db_comments) + 1
    new_comment = {
        "id": comment_id,
        "post_id": post_id,
        "author": current_user,
        "text": comment.text,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    db_comments[comment_id] = new_comment
    return new_comment

@app.get("/posts/{post_id}/comments", response_model=List[CommentResponse], tags=["Comments"])
def get_post_comments(post_id: int):
    if post_id not in db_posts:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return [c for c in db_comments.values() if c["post_id"] == post_id]