# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Sign up for activities

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## Authentication

Teachers sign in with `POST /auth/login`, sending credentials in the JSON body so
they never end up in access logs or browser history:

```json
{ "username": "principal", "password": "admin789" }
```

The response contains an opaque session token. Send it on every protected request:

```
Authorization: Bearer <token>
```

Sessions expire after 8 hours and can be ended early with `POST /auth/logout`.
Only a SHA-256 hash of each token is stored server side.

## API Endpoints

| Method | Endpoint                                            | Auth | Description                                                         |
| ------ | --------------------------------------------------- | ---- | ------------------------------------------------------------------- |
| POST   | `/auth/login`                                       | No   | Start a session and receive a bearer token                          |
| POST   | `/auth/logout`                                      | Yes  | Invalidate the current session token                                |
| GET    | `/auth/check-session`                               | Yes  | Return the profile tied to the session token                        |
| GET    | `/activities`                                       | No   | Get all activities with their details and current participant count |
| POST   | `/activities/{activity_name}/signup?email=...`      | Yes  | Sign up a student for an activity                                   |
| POST   | `/activities/{activity_name}/unregister?email=...`  | Yes  | Remove a student from an activity                                   |
| GET    | `/announcements/active`                             | No   | Get announcements that are currently visible                        |
| GET    | `/announcements`                                    | Yes  | Get all announcements, including scheduled and expired ones         |
| POST   | `/announcements`                                    | Yes  | Create an announcement                                              |
| PUT    | `/announcements/{announcement_id}`                  | Yes  | Update an announcement                                              |
| DELETE | `/announcements/{announcement_id}`                  | Yes  | Delete an announcement                                              |

Announcement create/update requests accept a JSON body:

```json
{
  "title": "Registration is open",
  "message": "Activity registration is open until the end of the month.",
  "start_date": "2026-09-01T08:00:00Z",
  "expiration_date": "2026-09-30T23:59:00Z"
}
```

`start_date` is optional; when omitted the announcement is visible immediately.
`expiration_date` is required, must be in the future, and must be after `start_date`.

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:

   - Name
   - Grade level

3. **Announcements** - Uses a generated identifier:

   - Title and message
   - Optional start date and required expiration date
   - Teacher who created it

4. **Sessions** - Uses the hashed token as identifier:
   - Teacher username
   - Expiry timestamp, removed automatically by a MongoDB TTL index

All data is stored in memory, which means data will be reset when the server restarts.
