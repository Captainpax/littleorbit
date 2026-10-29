<?php
/** Synthetic PHP protocol checks. No GPU inference or application access. */
declare(strict_types=1);
require dirname(__DIR__) . '/rx480-gpu-probe.php';

function check(bool $value, string $reason): void {
    if (!$value) { throw new RuntimeException($reason); }
}

function refused(array $metrics): void {
    try { combine_metrics($metrics); }
    catch (RuntimeException $error) { return; }
    throw new RuntimeException('Invalid metrics accepted');
}

function exact_metrics(array $left, array $right): bool {
    ksort($left); ksort($right);
    return $left === $right;
}

$active = ['runtime_status' => 'active', 'runtime_active_ms' => 1000,
    'vram_used_bytes' => 4096, 'gpu_busy_percent' => 0, 'gpu_busy_errno' => null];
$suspended = array_replace($active, ['runtime_status' => 'suspended',
    'gpu_busy_percent' => null, 'gpu_busy_errno' => 'EBUSY']);
$count = 0;
check(exact_metrics(combine_metrics([$active, $active]), $active), 'Active round trip'); $count++;
$quiet = combine_metrics([$suspended, $suspended]);
check(exact_metrics($quiet, $suspended) && $quiet['gpu_busy_percent'] === null, 'Missing counter is not zero'); $count++;
$busy = array_replace($active, ['gpu_busy_percent' => 100, 'vram_used_bytes' => 8192]);
check(combine_metrics([$active, $busy])['gpu_busy_percent'] === 100, 'Peak busy retained'); $count++;
check(combine_metrics([$active, $busy])['vram_used_bytes'] === 8192, 'Peak VRAM retained'); $count++;
refused([$active, $suspended]); $count++;
refused([$suspended, array_replace($suspended, ['runtime_active_ms' => 0])]); $count++;
refused([$suspended, array_replace($suspended, ['gpu_busy_errno' => 'EIO'])]); $count++;
refused([$suspended, array_replace($suspended, ['gpu_busy_percent' => 100, 'gpu_busy_errno' => null])]); $count++;
refused([$active, array_replace($active, ['runtime_status' => 'suspending'])]); $count++;
refused([$active, array_replace($active, ['gpu_busy_percent' => null])]); $count++;
refused([$active, array_replace($active, ['gpu_busy_percent' => '0'])]); $count++;
refused([$active, array_replace($active, ['gpu_busy_percent' => 101])]); $count++;
refused([$active, array_replace($active, ['vram_used_bytes' => -1])]); $count++;
refused([$active, array_replace($active, ['runtime_active_ms' => '1000'])]); $count++;
refused([$active]); $count++;
check(!owns_device((string) getmypid(), [57984, 57856]), 'Own enumeration handle remains inspectable'); $count++;

$pair = stream_socket_pair(STREAM_PF_UNIX, STREAM_SOCK_STREAM, STREAM_IPPROTO_IP);
check(is_array($pair), 'Synthetic socket pair available');
$config = ['native_helper_sha256' => hash_file('sha256', dirname(__DIR__) . '/rx480-probe-native.pl')];
try {
    $peer = native_helper($config, ['peer'], $pair[0]);
    check($peer['uid'] === posix_geteuid() && $peer['pid'] === getmypid(), 'Kernel peer credentials'); $count++;
} finally { fclose($pair[0]); fclose($pair[1]); }
echo json_encode(['syntheticChecksPassed' => $count, 'gpuInferenceOrApplicationAccess' => false], JSON_THROW_ON_ERROR) . "\n";
