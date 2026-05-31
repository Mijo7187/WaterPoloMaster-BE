# 🔐 Authentication Feature

Complete authentication and authorization system for WaterPoloMaster API.

## 📁 Structure

```
app/features/auth/
├── __init__.py              # Package initialization
├── auth_router.py           # API endpoints (login, refresh, me)
├── auth_service.py          # Business logic (authentication, tokens)
├── auth_schemas.py          # Request/response models
├── auth_dependencies.py     # FastAPI dependencies (get_current_user, etc.)
└── auth_examples.py         # Usage examples
```

## 🎯 Features

- ✅ **JWT Authentication** - Secure token-based auth
- ✅ **Refresh Tokens** - Long-lived tokens for seamless UX
- ✅ **Admin Permissions** - Role-based access control
- ✅ **Active User Check** - Handle suspended accounts
- ✅ **Optional Auth** - Support public/private endpoints
- ✅ **FastAPI Dependencies** - Reusable auth helpers

## 🚀 Quick Start

### 1. Create a User
```bash
POST /api/users/
{
    "email": "admin@waterpolo.com",
    "username": "admin",
    "password": "admin123",
    "full_name": "Admin User"
}
```

### 2. Login
```bash
POST /api/auth/login
{
    "email": "admin@waterpolo.com",
    "password": "admin123"
}
```

**Response:**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

### 3. Use Access Token
```bash
GET /api/auth/me
Headers:
    Authorization: Bearer <access_token>
```

### 4. Refresh Token (when access token expires)
```bash
POST /api/auth/refresh
{
    "refresh_token": "<refresh_token>"
}
```

## 🔑 Token Types

### Access Token
- **Lifetime:** 30 minutes (configurable)
- **Purpose:** API authentication
- **Contains:** user_id, email, is_superuser, expiration
- **Usage:** Include in `Authorization: Bearer <token>` header

### Refresh Token
- **Lifetime:** 7 days (configurable)
- **Purpose:** Get new access tokens without re-login
- **Contains:** user_id, email, expiration
- **Usage:** Send to `/api/auth/refresh` endpoint

## 🛡️ Dependencies

Use these in your routers to protect endpoints:

### `get_current_user`
Requires authentication. Returns User object.

```python
from app.features.auth.auth_dependencies import get_current_user

@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)):
    return {"email": user.email}
```

### `get_current_active_user`
Requires authentication + active account.

```python
from app.features.auth.auth_dependencies import get_current_active_user

@router.post("/posts")
async def create_post(user: User = Depends(get_current_active_user)):
    # Only active users can create posts
    return {"message": "Post created"}
```

### `require_admin`
Requires admin privileges.

```python
from app.features.auth.auth_dependencies import require_admin

@router.delete("/users/{id}")
async def delete_user(id: int, admin: User = Depends(require_admin)):
    # Only admins can delete users
    return {"message": f"User {id} deleted"}
```

### `get_current_user_optional`
Optional authentication (works with or without token).

```python
from app.features.auth.auth_dependencies import get_current_user_optional

@router.get("/posts")
async def get_posts(user: User | None = Depends(get_current_user_optional)):
    if user:
        return {"posts": [...]}  # Personalized
    else:
        return {"posts": [...]}  # Public
```

## 📝 API Endpoints

### POST `/api/auth/login`
User login - returns access and refresh tokens.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "password123"
}
```

**Response:**
```json
{
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer"
}
```

**Errors:**
- `401` - Invalid credentials
- `403` - Account inactive

---

### POST `/api/auth/refresh`
Refresh access token using refresh token.

**Request:**
```json
{
    "refresh_token": "eyJhbGci..."
}
```

**Response:**
```json
{
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer"
}
```

**Errors:**
- `401` - Invalid/expired refresh token

---

### GET `/api/auth/me`
Get current user information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
    "id": 1,
    "email": "user@example.com",
    "username": "user123",
    "full_name": "John Doe",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2024-01-01T12:00:00Z"
}
```

**Errors:**
- `401` - No token or invalid token
- `403` - User inactive

## ⚙️ Configuration

Update `.env` file:

```env
# Token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES=30    # 30 minutes
REFRESH_TOKEN_EXPIRE_DAYS=7       # 7 days

# Secret key (KEEP THIS SECRET!)
SECRET_KEY=your-secret-key-here

# Algorithm
ALGORITHM=HS256
```

## 🔒 Security Best Practices

1. **Keep SECRET_KEY secret** - Never commit to git
2. **Use HTTPS in production** - Tokens sent in headers
3. **Short access token lifetime** - Limits damage if stolen
4. **Store tokens securely** - HttpOnly cookies or secure storage
5. **Validate token type** - Access vs refresh tokens
6. **Check user is active** - Handle suspended accounts
7. **Rotate refresh tokens** - Issue new refresh token on refresh

## 🧪 Testing

See [auth_examples.py](auth_examples.py) for complete testing guide.

**Quick test:**
```bash
# 1. Create user
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"test","password":"test123"}'

# 2. Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# 3. Get user info (replace TOKEN with access_token from step 2)
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer TOKEN"
```

## 🎨 Usage Patterns

### Pattern 1: Protected Route
```python
@router.get("/dashboard")
async def dashboard(user: User = Depends(get_current_active_user)):
    return {"message": f"Welcome {user.username}"}
```

### Pattern 2: Admin Only
```python
@router.post("/admin", dependencies=[Depends(require_admin)])
async def admin_action():
    return {"message": "Admin action completed"}
```

### Pattern 3: User or Admin Can Access
```python
@router.put("/posts/{post_id}")
async def update_post(
    post_id: int,
    user: User = Depends(get_current_active_user)
):
    # Get post from DB
    post = db.query(Post).filter(Post.id == post_id).first()
    
    # Check permission: owner or admin
    if post.user_id != user.id and not user.is_superuser:
        raise HTTPException(403, "Not authorized")
    
    # Update post...
```

## 📊 Authentication Flow

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ 1. POST /auth/login (email, password)
     ▼
┌──────────┐
│   API    │ 2. Verify credentials
└────┬─────┘
     │ 3. Return tokens (access + refresh)
     ▼
┌──────────┐
│  Client  │ 4. Store tokens
└────┬─────┘
     │ 5. GET /api/protected (Authorization: Bearer <access_token>)
     ▼
┌──────────┐
│   API    │ 6. Validate token → Extract user
└────┬─────┘
     │ 7. Return protected data
     ▼
┌──────────┐
│  Client  │
└────┬─────┘
     │ (30 min later - access token expires)
     │ 8. POST /auth/refresh (refresh_token)
     ▼
┌──────────┐
│   API    │ 9. Verify refresh token
└────┬─────┘
     │ 10. Return new tokens
     ▼
┌──────────┐
│  Client  │ 11. Continue using new access token
└──────────┘
```

## 🐛 Troubleshooting

### 401 Unauthorized
- Check token format: `Authorization: Bearer <token>`
- Verify token hasn't expired (use `/auth/refresh`)
- Ensure user exists and is active

### 403 Forbidden
- User account may be inactive (`is_active=False`)
- User may not have admin privileges (for admin-only routes)

### Token expired
- Use refresh token to get new access token
- If refresh token also expired, user must log in again

## 🔮 Future Enhancements

- [ ] Logout (token blacklist)
- [ ] Password reset via email
- [ ] Two-factor authentication (2FA)
- [ ] OAuth2 providers (Google, Facebook)
- [ ] Session management
- [ ] Rate limiting
- [ ] Role-based permissions (beyond admin/user)

## 📚 Related Files

- [security.py](../../core/security.py) - Password hashing, JWT utilities
- [config.py](../../core/config.py) - Configuration settings
- [users/](../users/) - User management feature
