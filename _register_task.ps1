
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At (Get-Date)
$action  = New-ScheduledTaskAction -Execute '"C:\Users\91891\.gemini\antigravity-ide\scratch\ain-state-compiler\_ain_cron_sync.bat"'
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -StartWhenAvailable
Register-ScheduledTask -TaskName "AINBrainSync" -Trigger $trigger -Action $action -Settings $settings -RunLevel Highest -Force
