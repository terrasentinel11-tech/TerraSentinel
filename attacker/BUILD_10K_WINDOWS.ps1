param(
 [Parameter(Mandatory=$true)][string] $Spring,
 [Parameter(Mandatory=$true)][string] $Summer,
 [Parameter(Mandatory=$true)][string] $Output,
 [int] $Total=20,
 [string] $Attacks='cloud_injection,field_patch_replacement,atmospheric_haze',
 [string] $Profile='sen12ms-cr'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" -m black_pixel_agri.cli build `
  --input "$Spring" "$Summer" --output "$Output" --total $Total `
  --profile "$Profile" --selection auto --attacks "$Attacks"
