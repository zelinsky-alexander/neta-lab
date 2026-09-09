param([Parameter(Mandatory=$true)][string]$HostAddress,[int]$Port=18447,[int]$Bytes=33554432)
$ErrorActionPreference='Stop'
$client=[Net.Sockets.TcpClient]::new(); $client.Connect($HostAddress,$Port); $s=$client.GetStream(); $buf=New-Object byte[] 65536; $left=[int64]$Bytes
while($left -gt 0){$n=[Math]::Min($buf.Length,$left);$s.Write($buf,0,$n);$left-=$n}
$s.Close();$client.Close(); Write-Host "NETA-LAB-007 bytes_sent=$Bytes remote=$HostAddress`:$Port"
