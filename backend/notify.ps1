param(
    [string]$Title = "Amunty",
    [string]$Message = "Hello!"
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$notify.BalloonTipTitle = $Title
$notify.BalloonTipText = $Message
$notify.Visible = $true
$notify.ShowBalloonTip(5000)

Start-Sleep -Seconds 6
$notify.Dispose()
