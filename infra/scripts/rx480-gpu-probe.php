<?php
/** Read-only, root-owned host census. Deployment is a separate admission gate.
 * No Docker socket, shell commands, GPU ioctls, state/device mutations, signals
 * or tests. Only its private Unix socket is created and its own inode removed.
 * Configuration: exact reviewed PCI/render/card identity, quiet VRAM ceiling and
 * one full admitted Ollama container ID. Never derive that ID from a name here.
 */
declare(strict_types=1);

const PROBE_SOCKET = '/run/little-orbit-gpu-probe/idle.sock';

function require_true(bool $condition): void {
    if (!$condition) { throw new RuntimeException('GPU probe admission failed'); }
}

function read_small(string $path, int $limit = 4096): string {
    $value = @file_get_contents($path, false, null, 0, $limit + 1);
    require_true(is_string($value) && strlen($value) <= $limit);
    return trim($value);
}

function root_ancestors(string $path): void {
    for ($directory = dirname($path); ; $directory = dirname($directory)) {
        $info = lstat($directory);
        require_true(is_array($info) && ($info['mode'] & 0170000) === 0040000);
        require_true($info['uid'] === 0 && ($info['mode'] & 0022) === 0);
        if ($directory === '/') { return; }
    }
}

function stable_file(array $info): array {
    return array_intersect_key($info, array_flip(['dev', 'ino', 'mode', 'nlink', 'uid', 'gid', 'size', 'mtime', 'ctime']));
}

function read_config(string $path, string $sha256): string {
    root_ancestors($path);
    $info = lstat($path);
    require_true(is_array($info) && ($info['mode'] & 0170000) === 0100000);
    require_true($info['uid'] === 0 && ($info['mode'] & 0077) === 0 && $info['nlink'] === 1);
    require_true(preg_match('/^[0-9a-f]{64}$/D', $sha256) === 1);
    $handle = fopen($path, 'rb');
    require_true($handle !== false);
    try {
        require_true(stable_file(fstat($handle)) === stable_file($info));
        $raw = fread($handle, 8193);
        require_true(is_string($raw) && strlen($raw) <= 8192 && feof($handle));
        clearstatcache(true, $path);
        require_true(stable_file(fstat($handle)) === stable_file($info));
        require_true(stable_file(lstat($path)) === stable_file($info));
        require_true(hash_equals($sha256, hash('sha256', $raw)));
        return $raw;
    } finally { fclose($handle); }
}

function load_config(string $path, string $sha256): array {
    $value = json_decode(read_config($path, $sha256), true, 32, JSON_THROW_ON_ERROR);
    require_true(is_array($value) && ($value['schema'] ?? null) === 2);
    require_true(preg_match('/^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]$/D', $value['pci_bdf'] ?? '') === 1);
    require_true(($value['device_id'] ?? null) === '0x67df');
    require_true(($value['render_node'] ?? null) === '/dev/dri/renderD128');
    require_true(($value['card_node'] ?? null) === '/dev/dri/card0');
    require_true(($value['render_major'] ?? null) === 226 && ($value['render_minor'] ?? null) === 128);
    require_true(($value['vram_total_bytes'] ?? null) === 8589934592);
    require_true(is_int($value['idle_vram_bytes'] ?? null) && $value['idle_vram_bytes'] >= 0);
    require_true(preg_match('/^[0-9a-f]{64}$/D', $value['ollama_container_id'] ?? '') === 1);
    require_true(preg_match('/^[0-9a-f]{64}$/D', $value['worker_container_id'] ?? '') === 1);
    require_true(preg_match('/^[0-9a-f]{64}$/D', $value['native_helper_sha256'] ?? '') === 1);
    require_true(read_small('/proc/sys/kernel/random/boot_id') === ($value['boot_id'] ?? null));
    require_true(preg_match('/^pid:\[[0-9]+\]$/D', $value['host_pid_namespace'] ?? '') === 1);
    require_true(readlink('/proc/1/ns/pid') === $value['host_pid_namespace']);
    require_true(readlink('/proc/self/ns/pid') === $value['host_pid_namespace']);
    return $value;
}

function device_info(array $config): array {
    clearstatcache(true);
    $base = '/sys/bus/pci/devices/' . $config['pci_bdf'];
    require_true(read_small($base . '/vendor') === '0x1002');
    require_true(read_small($base . '/device') === $config['device_id']);
    require_true(read_small($base . '/subsystem_vendor') === '0x174b');
    require_true(read_small($base . '/subsystem_device') === '0xe353');
    require_true(metric($config, 'mem_info_vram_total') === $config['vram_total_bytes']);
    require_true(basename((string) realpath($base . '/driver')) === 'amdgpu');
    require_true(realpath('/sys/class/drm/renderD128/device') === realpath($base));
    require_true(realpath('/sys/class/drm/card0/device') === realpath($base));
    require_true(read_small('/sys/class/drm/renderD128/dev') === '226:128');
    require_true(read_small('/sys/class/drm/card0/dev') === '226:0');
    foreach ([$config['render_node'] => 57984, $config['card_node'] => 57856] as $node => $rdev) {
        $info = lstat($node);
        require_true(is_array($info) && ($info['mode'] & 0170000) === 0020000);
        require_true($info['rdev'] === $rdev);
    }
    return [
        'pci_bdf' => $config['pci_bdf'], 'vendor_id' => '0x1002',
        'device_id' => $config['device_id'], 'driver' => 'amdgpu',
        'render_major' => 226, 'render_minor' => 128,
    ];
}

function metric(array $config, string $name): int {
    $value = read_small('/sys/bus/pci/devices/' . $config['pci_bdf'] . '/' . $name, 64);
    require_true(preg_match('/^[0-9]+$/D', $value) === 1);
    $number = filter_var($value, FILTER_VALIDATE_INT);
    require_true(is_int($number) && $number >= 0);
    return $number;
}

function approved_owner(string $groups, array $config): bool {
    $id = preg_quote($config['ollama_container_id'], '/');
    return preg_match('/(?:^|\/)(?:docker-)?' . $id . '(?:\.scope)?(?:\/|$)/m', $groups) === 1;
}

function pid_gone(string $pid): bool {
    $current = scandir('/proc');
    require_true(is_array($current));
    return !in_array($pid, $current, true);
}

function fd_gone(string $pid, string $fd): bool {
    if (pid_gone($pid)) { return true; }
    $current = @scandir('/proc/' . $pid . '/fd');
    require_true(is_array($current));
    return !in_array($fd, $current, true);
}

function process_identity(string $pid): array {
    $record = read_small('/proc/' . $pid . '/stat', 8192);
    $delimiter = strrpos($record, ') ');
    require_true($delimiter !== false);
    $fields = explode(' ', substr($record, $delimiter + 2));
    require_true(isset($fields[19]) && ctype_digit($fields[19]));
    return ['start_time_ticks' => $fields[19], 'cgroup' => read_small('/proc/' . $pid . '/cgroup', 8192)];
}

function process_owners(string $pid, array $targets, array $config): array {
    try { $before = process_identity($pid); }
    catch (Throwable $error) {
        if (pid_gone($pid)) { return []; }
        throw $error;
    }
    $owns = owns_device($pid, $targets);
    if (pid_gone($pid)) { return []; }
    require_true(process_identity($pid) === $before);
    if (!$owns) { return []; }
    return [[
        'pid' => (int) $pid, 'start_time_ticks' => $before['start_time_ticks'],
        'approved' => approved_owner($before['cgroup'], $config),
    ]];
}

function owns_device(string $pid, array $targets): bool {
    $directory = '/proc/' . $pid . '/fd';
    // Keep our enumeration FD open: scandir closes it before its own FD can be
    // inspected, then a second scandir may reuse that number and mimic an error.
    $handle = @opendir($directory);
    if ($handle === false && pid_gone($pid)) { return false; }
    require_true(is_resource($handle));
    $owns = false; $count = 0;
    try {
        while (($fd = readdir($handle)) !== false) {
            require_true(++$count <= 65538);
            if (!ctype_digit($fd)) { continue; }
            clearstatcache(true, $directory . '/' . $fd);
            $info = @stat($directory . '/' . $fd);
            if ($info === false) { require_true(fd_gone($pid, $fd)); continue; }
            if (($info['mode'] & 0170000) === 0020000 && in_array($info['rdev'], $targets, true)) {
                $owns = true;
            }
        }
    } finally { closedir($handle); }
    return $owns;
}

function census(array $config): array {
    $targets = [];
    foreach ([$config['render_node'], $config['card_node']] as $node) {
        $info = stat($node);
        require_true(is_array($info));
        $targets[] = $info['rdev'];
    }
    $processes = scandir('/proc');
    require_true(is_array($processes) && count($processes) <= 65536);
    $owners = [];
    foreach ($processes as $pid) {
        if (!ctype_digit($pid)) { continue; }
        $owners = array_merge($owners, process_owners($pid, $targets, $config));
        require_true(count($owners) <= 64);
    }
    return $owners;
}

function sample(array $config, string $nonce): array {
    $started = hrtime(true);
    $identity = device_info($config);
    $owners = []; $metrics = [];
    for ($index = 0; $index < 2; $index++) {
        foreach (census($config) as $owner) {
            $key = (string) $owner['pid'];
            if (isset($owners[$key])) {
                require_true($owner['start_time_ticks'] === $owners[$key]['start_time_ticks']);
                $owner['approved'] = $owner['approved'] && $owners[$key]['approved'];
            }
            $owners[$key] = $owner;
        }
        $metrics[] = native_helper($config, ['telemetry', $config['pci_bdf']]);
        if ($index === 0) { usleep(100000); }
    }
    require_true(device_info($config) === $identity);
    $elapsed = (int) ceil((hrtime(true) - $started) / 1000000);
    require_true($elapsed > 0 && $elapsed <= 2000);
    return array_merge([
        'schema' => 2, 'nonce' => $nonce, 'device' => $identity,
        'census_complete' => true, 'owners' => array_values($owners), 'errors' => [],
        'samples' => 2, 'sample_span_ms' => $elapsed,
    ], combine_metrics($metrics));
}

function native_helper(array $config, array $args, $client = null): array {
    $path = __DIR__ . '/rx480-probe-native.pl';
    read_config($path, $config['native_helper_sha256']);
    $descriptors = [0 => ['file', '/dev/null', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    if ($client !== null) { $descriptors[3] = $client; }
    $process = proc_open(array_merge(['/usr/bin/perl', $path], $args), $descriptors, $pipes);
    require_true(is_resource($process));
    $raw = stream_get_contents($pipes[1], 8193); $errors = stream_get_contents($pipes[2], 1024);
    fclose($pipes[1]); fclose($pipes[2]); $exit = proc_close($process);
    require_true($exit === 0 && $errors === '' && is_string($raw) && strlen($raw) <= 8192);
    $value = json_decode($raw, true, 16, JSON_THROW_ON_ERROR);
    require_true(is_array($value));
    return $value;
}

function combine_metrics(array $metrics): array {
    require_true(count($metrics) === 2);
    $first = $metrics[0]; $second = $metrics[1];
    require_true($first['runtime_status'] === $second['runtime_status']);
    require_true(in_array($first['runtime_status'], ['active', 'suspended'], true));
    $missing = false; $busy = 0; $used = 0; $active = PHP_INT_MAX;
    foreach ($metrics as $item) {
        require_true(is_int($item['runtime_active_ms']) && $item['runtime_active_ms'] >= 0);
        require_true(is_int($item['vram_used_bytes']) && $item['vram_used_bytes'] >= 0);
        $used = max($used, $item['vram_used_bytes']); $active = min($active, $item['runtime_active_ms']);
        if ($item['gpu_busy_percent'] === null) {
            require_true($item['gpu_busy_errno'] === 'EBUSY' && $item['runtime_status'] === 'suspended');
            $missing = true;
        } else {
            require_true(is_int($item['gpu_busy_percent']) && $item['gpu_busy_percent'] >= 0);
            require_true($item['gpu_busy_percent'] <= 100 && $item['gpu_busy_errno'] === null);
            $busy = max($busy, $item['gpu_busy_percent']);
        }
    }
    require_true($first['runtime_status'] !== 'suspended' || $active > 0);
    require_true(!$missing || $busy === 0);
    return ['gpu_busy_percent' => $missing ? null : $busy, 'gpu_busy_errno' => $missing ? 'EBUSY' : null,
        'runtime_status' => $first['runtime_status'], 'runtime_active_ms' => $active, 'vram_used_bytes' => $used];
}

function client_identity($client, array $config): array {
    $peer = native_helper($config, ['peer'], $client);
    require_true(is_int($peer['pid']) && $peer['pid'] > 1 && $peer['uid'] === 65532);
    $identity = process_identity((string) $peer['pid']);
    $id = preg_quote($config['worker_container_id'], '/');
    require_true(preg_match('/^0::\/little-orbit-recovery-[a-z0-9-]+\/' . $id . '$/m', $identity['cgroup']) === 1);
    return ['peer' => $peer, 'process' => $identity];
}

function reply($client, array $config): void {
    $peer = client_identity($client, $config);
    stream_set_timeout($client, 2);
    $raw = fgets($client, 513);
    require_true(is_string($raw) && strlen($raw) <= 512 && substr($raw, -1) === "\n");
    $request = json_decode($raw, true, 16, JSON_THROW_ON_ERROR);
    require_true(is_array($request) && count($request) === 3 && ($request['schema'] ?? null) === 2);
    require_true(in_array($request['operation'] ?? null, ['idle', 'residency'], true));
    require_true(preg_match('/^[0-9a-f]{64}$/D', $request['nonce'] ?? '') === 1);
    $proof = sample($config, $request['nonce']);
    require_true(client_identity($client, $config) === $peer);
    $response = json_encode($proof, JSON_THROW_ON_ERROR) . "\n";
    require_true(strlen($response) <= 8192 && fwrite($client, $response) === strlen($response));
}

function serve(array $config): void {
    $directory = dirname(PROBE_SOCKET);
    root_ancestors(PROBE_SOCKET);
    $info = lstat($directory);
    require_true(is_array($info) && ($info['mode'] & 0170000) === 0040000);
    require_true($info['uid'] === 0 && $info['gid'] === 2000 && ($info['mode'] & 0027) === 0);
    require_true(!file_exists(PROBE_SOCKET) && !is_link(PROBE_SOCKET));
    umask(0007);
    $server = stream_socket_server('unix://' . PROBE_SOCKET, $code, $error);
    require_true($server !== false && chgrp(PROBE_SOCKET, 2000) && chmod(PROBE_SOCKET, 0660));
    $socketInfo = lstat(PROBE_SOCKET);
    register_shutdown_function(static function () use ($socketInfo): void {
        $current = @lstat(PROBE_SOCKET);
        if (is_array($current) && $current['dev'] === $socketInfo['dev'] && $current['ino'] === $socketInfo['ino']) {
            unlink(PROBE_SOCKET);
        }
    });
    while (true) {
        $client = @stream_socket_accept($server, 1);
        if ($client === false) { continue; }
        try { reply($client, $config); }
        catch (Throwable $error) { fwrite(STDERR, "GPU ownership proof unavailable\n"); }
        finally { fclose($client); }
    }
}

if (realpath($argv[0] ?? '') === __FILE__) { try {
    require_true(PHP_SAPI === 'cli' && PHP_INT_SIZE === 8 && count($argv) === 3);
    require_true(function_exists('posix_geteuid') && posix_geteuid() === 0);
    require_true(is_string($argv[1]) && substr($argv[1], 0, 1) === '/');
    serve(load_config($argv[1], $argv[2]));
} catch (Throwable $error) {
    fwrite(STDERR, "GPU host probe failed closed; no GPU admission\n");
    exit(1);
} }
