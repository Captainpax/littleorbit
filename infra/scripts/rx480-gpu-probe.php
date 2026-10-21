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
    require_true(is_array($value) && ($value['schema'] ?? null) === 1);
    require_true(preg_match('/^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]$/D', $value['pci_bdf'] ?? '') === 1);
    require_true(($value['device_id'] ?? null) === '0x67df');
    require_true(($value['render_node'] ?? null) === '/dev/dri/renderD128');
    require_true(($value['card_node'] ?? null) === '/dev/dri/card0');
    require_true(($value['render_major'] ?? null) === 226 && ($value['render_minor'] ?? null) === 128);
    require_true(($value['vram_total_bytes'] ?? null) === 8589934592);
    require_true(is_int($value['idle_vram_bytes'] ?? null) && $value['idle_vram_bytes'] >= 0);
    require_true(preg_match('/^[0-9a-f]{64}$/D', $value['ollama_container_id'] ?? '') === 1);
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
    $directory = '/proc/' . $pid . '/fd';
    $fds = @scandir($directory);
    if ($fds === false && pid_gone($pid)) { return []; }
    require_true(is_array($fds) && count($fds) <= 65538);
    $owns = false;
    foreach ($fds as $fd) {
        if (!ctype_digit($fd)) { continue; }
        clearstatcache(true, $directory . '/' . $fd);
        $info = @stat($directory . '/' . $fd);
        if ($info === false) {
            require_true(fd_gone($pid, $fd));
            continue;
        }
        if (($info['mode'] & 0170000) === 0020000 && in_array($info['rdev'], $targets, true)) {
            $owns = true;
        }
    }
    if (pid_gone($pid)) { return []; }
    require_true(process_identity($pid) === $before);
    if (!$owns) { return []; }
    return [[
        'pid' => (int) $pid, 'start_time_ticks' => $before['start_time_ticks'],
        'approved' => approved_owner($before['cgroup'], $config),
    ]];
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
    $owners = []; $busy = 0; $used = 0;
    for ($index = 0; $index < 2; $index++) {
        foreach (census($config) as $owner) {
            $key = (string) $owner['pid'];
            if (isset($owners[$key])) {
                require_true($owner['start_time_ticks'] === $owners[$key]['start_time_ticks']);
                $owner['approved'] = $owner['approved'] && $owners[$key]['approved'];
            }
            $owners[$key] = $owner;
        }
        $busy = max($busy, metric($config, 'gpu_busy_percent'));
        $used = max($used, metric($config, 'mem_info_vram_used'));
        if ($index === 0) { usleep(100000); }
    }
    require_true(device_info($config) === $identity);
    $elapsed = (int) ceil((hrtime(true) - $started) / 1000000);
    require_true($elapsed > 0 && $elapsed <= 2000 && $busy <= 100);
    return [
        'schema' => 1, 'nonce' => $nonce, 'device' => $identity,
        'census_complete' => true, 'owners' => array_values($owners), 'errors' => [],
        'samples' => 2, 'gpu_busy_percent' => $busy, 'vram_used_bytes' => $used,
        'sample_span_ms' => $elapsed,
    ];
}

function reply($client, array $config): void {
    stream_set_timeout($client, 2);
    $raw = fgets($client, 513);
    require_true(is_string($raw) && strlen($raw) <= 512 && substr($raw, -1) === "\n");
    $request = json_decode($raw, true, 16, JSON_THROW_ON_ERROR);
    require_true(is_array($request) && count($request) === 3 && ($request['schema'] ?? null) === 1);
    require_true(in_array($request['operation'] ?? null, ['idle', 'residency'], true));
    require_true(preg_match('/^[0-9a-f]{64}$/D', $request['nonce'] ?? '') === 1);
    $proof = sample($config, $request['nonce']);
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

try {
    require_true(PHP_SAPI === 'cli' && PHP_INT_SIZE === 8 && count($argv) === 3);
    require_true(function_exists('posix_geteuid') && posix_geteuid() === 0);
    require_true(is_string($argv[1]) && substr($argv[1], 0, 1) === '/');
    serve(load_config($argv[1], $argv[2]));
} catch (Throwable $error) {
    fwrite(STDERR, "GPU host probe failed closed; no GPU admission\n");
    exit(1);
}
