Add-Type -AssemblyName System.Drawing

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$assetsDir = Join-Path $repoRoot 'desktop\assets'
New-Item -ItemType Directory -Force -Path $assetsDir | Out-Null

$size = 256
$bitmap = New-Object System.Drawing.Bitmap $size, $size
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::FromArgb(247, 250, 252))

$gradientRect = New-Object System.Drawing.Rectangle 18, 18, 220, 220
$gradient = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    $gradientRect,
    [System.Drawing.Color]::FromArgb(14, 116, 144),
    [System.Drawing.Color]::FromArgb(29, 78, 216),
    45
)
$graphics.FillEllipse($gradient, $gradientRect)

$ringPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(180, 255, 255, 255), 8)
$graphics.DrawEllipse($ringPen, 28, 28, 200, 200)

$font = New-Object System.Drawing.Font('Segoe UI Semibold', 88, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$stringFormat = New-Object System.Drawing.StringFormat
$stringFormat.Alignment = [System.Drawing.StringAlignment]::Center
$stringFormat.LineAlignment = [System.Drawing.StringAlignment]::Center
$textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
$graphics.DrawString('SM', $font, $textBrush, (New-Object System.Drawing.RectangleF 0, 0, $size, $size), $stringFormat)

$pngPath = Join-Path $assetsDir 'icon.png'
$icoPath = Join-Path $assetsDir 'icon.ico'

$bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$fileStream = [System.IO.File]::Open($icoPath, [System.IO.FileMode]::Create)
$icon.Save($fileStream)
$fileStream.Dispose()

$icon.Dispose()
$ringPen.Dispose()
$gradient.Dispose()
$textBrush.Dispose()
$font.Dispose()
$stringFormat.Dispose()
$graphics.Dispose()
$bitmap.Dispose()
