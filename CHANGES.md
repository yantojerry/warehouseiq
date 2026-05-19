# WarehouseIQ — Changelog

## New Features

### 1. Login Page (ui/login.py)
- Created a modern, user-friendly login page with purple theme ([theme color])
- Centered login card with clean design
- Title: "WarehouseIQ" with subtitle "Store Management System"
- Username input field with placeholder "Enter username"
- Password input field with placeholder "Enter password"
- Show/hide password toggle support
- Full-width "Sign In" button with purple background
- Enter key support for quick login
- Input validation with clear error messages
- Database-backed authentication against the `users` table
- Default admin account seeded on first run when the table is empty
- Professional footer showing sign-in guidance
- Consistent spacing and Segoe UI font throughout

### 2. Database Authentication Setup (database/db_manager.py)
- Added the `users` table to the database schema with `id`, `username`, `password`, and `created_at` columns
- Added `seed_default_admin_user()` to create the default admin account on first run if the table is empty
- Added `authenticate_user()` to validate login credentials through `get_connection()`

### 3. Application Entry Flow Update (main.py)
- Modified `main()` function to display login page first
- Login dialog is shown before the main window
- Main window only appears after successful authentication
- If login is cancelled, application exits gracefully
- Database initialization still happens before login is presented

## UI Improvements

### 4. Inventory Page Actions Column (ui/inventory.py)
- Changed Actions column (column 7) resize mode from `ResizeToContents` to `Fixed`
- Set column width to 250px for better button visibility
- Updated "Edit" button: `setMinimumWidth(80)` (was `setFixedSize(60, 28)`)
- Updated "Restock" button: `setMinimumWidth(90)` (was `setFixedSize(70, 28)`)
- Both button texts now fully visible and properly aligned

### 5. Sidebar Navigation Section Styling (main_window.py, styles.py)
- Added 4px spacing between nav buttons for cleaner layout
- Increased left padding to 24px for better alignment
- Made "NAVIGATION" section label smaller (9px) and lighter gray
- Added subtle hover effect with purple tint
- Added subtle horizontal divider below section label
- Note: These changes were later undone by user

### 6. Login Page UI Overhaul (ui/login.py)
- Changed dialog background to light lavender [theme color]
- Wrapped form elements in a centered white card with border-radius: 16px
- Fixed "Create Account" link, which was invisible as white text, and changed it to purple [theme color]
- Fixed form centering so all elements are properly horizontally centered
- Password show/hide toggle button now displays "Show"/"Hide" text reliably
- Fixed toggle button width to 50px so full text is visible
- Fixed password field and toggle button to appear as one connected widget

### 7. Create Account Dialog UI Overhaul (ui/login.py)
- Removed alternating stripe background colors from form rows
- Applied matching lavender background [theme color] consistent with login page
- Wrapped form in centered white card matching login page style
- Fixed label styling by removing highlighted backgrounds and using plain text
- Added Show/Hide toggle buttons to Password and Confirm Password fields
- Submit button now matches Sign In button style (purple [theme color])
- Title "Create Account" styled in purple [theme color]

### 8. Account Created Success Dialog (ui/login.py)
- Replaced default Windows default dialog with custom styled dialog
- Applied purple theme consistent with the rest of the app
- OK button styled with purple background [theme color] matching Sign In button
- Dialog background set to [theme color]
- Added centered checkmark and success message

## Bug Fixes

### 9. Database Password Configuration (database/)
- Identified database password consistency between `database/db_manager.py` and `database/tempCodeRunnerFile.py`
- `database/db_manager.py` default password is `""` (empty)
- `database/tempCodeRunnerFile.py` default password is `""` (empty)
- No login-related blocker remains

### 10. Database Connection Fix (ui/login.py)
- `_create_user()` was using a direct `direct connector call` call instead of `get_connection()` from `db_manager.py`
- Fixed to use `get_connection()` so all writes go to the correct database
- Added `conn.commit()` after `INSERT` and verification query after save
- phpMyAdmin was viewing port 3306 while app was on port 3307, fixed by adding port config in phpMyAdmin's `config.inc.php`

## Files Modified

| File | Type | Change |
|------|------|--------|
| `database/db_manager.py` | MODIFIED | Added users table seeding and database login authentication helpers |
| `ui/login.py` | MODIFIED | Login flow, database-backed authentication, Create Account UI, success dialog styling, and database connection fix |
| `main.py` | MODIFIED | Added login flow before main window |
| `ui/inventory.py` | MODIFIED | Fixed Actions column button visibility |
| `ui/main_window.py` | ATTEMPTED | Navigation styling later undone |
| `utils/styles.py` | ATTEMPTED | Navigation styling later undone |
| `C:/xampp/phpMyAdmin/config.inc.php` | MODIFIED | Added port 3307 to match app database connection |

## Credentials

### Default Admin Account (Seeded on First Run)
- **Username:** `admin`
- **Password:** `admin123`
- Seeded automatically when the `users` table is empty

## Testing Notes

✅ Login page displays correctly on application startup
✅ Username and password fields accept input
✅ Show/Hide password toggle works on login and create account
✅ Enter key triggers login from both fields
✅ Input validation prevents empty submissions
✅ Login credentials are checked against the database `users` table
✅ Default admin account is created automatically if `users` is empty
✅ Error messages displayed for invalid credentials
✅ Successful login displays main window
✅ Cancelled login exits application
✅ Login page centered and styled correctly
✅ Create Account link visible in purple
✅ New accounts now save correctly to database database
✅ New accounts visible in phpMyAdmin
✅ Create Account dialog styled to match app theme
✅ Success dialog uses purple theme

## Future Improvements

- [x] Replace hardcoded credentials with database-based authentication
- [ ] Add password hashing and security measures
- [ ] Implement user roles and permissions system
- [ ] Add "Remember Me" checkbox to login page
- [ ] Add password reset functionality
- [ ] Add account lockout after failed login attempts
- [ ] Implement session management

## Version

WarehouseIQ v1.0.0 — School Project
