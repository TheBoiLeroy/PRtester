# task.md

## 🧠 Objective

Build a full-stack web application for managing contractors and their timesheets, with support for:

- Contractor registration using an `org_id`
- Boss (manager) login, viewing, and approval of pending contractor applications
- Assigning custom pay rates to contractors
- Contractor timesheet submission (hours per day per month)
- Boss view of contractor timesheets and pay calculations
- Clear distinction between contractors with or without timesheets
- Backend image handling via S3 or another image upload flow
- Real-time updates where necessary using Socket.IO

This system is intended for use on mobile (Flutter frontend), backed by a Flask/Python backend with a SQLite or PostgreSQL database. The backend should expose a clean REST API and optionally support WebSocket (via Flask-SocketIO) for real-time changes.

---

## 🧱 System Architecture

- **Frontend**: Flutter (mobile)
- **Backend**: Flask with Flask-SocketIO, SQLAlchemy
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Storage**: Amazon S3 for contractor-uploaded images
- **Auth**: Session/token-based per user type (Contractor, Boss)

---

## 📂 Files and Responsibilities

### `/backend/app.py`
- Flask app entry point.
- Initializes app, Socket.IO, and registers blueprints.
- Handles app config including DB, CORS, and S3 keys.

### `/backend/models.py`
- Defines SQLAlchemy models:
  - `User` (abstract base, inherited by Boss and Contractor)
  - `Boss` (id, name, email, org_id)
  - `Contractor` (id, name, email, org_id, boss_id, pay_rate, approved)
  - `Timesheet` (contractor_id, month, hours_by_day, image_urls)

### `/backend/routes/contractors.py`
- Handles:
  - POST `/apply`: Contractor applies using `org_id`
  - GET `/contractors`: Boss views contractors linked to their org
  - POST `/approve`: Boss approves contractor
  - GET `/dropdown`: Return contractor list for dropdown (exclude unapproved or include all based on filter)

### `/backend/routes/timesheets.py`
- Handles:
  - POST `/timesheets`: Contractor submits timesheet with optional image(s)
  - GET `/timesheets`: Boss views all timesheets
  - Calculation logic: Estimated pay = sum(hours) * contractor's pay_rate

### `/backend/routes/auth.py`
- Handles simple auth:
  - POST `/login`: Boss or Contractor login
  - POST `/logout`
  - Possibly generate auth tokens or maintain session

### `/backend/services/s3.py`
- Functions to upload images to S3 and return URLs
- Securely handles AWS credentials

### `/backend/utils/helpers.py`
- JSON parsing, date/month utils, error formatting

---

## 📦 Data Flow

1. **Contractor Signup**:
   - Hits `/apply` with `name`, `email`, `org_id`
   - Waits in DB with `approved = False`

2. **Boss View + Approve**:
   - Logs in and calls `/contractors`
   - Sees pending list and clicks approve, which sets `approved = True` and links `boss_id`

3. **Timesheet Submission**:
   - Contractor selects month, uploads hour data (map of day -> hours), and optional image(s)
   - Backend calculates total pay (based on custom pay_rate)
   - Stores hours, pay, and S3 image URLs

4. **Boss Dashboard**:
   - Displays contractor list
   - Shows total hours and pay for each
   - Can filter by contractor and month

---

## 🔁 Real-Time Interactions (Optional)
- Use Flask-SocketIO to:
  - Notify boss when a new contractor applies
  - Notify contractor when they are approved
  - Emit events when timesheets are submitted

---

## 🖼 UI Expectations (For Flutter Agent)
- Dropdown to select contractor (includes all approved; if no timesheet, still shows)
- Table/list per contractor of:
  - Month
  - Daily hours
  - Total pay
  - Image thumbnails (from S3 URLs)
- Boss-only actions (approve, set pay_rate)
- Contractor-only actions (submit timesheet)

---

## 🧪 Testing Requirements
- Unit test routes and models
- Mock S3 during tests
- Verify permission boundaries (e.g., contractor can’t approve themselves)
