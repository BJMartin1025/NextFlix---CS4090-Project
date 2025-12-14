# NextFlix---CS4090-Project
**Developers**: Brayden Martin & Raymond Stahl

**Project Description**:
This application is a course project for CS4090 at Missouri S&amp;T. NextFlix is a movie recommendation application which aims to deliver quick and efficient search results catered to the user's preferences, with transparency on what platforms the movie suggestions are available on. 

**How to Run:**
To test the model logic, open the model.ipynb jupyter notebook under model and run the cells sequentially. Doing this will generate two .pkl files. Move these into the backend\flask folder before running the backend.

To run the backend server, run:
./run_back.sh (if on Linux) or .\run_back.bat (if on Windows)

To run the frontend server, in a new terminal, run the following with node.js installed on your device:
;./run_front.sh (if on Linux) or .\run_front.bat (if on Windows)

Note: Sometimes npm causes the script to exit after running "npm install", so you may have to direct to the frontend folder and manually run "npm start". 

This will automatically open the site in your browser after a few seconds.

Environment variables for deployment:
- `REACT_APP_API_URL`: Set at build time to override the API base URL used by the frontend. Defaults to `http://localhost:5000` for local development.
- `CORS_ORIGINS`: Comma-separated list used by the backend to set CORS origins (default includes `http://localhost:3000` and the GitHub Pages origin). Example: `http://localhost:3000,https://yourdomain.github.io`.
 - `PRODUCTION_API_URL` (GitHub secret): The CI/CD `cd.yml` workflow reads this as `REACT_APP_API_URL` during the production build. Set this in the repository secrets if your backend is publicly available (e.g., `https://api.yoursite.com`).

To access the admin server to add, edit, or delete movie entries, run:
cd backend/flask
python admin.py
