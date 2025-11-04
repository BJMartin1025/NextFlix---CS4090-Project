cd frontend
del /f package-lock.json
del /s /q node_modules\
npm install --no-audit
npm start