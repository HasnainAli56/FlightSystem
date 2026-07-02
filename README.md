# FlightApp

A Flask-based Flight Time Prediction application with Firebase Authentication and EmailJS OTP verification.

## Setup Instructions

1.  **Environment Variables**:
    - Open `.env` file.
    - Fill in your EmailJS credentials:
        - `EMAILJS_SERVICE_ID`
        - `EMAILJS_TEMPLATE_ID`
        - `EMAILJS_USER_ID` (Public Key)
    - Fill in `FIREBASE_API_KEY` (Web API Key from Project Settings > General).

2.  **Firebase Credentials**:
    - Download your `serviceAccountKey.json` from Firebase Console (Project Settings > Service Accounts > Generate New Private Key).
    - Place the file in the `FlightApp` directory (replacing the placeholder).

3.  **Run the Application**:
    ```bash
    run_project.bat
    ```
    - Access the app at `http://127.0.0.1:5000`.
    - The run script creates a fresh virtual environment and installs dependencies automatically.
    - Python 3.11+ must be installed on the computer first.

4.  **MongoDB Notes**:
    - The app now starts even when MongoDB Atlas DNS/network access is unavailable.
    - In that case it uses an in-memory development database, so data resets when the app restarts.
    - Set `REQUIRE_MONGO=true` in `.env` if you want startup to fail when Atlas cannot connect.
    - For client testing without MongoDB, login with `user@gmail.com` / `12345678`.

## Features
- **User Registration**: Email OTP verification required.
- **Login**: Secure login with Firebase.
- **Dashboard**: Predict flight times between cities.
- **Admin Panel**: Manage users (Block/Unblock).
- **Profile**: Update display name and password.
- **Design**: Modern UI with TailwindCSS.
