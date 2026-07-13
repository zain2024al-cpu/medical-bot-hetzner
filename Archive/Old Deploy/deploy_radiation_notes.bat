@echo off
chcp 65001 >nul
SET SCRIPT_DIR=%~dp0
SET REMOTE_HOST=botuser@5.223.58.71
SET REMOTE_DIR=/home/botuser/medical-bot

echo ===============================================
echo Deploy Radiation Therapy Notes Feature
echo ===============================================
echo.

echo [1/8] Uploading states.py...
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%bot\handlers\user\user_reports_add_new_system\states.py" "%REMOTE_HOST%:%REMOTE_DIR%/bot/handlers/user/user_reports_add_new_system/states.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: states.py & GOTO :EOF)
echo OK: states.py

echo [2/8] Uploading radiation_therapy.py...
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%bot\handlers\user\user_reports_add_new_system\flows\radiation_therapy.py" "%REMOTE_HOST%:%REMOTE_DIR%/bot/handlers/user/user_reports_add_new_system/flows/radiation_therapy.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: radiation_therapy.py & GOTO :EOF)
echo OK: radiation_therapy.py

echo [3/8] Uploading user_reports_add_new_system.py...
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%bot\handlers\user\user_reports_add_new_system.py" "%REMOTE_HOST%:%REMOTE_DIR%/bot/handlers/user/user_reports_add_new_system.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: user_reports_add_new_system.py & GOTO :EOF)
echo OK: user_reports_add_new_system.py

echo [4/8] Uploading shared.py...
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%bot\handlers\user\user_reports_add_new_system\flows\shared.py" "%REMOTE_HOST%:%REMOTE_DIR%/bot/handlers/user/user_reports_add_new_system/flows/shared.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: shared.py & GOTO :EOF)
echo OK: shared.py

echo [5/8] Uploading broadcast_service.py...
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%services\broadcast_service.py" "%REMOTE_HOST%:%REMOTE_DIR%/services/broadcast_service.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: broadcast_service.py & GOTO :EOF)
echo OK: broadcast_service.py

echo [6/8] Uploading user_reports_edit.py...
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%bot\handlers\user\user_reports_edit.py" "%REMOTE_HOST%:%REMOTE_DIR%/bot/handlers/user/user_reports_edit.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: user_reports_edit.py & GOTO :EOF)
echo OK: user_reports_edit.py

echo [7/8] Uploading models.py and migration script...
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%db\models.py" "%REMOTE_HOST%:%REMOTE_DIR%/db/models.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: models.py & GOTO :EOF)
echo OK: models.py
scp -o StrictHostKeyChecking=no "%SCRIPT_DIR%add_radiation_recommendations_column.py" "%REMOTE_HOST%:%REMOTE_DIR%/add_radiation_recommendations_column.py"
IF %ERRORLEVEL% NEQ 0 (echo FAILED: migration script & GOTO :EOF)
echo OK: migration script

echo [8/8] Running migration and restarting bot...
ssh -o StrictHostKeyChecking=no %REMOTE_HOST% "cd %REMOTE_DIR% && /home/botuser/medical-bot/venv/bin/python add_radiation_recommendations_column.py && echo 'Migration done' && (supervisorctl restart medical_bot 2>/dev/null || (pkill -f 'python.*app.py' 2>/dev/null; sleep 2; cd /home/botuser/medical-bot && nohup /home/botuser/medical-bot/venv/bin/python app.py > bot.log 2>&1 &)) && echo 'Bot restarted'"
echo.

echo ===============================================
echo Deployment Complete!
echo ===============================================
pause
