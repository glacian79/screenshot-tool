Add-Type -AssemblyName System.Windows.Forms
while ($true) {
    $pos = [System.Windows.Forms.Cursor]::Position
    Write-Host "`rX=$($pos.X)  Y=$($pos.Y)   " -NoNewline
    Start-Sleep -Milliseconds 100
}