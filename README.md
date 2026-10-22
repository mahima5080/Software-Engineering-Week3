# Blog Platform API (Software Engineering — Week 3)

A RESTful Blog Platform API constructed with FastAPI, offering JWT user authentication, post CRUD operations, comment tracking, post likes, title/content searching, limit-skip pagination, input validation, and rate limiting.

---

## 📌 Features

- **JWT Authentication:** User registration and login token generation with bcrypt password hashing.
- **Post CRUD Operations:** Full create, read, update, and delete access for posts[cite: 13].
- **Search & Pagination:** Search posts by keyword with configurable `skip` and `limit` parameters[cite: 13].
- **Likes & Comments:** Interactive post liking and comment thread management[cite: 13].
- **Rate Limiting:** Endpoint protection powered by SlowAPI[cite: 13].
- **Swagger Documentation:** Auto-generated interactive UI at `/docs`[cite: 13].

---

## 🚀 How to Run the API Locally

1. **Start the FastAPI server with Uvicorn:**
   ```bash
   uvicorn main:app --reload
   ```
