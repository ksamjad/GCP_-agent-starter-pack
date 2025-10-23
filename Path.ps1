# Get the current User PATH
$UserPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")

# Add your new path (if it's not already there)
if ($UserPath -notlike "*D:\Programs\Scripts*") {
  [System.Environment]::SetEnvironmentVariable("PATH", $UserPath + ";D:\Programs\Scripts", "User")
  Write-Host "PATH has been updated! Please restart PowerShell."
} else {
  Write-Host "PATH already includes this directory."
}